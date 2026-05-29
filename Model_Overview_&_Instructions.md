# Critical Industrial Machinery Simulator

A simulation tool built on the **CWRU (Case Western Reserve University) Bearing Fault Dataset** that generates realistic motor vibration data with configurable healthy and faulty operating conditions. The simulator models fault onset, fault escalation, and multi-load operation over a user-defined run duration.

---

## Project Structure

```
CWRU_Simulator/
│
├── Data/                        ← All renamed CWRU dataset CSV files (not pushed to GitHub)
├── modules/
│   ├── __init__.py
│   ├── user_input.py            ← Module 1
│   ├── fault_timer.py           ← Module 2
│   ├── load_timeline.py         ← Module 3
│   ├── file_mapper.py           ← Module 4
│   ├── signal_engine.py         ← Module 5
│   ├── assembler.py             ← Module 6
│   └── csv_exporter.py          ← Module 7
│
├── outputs/                     ← All generated CSVs land here (not pushed to GitHub)
├── main.py                      ← Entry point — run this to start the simulator
├── config.py                    ← Global constants and paths
├── requirements.txt             ← Python dependencies
└── README.md                    ← This file
```

---

## What Each File Does

### `config.py`
Central configuration file. Defines all constants used across modules:
- `DATA_PATH` — path to the folder containing all renamed CWRU CSV files
- `OUTPUT_PATH` — path to the outputs folder where generated CSVs are saved
- `SAMPLING_RATES` — available sampling rates per system (DE: 12k/48k, FE: 12k only)
- `AVAILABLE_LOADS` — motor load options in HP: [0, 1, 2, 3]
- `LOAD_RPM` — maps each HP load to its corresponding shaft speed in RPM
- `FAULT_LOCATIONS` — available fault types: IR (Inner Race), B (Ball), OR (Outer Race)
- `OR_POSITIONS` — outer race clock positions: [6, 3, 12]
- `FAULT_SIZES` — available fault diameters per system and fault type
- `SOURCE_DATA_DURATION` — number of seconds used from each source file (10s)
- `DISTRIBUTIONS` — supported probability distributions: Weibull and Normal

---

### `modules/user_input.py` — Module 1
Handles all user interaction at the start of each simulation run. Collects and validates:

| Parameter | Description |
|---|---|
| Physical system | DE (Drive End) or FE (Fan End) |
| Sampling rate | 12,000 or 48,000 Hz (48k only available for DE) |
| Fault location | IR, B, or OR |
| OR position | Clock position @6:00, @3:00, or @12:00 (only if OR selected) |
| Starting fault severity | 0.007", 0.014", 0.021", 0.028" (availability depends on system and fault type) |
| Load mode | Fixed single load or multi-load rectangular wave |
| Loads and durations | Which HP loads to use and how long each runs per cycle |
| Total run duration | In minutes |
| Sample duration | How long each output snapshot is in seconds (e.g. 0.2s) |
| Sampling interval | Gap between end of one snapshot and start of the next (e.g. 1.0s) |
| Distribution | Weibull or Normal for fault timing |
| Distribution parameters | β and η for Weibull, μ and σ for Normal (as fractions of run duration) |

Returns a clean config dictionary used by all downstream modules.

---

### `modules/fault_timer.py` — Module 2
Generates the fault escalation timeline using the user's chosen probability distribution.

- Starts directly at the user-specified fault severity — never steps through lower severities first
- Draws fault onset time independently from the distribution
- Draws each subsequent escalation time independently and adds it on top
- Escalation is always sequential: 0.007" → 0.014" → 0.021" → 0.028"
- Stops adding escalation steps when time exceeds the run duration

Returns a list of `(time_seconds, fault_size)` tuples, e.g.:
```
[(480.2, 0.014"), (890.5, 0.021")]
```

---

### `modules/load_timeline.py` — Module 3
Builds the complete load vs time map for the entire run duration — the rectangular wave.

- For fixed single load: one segment covering the entire run
- For multi-load: alternates between selected loads at their specified durations, repeating until end of run

Returns a list of segments:
```
[{"start": 0.0, "end": 3.0, "load": 2, "rpm": 1750},
 {"start": 3.0, "end": 5.0, "load": 3, "rpm": 1730}, ...]
```

---

### `modules/file_mapper.py` — Module 4
Maps a set of parameters to the correct source CSV filename in the Data folder.

Constructs filenames using the convention:
- Normal: `Normal_{load}.csv`
- Fault (IR/B): `{rate}_{system}_{fault}{size}_{load}.csv`
- Fault (OR): `{rate}_{system}_OR{size}_{position}_{load}.csv`

Also provides `get_segment_file()` which takes a time segment and the fault timeline and automatically determines whether to return a normal or fault file based on the current simulation time.

