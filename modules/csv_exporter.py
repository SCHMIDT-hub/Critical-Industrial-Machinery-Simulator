import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from config import OUTPUT_PATH


def export_snapshots(snapshots, config, fault_timeline):
    """
    Exports all snapshots to individual CSV files and
    writes one ground_truth.csv covering the full run.

    Signal CSVs — one per snapshot:
        filename : {t_start}_{t_end}.csv
        columns  : sample_index | [Dynamic Channel Names]

    Ground truth CSV — one file:
        filename : ground_truth.csv
        columns  : t_start | t_end | label | transition | health_state | fault_size
    """
    machine_type = config.get("machine_type", "bearing")

    # ── Create output folder for this run ──────────────────────────────────
    run_folder = _make_run_folder(config)
    print(f"\n  Output folder: {run_folder}")

    # ── Export individual signal CSVs ──────────────────────────────────────
    print(f"  Writing {len(snapshots)} signal CSVs...")

    for snap in snapshots:
        t_start  = snap["t_start"]
        t_end    = snap["t_end"]
        signals  = snap["signals"]  # Dict mapping channel_name -> np.array

        filename = f"{t_start}_{t_end}.csv"
        filepath = os.path.join(run_folder, filename)

        # First channel determines the array payload length
        first_channel = list(signals.keys())[0]
        num_samples = len(signals[first_channel])

        # Construct DataFrame dynamically using active channel track names
        df_payload = {"sample_index": np.arange(num_samples)}
        for channel_name, data_array in signals.items():
            # Format header string nicely (e.g., de_time -> DE_time, x_axis -> X_axis)
            header_title = channel_name.replace("_", " ").title().replace(" ", "_")
            df_payload[header_title] = data_array

        df = pd.DataFrame(df_payload)
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
    _print_summary(snapshots, gt_df, fault_timeline, run_folder, config)

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
    """
    machine_type = config.get("machine_type", "bearing")
    system = config["system"]
    
    # ── ADAPTIVE SUFFIX SELECTION LAYER ─────────────────────────────────────
    if system == "NU205" or machine_type == "gearbox":
        unit_suffix = "RPM"
    else:
        unit_suffix = "HP"
    
    loads_str  = "_".join(str(l) + unit_suffix for l in config["loads"])
    dur_str    = f"{int(config['run_duration_mins'])}min"
    fault_str  = config["fault_location"]
    size_str   = str(config["fault_size_start"])

    if machine_type == "bearing" and config["fault_location"] == "OR" and system != "NU205":
        fault_str += f"_pos{config['or_position']}"

    folder_name = (
        f"{config['machine_type'].upper()}_"
        f"{config['system']}_"
        f"{config['sampling_rate']//1000}k_"
        f"{fault_str.replace(' ', '_')}_"
        f"{size_str}_"
        f"{loads_str}_"
        f"{dur_str}"
    )

    full_path = os.path.join(OUTPUT_PATH, folder_name)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def _print_summary(snapshots, gt_df, fault_timeline, run_folder, config):
    """Prints a clean summary terminal dashboard after exporting."""
    machine_type = config.get("machine_type", "bearing")
    system = config["system"]

    total      = len(snapshots)
    clean      = sum(1 for s in snapshots if not s["transition"])
    transition = sum(1 for s in snapshots if s["transition"])
    healthy    = len(gt_df[gt_df["health_state"] == "healthy"])
    faulty     = len(gt_df[gt_df["health_state"] == "faulty"])

    # Format dimensions appropriately based on backend properties
    if system == "NU205":
        size_suffix = ""  # Drops inch annotations since labels are purely code strings
    else:
        size_suffix = '"' if machine_type == "bearing" else "mm"

    print(f"\n  {'='*50}")
    print(f"  EXPORT COMPLETE ({machine_type.upper()} MODE)")
    print(f"  {'='*50}")
    print(f"  Total snapshots   : {total}")
    print(f"  Clean snapshots   : {clean}")
    print(f"  Transition snaps  : {transition}")
    print(f"  Healthy snapshots : {healthy}")
    print(f"  Faulty snapshots  : {faulty}")
    
    if fault_timeline:
        # Check if the severity target is numeric or a text code block
        onset_val = fault_timeline[0][1]
        display_val = f"{onset_val}{size_suffix}" if isinstance(onset_val, (int, float)) else str(onset_val)
        
        print(f"\n  Fault onset       : t={fault_timeline[0][0]}s "
              f"({fault_timeline[0][0]/60:.2f} mins) "
              f"→ {display_val}")
              
        for ft, fs in fault_timeline[1:]:
            display_esc = f"{fs}{size_suffix}" if isinstance(fs, (int, float)) else str(fs)
            print(f"  Escalation        : t={ft}s "
                  f"({ft/60:.2f} mins) → {display_esc}")
                  
    print(f"\n  Output folder     : {run_folder}")
    print(f"  {'='*50}")


if __name__ == "__main__":
    print("Testing dynamic export framing execution layer structures...")