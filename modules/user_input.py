import os
import sys
import subprocess
import time
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def open_file_safely(file_path):
    """Utility wrapper to cross-platform open documents automatically."""
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", file_path], check=True)
        else:
            subprocess.run(["xdg-open", file_path], check=True)
    except Exception as e:
        print(f"  [Warning] Could not open file automatically: {e}")
        print(f"  Please look manually at: {file_path}")


def get_user_input():
    """
    Orchestrates the logical configuration pipeline from core gearbox hardware definitions,
    to terminal global runtime constraints, to raw machine log file collection.
    """
    print("\n==================================================")
    print("      TELEMETRY-DRIVEN POWERTRAIN FAULT SIMULATOR")
    print("==================================================")
    
    # ── TIER 1: CHOOSE ASSET CLASS (LOCKED TO GEARBOX) ───────────────────────
    print("\nSelect Main Asset Class:")
    print("  1 ── Gearbox Assemblies [ACTIVE]")
    
    while True:
        class_choice = input("\nEnter Asset Class Serial Number (or press ENTER for default): ").strip()
        if class_choice in ["1", ""]:
            print("  --> Machinery Class Initialized: GEARBOX TRANSMISSION ARCHITECTURE")
            break
        print("  Invalid selection. Currently, only the Gearbox framework is active. Please press 1.")

    # ── TIER 2: CHOOSE SPECIFIC SUB-SYSTEM COMPONENTS ────────────────────────
    print("\nSelect Gearbox Asset Sub-system Component:")
    print("  1 ── Parallel Gearbox Assembly [ACTIVE]")
    
    while True:
        sub_choice = input("\nEnter Sub-system Option (or press ENTER for default): ").strip()
        if sub_choice in ["1", ""]:
            print("  --> Drivetrain Rig Initialized: PARALLEL SHAFT CONFIGURATION")
            break
        print("  Invalid selection. Currently, only the Parallel Shaft rig is active. Please press 1.")

    # Route dynamically to the Templates subfolder
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file_path = os.path.join(base_dir, "Templates", "config_gearbox.xlsx")
    
    config = {
        "machine_type": "gearbox",
        "system": "parallel",  # Standardized to lowercase to match config.py lookup structures
        "config_file_path": config_file_path
    }

    # ── STEP 1: CORE HARDWARE PARAMETERS EXCEL SHEET ──────────────────────────
    if os.path.exists(config_file_path):
        print(f"\n[Action Required] Opening hardware asset config template: {os.path.basename(config_file_path)}")
        print("--> Set your Parameters in Column B, then SAVE and CLOSE the file...")
        open_file_safely(config_file_path)
    else:
        raise FileNotFoundError(f"[System Error]: Configuration file not found at expected path: {config_file_path}")

    input("\nPress [ENTER] here in the terminal *ONLY AFTER* you have Saved and Closed that Excel sheet... ")
    time.sleep(1.0)

    print("  Parsing hardware configuration specifications...")
    try:
        df_cfg = pd.read_excel(config_file_path, sheet_name=0)
        
        # Strip string columns to avoid whitespace matching issues
        df_cfg.iloc[:, 0] = df_cfg.iloc[:, 0].astype(str).str.strip()
        
        # Create the raw dictionary lookup map
        cfg_dict = dict(zip(df_cfg.iloc[:, 0], df_cfg.iloc[:, 1]))
        
        # ── EXPLICIT HARDWARE PARAMETERS SAFEGUARD ───────────────────────────
        required_keys = [
            "Sampling Rate", 
            "Fault Type", 
            "Fault Size", 
            "Sampling Window (s)", 
            "Sampling Interval (s)"
        ]
        
        missing_keys = []
        for key in required_keys:
            # Check if the key is completely missing, or if its value is null/NaN/empty string
            if key not in cfg_dict or pd.isna(cfg_dict[key]) or str(cfg_dict[key]).strip() == "":
                missing_keys.append(key)
                
        if missing_keys:
            print("\n==================================================")
            print("❌ [CRITICAL CONFIGURATION ERROR] UNFILLED PARAMETERS")
            print("==================================================")
            print("The following mandatory parameters are missing or empty in Column B:")
            for m_key in missing_keys:
                print(f"  --> {m_key}")
            print("\n[Action Required]: Please reopen your Excel template, fill in these values,")
            print("SAVE and CLOSE the file, and restart the simulator.")
            print("==================================================\n")
            sys.exit(1)
            
    except Exception as e:
        raise RuntimeError(f"[Config Parse Error]: Failed to read parameters from Excel. Details: {e}")

    # ── STEP 2: GLOBAL SIMULATION RULES (TERMINAL INTERACTIVITY) ─────────────
    print("\n--------------------------------------------------")
    print("        SET GLOBAL EXPERIMENT RUN RULES")
    print("--------------------------------------------------")
    
    while True:
        try:
            run_mins = input("Enter Total Simulation Run Duration (in minutes, e.g., 5 or 10): ").strip()
            run_duration_mins = float(run_mins)
            if run_duration_mins > 0:
                break
            print("  Duration must be greater than 0.")
        except ValueError:
            print("  Please enter a valid numeric value.")

    # ── NUMERIC SELECTION FOR DEGRADATION MODELS ──────────────────────
    print("\nSelect Failure Degradation Distribution Model:")
    print("  1 ── Weibull Distribution")
    print("  2 ── Normal (Gaussian) Distribution")

    while True:
        dist_input = input("\nEnter Distribution Serial Number (1-2): ").strip()
        if dist_input == "1":
            dist_choice = "weibull"
            break
        elif dist_input == "2":
            dist_choice = "normal"
            break
        print("  Invalid selection. Please enter 1 for Weibull or 2 for Normal.")

    # ── DYNAMICALLY GENERATE INTERACTIVE PARAMETER INPUTS ─────────────────────
    dist_params = {}
    print(f"\n   Configure parameters for {dist_choice.upper()} distribution:")
    
    if dist_choice == "weibull":
        while True:
            try:
                beta_in = input("    Enter Beta (Shape Parameter, e.g., 2.0): ").strip()
                dist_params["beta"] = float(beta_in)
                if dist_params["beta"] > 0:
                    break
                print("      Shape parameter Beta must be greater than 0.")
            except ValueError:
                print("      Please enter a valid numeric value.")
                
        while True:
            try:
                eta_in = input("    Enter Eta (Scale Parameter, fraction of run duration, e.g., 0.5): ").strip()
                dist_params["eta"] = float(eta_in)
                if 0 < dist_params["eta"] <= 1.0:
                    break
                print("      Scale parameter Eta should be between 0 and 1.0 (relative fraction of run).")
            except ValueError:
                print("      Please enter a valid numeric value.")
                
    else:  # ── NORMAL DISTRIBUTION LOOP PARAMETERS ───────────────────────────
        while True:
            try:
                mu_in = input("    Enter Mu (Mean Onset, fraction of run duration, e.g., 0.4): ").strip()
                dist_params["mu"] = float(mu_in)
                if 0 < dist_params["mu"] < 1.0:
                    break
                print("      Mean onset Mu should be between 0 and 1.0 (relative location in timeline).")
            except ValueError:
                print("      Please enter a valid numeric value.")
                
        while True:
            try:
                sigma_in = input("    Enter Sigma (Standard Deviation, e.g., 0.15): ").strip()
                dist_params["sigma"] = float(sigma_in)
                if dist_params["sigma"] > 0:
                    break
                print("      Standard Deviation Sigma must be greater than 0.")
            except ValueError:
                print("      Please enter a valid numeric value.")

    # ── STEP 3: DYNAMICALLY ASK FOR RAW DATA MACHINE LOG FILE ──────────────────
    print("\n--------------------------------------------------")
    print("        CAPTURE RAW MACHINE TELEMETRY LOG")
    print("--------------------------------------------------")
    while True:
        log_input = input("Enter path to raw machine log file (CSV or Excel format): ").strip()
        log_input = log_input.strip("'\"")
        
        if os.path.exists(log_input):
            machine_log_path = log_input
            break
        print(f"  [Error] File not found at path: {log_input}. Please try again.")

    # Populate final config dictionary values
    config["sampling_rate"] = int(cfg_dict.get("Sampling Rate"))
    config["fault_location"] = str(cfg_dict.get("Fault Type")).strip().lower()
    config["fault_size_start"] = str(cfg_dict.get("Fault Size")).strip()
    config["sample_duration"] = float(cfg_dict.get("Sampling Window (s)"))
    config["sampling_interval"] = float(cfg_dict.get("Sampling Interval (s)"))
    
    config["machine_log_path"] = machine_log_path
    config["run_duration_mins"] = run_duration_mins
    config["run_duration_secs"] = round(run_duration_mins * 60.0, 4)
    config["distribution"] = dist_choice
    config["dist_params"] = dist_params
    config["or_position"] = None

    return config