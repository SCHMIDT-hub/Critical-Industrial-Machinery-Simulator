import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
# MATCHED EXACTLY TO YOUR FILENAMES: file_mapper and signal_engine
from modules.signal_engine import fetch_signal, reset_pointers
from modules.file_mapper   import get_file_name, get_segment_file
from modules.load_timeline import build_load_timeline
from modules.fault_timer   import generate_fault_timeline


def get_state_at_time(t, load_segments, fault_timeline):
    """
    Returns the active load, active rpm, and fault size at time t.
    """
    # ── Active load and RPM speed values ───────────────────────────────────
    active_load = None
    active_rpm = None
    for seg in load_segments:
        if seg["start"] <= t < seg["end"]:
            active_load = seg["load"]
            active_rpm = seg.get("rpm", None)
            break
    if active_load is None:
        active_load = load_segments[-1]["load"]
        active_rpm = load_segments[-1].get("rpm", None)

    # ── Active fault size ──────────────────────────────────────────────────
    active_fault = None
    for (fault_time, fault_size) in fault_timeline:
        if t >= fault_time:
            active_fault = fault_size
        else:
            break

    return active_load, active_rpm, active_fault


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


def get_label(load, rpm, fault_size, experiment):
    """
    Returns the source filename as the label — this is the ground truth
    state description. For transition snapshots returns e.g. 'S1/S2'.
    """
    machine_type  = experiment.get("machine_type", "bearing")
    system        = experiment["system"]
    sampling_rate = experiment["sampling_rate"]
    fault_loc     = experiment["fault_location"]
    or_pos        = experiment.get("or_position", None)

    if fault_size is None:
        return os.path.basename(
            get_file_name(system, sampling_rate, "normal", load, rpm=rpm, machine_type=machine_type)
        )
    else:
        return os.path.basename(
            get_file_name(system, sampling_rate, "fault",
                          load, rpm=rpm, fault_location=fault_loc, fault_size=fault_size, or_position=or_pos, machine_type=machine_type)
        )


def run_assembler(config, load_segments, fault_timeline):
    """
    Main assembler loop. Walks forward in time, takes snapshots,
    fetches signals, records labels. Accommodates dynamic sensor channel tracking.
    """
    reset_pointers()

    machine_type    = config.get("machine_type", "bearing")
    system          = config["system"]
    sampling_rate   = config["sampling_rate"]
    fault_loc       = config["fault_location"]
    or_pos          = config.get("or_position", None)
    sample_dur      = config["sample_duration"]
    interval        = config["sampling_interval"]
    total_duration  = config["run_duration_secs"]

    snapshots   = []
    t           = 0.0
    snap_count  = 0

    print(f"\n  Starting assembler loop...")
    print(f"  Asset Class       : {machine_type.upper()}")
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

        load_start, rpm_start, fault_start = get_state_at_time(
            t_start, load_segments, fault_timeline
        )
        load_end, rpm_end, fault_end = get_state_at_time(
            t_end, load_segments, fault_timeline
        )

        # ── Resolve Active Source File Path ────────────────────────────────
        file_path = get_file_name(
            system=system, sampling_rate=sampling_rate,
            state="normal" if fault_start is None else "fault",
            load=load_start, rpm=rpm_start, fault_location=fault_loc, fault_size=fault_start, or_position=or_pos,
            machine_type=machine_type
        )
        
        # Stream arbitrary channel data dictionary from signal engine
        signals_dict = fetch_signal(file_path, sampling_rate, sample_dur, machine_type=machine_type)

        if is_transition:
            # ── Transition snapshot labeling ────────────────────────────────
            label_start = get_label(load_start, rpm_start, fault_start, config)
            label_end   = get_label(load_end, rpm_end, fault_end, config)
            label = f"{label_start}/{label_end}"
        else:
            # ── Clean snapshot labeling ─────────────────────────────────────
            label = get_label(load_start, rpm_start, fault_start, config)

        # Package data with generalized 'signals' payload mapping
        snapshots.append({
            "t_start"   : t_start,
            "t_end"     : t_end,
            "signals"   : signals_dict,
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
    print("Testing assembler baseline framework generation...")