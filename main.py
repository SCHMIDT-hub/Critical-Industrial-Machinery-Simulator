import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.user_input    import get_user_input
from modules.fault_timer   import generate_fault_timeline
from modules.load_timeline import build_load_timeline
from modules.assembler     import run_assembler
from modules.csv_exporter  import export_snapshots


def run_simulator():

    while True:

        # ── Step 1: Get user input ─────────────────────────────────────────
        config = get_user_input()

        # ── Step 2: Generate fault timeline ───────────────────────────────
        print("\n  Generating fault timeline...")
        fault_timeline = generate_fault_timeline(config)
        if fault_timeline:
            for t, size in fault_timeline:
                print(f"    t={t}s ({t/60:.2f} mins) → fault size {size}\"")
        else:
            print("    No fault occurs within run duration.")

        # ── Step 3: Build load timeline ────────────────────────────────────
        print("\n  Building load timeline...")
        load_segments = build_load_timeline(config)
        print(f"    {len(load_segments)} load segments generated.")

        # ── Step 4: Run assembler ──────────────────────────────────────────
        snapshots = run_assembler(config, load_segments, fault_timeline)

        # ── Step 5: Export CSVs ────────────────────────────────────────────
        run_folder = export_snapshots(snapshots, config, fault_timeline)

        # ── Step 6: Ask to run again ───────────────────────────────────────
        print("\n" + "="*50)
        again = input("  Run another experiment? (yes / no): ").strip().lower()
        if again != "yes":
            print("\n  Simulator exited. All outputs saved to:")
            print(f"  {run_folder.rsplit(os.sep, 1)[0]}")
            break


if __name__ == "__main__":
    run_simulator()