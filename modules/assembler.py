import numpy as np
import random
from config import COMPONENTS

def run_assembler(config, load_segments, fault_timeline):
    """
    Continuous Timeline Assembler with Exact Proportional Multi-State Tracking.
    Tracks all overlapping segments within a window to allow precise row-slicing.
    """
    sampling_rate = config["sampling_rate"]
    sample_duration = config["sample_duration"]      
    sampling_interval = config["sampling_interval"]   
    
    total_duration = load_segments[-1]["end"]

    # ── STAGE 1: SET UP STATIC REFERENCE POOLS ───────────────────────────────
    pool_overlap = 0.95
    pool_step_seconds = sample_duration * (1.0 - pool_overlap)
    raw_reference_duration = float(COMPONENTS[config["machine_type"]]["source_data_duration"])
    
    pool_start_times = np.arange(0, raw_reference_duration - sample_duration, pool_step_seconds)
    total_pool_size = len(pool_start_times)

    # ── STAGE 2: CONTINUOUS GLOBAL TIMELINE SAMPLING LOOP ───────────────────
    final_snapshots = []
    global_clock = 0.0

    print("\n  [Assembler] Running Proportional Multi-State Timeline Sampler...")

    while global_clock + sample_duration <= total_duration:
        w_start = round(global_clock, 4)
        w_end = round(w_start + sample_duration, 4)

        # Find all segments that overlap with this window
        overlapping_segs = []
        for seg in load_segments:
            if not (seg["end"] <= w_start or seg["start"] >= w_end):
                overlapping_segs.append(seg)

        if not overlapping_segs:
            # Fallback to catch borderline rounding frames
            global_clock += (sample_duration + sampling_interval)
            continue

        # Determine fault state
        active_fault_size = 0.0
        if fault_timeline:
            for t_fault, size in fault_timeline:
                if t_fault <= w_start:
                    active_fault_size = size

        state_classification = "PURE" if len(overlapping_segs) == 1 else "MIXTURE"
        
        # Build state name (e.g., "1200" or "1200->1800")
        rpm_strings = [str(int(s["rpm"])) for s in overlapping_segs]
        rpm_state_profile = "->".join(rpm_strings)

        # ── DYNAMIC SUB-SEGMENT POOL ASSIGNMENT ──────────────────────────────
        state_pool_manifest = []
        for seg in overlapping_segs:
            idx = random.randint(0, total_pool_size - 1)
            offset = pool_start_times[idx]
            
            # FIXED: Bound the segment limits to the window frame to prevent duration inversion bugs!
            manifest_start = max(w_start, seg["start"])
            manifest_end = min(w_end, seg["end"])
            
            if manifest_end > manifest_start:
                state_pool_manifest.append({
                    "rpm": seg["rpm"],
                    "seg_start": manifest_start,
                    "seg_end": manifest_end,
                    "pool_index": idx,
                    "pool_offset": round(offset, 4)
                })

        if state_pool_manifest:
            final_snapshots.append({
                "timestamp": w_start,
                "end_timestamp": w_end,
                "rpm_state": rpm_state_profile,
                "state_classification": state_classification,
                "fault_severity": active_fault_size,
                "manifest": state_pool_manifest
            })

        # Dead gap stride increment rules
        global_clock += (sample_duration + sampling_interval)

    print(f"  [Assembly Complete]: Compiled {len(final_snapshots)} track snapshots.")
    return final_snapshots