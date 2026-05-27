import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import AVAILABLE_LOADS, FAULT_LOCATIONS, FAULT_SIZES, OR_POSITIONS, SAMPLING_RATES, DISTRIBUTIONS


def get_user_input():
    print("\n" + "="*50)
    print("       CWRU BEARING FAULT SIMULATOR")
    print("="*50)
    config = {}
    # ── 1. Physical System ─────────────────────────────────────────────────
    while True:
        system = input("\nPhysical system (DE / FE): ").strip().upper()
        if system in ["DE", "FE"]:
            config["system"] = system
            break
        print("  Invalid. Enter DE or FE.")

    # ── 2. Sampling Rate ───────────────────────────────────────────────────
    available_rates = SAMPLING_RATES[config["system"]]
    if len(available_rates) == 1:
        config["sampling_rate"] = available_rates[0]
        print(f"  Sampling rate locked to {available_rates[0]} Hz (FE only supports 12k)")
    else:
        while True:
            rate = input(f"\nSampling rate {available_rates} Hz: ").strip()
            try:
                rate = int(rate)
                if rate in available_rates:
                    config["sampling_rate"] = rate
                    break
                print(f"  Invalid. Choose from {available_rates}.")
            except ValueError:
                print("  Enter a number.")

    # ── 3. Fault Location ──────────────────────────────────────────────────
    while True:
        fault = input(f"\nFault location (IR / B / OR): ").strip().upper()
        if fault in FAULT_LOCATIONS:
            config["fault_location"] = fault
            break
        print(f"  Invalid. Choose from {FAULT_LOCATIONS}.")

    # ── 4. OR Position (only if OR selected) ──────────────────────────────
    if config["fault_location"] == "OR":
        while True:
            pos = input(f"\nOR position (6 / 3 / 12) — clock position: ").strip()
            try:
                pos = int(pos)
                if pos in OR_POSITIONS:
                    config["or_position"] = pos
                    break
                print(f"  Invalid. Choose from {OR_POSITIONS}.")
            except ValueError:
                print("  Enter a number.")
    else:
        config["or_position"] = None

    # ── 5. Starting Fault Severity ─────────────────────────────────────────
    valid_sizes = FAULT_SIZES[config["system"]][config["fault_location"]]
    while True:
        print(f"\n  Available fault sizes for "
              f"{config['system']} - {config['fault_location']}: {valid_sizes}")
        size = input("  Starting fault severity (e.g. 0.007): ").strip()
        try:
            size = float(size)
            if size in valid_sizes:
                config["fault_size_start"] = size
                break
            print(f"  Invalid. Choose from {valid_sizes}.")
        except ValueError:
            print("  Enter a number.")

    # ── 6. Load Selection ──────────────────────────────────────────────────
    print(f"\nLoad options:")
    print(f"  A — Fix a single load (e.g. always 1 HP)")
    print(f"  B — Choose multiple loads (rectangular wave)")
    while True:
        load_mode = input("  Choose A or B: ").strip().upper()
        if load_mode in ["A", "B"]:
            break
        print("  Enter A or B.")

    if load_mode == "A":
        while True:
            load = input(f"\n  Enter load {AVAILABLE_LOADS} HP: ").strip()
            try:
                load = int(load)
                if load in AVAILABLE_LOADS:
                    config["load_mode"]      = "fixed"
                    config["loads"]          = [load]
                    config["load_durations"] = None
                    break
                print(f"  Invalid. Choose from {AVAILABLE_LOADS}.")
            except ValueError:
                print("  Enter a number.")

    else:
        while True:
            n = input(f"\n  How many loads to combine (2 / 3 / 4): ").strip()
            try:
                n = int(n)
                if 2 <= n <= 4:
                    break
                print("  Enter a number between 2 and 4.")
            except ValueError:
                print("  Enter a number.")

        print(f"\n  Enter {n} load values from {AVAILABLE_LOADS}, one per line:")
        loads = []
        while len(loads) < n:
            val = input(f"    Load {len(loads)+1}: ").strip()
            try:
                val = int(val)
                if val in AVAILABLE_LOADS and val not in loads:
                    loads.append(val)
                else:
                    print(f"    Invalid or duplicate. Choose from {AVAILABLE_LOADS}.")
            except ValueError:
                print("    Enter a number.")

        print(f"\n  Enter duration (in seconds) for each load:")
        durations = {}
        for load in loads:
            while True:
                dur = input(f"    Duration for {load} HP (seconds): ").strip()
                try:
                    dur = float(dur)
                    if dur > 0:
                        durations[load] = dur
                        break
                    print("    Must be greater than 0.")
                except ValueError:
                    print("    Enter a number.")

        config["load_mode"]      = "combination"
        config["loads"]          = loads
        config["load_durations"] = durations

    # ── 7. Total Run Duration ──────────────────────────────────────────────
    while True:
        duration = input("\nTotal run duration (minutes): ").strip()
        try:
            duration = float(duration)
            if duration > 0:
                config["run_duration_mins"] = duration
                config["run_duration_secs"] = duration * 60
                break
            print("  Must be greater than 0.")
        except ValueError:
            print("  Enter a number.")

    # ── 8. Sample Duration ─────────────────────────────────────────────────
    while True:
        sample_dur = input("\nSample duration (seconds, e.g. 0.5): ").strip()
        try:
            sample_dur = float(sample_dur)
            if sample_dur > 0:
                config["sample_duration"] = sample_dur
                break
            print("  Must be greater than 0.")
        except ValueError:
            print("  Enter a number.")

    # ── 9. Sampling Interval ───────────────────────────────────────────────
    while True:
        interval = input("\nSampling interval — gap between end of one sample\n"
                         "and start of next (seconds, e.g. 1.0): ").strip()
        try:
            interval = float(interval)
            if interval > 0:
                config["sampling_interval"] = interval
                break
            print("  Must be greater than 0.")
        except ValueError:
            print("  Enter a number.")

    # ── 10. Distribution Choice ────────────────────────────────────────────
    print(f"\nDistribution for fault onset and escalation timing:")
    print(f"  Available: {DISTRIBUTIONS}")
    while True:
        dist = input("  Choose distribution (weibull / normal): ").strip().lower()
        if dist in DISTRIBUTIONS:
            config["distribution"] = dist
            break
        print(f"  Invalid. Choose from {DISTRIBUTIONS}.")

    # ── 11. Distribution Parameters ───────────────────────────────────────
    if config["distribution"] == "weibull":
        print("\n  Weibull parameters:")
        while True:
            try:
                beta = float(input("    Shape parameter β (e.g. 2.5): ").strip())
                if beta > 0:
                    config["dist_params"] = {"beta": beta}
                    break
                print("    Must be greater than 0.")
            except ValueError:
                print("    Enter a number.")
        while True:
            try:
                eta = float(input("    Scale parameter η — as fraction of run duration "
                                  "(e.g. 0.6 means fault tends to occur at 60%): ").strip())
                if 0 < eta <= 1:
                    config["dist_params"]["eta"] = eta
                    break
                print("    Must be between 0 and 1.")
            except ValueError:
                print("    Enter a number.")

    else:  # normal
        print("\n  Normal distribution parameters:")
        print("  (Both are as fraction of total run duration, e.g. 0.5 = 50% of run time)")
        while True:
            try:
                mu = float(input("    Mean μ (e.g. 0.5): ").strip())
                if 0 < mu <= 1:
                    config["dist_params"] = {"mu": mu}
                    break
                print("    Must be between 0 and 1.")
            except ValueError:
                print("    Enter a number.")
        while True:
            try:
                sigma = float(input("    Standard deviation σ (e.g. 0.1): ").strip())
                if sigma > 0:
                    config["dist_params"]["sigma"] = sigma
                    break
                print("    Must be greater than 0.")
            except ValueError:
                print("    Enter a number.")

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "="*50)
    print("  CONFIGURATION SUMMARY")
    print("="*50)
    for key, value in config.items():
        print(f"  {key:<25} {value}")
    print("="*50)

    confirm = input("\nProceed with this config? (yes / no): ").strip().lower()
    if confirm != "yes":
        print("  Restarting...\n")
        return get_user_input()

    return config


if __name__ == "__main__":
    config = get_user_input()