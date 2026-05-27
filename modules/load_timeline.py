import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LOAD_RPM


def build_load_timeline(experiment):
    """
    Builds a time-indexed list of segments showing which load is active
    at every point during the run — the rectangular wave.

    Returns a list of segments:
    [
        {"start": 0.0,  "end": 1.0,  "load": 2, "rpm": 1750},
        {"start": 1.0,  "end": 5.0,  "load": 1, "rpm": 1772},
        {"start": 5.0,  "end": 8.0,  "load": 3, "rpm": 1730},
        {"start": 8.0,  "end": 9.0,  "load": 2, "rpm": 1750},
        ...
    ]
    """

    loads          = experiment["loads"]
    total_duration = experiment["run_duration_secs"]

    # ── Fixed single load ──────────────────────────────────────────────────
    if experiment["load_mode"] == "fixed":
        load = loads[0]
        return [{
            "start": 0.0,
            "end"  : total_duration,
            "load" : load,
            "rpm"  : LOAD_RPM[load]
        }]

    # ── Combination of loads — rectangular wave ────────────────────────────
    load_durations = experiment["load_durations"]

    # one full cycle duration
    cycle_duration = sum(load_durations[l] for l in loads)

    segments = []
    current_time = 0.0

    while current_time < total_duration:
        for load in loads:
            duration = load_durations[load]
            start    = current_time
            end      = min(current_time + duration, total_duration)

            segments.append({
                "start": round(start, 4),
                "end"  : round(end,   4),
                "load" : load,
                "rpm"  : LOAD_RPM[load]
            })

            current_time = end

            if current_time >= total_duration:
                break

    return segments


def print_timeline_summary(segments):
    """Prints a readable summary of the load timeline."""

    print(f"\n  {'Segment':<10} {'Start (s)':<12} {'End (s)':<12} "
          f"{'Duration (s)':<15} {'Load (HP)':<12} {'RPM'}")
    print(f"  {'-'*65}")

    for i, seg in enumerate(segments):
        duration = round(seg["end"] - seg["start"], 4)
        print(f"  {i+1:<10} {seg['start']:<12} {seg['end']:<12} "
              f"{duration:<15} {seg['load']:<12} {seg['rpm']}")

    print(f"\n  Total segments    : {len(segments)}")
    print(f"  Total duration    : {segments[-1]['end']}s "
          f"({segments[-1]['end']/60:.2f} mins)")


if __name__ == "__main__":

    test_experiment = {
        "experiment_id"    : 1,
        "load_mode"        : "combination",
        "loads"            : [2, 1, 3],
        "load_durations"   : {2: 1.0, 1: 4.0, 3: 3.0},
        "run_duration_secs": 1200.0,
    }

    print("\nBuilding load timeline...\n")
    print(f"  Loads          : {test_experiment['loads']}")
    print(f"  Durations      : {test_experiment['load_durations']}")
    print(f"  Total run time : {test_experiment['run_duration_secs']}s "
          f"({test_experiment['run_duration_secs']/60:.1f} mins)")

    segments = build_load_timeline(test_experiment)
    print_timeline_summary(segments)