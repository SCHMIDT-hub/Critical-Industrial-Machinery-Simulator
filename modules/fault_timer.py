import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from config import FAULT_SIZES


def _draw_sample(distribution, params, total_duration):
    """
    Draws one time value from the chosen distribution.
    Scaled to total_duration so result is in seconds.
    Clamped to 90% of total duration so fault never
    occurs right at the end.
    """
    if distribution == "weibull":
        beta   = params["beta"]
        eta    = params["eta"]
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

    Starts directly at the user-specified fault size — never goes
    below it. Escalates sequentially upward from there.

    Returns a list of (time_seconds, fault_size) tuples in order.
    e.g. if start = 0.014:
         [(480.2, 0.014), (890.3, 0.021), (1050.1, 0.028)]

    - First draw  : when fault first appears at starting severity
    - Each next draw : additional time from current point
                       until next escalation
    Each draw is independent.
    """

    system         = config["system"]
    fault_location = config["fault_location"]
    total_duration = config["run_duration_secs"]
    start_size     = config["fault_size_start"]
    distribution   = config["distribution"]
    params         = config["dist_params"]

    # ── Get only sizes from starting size onwards ──────────────────────────
    # e.g. if start = 0.014 and available = [0.007, 0.014, 0.021, 0.028]
    # active_sizes = [0.014, 0.021, 0.028]
    all_sizes    = FAULT_SIZES[system][fault_location]

    if start_size not in all_sizes:
        raise ValueError(f"Starting fault size {start_size} not available "
                         f"for {system} - {fault_location}. "
                         f"Available: {all_sizes}")

    start_index  = all_sizes.index(start_size)
    active_sizes = all_sizes[start_index:]   # from start size onwards only

    timeline     = []
    current_time = 0.0

    for size in active_sizes:
        time_offset   = _draw_sample(distribution, params, total_duration)
        current_time += time_offset

        if current_time >= total_duration:
            break

        timeline.append((round(current_time, 2), size))

    return timeline


if __name__ == "__main__":

    test_config = {
        "system"           : "DE",
        "fault_location"   : "IR",
        "fault_size_start" : 0.014,
        "run_duration_secs": 1200.0,
        "distribution"     : "weibull",
        "dist_params"      : {"beta": 2.5, "eta": 0.4},
    }

    timeline = generate_fault_timeline(test_config)

    print(f"\n  System         : {test_config['system']}")
    print(f"  Fault location : {test_config['fault_location']}")
    print(f"  Starting size  : {test_config['fault_size_start']}\"")
    print(f"  Distribution   : {test_config['distribution']}")
    print(f"  Run duration   : {test_config['run_duration_secs']}s "
          f"({test_config['run_duration_secs']/60:.1f} mins)")

    print(f"\n  {'Time (s)':<15} {'Time (min)':<15} {'Fault Size'}")
    print(f"  {'-'*45}")
    for t, size in timeline:
        print(f"  {t:<15} {t/60:<15.2f} {size}\"")

    if timeline:
        print(f"\n  Healthy from 0s to {timeline[0][0]}s "
              f"({timeline[0][0]/60:.2f} mins)")
    print(f"  Total escalation steps : {len(timeline)}")