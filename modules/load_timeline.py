import sys
import os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COMPONENTS, VALID_GEARBOX_RPMS


def find_nearest_rpm(raw_rpm):
    """Finds the closest physical target speed from the available data constants."""
    try:
        val = float(raw_rpm)
    except (ValueError, TypeError):
        return 0
        
    if val < 50.0:
        return 0
    
    idx = (np.abs(np.array(VALID_GEARBOX_RPMS) - val)).argmin()
    return VALID_GEARBOX_RPMS[idx]


def build_load_timeline(experiment):
    """
    Parses the raw machine log file, converts it to a base profile, applies lookahead
    transient smoothing to seal time leaks, and loops that profile periodically.
    """
    file_path = experiment["machine_log_path"]
    total_duration = experiment["run_duration_secs"]

    # 1. Load Raw Telemetry Sheet
    if str(file_path).lower().endswith(('.xlsx', '.xls')):
        df_raw = pd.read_excel(file_path)
    else:
        df_raw = pd.read_csv(file_path)
        
    df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]

    time_col = next((c for c in df_raw.columns if "time" in c or "stamp" in c or "date" in c), None)
    rpm_col = next((c for c in df_raw.columns if any(x in c for x in ["rpm", "speed", "velocity", "sp_rpm", "motor", "freq"])), None)

    if not time_col or not rpm_col:
        raise KeyError(f"[Telemetry Log Error]: Failed to locate required columns.")

    # 2. Extract Base Timestamps Layer
    t_series = pd.to_timedelta(df_raw[time_col].astype(str), errors='coerce')
    if t_series.isna().all():
        t_series = pd.to_datetime(df_raw[time_col].astype(str), format='%M:%S', errors='coerce')
        if t_series.isna().all():
            t_series = pd.to_datetime(df_raw[time_col], errors='coerce')

    df_raw["parsed_time"] = t_series
    df_raw = df_raw.dropna(subset=["parsed_time", rpm_col]).sort_values(by="parsed_time").reset_index(drop=True)

    if len(df_raw) == 0:
        raise ValueError(f"[Time Parse Error]: The time column '{time_col}' could not be converted.")

    if isinstance(df_raw["parsed_time"].iloc[0], pd.Timestamp):
        df_raw["elapsed_seconds"] = (df_raw["parsed_time"] - df_raw["parsed_time"].iloc[0]).dt.total_seconds()
    else:
        df_raw["elapsed_seconds"] = df_raw["parsed_time"] - df_raw["parsed_time"].iloc[0]
        if hasattr(df_raw["elapsed_seconds"], "dt"):
            df_raw["elapsed_seconds"] = df_raw["elapsed_seconds"].dt.total_seconds()

    # 3. Clustering and State Mapping (with Lookahead Edge Correction)
    df_raw["rpm_mapped"] = df_raw[rpm_col].apply(find_nearest_rpm)

    # ── FIXED LOOKAHEAD SMOOTHING LAYER ──────────────────────────────────────
    # Using fillna ensures edge frames don't read as artificial isolated spikes
    shift_back = df_raw["rpm_mapped"].shift(1).fillna(df_raw["rpm_mapped"])
    shift_fwd = df_raw["rpm_mapped"].shift(-1).fillna(df_raw["rpm_mapped"])
    
    is_isolated = (df_raw["rpm_mapped"] != shift_back) & (df_raw["rpm_mapped"] != shift_fwd)
    df_raw.loc[is_isolated, "rpm_mapped"] = shift_fwd
    # ─────────────────────────────────────────────────────────────────────────

    # Evaluate steady state changes post-smoothing
    df_raw["state_changed"] = df_raw["rpm_mapped"] != df_raw["rpm_mapped"].shift()
    df_raw["state_id"] = df_raw["state_changed"].cumsum()

    state_blocks = df_raw.groupby("state_id").agg(
        rpm_mapped=('rpm_mapped', 'first'),
        start_time=('elapsed_seconds', 'min'),
        end_time=('elapsed_seconds', 'max')
    ).reset_index(drop=True)

    # FIXED: Close inter-block time leaks by shifting the NEXT block's start backward
    state_blocks["end_time_adjusted"] = state_blocks["start_time"].shift(-1).fillna(state_blocks["end_time"])
    state_blocks["duration"] = state_blocks["end_time_adjusted"] - state_blocks["start_time"]

    # Filter out residual mathematical structural anomalies
    MIN_STEADY_DURATION = 0.1
    state_blocks = state_blocks[state_blocks["duration"] >= MIN_STEADY_DURATION].reset_index(drop=True)

    # ── THE PERIODIC LOOP ENGINE ─────────────────────────────────────────────
    base_cycle_duration = float(df_raw["elapsed_seconds"].iloc[-1] - df_raw["elapsed_seconds"].iloc[0])
    if base_cycle_duration <= 0:
        base_cycle_duration = 1.0

    segments = []
    current_time = 0.0

    while current_time < total_duration:
        for _, row in state_blocks.iterrows():
            duration = float(row["duration"])
            start = current_time
            end = min(current_time + duration, total_duration)

            if end <= start:
                break

            segments.append({
                "start": round(start, 4),
                "end": round(end, 4),
                "load": 0, 
                "rpm": float(row["rpm_mapped"])
            })

            current_time = end
            if current_time >= total_duration:
                break

    experiment["loads"] = [0]
    return segments


def print_timeline_summary(segments, experiment):
    """Prints a clear, structured summary of the generated periodic timeline."""
    print(f"\n  {'Segment':<10} {'Start (s)':<12} {'End (s)':<12} {'Duration (s)':<15} {'Target State'}")
    print(f"  {'-'*65}")

    for i, seg in enumerate(segments):
        duration = round(seg["end"] - seg["start"], 4)
        state_label = "REST / STATIONARY" if seg["rpm"] == 0 else f"RUNNING @ {int(seg['rpm'])} RPM"
        print(f"  {i+1:<10} {seg['start']:<12} {seg['end']:<12} {duration:<15} {state_label}")

    print(f"\n  Total segments     : {len(segments)}")
    print(f"  Total run timeline : {segments[-1]['end']}s ({segments[-1]['end']/60:.2f} mins)")