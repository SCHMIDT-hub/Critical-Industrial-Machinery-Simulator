import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from config import DATA_PATH, SOURCE_DATA_DURATION


# ── Global read pointer tracker ────────────────────────────────────────────
_read_pointers = {}


def reset_pointers():
    """Call this at the start of each new experiment."""
    global _read_pointers
    _read_pointers = {}


def load_source_file(file_path, sampling_rate):
    """
    Loads a CSV file and returns DE_time and FE_time as numpy arrays.
    Only uses the first 10 seconds of data.
    """
    df = pd.read_csv(file_path)

    df.columns = [c.strip().lower() for c in df.columns]

    max_samples = SOURCE_DATA_DURATION * sampling_rate

    de = df["de_time"].values[:max_samples].astype(np.float64)
    fe = df["fe_time"].values[:max_samples].astype(np.float64)

    return de, fe


def fetch_signal(file_path, sampling_rate, required_duration_secs):
    """
    Fetches exactly the required number of samples from the source file
    using a 95% overlap sliding window strategy.

    Each call advances the read pointer by 5% of the requested duration.
    When source data exhausts, wraps around to the beginning — infinite loop,
    no hard limit on run duration.

    Returns:
        de_signal : numpy array of length = required_samples
        fe_signal : numpy array of length = required_samples
    """
    global _read_pointers

    required_samples     = int(required_duration_secs * sampling_rate)
    total_source_samples = SOURCE_DATA_DURATION * sampling_rate

    de_source, fe_source = load_source_file(file_path, sampling_rate)

    if file_path not in _read_pointers:
        _read_pointers[file_path] = 0

    pointer = _read_pointers[file_path]

    de_out = np.zeros(required_samples)
    fe_out = np.zeros(required_samples)

    samples_filled = 0
    current_pos    = pointer

    while samples_filled < required_samples:
        available = total_source_samples - (current_pos % total_source_samples)
        needed    = required_samples - samples_filled
        to_copy   = min(available, needed)

        src_start = current_pos % total_source_samples
        src_end   = src_start + to_copy

        de_out[samples_filled : samples_filled + to_copy] = de_source[src_start:src_end]
        fe_out[samples_filled : samples_filled + to_copy] = fe_source[src_start:src_end]

        samples_filled += to_copy
        current_pos    += to_copy

    # ── Advance pointer by 5% — wraps around automatically ────────────────
    step = max(1, int(required_samples * 0.05))
    _read_pointers[file_path] = (pointer + step) % total_source_samples

    return de_out, fe_out


if __name__ == "__main__":
    from file_mapper import get_file_name

    # ── Test 1: Load a file and check shape ────────────────────────────────
    print("\nTest 1 — Load source file and check dimensions:")
    path = get_file_name("DE", 12000, "normal", 0)
    de, fe = load_source_file(path, 12000)
    print(f"  File          : {os.path.basename(path)}")
    print(f"  DE samples    : {len(de)}  ({len(de)/12000:.1f}s at 12k)")
    print(f"  FE samples    : {len(fe)}")
    print(f"  DE range      : [{de.min():.4f}, {de.max():.4f}]")

    # ── Test 2: Fetch exact duration ───────────────────────────────────────
    print("\nTest 2 — Fetch exact segment durations:")
    reset_pointers()
    for duration in [1.0, 4.0, 3.0]:
        de_seg, fe_seg = fetch_signal(path, 12000, duration)
        print(f"  Requested {duration}s → got {len(de_seg)} samples "
              f"({len(de_seg)/12000:.2f}s)")

    # ── Test 3: Overlap — wrap-around on infinite loop ─────────────────────
    print("\nTest 3 — Overlap behaviour (same 1s segment fetched 5 times):")
    reset_pointers()
    path_fault = get_file_name("DE", 12000, "fault", 1, "IR", 0.007)
    for i in range(5):
        de_seg, _ = fetch_signal(path_fault, 12000, 1.0)
        print(f"  Fetch {i+1}: first sample = {de_seg[0]:.6f}  "
              f"last sample = {de_seg[-1]:.6f}  "
              f"pointer → {_read_pointers[path_fault]}")