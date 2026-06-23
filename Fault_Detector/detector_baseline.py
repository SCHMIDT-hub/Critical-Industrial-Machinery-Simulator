"""
detector_baseline.py
-----------------------
Builds TWO independent healthy models -- one for DE, one for FE -- AND
auto-calibrates the combined-channel CUSUM decision threshold directly
from the same healthy data, via Monte Carlo resampling.

WHY auto-calibration replaces a manually-chosen multiplier:
  A fixed "H = multiplier x sigma" recipe assumes the underlying noise is
  roughly symmetric and well-behaved. Our combined statistic is the WORSE
  of two channels at each instant (max of two z-scores), and the max of
  two things is right-skewed by construction -- it drifts upward over time
  more than a textbook symmetric-noise CUSUM expects, even with no fault
  present. A manually-picked multiplier that survives one run's noise can
  still be crossed by a different run's noise, purely by chance, well
  before any real fault appears. That is exactly what was happening.

  Instead, we directly simulate thousands of snapshots' worth of pure
  healthy noise (resampling the ACTUAL healthy feature data with
  replacement, many times) and measure how high the CUSUM statistic can
  climb from chance alone over a run as long as any realistic deployment.
  The threshold is set safely above the worst case actually observed in
  that simulation -- not above a value implied by an assumption that may
  not hold for this particular signal.
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from typing import Dict, Tuple

from detector_config import (
    DATA_DIR, WINDOW_SAMPLES, BASELINE_OVERLAP,
    LOAD_RPM, PCA_VARIANCE, THRESHOLD_PERCENTILE,
    CALIBRATION_RUN_LENGTH, CALIBRATION_N_TRIALS, CALIBRATION_SAFETY_MARGIN,
)
from detector_features import channel_features


def _read_de_fe(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Read DE_time / FE_time by EXACT name first (avoids matching 'sample_index')."""
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

    return de, fe


