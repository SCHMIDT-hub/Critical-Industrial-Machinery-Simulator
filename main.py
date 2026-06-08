import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_PATH
from modules.user_input    import get_user_input
from modules.fault_timer   import generate_fault_timeline
from modules.load_timeline import build_load_timeline, print_timeline_summary
from modules.assembler     import run_assembler
from modules.csv_exporter  import export_snapshots


def run_simulator():

    while True:
        # ── Step 1: Complete Sequenced User Interaction ───────────────────
        # This prompts for core config, terminal values, and profile sheets
        config = get_user_input()
        machine_type = config.get("machine_type", "bearing")
        system = config["system"]
        
        # Dynamically switch the display string suffix based on asset class
        if system == "NU205" or machine_type == "gearbox":
            size_suffix = ""  # Drops unit markers for pure string fault identifiers
        else:
            size_suffix = '"' if machine_type == "bearing" else "mm"

        # ── Step 2: Build Operational Load Timeline ───────────────────────
        # Runs first to map operational speeds before wear evaluation
        print("\n  Parsing operational speed/load profile steps...")
        load_segments = build_load_timeline(config)
        print_timeline_summary(load_segments, config)

        # ── Step 3: Generate Degradation Fault Timeline ───────────────────
        print("\n  Simulating stochastically scheduled fault timeline...")
        fault_timeline = generate_fault_timeline(config)
        if fault_timeline:
            for t, size in fault_timeline:
                display_size = f"{size}{size_suffix}" if isinstance(size, (int, float)) else str(size)
                print(f"    t={t}s ({t/60:.2f} mins) → active fault condition initialized: {display_size}")
        else:
            print("    No degradation faults occur within this simulation runtime window.")

        # ── Step 4: Execute Signal Matrix Assembly ──────────────────────────
        snapshots = run_assembler(config, load_segments, fault_timeline)

        # ── Step 5: Export Snapshots & Ground Truth ─────────────────────────
        run_folder = export_snapshots(snapshots, config, fault_timeline)

        # ── Step 6: Loop Execution Query ───────────────────────────────────
        print("\n" + "="*50)
        again = input("  Run another experiment profile? (yes / no): ").strip().lower()
        if again != "yes":
            print("\n  Simulator exited cleanly. Outputs archived within:")
            print(f"  {OUTPUT_PATH}")
            break


if __name__ == "__main__":
    run_simulator()