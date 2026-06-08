import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_PATH


def get_file_name(system, sampling_rate, state, load, rpm=None,
                  fault_location=None, fault_size=None, or_position=None, machine_type="bearing"):
    """
    Constructs the correct filename from the given parameters.
    Handles traditional CWRU (DE/FE), Parallel Gearbox, and your custom NU205 dataset formats.
    """
    # ── CRITICAL STRIPPER: Decouple composite dropdown entries like "OR_6" universally ──
    raw_loc = str(fault_location).strip()
    if raw_loc.upper().startswith("OR_"):
        cleaned_fault_location = "OR"
        # Extract the clock position digit safely from the dropdown text (e.g., "6")
        resolved_or_position = raw_loc.split("_")[-1]
    else:
        cleaned_fault_location = raw_loc
        resolved_or_position = str(or_position).strip() if or_position is not None else None
    # ─────────────────────────────────────────────────────────────────────────

    # Choose suffix based on asset class rules
    if rpm is not None and (system == "NU205" or machine_type == "gearbox"):
        raw_suffix = str(rpm).strip()
    else:
        raw_suffix = str(load).strip()

    # ── SAFE STRIPPING LAYER: Removes trailing '.0' from numeric strings ──
    if raw_suffix.endswith(".0"):
        suffix_id = raw_suffix[:-2]
    else:
        suffix_id = raw_suffix
    # ─────────────────────────────────────────────────────────────────────────

    # ── BRANCH A: BEARING MAPPING ───────────────────────────────────────────
    if machine_type == "bearing":
        # 1. Custom NU205 Dataset Branch
        if system == "NU205":
            if state == "normal":
                filename = f"normal_{suffix_id}.csv"  # e.g., normal_1200.csv
            else:
                filename = f"{str(cleaned_fault_location).upper()}_{suffix_id}.csv"
        
        # 2. Traditional CWRU Ball Bearing Branch (DE / FE)
        else:
            rate_str = f"{sampling_rate // 1000}k"  # 12000 → "12k"
            if state == "normal":
                filename = f"Normal_{suffix_id}.csv"
            else:
                # Defensive formatting string converter to prevent crash on dynamic string sizes
                try:
                    float_val = float(fault_size)
                    size_str = f"{float_val:.3f}".split(".")[-1] # 0.007 -> "007", 0.021 -> "021"
                except (ValueError, TypeError):
                    size_str = str(fault_size).replace("0.", "").ljust(3, "0")

                # Use the cleaned variables to build the structured string perfectly
                if cleaned_fault_location == "OR":
                    filename = f"{rate_str}_{system}_OR{size_str}_{resolved_or_position}_{suffix_id}.csv"
                else:
                    filename = f"{rate_str}_{system}_{cleaned_fault_location}{size_str}_{suffix_id}.csv"

    # ── BRANCH B: PARALLEL GEARBOX STRINGS ─────────────────────────────────
    elif machine_type == "gearbox":
        if state == "normal":
            filename = f"normal_{suffix_id}.csv"
        else:
            filename = f"{str(cleaned_fault_location).lower()}_{suffix_id}.csv"

    else:
        raise ValueError(f"Unknown machine type reference: {machine_type}")

    full_path = os.path.join(DATA_PATH, filename)

    if not os.path.exists(full_path):
        raise FileNotFoundError(
            f"Required dataset file not found: '{filename}'\n"
            f"Ensure this file exists in your data directory: {DATA_PATH}"
        )

    return full_path


def get_segment_file(segment, experiment, fault_timeline):
    """
    Determines if the machine is healthy or faulty at this point in time,
    then fetches the correct file path using the customized naming routing.
    """
    machine_type   = experiment.get("machine_type", "bearing")
    seg_start      = segment["start"]
    load           = segment["load"]
    rpm            = segment.get("rpm", None)
    system         = experiment["system"]
    sampling_rate  = experiment["sampling_rate"]
    raw_fault_loc  = experiment["fault_location"]

    # ── Determine fault state at this segment's start time ─────────────────
    active_fault_size = None
    for (fault_time, fault_size) in fault_timeline:
        if seg_start >= fault_time:
            active_fault_size = fault_size
        else:
            break

    # Healthy — use normal baseline
    if active_fault_size is None:
        return get_file_name(
            system        = system,
            sampling_rate = sampling_rate,
            state         = "normal",
            load          = load,
            rpm           = rpm,
            machine_type  = machine_type
        )

    # Faulty — use fault file (The parameters get cleaned inside get_file_name now!)
    return get_file_name(
        system         = system,
        sampling_rate  = sampling_rate,
        state          = "fault",
        load           = load,
        rpm            = rpm,
        fault_location = raw_fault_loc,
        fault_size     = active_fault_size,
        or_position    = experiment.get("or_position", None),
        machine_type   = machine_type
    )