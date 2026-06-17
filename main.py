import sys
import os
import pandas as pd

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
        config = get_user_input()
        
        # Hardcoded suffix since architecture is now exclusively gearbox components
        size_suffix = ""  

        # ── Step 2: Build Operational Load Timeline ───────────────────────
        print("\n  Parsing operational speed/load profile steps...")
        load_segments = build_load_timeline(config)
        print_timeline_summary(load_segments, config)

        # ── STREAMLINED Y/N CONFIRMATION GATE ────────────────────────────────
        # Graph plotting removed. Evaluates y/n input loops directly.
        proceed = input("\nDoes the extracted profile look correct? Proceed to signal sampling? (y / n): ").strip().lower()
        if proceed not in ["y", "yes"]:
            print("\n[Operation Aborted] Exiting simulator safely so you can check your input data columns.")
            print("="*50)
            break
        # ─────────────────────────────────────────────────────────────────────

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
        again = input("  Run another experiment profile? (y / n): ").strip().lower()
        if again not in ["y", "yes"]:
            print("\n  Simulator exited cleanly. Outputs archived within:")
            print(f"  {OUTPUT_PATH}")
            break


if __name__ == "__main__":
    run_simulator()