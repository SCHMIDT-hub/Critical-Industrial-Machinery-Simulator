import sys
import os

# ── FIXED: DYNAMIC ABSOLUTE WORKSPACE PATH RESOLUTION ─────────────────────
MODULES_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(MODULES_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, "Data")
# ───────────────────────────────────────────────────────────────────────────


def get_file_name(system, sampling_rate, state, load, rpm=None,
                  fault_location=None, fault_size=None, or_position=None, machine_type="bearing"):
    """
    Constructs the correct filename from the given parameters.
    Handles traditional CWRU (DE/FE), Parallel Gearbox, and your custom NU205 dataset formats.
    """
    raw_loc = str(fault_location).strip()
    if raw_loc.upper().startswith("OR_"):
        cleaned_fault_location = "OR"
        resolved_or_position = raw_loc.split("_")[-1]
    else:
        cleaned_fault_location = raw_loc
        resolved_or_position = str(or_position).strip() if or_position is not None else None

    # Choose suffix based on asset class rules
    if rpm is not None and (system.lower() == "nu205" or machine_type == "gearbox"):
        raw_suffix = str(rpm).strip()
    else:
        raw_suffix = str(load).strip()

    if raw_suffix.endswith(".0"):
        suffix_id = raw_suffix[:-2]
    else:
        suffix_id = raw_suffix

    # ── BRANCH A: BEARING MAPPING (.CSV) ────────────────────────────────────
    if machine_type == "bearing":
        if system.lower() == "nu205":
            if state == "normal" or suffix_id == "0":
                base_filename = f"normal_{suffix_id}"
            else:
                base_filename = f"{str(cleaned_fault_location).upper()}_{suffix_id}"
            
            # Auto-resolve extension
            filename = f"{base_filename}.csv" if os.path.exists(os.path.join(DATA_PATH, f"{base_filename}.csv")) else f"{base_filename}.xlsx"
        
        else:
            rate_str = f"{sampling_rate // 1000}k"
            if state == "normal" or suffix_id == "0":
                filename = f"Normal_{suffix_id}.csv"
            else:
                try:
                    float_val = float(fault_size)
                    size_str = f"{float_val:.3f}".split(".")[-1]
                except (ValueError, TypeError):
                    size_str = str(fault_size).replace("0.", "").ljust(3, "0")

                if cleaned_fault_location == "OR":
                    filename = f"{rate_str}_{system}_OR{size_str}_{resolved_or_position}_{suffix_id}.csv"
                else:
                    filename = f"{rate_str}_{system}_{cleaned_fault_location}{size_str}_{suffix_id}.csv"

    # ── BRANCH B: PARALLEL GEARBOX STRINGS (DYNAMIC SCANNING) ─────────────────
    elif machine_type == "gearbox":
        if state == "normal" or suffix_id == "0":
            base_filename = f"normal_{suffix_id}"  
        else:
            filename_fault = str(cleaned_fault_location).lower()
            base_filename = f"{filename_fault}_{suffix_id}"

        # FIXED: Scan for whichever extension (.xlsx vs .csv) physically exists on disk
        xlsx_path = os.path.join(DATA_PATH, f"{base_filename}.xlsx")
        csv_path = os.path.join(DATA_PATH, f"{base_filename}.csv")
        
        if os.path.exists(xlsx_path):
            filename = f"{base_filename}.xlsx"
        elif os.path.exists(csv_path):
            filename = f"{base_filename}.csv"
        else:
            # Fallback placeholder to allow downstream zero matrix filling if it's a rest state
            filename = f"{base_filename}.xlsx"

    else:
        raise ValueError(f"Unknown machine type reference: {machine_type}")

    full_path = os.path.join(DATA_PATH, filename)

    # Stationary run engine bypass
    if suffix_id == "0":
        return full_path

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

    active_fault_size = None
    for (fault_time, fault_size) in fault_timeline:
        if seg_start >= fault_time:
            active_fault_size = fault_size
        else:
            break

    if active_fault_size is None:
        return get_file_name(
            system        = system,
            sampling_rate = sampling_rate,
            state         = "normal",
            load          = load,
            rpm           = rpm,
            machine_type  = machine_type
        )

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