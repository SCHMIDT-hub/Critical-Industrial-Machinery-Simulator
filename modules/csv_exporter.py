import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OUTPUT_PATH, COMPONENTS
from modules.file_mapper import get_segment_file


def export_snapshots(snapshots, config, fault_timeline):
    """
    Slices and exports snapshot CSV files by calculating exact time-proportional 
    row spans across an arbitrary number of overlapping transient states.
    """
    fault_type = config["fault_location"].strip().lower()  
    severity = config["fault_size_start"]
    sampling_rate_khz = int(config["sampling_rate"] / 1000)
    sampling_rate = config["sampling_rate"]
    sample_duration = config["sample_duration"]
    
    run_name = f"GEARBOX_parallel_{sampling_rate_khz}k_{fault_type.replace(' ', '_')}_{severity}"
    run_dir = os.path.join(OUTPUT_PATH, run_name)
    os.makedirs(run_dir, exist_ok=True)
    
    src_duration = float(COMPONENTS[config["machine_type"]]["source_data_duration"])
    window_points = int(sample_duration * sampling_rate)

    # ── STEP 1: LOG ENHANCED GROUND TRUTH INDEX ─────────────────────────────
    meta_rows = []
    for snap in snapshots:
        meta_rows.append({
            "Snapshot_File": f"{snap['timestamp']:.1f}_{snap['end_timestamp']:.1f}.csv",
            "Simulated_Start_Seconds": snap["timestamp"],
            "RPM_State_Profile": snap["rpm_state"],
            "Composition_Type": snap["state_classification"],
            "Fault_Severity": snap["fault_severity"],
            "Manifest_Summary": str([(m["rpm"], m["pool_offset"]) for m in snap["manifest"]])
        })
        
    df_meta = pd.DataFrame(meta_rows)
    meta_file_path = os.path.join(run_dir, f"{run_name}_ground_truth.csv")
    df_meta.to_csv(meta_file_path, index=False)
    
    cached_file_data = {}
    print(f"\n  [Export Pipeline] Slicing high-fidelity proportional streams...")

    # ── STEP 2: EXECUTE TIME-PROPORTIONAL ROW SLICING ──────────────────────
    for snap in snapshots:
        w_start = snap["timestamp"]
        w_end = snap["end_timestamp"]
        
        sliced_blocks = []
        accumulated_rows = 0

        for i, item in enumerate(snap["manifest"]):
            speed = item["rpm"]
            
            chunk_start = max(w_start, item["seg_start"])
            chunk_end = min(w_end, item["seg_end"])
            chunk_duration = chunk_end - chunk_start
            
            if i == len(snap["manifest"]) - 1:
                allocated_rows = window_points - accumulated_rows
            else:
                allocated_rows = int(round((chunk_duration / sample_duration) * window_points))
            
            if allocated_rows <= 0:
                continue
                
            accumulated_rows += allocated_rows

            mock_segment = {"start": chunk_start, "load": 0, "rpm": speed}
            
            try:
                # FIXED: Build a verified config map structure matching file_mapper expectations
                resolved_config_map = {
                    "machine_type": config.get("machine_type", "gearbox"),
                    "system": config.get("system", "parallel"),
                    "sampling_rate": config.get("sampling_rate", 16000),
                    "fault_location": config.get("fault_location", "normal"),
                    "or_position": config.get("or_position", None)
                }
                
                target_file_path = get_segment_file(mock_segment, resolved_config_map, fault_timeline)
                
                if target_file_path not in cached_file_data:
                    if "normal_0" in os.path.basename(target_file_path) or speed == 0:
                        cached_file_data[target_file_path] = None
                    else:
                        if not os.path.exists(target_file_path):
                            print(f"⚠️  [File Missing]: Could not open path: {target_file_path}. Filling window with zeros.")
                            cached_file_data[target_file_path] = None
                        else:
                            if target_file_path.lower().endswith('.xlsx'):
                                raw_df = pd.read_excel(target_file_path)
                            else:
                                raw_df = pd.read_csv(target_file_path)
                            
                            # FIXED: Normalize all header names to lowercase right after reading 
                            # to ensure smooth column mapping during matrix concat steps
                            raw_df.columns = [str(c).strip().lower() for c in raw_df.columns]
                            cached_file_data[target_file_path] = raw_df
                
                df_src = cached_file_data[target_file_path]
            except Exception as e:
                print(f"⚠️  [File Map Router Exception]: {e}")
                df_src = None
            
            total_src_rows = len(df_src) if df_src is not None else 100000
            start_idx = int((item["pool_offset"] / src_duration) * total_src_rows)
            end_idx = min(start_idx + allocated_rows, total_src_rows)
            
            if df_src is not None:
                time_keywords = ["time", "stamp", "date", "parsed_time", "elapsed_seconds", "timestamp"]
                signal_cols = [c for c in df_src.columns if c not in time_keywords and "load" not in c and "rpm" not in c]
                slice_chunk = df_src.iloc[start_idx:end_idx][signal_cols].reset_index(drop=True)
                
                if len(slice_chunk) < allocated_rows:
                    shortage = allocated_rows - len(slice_chunk)
                    padding = pd.DataFrame(0.0, index=range(shortage), columns=slice_chunk.columns)
                    slice_chunk = pd.concat([slice_chunk, padding], ignore_index=True)
            else:
                target_channels = COMPONENTS[config["machine_type"]]["sensor_channels"]
                slice_chunk = pd.DataFrame(0.0, index=range(allocated_rows), columns=target_channels)

            sliced_blocks.append(slice_chunk)

        # Uniform structure concatenation
        df_final_slice = pd.concat(sliced_blocks, ignore_index=True) if sliced_blocks else pd.DataFrame()
        
        # Enforce consistent uppercase names (CH 1, CH 2, CH 3) across the generated CSV files
        if not df_final_slice.empty:
            df_final_slice.columns = [str(c).upper() for c in df_final_slice.columns]

        filename = f"{w_start:.1f}_{w_end:.1f}.csv"
        df_final_slice.to_csv(os.path.join(run_dir, filename), index=False)

    print(f"  [Export Complete] Run files successfully generated inside: {run_dir}")
    return run_dir