"""
detector_core.py
-------------------
Key change from v5: LOAD_SCHEDULE is gone.

Previously, the load active at each snapshot was read from a manually
maintained LOAD_SCHEDULE list in detector_config.py. That list was wrong
twice across different test runs, silently mismatching every snapshot's
baseline reference from t=0.

Now the load is AUTO-INFERRED per snapshot via t_squared_auto_load():
  - Compute T2 against ALL four per-load healthy models
  - The load giving the lowest T2 is the one the signal most resembles
  - That minimum T2 is also the anomaly score

If the machine is healthy at load L, the signal will score low against
load L's model and higher against all others. If the machine is faulty,
even its best-matching load model will give a high T2 because the signal
has genuinely changed. Either way, no external schedule is needed.
"""

import os
import glob
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from detector_config import (
    FS, SNAP_DIR, MIN_CONSECUTIVE,
    LOCATION_WINDOW, LOCATION_RATIO,
)


# ══════════════════════════════════════════════════════════════════════════════
# SNAPSHOT I/O
# ══════════════════════════════════════════════════════════════════════════════

def load_snapshot(path: str) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """Reads DE_time / FE_time by EXACT name first (avoids matching sample_index)."""
    stem  = os.path.basename(path).replace(".csv", "")
    parts = stem.split("_")
    t_start, t_end = float(parts[0]), float(parts[1])

    df = pd.read_csv(path)

    if "DE_time" in df.columns:
        de = df["DE_time"].values.astype(np.float64)
    else:
        cu = [c.upper() for c in df.columns]
        idx = next(i for i, c in enumerate(cu) if c.startswith("DE"))
        de = df.iloc[:, idx].values.astype(np.float64)

    if "FE_time" in df.columns:
        fe = df["FE_time"].values.astype(np.float64)
    else:
        cu = [c.upper() for c in df.columns]
        idx = next(i for i, c in enumerate(cu) if c.startswith("FE"))
        fe = df.iloc[:, idx].values.astype(np.float64)

    return de, fe, t_start, t_end


def all_snapshots(snap_dir: str = SNAP_DIR) -> List[str]:
    paths = [
        p for p in glob.glob(os.path.join(snap_dir, "*.csv"))
        if "ground_truth" not in os.path.basename(p).lower()
    ]

    def _t(p):
        try:
            return float(os.path.basename(p).replace(".csv", "").split("_")[0])
        except ValueError:
            return float("inf")

    return sorted(paths, key=_t)


# ══════════════════════════════════════════════════════════════════════════════
# ANOMALY SCORER  —  auto-inferring load from the signal itself
# ══════════════════════════════════════════════════════════════════════════════

def t_squared_auto_load(fv: np.ndarray,
                         channel_baseline: dict) -> Tuple[float, int]:
    """
    Compute T2 against EVERY per-load healthy model and return the minimum.

    The load whose model gives the lowest T2 is the one the current signal
    most closely resembles -- this IS the load inference, derived from the
    data itself, with no external schedule needed.

    The minimum T2 is also the anomaly score: if healthy, the signal will
    fit at least one load model well (small T2). If faulty, even the
    best-matching load model will give a large T2 because the signal's
    character has genuinely changed beyond what any load shift explains.

    Returns: (min_t2, inferred_load_hp)
    """
    pca = channel_baseline["pca"]
    ev  = pca.explained_variance_

    min_t2     = float("inf")
    best_load  = -1

    for lhp, stats in channel_baseline["per_load_stats"].items():
        norm = (fv - stats["mean"]) / stats["std"]
        proj = pca.transform(norm.reshape(1, -1))[0]
        t2   = float(np.sum(proj ** 2 / ev))
        if t2 < min_t2:
            min_t2    = t2
            best_load = lhp

    return min_t2, best_load


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED DETECTION  —  auto-calibrated threshold from baseline
# ══════════════════════════════════════════════════════════════════════════════

def combined_detection(
    de_scores: np.ndarray,
    fe_scores: np.ndarray,
    de_base: dict,
    fe_base: dict,
    combined_calib: dict,
    min_consec: int = MIN_CONSECUTIVE,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[int], float, float]:
    """
    Standardise DE and FE T2 onto the same z-score scale, then run ONE
    CUSUM using the auto-calibrated k/H from detector_baseline.py's Monte
    Carlo calibration.
    """
    mu_de = float(de_base["healthy_t2"].mean())
    sd_de = float(de_base["healthy_t2"].std())
    mu_fe = float(fe_base["healthy_t2"].mean())
    sd_fe = float(fe_base["healthy_t2"].std())

    z_de       = (de_scores - mu_de) / sd_de
    z_fe       = (fe_scores - mu_fe) / sd_fe
    combined_z = np.maximum(z_de, z_fe)

    k = combined_calib["k"]
    H = combined_calib["H"]

    S = np.zeros(len(combined_z))
    for i, x in enumerate(combined_z):
        S[i] = max(0.0, (S[i - 1] if i > 0 else 0.0) + (x - k))

    above     = S > H
    onset_idx = None
    for i in range(len(above) - min_consec + 1):
        if above[i: i + min_consec].all():
            onset_idx = int(i)
            break

    return z_de, z_fe, combined_z, S, onset_idx, k, H


