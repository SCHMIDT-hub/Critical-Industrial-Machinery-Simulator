import sys
import os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import COMPONENTS

# ── Global read pointer tracker ────────────────────────────────────────────
_read_pointers = {}


def reset_pointers():
    """Call this at the start of each new experiment."""
    global _read_pointers
    _read_pointers = {}


def load_source_file(file_path, sampling_rate, machine_type="bearing"):
    """
    Loads a CSV or Excel file and returns the active sensor channels as a dictionary 
    of numpy arrays. Dynamically adjusts array duration based on the machine type.
    """
    meta = COMPONENTS[machine_type]
    source_duration = meta["source_data_duration"]
    sensor_channels = meta["sensor_channels"]
    max_samples = int(source_duration * sampling_rate)

    # ── FIXED: UPDATED REST STATE INTERCEPT LAYER ───────────────────────────
    # Detects the rest status identifier cleanly if no physical file exists on disk
    if file_path == "REST_STATE" or "normal_0" in os.path.basename(file_path):
        return {channel: np.zeros(max_samples, dtype=np.float64) for channel in sensor_channels}
    # ─────────────────────────────────────────────────────────────────────────

    # ── FIXED: DYNAMIC EXTENSION ROUTER (PREVENTS EXCEL CRASHES) ─────────────
    if str(file_path).lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            first_line = f.readline()
        
        chosen_sep = ';' if ';' in first_line else ','
        df = pd.read_csv(file_path, sep=chosen_sep)
        
    df.columns = [str(c).strip().replace('\r', '').replace('\n', '').lower() for c in df.columns]
    
    if len(df.columns) == 1 and ',' in df.columns[0]:
        df = pd.read_csv(file_path, sep=',')
        df.columns = [str(c).strip().lower() for c in df.columns]
    # ─────────────────────────────────────────────────────────────────────────
    
    channels_data = {}

    # ── BRANCH A: BEARING TRACKING ───────────────────────────────────────────
    if machine_type == "bearing":
        if "nu205" in os.path.basename(file_path).lower() or any(x in os.path.basename(file_path).upper() for x in ["IF_", "OF_", "BF_"]):
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            for i, channel in enumerate(sensor_channels):
                col_name = numeric_cols[i] if i < len(numeric_cols) else numeric_cols[-1]
                channels_data[channel] = df[col_name].values[:max_samples].astype(np.float64)
        else:
            for channel in sensor_channels:
                if channel not in df.columns:
                    raise KeyError(
                        f"Expected channel column '{channel}' not found in {os.path.basename(file_path)}. "
                        f"Available columns are: {list(df.columns)}"
                    )
                channels_data[channel] = df[channel].values[:max_samples].astype(np.float64)

    # ── BRANCH B: GEARBOX TRACKING (By absolute numeric position) ──────────
    elif machine_type == "gearbox":
        if df.shape[1] < 4:
            raise ValueError(f"File {os.path.basename(file_path)} does not have enough columns! "
                             f"Expected at least 4 columns (Time, CH1, CH2, CH3), got {df.shape[1]}.")
                             
        for idx, channel in enumerate(sensor_channels):
            # Column 0 is Time(s), Columns 1, 2, 3 map to CH1, CH2, CH3
            channels_data[channel] = df.iloc[:, idx + 1].values[:max_samples].astype(np.float64)

    return channels_data


def fetch_signal(file_path, sampling_rate, required_duration_secs, machine_type="bearing"):
    """
    Fetches exactly the required number of samples from the source file
    using a 95% overlap sliding window strategy.
    """
    global _read_pointers

    meta = COMPONENTS[machine_type]
    sensor_channels = meta["sensor_channels"]

    required_samples     = int(required_duration_secs * sampling_rate)
    total_source_samples = int(meta["source_data_duration"] * sampling_rate)

    # ── FIXED: REST STATE INTERCEPT LAYER ───────────────────────────────────
    if file_path == "REST_STATE" or "normal_0" in os.path.basename(file_path):
        return {channel: np.zeros(required_samples, dtype=np.float64) for channel in sensor_channels}
    # ─────────────────────────────────────────────────────────────────────────

    source_signals = load_source_file(file_path, sampling_rate, machine_type)

    if file_path not in _read_pointers:
        _read_pointers[file_path] = 0

    pointer = _read_pointers[file_path]
    signals_out = {channel: np.zeros(required_samples, dtype=np.float64) for channel in sensor_channels}

    samples_filled = 0
    current_pos    = pointer

    while samples_filled < required_samples:
        available = total_source_samples - (current_pos % total_source_samples)
        needed    = required_samples - samples_filled
        to_copy   = min(available, needed)

        src_start = current_pos % total_source_samples
        src_end   = src_start + to_copy

        for channel in sensor_channels:
            signals_out[channel][samples_filled : samples_filled + to_copy] = \
                source_signals[channel][src_start:src_end]

        samples_filled += to_copy
        current_pos    += to_copy

    step = max(1, int(required_samples * 0.05))
    _read_pointers[file_path] = (pointer + step) % total_source_samples

    return signals_out


if __name__ == "__main__":
    print("Testing dynamic signal streaming engine framework execution...")