---

### `modules/signal_engine.py` — Module 5
Fetches raw vibration signal data from source CSV files.

- Loads DE_time and FE_time columns from the source file
- Uses only the first 10 seconds of each file
- Implements a 95% overlap sliding window: each fetch advances the read pointer by 5% of the requested duration
- When the source data is exhausted, wraps back to the beginning — allowing infinite run durations without hard limits

Returns numpy arrays of exactly the requested number of samples for both DE and FE channels.

---

### `modules/assembler.py` — Module 6
The core pipeline module. Walks forward through the run duration and collects snapshots.

For each snapshot window [t_start, t_end]:
1. Checks if the window crosses a state boundary (load change or fault onset/escalation)
2. If it crosses a boundary: fetches signal from the starting state, labels it as a transition (e.g. `Normal_2.csv/Normal_3.csv`)
3. If clean: determines the active load and fault state, fetches the correct signal, labels it with the source filename
4. Advances time by sample_duration + sampling_interval and repeats

Returns a list of snapshot dictionaries containing t_start, t_end, DE array, FE array, label, and transition flag.

---

### `modules/csv_exporter.py` — Module 7
Writes all collected snapshots to disk.

**Signal CSVs** — one per snapshot:
- Filename: `{t_start}_{t_end}.csv`
- Columns: `sample_index`, `DE_time`, `FE_time`

**Ground truth CSV** — one file named `ground_truth.csv`:
- Columns: `t_start`, `t_end`, `label`, `transition`, `health_state`, `fault_size`
- Label is the source filename (e.g. `12k_DE_IR014_2.csv`) so all parameters are traceable
- Transition snapshots are labelled as `State1/State2`

All outputs are saved in a self-named subfolder inside `outputs/`:
```
outputs/DE_12k_IR_0.014_2HP_3HP_20min_20240517_143022/
```

---

### `main.py`
Entry point for the simulator. Ties all modules together in sequence:
1. Collects user input (Module 1)
2. Generates fault timeline (Module 2)
3. Builds load timeline (Module 3)
4. Runs the assembler loop (Module 6, which calls Modules 4 and 5 internally)
5. Exports all CSVs (Module 7)
6. Asks if the user wants to run another experiment

---

## How to Run

### Step 1 — Set up the environment

```bash
pip install -r requirements.txt
```

### Step 2 — Prepare the Data folder

Download the CWRU dataset files and rename them using the convention:
- `12k_DE_` prefix for 12k Drive End files
- `48k_DE_` prefix for 48k Drive End files
- `12k_FE_` prefix for 12k Fan End files
- Normal baseline files keep their original names (`Normal_0.csv` etc.)

Place all renamed files in `CWRU_Simulator/Data/`.

### Step 3 — Run the simulator

```bash
python main.py
```

Follow the prompts. At the end of each run, all output CSVs are saved to the `outputs/` folder.

---

## Dataset Information

The simulator uses the **CWRU Bearing Fault Dataset** — the most widely cited benchmark dataset for bearing fault diagnosis.

| Component | Specification |
|---|---|
| Drive End bearing | SKF 6205-2RS (BPFO: 3.5848×, BPFI: 5.4152×, BSF: 4.7135×) |
| Fan End bearing | SKF 6203-2RS (BPFO: 3.0530×, BPFI: 4.9469×, BSF: 3.9874×) |
| Motor | 2 HP |
| Load range | 0–3 HP |
| Shaft speed | 1797–1730 RPM |
| Fault types | Inner Race (IR), Ball (B), Outer Race (OR) |
| Fault sizes | 0.007", 0.014", 0.021", 0.028" |
| Sampling rates | 12,000 and 48,000 samples/second |

---

## Output Format

After each run the outputs folder contains:

```
outputs/DE_12k_IR_0.014_2HP_3HP_20min_TIMESTAMP/
│
├── 0.0_0.2.csv          ← snapshot at t=0.0s to t=0.2s
├── 1.2_1.4.csv          ← snapshot at t=1.2s to t=1.4s
├── 2.4_2.6.csv
├── ...
└── ground_truth.csv     ← full label record for all snapshots
```

**Signal CSV** (e.g. `0.0_0.2.csv`):
```
sample_index, DE_time, FE_time
0, 0.051749, 0.047665
1, 0.055923, 0.047049
...
```

**Ground truth CSV**:
```
t_start, t_end, label, transition, health_state, fault_size
0.0, 0.2, Normal_2.csv, False, healthy, —
1.2, 1.4, Normal_3.csv, False, healthy, —
...
480.0, 480.2, 12k_DE_IR014_2.csv, False, faulty, 0.014
481.2, 481.4, 12k_DE_IR014_2.csv/12k_DE_IR014_3.csv, True, faulty, 0.014
```