# ══════════════════════════════════════════════════════════════════════════════
# LOCATION DECISION  —  magnitude comparison after onset, not a timing race
# ══════════════════════════════════════════════════════════════════════════════

def decide_location(
    z_de: np.ndarray,
    z_fe: np.ndarray,
    onset_idx: Optional[int],
    window: int = LOCATION_WINDOW,
    ratio: float = LOCATION_RATIO,
) -> Optional[str]:
    """
    Decided only after detection is confirmed. Directly compares which
    channel is more deviant right after onset -- not a race between two
    separately-thresholded detectors.
    """
    if onset_idx is None:
        return None

    end      = min(len(z_de), onset_idx + window)
    de_level = float(np.mean(z_de[onset_idx:end]))
    fe_level = float(np.mean(z_fe[onset_idx:end]))

    if de_level <= 0 and fe_level <= 0:
        return None

    if de_level >= fe_level * ratio:
        return "DE"
    if fe_level >= de_level * ratio:
        return "FE"
    return "Both"


# ══════════════════════════════════════════════════════════════════════════════
# GROUND TRUTH PARSING  —  location only, not used for inference
# ══════════════════════════════════════════════════════════════════════════════

def parse_location(label: str) -> Optional[str]:
    if "/" in label:
        parts = label.split("/")
        label = next((p for p in parts if not p.upper().startswith("NORMAL")),
                     parts[-1])
    label = label.replace(".csv", "").replace(".CSV", "")
    if label.upper().startswith("NORMAL"):
        return None
    parts = label.upper().split("_")
    return next((p for p in parts if p in ("DE", "FE")), None)


def true_onset_time(gt: pd.DataFrame) -> Optional[float]:
    for _, row in gt.iterrows():
        hs = str(row.get("health_state", "healthy")).lower()
        lb = str(row.get("label", ""))
        if hs == "faulty" and "/" not in lb:
            return float(row["t_start"])
    return None


def true_location(gt: pd.DataFrame) -> Optional[str]:
    for _, row in gt.iterrows():
        hs = str(row.get("health_state", "healthy")).lower()
        lb = str(row.get("label", ""))
        if hs == "faulty" and "/" not in lb:
            return parse_location(lb)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATOR
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(gt: pd.DataFrame,
             times: np.ndarray,
             onset_idx: Optional[int],
             location: Optional[str]) -> Dict:
    t_onset     = true_onset_time(gt)
    run_healthy = (t_onset is None)
    tloc        = None if run_healthy else true_location(gt)
    pred_t      = float(times[onset_idx]) if onset_idx is not None else None

    if run_healthy:
        outcome = "TRUE_NEGATIVE" if onset_idx is None else "FALSE_POSITIVE"
        delay   = None
    else:
        if onset_idx is None:
            outcome, delay = "MISSED_DETECTION", None
        else:
            delay   = pred_t - t_onset
            outcome = "DETECTED" if delay >= 0 else "EARLY_DETECTION"

    loc_ok = (location == tloc) if (outcome == "DETECTED" and tloc) else None

    return dict(
        outcome           = outcome,
        true_onset_s      = t_onset,
        pred_onset_s      = pred_t,
        detection_delay_s = delay,
        true_location     = tloc,
        pred_location     = location,
        location_correct  = loc_ok,
    )


def print_evaluation(ev: Dict):
    ck  = lambda v: "CORRECT" if v else ("INCORRECT" if v is not None else "n/a")
    sep = "=" * 56
    print(f"\n{sep}\n  FAULT DETECTION RESULT\n{sep}")
    print(f"  Outcome              : {ev['outcome']}")
    print(f"  True onset (s)       : {ev['true_onset_s']}")
    print(f"  Predicted onset (s)  : {ev['pred_onset_s']}")
    if ev["detection_delay_s"] is not None:
        print(f"  Detection delay      : {ev['detection_delay_s']:+.1f} s")
    print(f"  True location        : {ev['true_location']}")
    print(f"  Predicted location   : {ev['pred_location']}  ({ck(ev['location_correct'])})")
    print(sep)