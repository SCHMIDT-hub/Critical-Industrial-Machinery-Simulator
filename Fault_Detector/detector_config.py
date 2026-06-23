"""
detector_config.py
--------------------
Scope: detect WHEN a fault occurs and WHICH side (DE or FE) it's on.

LOAD_SCHEDULE HAS BEEN REMOVED.

Previously the detector needed you to tell it which load was active at
each timestamp, via a manually-maintained LOAD_SCHEDULE list. That list
was wrong twice across different test runs, causing the entire baseline
comparison to be structurally mismatched from t=0.

The detector now infers the load automatically from the signal itself,
by comparing each snapshot against ALL four per-load healthy models and
picking the one it resembles most closely (minimum T2 across all loads).
No external schedule, nothing that can go stale between test runs.

The ONLY thing you need to edit before running is WINDOW_SAMPLES if your
sample_duration changed. Nothing else.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _latest_run_dir(base_name):
    base = os.path.join(BASE_DIR, base_name)
    if not os.path.isdir(base):
        return base
    subs = [os.path.join(base, d) for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d))]
    return max(subs, key=os.path.getmtime) if subs else base


DATA_DIR = os.path.join(BASE_DIR, "Data")
SNAP_DIR = _latest_run_dir("outputs")
GT_PATH  = os.path.join(SNAP_DIR, "ground_truth.csv")
RES_DIR  = os.path.join(BASE_DIR, "detector_results")

# ── Signal parameters ─────────────────────────────────────────────────────────
FS             = 12_000
WINDOW_SAMPLES = 4800   # = sample_duration(s) x FS
                         # EDIT THIS if sample_duration changed from 0.4s

# ── Baseline ─────────────────────────────────────────────────────────────────
LOAD_RPM             = {0: 1797, 1: 1772, 2: 1750, 3: 1730}  # display only
BASELINE_OVERLAP     = 0.0
PCA_VARIANCE         = 0.95
THRESHOLD_PERCENTILE = 99

# ── Auto-calibration ──────────────────────────────────────────────────────────
CALIBRATION_RUN_LENGTH    = 3000   # snapshots -- raise if runs are longer than ~60 min
CALIBRATION_N_TRIALS      = 500
CALIBRATION_SAFETY_MARGIN = 1.3

MIN_CONSECUTIVE = 3

# ── Location decision ─────────────────────────────────────────────────────────
LOCATION_WINDOW = 15
LOCATION_RATIO  = 1.3

# ── Output ────────────────────────────────────────────────────────────────────
SAVE_RESULTS = True
PLOT_RESULTS = True