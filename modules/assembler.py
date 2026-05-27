import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from modules.signal_engine import fetch_signal, reset_pointers
from modules.file_mapper  import get_file_name, get_segment_file
from modules.load_timeline import build_load_timeline
from modules.fault_timer  import generate_fault_timeline


def get_state_at_time(t, load_segments, fault_timeline):
    """
    Returns the active load and fault size at time t.
    """
    # ── Active load ────────────────────────────────────────────────────────
    active_load = None
    for seg in load_segments:
        if seg["start"] <= t < seg["end"]:
            active_load = seg["load"]
            break
    if active_load is None:
        active_load = load_segments[-1]["load"]

    # ── Active fault size ──────────────────────────────────────────────────
    active_fault = None
    for (fault_time, fault_size) in fault_timeline:
        if t >= fault_time:
            active_fault = fault_size
        else:
            break

    return active_load, active_fault


def crosses_boundary(t_start, t_end, load_segments, fault_timeline):
    """
    Returns True if the snapshot window [t_start, t_end] crosses
    a load change or fault onset/escalation boundary.
    """
    # ── Check load boundaries ──────────────────────────────────────────────
    for seg in load_segments:
        if t_start < seg["start"] < t_end:
            return True
        if t_start < seg["end"] < t_end:
            return True

    # ── Check fault boundaries ─────────────────────────────────────────────
    for (fault_time, _) in fault_timeline:
        if t_start < fault_time < t_end:
            return True

    return False


def get_label(load, fault_size, experiment):
    """
    Returns the source filename as the label — this is the ground truth
    state description. For transition snapshots returns e.g. 'S1/S2'.
    """
    system        = experiment["system"]
    sampling_rate = experiment["sampling_rate"]
    fault_loc     = experiment["fault_location"]
    or_pos        = experiment["or_position"]

    if fault_size is None:
        return os.path.basename(
            get_file_name(system, sampling_rate, "normal", load)
        )
    else:
        return os.path.basename(
            get_file_name(system, sampling_rate, "fault",
                          load, fault_loc, fault_size, or_pos)
        )


def run_assembler(config, load_segments, fault_timeline):
    """
    Main assembler loop. Walks forward in time, takes snapshots,
    fetches signals, records labels.

    Returns list of snapshot dicts:
    [
        {
            "t_start"  : 0.0,
            "t_end"    : 0.2,
            "de"       : np.array([...]),
            "fe"       : np.array([...]),
            "label"    : "Normal_2.csv",
            "transition": False
        },
        ...
    ]
    """
    reset_pointers()

    system          = config["system"]
    sampling_rate   = config["sampling_rate"]
    fault_loc       = config["fault_location"]
    or_pos          = config["or_position"]
    sample_dur      = config["sample_duration"]
    interval        = config["sampling_interval"]
    total_duration  = config["run_duration_secs"]

    snapshots   = []
    t           = 0.0
    snap_count  = 0

    print(f"\n  Starting assembler loop...")
    print(f"  Sample duration   : {sample_dur}s")
    print(f"  Sampling interval : {interval}s  (end to start)")
    print(f"  Total run         : {total_duration}s ({total_duration/60:.1f} mins)\n")

    while True:
        t_start = round(t, 6)
        t_end   = round(t + sample_dur, 6)

        # ── End condition ──────────────────────────────────────────────────
        if t_end > total_duration:
            break

        # ── Check for boundary crossing ────────────────────────────────────
        is_transition = crosses_boundary(
            t_start, t_end, load_segments, fault_timeline
        )

        load_start, fault_start = get_state_at_time(
            t_start, load_segments, fault_timeline
        )
        load_end, fault_end = get_state_at_time(
            t_end, load_segments, fault_timeline
        )

        if is_transition:
            # ── Transition snapshot ────────────────────────────────────────
            # fetch from the starting state file
            file_path = get_file_name(
                system, sampling_rate,
                "normal" if fault_start is None else "fault",
                load_start, fault_loc, fault_start, or_pos
            )
            de, fe = fetch_signal(file_path, sampling_rate, sample_dur)

            # build transition label e.g. Normal_2.csv/Normal_3.csv
            label_start = get_label(load_start, fault_start, config)
            label_end   = get_label(load_end,   fault_end,   config)
            label = f"{label_start}/{label_end}"

        else:
            # ── Clean snapshot ─────────────────────────────────────────────
            file_path = get_file_name(
                system, sampling_rate,
                "normal" if fault_start is None else "fault",
                load_start, fault_loc, fault_start, or_pos
            )
            de, fe = fetch_signal(file_path, sampling_rate, sample_dur)
            label  = get_label(load_start, fault_start, config)

        snapshots.append({
            "t_start"   : t_start,
            "t_end"     : t_end,
            "de"        : de,
            "fe"        : fe,
            "label"     : label,
            "transition": is_transition
        })

        snap_count += 1

        # ── Progress print every 100 snapshots ────────────────────────────
        if snap_count % 100 == 0:
            print(f"  {snap_count} snapshots collected "
                  f"| t = {t_start:.1f}s ({t_start/60:.2f} mins) "
                  f"| last label: {label}")

        # ── Advance time — interval is end to start ────────────────────────
        t = round(t_end + interval, 6)

    # ── Summary ────────────────────────────────────────────────────────────
    clean      = sum(1 for s in snapshots if not s["transition"])
    transition = sum(1 for s in snapshots if s["transition"])

    print(f"\n  Assembler complete.")
    print(f"  Total snapshots   : {len(snapshots)}")
    print(f"  Clean snapshots   : {clean}")
    print(f"  Transition snaps  : {transition}")

    return snapshots


if __name__ == "__main__":

    test_config = {
        "system"           : "DE",
        "sampling_rate"    : 12000,
        "fault_location"   : "IR",
        "or_position"      : None,
        "fault_size_start" : 0.014,
        "load_mode"        : "combination",
        "loads"            : [2, 3],
        "load_durations"   : {2: 3.0, 3: 2.0},
        "run_duration_secs": 120.0,   # 2 mins for quick test
        "sample_duration"  : 0.2,
        "sampling_interval": 1.0,
        "distribution"     : "weibull",
        "dist_params"      : {"beta": 2.0, "eta": 0.4},
    }

    # ── Build timelines ────────────────────────────────────────────────────
    load_segments  = build_load_timeline(test_config)
    fault_timeline = generate_fault_timeline(test_config)

    print(f"\n  Fault timeline:")
    for t, size in fault_timeline:
        print(f"    t={t}s → {size}\"")

    # ── Run assembler ──────────────────────────────────────────────────────
    snapshots = run_assembler(test_config, load_segments, fault_timeline)

    # ── Print first 10 and last 5 snapshots ───────────────────────────────
    print(f"\n  {'t_start':<10} {'t_end':<10} {'transition':<12} {'label'}")
    print(f"  {'-'*70}")
    for s in snapshots[:10]:
        print(f"  {s['t_start']:<10} {s['t_end']:<10} "
              f"{'YES' if s['transition'] else 'no':<12} {s['label']}")
    print(f"  ...")
    for s in snapshots[-5:]:
        print(f"  {s['t_start']:<10} {s['t_end']:<10} "
              f"{'YES' if s['transition'] else 'no':<12} {s['label']}")