def _load_normal(load_hp: int) -> Tuple[np.ndarray, np.ndarray]:
    path = os.path.join(DATA_DIR, f"Normal_{load_hp}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return _read_de_fe(path)


def _segment(arr: np.ndarray, win: int, overlap: float) -> np.ndarray:
    step = max(1, int(win * (1 - overlap)))
    starts = list(range(0, len(arr) - win + 1, step))
    return np.stack([arr[s:s + win] for s in starts]) if starts else np.empty((0, win))


def _build_channel_baseline(windows_by_load: Dict[int, np.ndarray]) -> dict:
    """Fit PCA + T2 threshold for ONE channel, pooled across all loads."""
    per_load_raw = {
        lhp: np.array([channel_features(w) for w in wins])
        for lhp, wins in windows_by_load.items()
    }

    per_load_stats = {}
    for lhp, feats in per_load_raw.items():
        mu, sig = feats.mean(axis=0), feats.std(axis=0)
        sig[sig < 1e-10] = 1e-10
        per_load_stats[lhp] = {"mean": mu, "std": sig}

    blocks = [
        (feats - per_load_stats[lhp]["mean"]) / per_load_stats[lhp]["std"]
        for lhp, feats in per_load_raw.items()
    ]
    X = np.vstack(blocks)

    pca = PCA(n_components=PCA_VARIANCE, svd_solver="full")
    pca.fit(X)
    ev = pca.explained_variance_

    all_t2 = []
    for lhp, feats in per_load_raw.items():
        mu, sig = per_load_stats[lhp]["mean"], per_load_stats[lhp]["std"]
        proj = pca.transform((feats - mu) / sig)
        all_t2.extend(np.sum(proj ** 2 / ev, axis=1).tolist())

    healthy_t2 = np.array(all_t2)
    threshold = float(np.percentile(healthy_t2, THRESHOLD_PERCENTILE))

    return dict(
        per_load_stats=per_load_stats,
        pca=pca,
        threshold=threshold,
        healthy_t2=healthy_t2,
        n_features=X.shape[1],
        n_components=pca.n_components_,
    )


def _calibrate_combined_threshold(de_base: dict, fe_base: dict) -> dict:
    """
    Monte Carlo calibration of the combined CUSUM threshold H.

    Resamples the actual healthy T2 values (with replacement) to build many
    long synthetic "pure healthy" runs, each CALIBRATION_RUN_LENGTH snapshots
    long, and measures the highest the CUSUM statistic ever climbs from
    chance alone. H is set safely above the worst case actually observed.
    """
    mu_de, sd_de = float(de_base["healthy_t2"].mean()), float(de_base["healthy_t2"].std())
    mu_fe, sd_fe = float(fe_base["healthy_t2"].mean()), float(fe_base["healthy_t2"].std())

    hz_de = (de_base["healthy_t2"] - mu_de) / sd_de
    hz_fe = (fe_base["healthy_t2"] - mu_fe) / sd_fe
    n = min(len(hz_de), len(hz_fe))
    healthy_combined_z = np.maximum(hz_de[:n], hz_fe[:n])

    mu0c    = float(healthy_combined_z.mean())
    sigma0c = max(float(healthy_combined_z.std()), 1e-6)
    k       = mu0c + 0.5 * sigma0c

    print(f"\n  Calibrating decision threshold via Monte Carlo "
          f"({CALIBRATION_N_TRIALS} trials x {CALIBRATION_RUN_LENGTH} snapshots) ...")

    rng = np.random.default_rng(seed=42)
    samples = rng.choice(healthy_combined_z,
                          size=(CALIBRATION_N_TRIALS, CALIBRATION_RUN_LENGTH),
                          replace=True)

    S     = np.zeros(CALIBRATION_N_TRIALS)
    max_S = np.zeros(CALIBRATION_N_TRIALS)
    for t in range(CALIBRATION_RUN_LENGTH):
        S = np.maximum(0.0, S + (samples[:, t] - k))
        max_S = np.maximum(max_S, S)

    worst_case = float(max_S.max())
    H = worst_case * CALIBRATION_SAFETY_MARGIN

    print(f"  Worst-case CUSUM drift from pure noise over "
          f"{CALIBRATION_N_TRIALS} simulated healthy runs: {worst_case:.3f}")
    print(f"  Decision threshold H set to {H:.3f} "
          f"({CALIBRATION_SAFETY_MARGIN}x safety margin)")

    return dict(
        k=k, H=H, mu0c=mu0c, sigma0c=sigma0c,
        worst_case_observed=worst_case,
        calibration_run_length=CALIBRATION_RUN_LENGTH,
        calibration_n_trials=CALIBRATION_N_TRIALS,
    )


def build_baseline(save_path: str = None) -> dict:
    print("Building healthy baseline (DE and FE modelled independently) ...")

    de_windows: Dict[int, np.ndarray] = {}
    fe_windows: Dict[int, np.ndarray] = {}

    for lhp, rpm in LOAD_RPM.items():
        try:
            de_full, fe_full = _load_normal(lhp)
        except FileNotFoundError as exc:
            print(f"  [skip] {exc}")
            continue

        n = min(len(de_full), len(fe_full))
        if n < WINDOW_SAMPLES:
            print(f"  [skip] Normal_{lhp}.csv too short ({n} < {WINDOW_SAMPLES})")
            continue

        dw = _segment(de_full[:n], WINDOW_SAMPLES, BASELINE_OVERLAP)
        fw = _segment(fe_full[:n], WINDOW_SAMPLES, BASELINE_OVERLAP)
        nw = min(len(dw), len(fw))
        print(f"  Normal_{lhp}.csv  ({rpm} RPM): {nw} windows")

        de_windows[lhp] = dw[:nw]
        fe_windows[lhp] = fw[:nw]

    if not de_windows:
        raise RuntimeError(f"No Normal files found in {DATA_DIR!r}")

    de_base = _build_channel_baseline(de_windows)
    fe_base = _build_channel_baseline(fe_windows)

    print(f"\n  DE  healthy T2  mean={de_base['healthy_t2'].mean():.2f}  "
          f"std={de_base['healthy_t2'].std():.2f}  threshold={de_base['threshold']:.2f}  "
          f"({de_base['n_components']} PCA components)")
    print(f"  FE  healthy T2  mean={fe_base['healthy_t2'].mean():.2f}  "
          f"std={fe_base['healthy_t2'].std():.2f}  threshold={fe_base['threshold']:.2f}  "
          f"({fe_base['n_components']} PCA components)")

    combined_calib = _calibrate_combined_threshold(de_base, fe_base)

    baseline = {"DE": de_base, "FE": fe_base, "COMBINED": combined_calib}

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as fh:
            pickle.dump(baseline, fh)
        print(f"  Saved -> {save_path}")

    return baseline


def load_baseline(path: str) -> dict:
    with open(path, "rb") as fh:
        return pickle.load(fh)