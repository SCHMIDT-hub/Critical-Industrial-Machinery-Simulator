import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from config import OUTPUT_PATH
from modules.assembler     import run_assembler
from modules.load_timeline import build_load_timeline
from modules.fault_timer   import generate_fault_timeline

def export_snapshots(snapshots, config, fault_timeline):
    """
    Exports all snapshots to individual CSV files and
    writes one ground_truth.csv covering the full run.

    Signal CSVs — one per snapshot:
        filename : {t_start}_{t_end}.csv
        columns  : sample_index | DE_time | FE_time

    Ground truth CSV — one file:
        filename : ground_truth.csv
        columns  : t_start | t_end | label | transition | health_state | fault_size
    """

    # ── Create output folder for this run ──────────────────────────────────
    run_folder = _make_run_folder(config)
    print(f"\n  Output folder: {run_folder}")

    # ── Export individual signal CSVs ──────────────────────────────────────
    print(f"  Writing {len(snapshots)} signal CSVs...")

    for snap in snapshots:
        t_start  = snap["t_start"]
        t_end    = snap["t_end"]
        de       = snap["de"]
        fe       = snap["fe"]

        filename = f"{t_start}_{t_end}.csv"
        filepath = os.path.join(run_folder, filename)

        df = pd.DataFrame({
            "sample_index": np.arange(len(de)),
            "DE_time"     : de,
            "FE_time"     : fe
        })
        df.to_csv(filepath, index=False)

    print(f"  Signal CSVs written.")

    # ── Export ground truth CSV ────────────────────────────────────────────
    gt_rows = []
    for snap in snapshots:
        t_start      = snap["t_start"]
        fault_size   = _get_fault_size_at(t_start, fault_timeline)
        health_state = "faulty" if fault_size is not None else "healthy"

        gt_rows.append({
            "t_start"     : snap["t_start"],
            "t_end"       : snap["t_end"],
            "label"       : snap["label"],
            "transition"  : snap["transition"],
            "health_state": health_state,
            "fault_size"  : fault_size if fault_size is not None else "—"
        })

    gt_df    = pd.DataFrame(gt_rows)
    gt_path  = os.path.join(run_folder, "ground_truth.csv")
    gt_df.to_csv(gt_path, index=False)

    print(f"  Ground truth CSV written → ground_truth.csv")

    # ── Summary ────────────────────────────────────────────────────────────
    _print_summary(snapshots, gt_df, fault_timeline, run_folder)

    return run_folder


def _get_fault_size_at(t, fault_timeline):
    """Returns the active fault size at time t, or None if healthy."""
    active = None
    for (fault_time, fault_size) in fault_timeline:
        if t >= fault_time:
            active = fault_size
        else:
            break
    return active


def _make_run_folder(config):
    """
    Creates a uniquely named output folder for this run.
    Name encodes key config parameters so it's self-describing.
    e.g. outputs/DE_12k_IR_0.014_2HP_3HP_20min/
    """
    loads_str  = "_".join(str(l) + "HP" for l in config["loads"])
    dur_str    = f"{int(config['run_duration_mins'])}min"
    fault_str  = config["fault_location"]
    size_str   = str(config["fault_size_start"])

    if config["fault_location"] == "OR":
        fault_str += f"_pos{config['or_position']}"

    folder_name = (
        f"{config['system']}_"
        f"{config['sampling_rate']//1000}k_"
        f"{fault_str}_"
        f"{size_str}_"
        f"{loads_str}_"
        f"{dur_str}"
    )

    full_path = os.path.join(OUTPUT_PATH, folder_name)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def _print_summary(snapshots, gt_df, fault_timeline, run_folder):
    """Prints a clean summary after export."""

    total      = len(snapshots)
    clean      = sum(1 for s in snapshots if not s["transition"])
    transition = sum(1 for s in snapshots if s["transition"])
    healthy    = len(gt_df[gt_df["health_state"] == "healthy"])
    faulty     = len(gt_df[gt_df["health_state"] == "faulty"])

    print(f"\n  {'='*50}")
    print(f"  EXPORT COMPLETE")
    print(f"  {'='*50}")
    print(f"  Total snapshots   : {total}")
    print(f"  Clean snapshots   : {clean}")
    print(f"  Transition snaps  : {transition}")
    print(f"  Healthy snapshots : {healthy}")
    print(f"  Faulty snapshots  : {faulty}")
    if fault_timeline:
        print(f"\n  Fault onset       : t={fault_timeline[0][0]}s "
              f"({fault_timeline[0][0]/60:.2f} mins) "
              f"→ {fault_timeline[0][1]}\"")
        for ft, fs in fault_timeline[1:]:
            print(f"  Escalation        : t={ft}s "
                  f"({ft/60:.2f} mins) → {fs}\"")
    print(f"\n  Output folder     : {run_folder}")
    print(f"  {'='*50}")


if __name__ == "__main__":
    from assembler     import run_assembler
    from load_timeline import build_load_timeline
    from fault_timer   import generate_fault_timeline

    test_config = {
        "system"           : "DE",
        "sampling_rate"    : 12000,
        "fault_location"   : "IR",
        "or_position"      : None,
        "fault_size_start" : 0.014,
        "load_mode"        : "combination",
        "loads"            : [2, 3],
        "load_durations"   : {2: 3.0, 3: 2.0},
        "run_duration_mins": 2.0,
        "run_duration_secs": 120.0,
        "sample_duration"  : 0.2,
        "sampling_interval": 1.0,
        "distribution"     : "weibull",
        "dist_params"      : {"beta": 2.0, "eta": 0.4},
    }

    load_segments  = build_load_timeline(test_config)
    fault_timeline = generate_fault_timeline(test_config)

    print(f"\n  Fault timeline:")
    for t, size in fault_timeline:
        print(f"    t={t}s → {size}\"")

    snapshots = run_assembler(test_config, load_segments, fault_timeline)
    run_folder = export_snapshots(snapshots, test_config, fault_timeline)

    # ── Peek at ground truth ───────────────────────────────────────────────
    import pandas as pd
    gt = pd.read_csv(os.path.join(run_folder, "ground_truth.csv"))
    print(f"\n  Ground truth preview (first 5 rows):")
    print(gt.head().to_string(index=False))
    print(f"\n  Ground truth preview (last 5 rows):")
    print(gt.tail().to_string(index=False))