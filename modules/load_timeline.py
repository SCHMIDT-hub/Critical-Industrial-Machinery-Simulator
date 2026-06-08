import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COMPONENTS


def build_load_timeline(experiment):
    """
    Builds a time-indexed list of segments showing which load/speed state is active
    at every point during the run by parsing the selected Excel profile sheet.
    
    It loops through the sequence steps repeatedly until the total simulation 
    run time limit is reached.
    """
    file_path = experiment["profile_file_path"]
    machine_type = experiment.get("machine_type", "bearing")
    system = experiment.get("system", "DE")
    total_duration = experiment["run_duration_secs"]
    
    # Read profile data from Excel workbook
    df_prof = pd.read_excel(file_path)
    df_prof.columns = [str(c).strip() for c in df_prof.columns]
    
    # Enforce chronological ordering based on sequence keys
    df_prof = df_prof.sort_values(by="Sequence Number")
    
    segments = []
    current_time = 0.0

    # Repeat the spreadsheet profile sequence continuously until total run duration is met
    while current_time < total_duration:
        for _, row in df_prof.iterrows():
            # Create a cleaned row dictionary to strip out accidental hidden spaces
            clean_row = {str(k).strip(): v for k, v in row.items()}
            
            # ── FUZZY COLUMN MATCHING FOR LOAD PARAMETER ─────────────────────
            # Look for any column header that starts with "Load Parameter"
            load_col = None
            for key in clean_row.keys():
                if key.startswith("Load Parameter"):
                    load_col = key
                    break
            
            if load_col is not None:
                raw_load = clean_row[load_col]
            else:
                # Fallback to general names if present
                raw_load = clean_row.get("Load", None)
                
            if raw_load is None:
                raise KeyError(
                    f"\n[Excel Column Error]: Could not find a column starting with 'Load Parameter' in your profile sheet.\n"
                    f"Available headers: {list(clean_row.keys())}"
                )
            # ─────────────────────────────────────────────────────────────────
                
            parsed_load = int(raw_load) if str(raw_load).isdigit() else raw_load
            
            # Extract duration safely
            duration = float(clean_row["State Duration (s)"]) if not pd.isna(clean_row["State Duration (s)"]) else 0.0
            if duration <= 0:
                print(f"\n  [Warning] Detected zero or invalid duration ({duration}s) in operational profile sheet.")
                print("  Defaulting this segment segment to 5.0 seconds to prevent an infinite loop.")
                duration = 5.0
            
            # Determine start/end boundaries for this step segment
            start = current_time
            end = min(current_time + duration, total_duration)
            
            # Prevent infinite loop stagnation if time calculation doesn't advance
            if end <= start:
                current_time = total_duration
                break
            
            # ── Dynamic RPM Mapping Logic ────────────────────────────────────
            if "RPM Speed" in clean_row:
                rpm_value = float(clean_row["RPM Speed"])
            else:
                load_map = COMPONENTS["bearing"]["load_mapping"]
                rpm_value = float(load_map.get(parsed_load, 1797))
            # ─────────────────────────────────────────────────────────────────
            
            segments.append({
                "start": round(start, 4),
                "end": round(end, 4),
                "load": parsed_load,
                "rpm": rpm_value
            })
            
            current_time = end
            if current_time >= total_duration:
                break
                
    # Expose unique load entries back to experiment object for data indexing
    # Extract unique values using dynamic column tracking
    experiment["loads"] = df_prof[load_col].unique().tolist() if load_col else [0]
    
    return segments


def print_timeline_summary(segments, experiment):
    """Prints a readable summary of the generated load/speed timeline."""
    machine_type = experiment.get("machine_type", "bearing")
    system = experiment.get("system", "DE")

    # Match display headings dynamically with the specific equipment type
    if system == "NU205":
        unit_header = "Speed (RPM)"
    elif machine_type == "bearing":
        unit_header = "Load (HP)"
    else:
        unit_header = "Condition"

    print(f"\n  {'Segment':<10} {'Start (s)':<12} {'End (s)':<12} "
          f"{'Duration (s)':<15} {unit_header:<15} {'RPM/State'}")
    print(f"  {'-'*70}")

    for i, seg in enumerate(segments):
        duration = round(seg["end"] - seg["start"], 4)
        print(f"  {i+1:<10} {seg['start']:<12} {seg['end']:<12} "
              f"{duration:<15} {str(seg['load']):<15} {seg['rpm']}")

    print(f"\n  Total segments     : {len(segments)}")
    print(f"  Total duration     : {segments[-1]['end']}s "
          f"({segments[-1]['end']/60:.2f} mins)")


if __name__ == "__main__":
    print("\n==================================================")
    print("RUNNING EXCEL PROFILE PARSER UNIT TESTS")
    print("==================================================")