"""
detector_main.py
-------------------
Run the full WHEN + WHERE detection pipeline.

Usage:
    python detector_main.py              # uses cached baseline if present
    python detector_main.py --rebuild    # forces baseline rebuild

No LOAD_SCHEDULE to edit. The load is inferred from the signal itself.
The ONLY config value you may need to change is WINDOW_SAMPLES in
detector_config.py if your simulator's sample_duration is not 0.4s.
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from collections import Counter

from detector_config import (
    SNAP_DIR, GT_PATH, RES_DIR, WINDOW_SAMPLES,
    SAVE_RESULTS, PLOT_RESULTS,
)
from detector_baseline import build_baseline, load_baseline
from detector_features  import channel_features
from detector_core import (
    all_snapshots, load_snapshot,
    t_squared_auto_load, combined_detection, decide_location,
    evaluate, print_evaluation, true_onset_time, true_location,
)

try:
    from detector_plotter import plot_results
    _CAN_PLOT = True
except ImportError:
    _CAN_PLOT = False
    print("Warning: matplotlib not found -- plots disabled")


def _np(o):
    if isinstance(o, np.integer):  return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, np.ndarray):  return o.tolist()
    return o


def run(rebuild: bool = False):
    os.makedirs(RES_DIR, exist_ok=True)
    pkl_path = os.path.join(RES_DIR, "baseline.pkl")

    # ── Step 0: baseline ─────────────────────────────────────────────────────
    if os.path.exists(pkl_path) and not rebuild:
        print(f"Loading cached baseline from {pkl_path}")
        baseline = load_baseline(pkl_path)
        if "COMBINED" not in baseline:
            print("Cached baseline predates auto-calibration -- rebuilding ...")
            baseline = build_baseline(save_path=pkl_path)
    else:
        baseline = build_baseline(save_path=pkl_path)

    de_base        = baseline["DE"]
    fe_base        = baseline["FE"]
    combined_calib = baseline["COMBINED"]

    print(f"\nDE T2 healthy mean={de_base['healthy_t2'].mean():.2f}  "
          f"threshold={de_base['threshold']:.2f}")
    print(f"FE T2 healthy mean={fe_base['healthy_t2'].mean():.2f}  "
          f"threshold={fe_base['threshold']:.2f}")
    print(f"Auto-calibrated combined threshold: k={combined_calib['k']:.3f}  "
          f"H={combined_calib['H']:.3f}")

    # ── Step 1: collect snapshots ─────────────────────────────────────────────
    paths = all_snapshots(SNAP_DIR)
    if not paths:
        sys.exit(f"ERROR: no snapshot CSVs found in {SNAP_DIR!r}")
    print(f"\nFound {len(paths)} snapshots in:\n  {SNAP_DIR}")

    # ── Step 2: score every snapshot -- load inferred from signal itself ──────
    print("\nScoring snapshots (load auto-inferred per snapshot) ...")
    times, files           = [], []
    de_scores, fe_scores   = [], []
    de_inferred, fe_inferred = [], []   # track which load was inferred each time

    for i, path in enumerate(paths):
        if i % 100 == 0:
            print(f"  {i}/{len(paths)}", end="\r", flush=True)

        de, fe, t0, t1 = load_snapshot(path)
        if len(de) < WINDOW_SAMPLES or len(fe) < WINDOW_SAMPLES:
            continue
        de, fe = de[:WINDOW_SAMPLES], fe[:WINDOW_SAMPLES]

        fv_de = channel_features(de)
        fv_fe = channel_features(fe)

        de_t2, de_load = t_squared_auto_load(fv_de, de_base)
        fe_t2, fe_load = t_squared_auto_load(fv_fe, fe_base)

        de_scores.append(de_t2)
        fe_scores.append(fe_t2)
        de_inferred.append(de_load)
        fe_inferred.append(fe_load)
        times.append(t0)
        files.append(os.path.basename(path))

    print(f"  {len(times)}/{len(paths)} snapshots scored      ")

    times     = np.array(times)
    de_scores = np.array(de_scores)
    fe_scores = np.array(fe_scores)

    print(f"\nDE T2 -- min={de_scores.min():.2f}  max={de_scores.max():.2f}  "
          f"mean={de_scores.mean():.2f}")
    print(f"FE T2 -- min={fe_scores.min():.2f}  max={fe_scores.max():.2f}  "
          f"mean={fe_scores.mean():.2f}")
    de_load_dist = Counter(de_inferred)
    fe_load_dist = Counter(fe_inferred)
    print(f"Inferred load distribution -- DE: {dict(sorted(de_load_dist.items()))}  "
          f"FE: {dict(sorted(fe_load_dist.items()))}")

    # ── Step 3: ONE fair, auto-calibrated detector decides WHEN ──────────────
    z_de, z_fe, combined_z, S, onset_idx, k, H = combined_detection(
        de_scores, fe_scores, de_base, fe_base, combined_calib
    )

    if onset_idx is not None:
        print(f"\nFault DETECTED -- snapshot index {onset_idx}, "
              f"file {files[onset_idx]}, t={times[onset_idx]:.2f}s")
    else:
        print("\nNo fault detected in this run.")

    # ── Step 4: location decided by magnitude after onset --------------------
    location = decide_location(z_de, z_fe, onset_idx)
    if onset_idx is not None:
        print(f"Predicted location: {location}")

    # ── Step 5: evaluate against ground truth ─────────────────────────────────
    gt_df = pd.DataFrame()
    ev    = {"outcome": "N/A"}

    if os.path.exists(GT_PATH):
        gt_df = pd.read_csv(GT_PATH)
        ev    = evaluate(gt_df, times, onset_idx, location)
        print_evaluation(ev)
    else:
        print(f"\nNote: ground truth not found at {GT_PATH}")

    # ── Step 6: save ──────────────────────────────────────────────────────────
    if SAVE_RESULTS:
        out = dict(
            snapshot_times      = times.tolist(),
            snapshot_files      = files,
            de_scores           = de_scores.tolist(),
            fe_scores           = fe_scores.tolist(),
            de_inferred_loads   = de_inferred,
            fe_inferred_loads   = fe_inferred,
            combined_z          = combined_z.tolist(),
            cusum_S             = S.tolist(),
            cusum_k             = float(k),
            cusum_H             = float(H),
            de_threshold        = float(de_base["threshold"]),
            fe_threshold        = float(fe_base["threshold"]),
            onset_idx           = onset_idx,
            onset_time_s        = float(times[onset_idx]) if onset_idx is not None else None,
            onset_file          = files[onset_idx] if onset_idx is not None else None,
            predicted_location  = location,
            evaluation          = ev,
        )
        out_path = os.path.join(RES_DIR, "detection_results.json")
        with open(out_path, "w") as fh:
            json.dump(out, fh, indent=2, default=_np)
        print(f"\nResults saved -> {out_path}")

    # ── Step 7: plot ──────────────────────────────────────────────────────────
    if PLOT_RESULTS and _CAN_PLOT:
        plot_results(
            times        = times,
            de_scores    = de_scores,
            fe_scores    = fe_scores,
            de_threshold = de_base["threshold"],
            fe_threshold = fe_base["threshold"],
            combined_z   = combined_z,
            S            = S,
            H            = H,
            onset_idx    = onset_idx,
            location     = location,
            gt_df        = gt_df,
            true_onset_s = true_onset_time(gt_df) if not gt_df.empty else None,
            true_loc     = true_location(gt_df) if not gt_df.empty else None,
            save         = SAVE_RESULTS,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true",
                        help="Force rebuild of healthy baseline")
    run(rebuild=parser.parse_args().rebuild)