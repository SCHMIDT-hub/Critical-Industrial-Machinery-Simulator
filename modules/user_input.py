import sys
import os
import subprocess
import time
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ASSET_MENU


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
    Orchestrates the logical configuration pipeline from core hardware definitions,
    to terminal global runtime constraints, to sequential operational profile spreadsheets.
    """
    print("\n==================================================")
    print("      EXCEL-DRIVEN POWERTRAIN FAULT SIMULATOR")
    print("==================================================")
    
    # ── TIER 1: CHOOSE ASSET CLASS ───────────────────────────────────────────
    print("\nSelect Main Asset Class:")
    print("  1 ── Rolling Element Bearings")
    print("  2 ── Gearbox Assemblies")
    
    while True:
        class_choice = input("\nEnter Asset Class Serial Number (1-2): ").strip()
        if class_choice in ["1", "2"]:
            break
        print("  Invalid selection. Please input 1 for Bearing or 2 for Gearbox.")

    # ── TIER 2: CHOOSE SPECIFIC SUB-SYSTEM COMPONENTS ────────────────────────
    if class_choice == "1":
        print("\nSelect Bearing Asset Sub-system Component:")
        print("  1 ── Drive End Bearing (6205-2RS JEM SKF)")
        print("  2 ── Fan End Bearing (6203-2RS JEM SKF)")
        print("  3 ── NU205 Bearing Asset Component")
        
        while True:
            sub_choice = input("\nEnter Sub-system Option (1-3): ").strip()
            if sub_choice in ["1", "2", "3"]:
                menu_key = sub_choice 
                break
            print("  Invalid selection. Please input a number between 1 and 3.")
            
    else:
        print("\nSelect Gearbox Asset Sub-system Component:")
        print("  1 ── Parallel Gearbox Assembly")
        
        while True:
            sub_choice = input("\nEnter Sub-system Option (1): ").strip()
            if sub_choice == "1":
                menu_key = "4"  # Maps back to Parallel Gearbox in ASSET_MENU
                break
            print("  Invalid selection. Please input 1 for Parallel Gearbox.")

    asset_meta = ASSET_MENU[menu_key]
    config_file_path = asset_meta["config_file"]
    profile_file_path = asset_meta["profile_file"]

    # ── STEP 1: CORE HARDWARE PARAMETERS EXCEL SHEET ──────────────────────────
    print(f"\n[Action Required] Opening hardware asset config template: {os.path.basename(config_file_path)}")
    print("--> Set your Sampling Rate, Fault Type, and Size in Column B, then SAVE and CLOSE the file...")
    open_file_safely(config_file_path)

    input("\nPress [ENTER] here in the terminal *ONLY AFTER* you have Saved and Closed that Excel sheet...")
    time.sleep(1.0)

    print("  Parsing hardware configuration specifications...")
    df_cfg = pd.read_excel(config_file_path, sheet_name=0, index_col=0)
    df_cfg.columns = [str(c).strip() for c in df_cfg.columns]
    
    if df_cfg["User Selection Value"].isna().any():
        blank_fields = df_cfg[df_cfg["User Selection Value"].isna()].index.tolist()
        print(f"\n[Excel Configuration Error]: Blank values found in '{os.path.basename(config_file_path)}': {blank_fields}")
        sys.exit(1)

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

    # ── UPDATED NUMERIC SELECTION FOR DEGRADATION MODELS ──────────────────────
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
    print(f"\n  Configure parameters for {dist_choice.upper()} distribution:")
    
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

    # ── STEP 3: OPERATIONAL SPEED/LOAD PROFILE ROWS EXCEL SHEET ────────────────
    print(f"\n[Action Required] Opening operational load profile template: {os.path.basename(profile_file_path)}")
    print("--> Define your sequence blocks (durations & speeds), then SAVE and CLOSE the file...")
    open_file_safely(profile_file_path)

    input("\nPress [ENTER] here in the terminal *ONLY AFTER* you have Saved and Closed the profile sheet...")
    time.sleep(1.0)

    # Pack everything back together for consumption by downstream modules
    config = {
        "machine_type": asset_meta["machine_type"],
        "system": asset_meta["sub_system"],
        "config_file_path": config_file_path,
        "profile_file_path": profile_file_path,
        
        "sampling_rate": int(df_cfg.loc["Sampling Rate", "User Selection Value"]),
        "fault_location": str(df_cfg.loc["Fault Type", "User Selection Value"]).strip(),
        "fault_size_start": float(df_cfg.loc["Fault Size", "User Selection Value"]),
        "sample_duration": float(df_cfg.loc["Sampling Window (s)", "User Selection Value"]),
        "sampling_interval": float(df_cfg.loc["Sampling Interval (s)", "User Selection Value"]),
        
        "run_duration_mins": run_duration_mins,
        "run_duration_secs": run_duration_mins * 60.0,
        "distribution": dist_choice,
        "dist_params": dist_params
    }

    if "Outer Race Position" in df_cfg.index:
        val = df_cfg.loc["Outer Race Position", "User Selection Value"]
        config["or_position"] = int(val) if not pd.isna(val) else None
    else:
        config["or_position"] = None

    return config


if __name__ == "__main__":
    cfg = get_user_input()
    print("\nPipeline Complete. Exporting configuration profile dictionary context:")
    print(cfg)