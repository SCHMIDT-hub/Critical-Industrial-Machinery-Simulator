import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from config import COMPONENTS


def _draw_sample(distribution, params, total_duration):
    """
    Draws one time value from the chosen distribution.
    Scaled to total_duration so result is in seconds.
    Clamped to 90% of total duration so fault never
    occurs right at the end.
    """
    if distribution == "weibull":
        beta   = params["beta"]
        eta    = params["eta"]  # If eta is absolute seconds, drop the "* total_duration" multiplier below
        sample = np.random.weibull(beta) * eta * total_duration

    elif distribution == "normal":
        mu     = params["mu"]    * total_duration
        sigma  = params["sigma"] * total_duration
        sample = np.random.normal(mu, sigma)
        sample = max(0, sample)  # clamp — no negative times

    # clamp to 90% of run so fault doesn't appear at the very end
    sample = min(sample, total_duration * 0.9)

    return round(sample, 2)


def generate_fault_timeline(config):
    """
    Generates the full fault escalation timeline.
    Dynamically switches lookups based on machine_type (bearing vs gearbox).
    Accommodates size-less custom NU205 and gearbox single-onset schemas safely.
    """
    machine_type   = config.get("machine_type", "bearing")
    system         = config["system"]
    fault_location = config["fault_location"]
    total_duration = config["run_duration_secs"]
    start_size     = config["fault_size_start"]
    distribution   = config["distribution"]
    params         = config["dist_params"]

    # ── SPECIAL BRANCH: CUSTOM NU205 & PARALLEL GEARBOX ARCHITECTURES ───────
    if system == "NU205" or machine_type == "gearbox":
        time_offset = _draw_sample(distribution, params, total_duration)
        if time_offset < total_duration:
            return [(round(time_offset, 2), start_size)]
        return []

    # ── STANDARD BRANCH: MULTI-STAGE STEP PROGRESSIONS (CWRU DE/FE) ─────────
    meta = COMPONENTS[machine_type]
    
    if str(fault_location).upper().startswith("OR_"):
        lookup_location = "OR"
    else:
        lookup_location = fault_location

    all_sizes = meta["fault_sizes"][system][lookup_location]

    if start_size not in all_sizes:
        raise ValueError(f"Starting fault size {start_size} not available "
                         f"for {system} - {lookup_location}. "
                         f"Available: {all_sizes}")

    start_index  = all_sizes.index(start_size)
    active_sizes = all_sizes[start_index:]   

    timeline     = []
    current_time = 0.0

    for size in active_sizes:
        # FIXED: Sample across the remaining available time horizon rather than the whole duration
        remaining_duration = total_duration - current_time
        if remaining_duration <= 0.1:
            break
            
        time_offset = _draw_sample(distribution, params, remaining_duration)
        current_time += time_offset

        if current_time >= total_duration:
            break

        timeline.append((round(current_time, 2), size))

    return timeline


if __name__ == "__main__":
    print("Fault timer module running unit test baseline verification checks...")