import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_PATH


def get_file_name(system, sampling_rate, state, load,
                  fault_location=None, fault_size=None, or_position=None):
    """
    Constructs the correct filename from the given parameters
    and verifies it exists in the Data folder.

    Returns full file path if found, raises FileNotFoundError if not.
    """

    rate_str = f"{sampling_rate // 1000}k"  # 12000 → "12k", 48000 → "48k"

    # ── Normal baseline ────────────────────────────────────────────────────
    if state == "normal":
        filename = f"Normal_{load}.csv"

    # ── Fault file ─────────────────────────────────────────────────────────
    else:
        if fault_location == "OR":
            # e.g. 12k_DE_OR007_6_0.csv
            size_str = str(fault_size).replace("0.", "").ljust(3, "0")  # 0.007 → "007"
            filename = f"{rate_str}_{system}_OR{size_str}_{or_position}_{load}.csv"
        else:
            # e.g. 12k_DE_IR007_0.csv or 12k_DE_B007_0.csv
            size_str = str(fault_size).replace("0.", "").ljust(3, "0")  # 0.007 → "007"
            filename = f"{rate_str}_{system}_{fault_location}{size_str}_{load}.csv"

    full_path = os.path.join(DATA_PATH, filename)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found: {filename}\n  Expected at: {full_path}")

    return full_path


def get_segment_file(segment, experiment, fault_timeline):
    """
    For a given load segment and fault timeline, determines:
    - Is the machine healthy or faulty at this point in time?
    - If faulty, what severity level is active?
    Then returns the correct file path.
    """

    seg_start      = segment["start"]
    load           = segment["load"]
    system         = experiment["system"]
    sampling_rate  = experiment["sampling_rate"]
    fault_location = experiment["fault_location"]
    or_position    = experiment["or_position"]

    # ── Determine fault state at this segment's start time ─────────────────
    active_fault_size = None
    for (fault_time, fault_size) in fault_timeline:
        if seg_start >= fault_time:
            active_fault_size = fault_size
        else:
            break

    # ── Healthy — use normal baseline ──────────────────────────────────────
    if active_fault_size is None:
        return get_file_name(
            system       = system,
            sampling_rate= sampling_rate,
            state        = "normal",
            load         = load
        )

    # ── Faulty — use fault file ────────────────────────────────────────────
    return get_file_name(
        system        = system,
        sampling_rate = sampling_rate,
        state         = "fault",
        load          = load,
        fault_location= fault_location,
        fault_size    = active_fault_size,
        or_position   = or_position
    )


if __name__ == "__main__":

    # ── Test 1: Normal baseline file lookup ────────────────────────────────
    print("\nTest 1 — Normal baseline files:")
    for load in [0, 1, 2, 3]:
        try:
            path = get_file_name("DE", 12000, "normal", load)
            print(f"  Load {load} HP → {os.path.basename(path)}")
        except FileNotFoundError as e:
            print(f"  {e}")

    # ── Test 2: Fault file lookup ──────────────────────────────────────────
    print("\nTest 2 — Fault file lookups:")
    test_cases = [
        ("DE", 12000, "fault", 0, "IR",  0.007, None),
        ("DE", 12000, "fault", 1, "B",   0.014, None),
        ("DE", 12000, "fault", 2, "OR",  0.007, 6),
        ("DE", 48000, "fault", 0, "IR",  0.007, None),
        ("FE", 12000, "fault", 1, "IR",  0.014, None),
    ]
    for (sys, rate, state, load, fault, size, or_pos) in test_cases:
        try:
            path = get_file_name(sys, rate, state, load, fault, size, or_pos)
            print(f"  {sys} {rate//1000}k {fault}{size} load{load} "
                  f"→ {os.path.basename(path)}")
        except FileNotFoundError as e:
            print(f"  ERROR: {e}")

    # ── Test 3: Segment file mapping with fault timeline ───────────────────
    print("\nTest 3 — Segment file mapping with fault timeline:")

    test_experiment = {
        "system"        : "DE",
        "sampling_rate" : 12000,
        "fault_location": "IR",
        "or_position"   : None,
    }

    # fault appears at 300s, escalates at 700s
    test_fault_timeline = [(300.0, 0.007), (700.0, 0.014)]

    test_segments = [
        {"start":   0.0, "end":   8.0, "load": 1, "rpm": 1772},  # healthy
        {"start": 300.0, "end": 308.0, "load": 2, "rpm": 1750},  # fault 0.007
        {"start": 700.0, "end": 708.0, "load": 3, "rpm": 1730},  # fault 0.014
    ]

    for seg in test_segments:
        try:
            path = get_segment_file(seg, test_experiment, test_fault_timeline)
            state = "healthy" if seg["start"] < 300 else "faulty"
            print(f"  t={seg['start']}s load={seg['load']}HP [{state}]"
                  f" → {os.path.basename(path)}")
        except FileNotFoundError as e:
            print(f"  ERROR: {e}")