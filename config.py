import os

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "Data")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "outputs")

# ── Sampling Rates ─────────────────────────────────────────────────────────
SAMPLING_RATES = {
    "DE": [12000, 48000],
    "FE": [12000]           # FE only has 12k
}

# ── Available Loads ────────────────────────────────────────────────────────
AVAILABLE_LOADS = [0, 1, 2, 3]  # HP

# Load → RPM mapping
LOAD_RPM = {
    0: 1797,
    1: 1772,
    2: 1750,
    3: 1730
}

# ── Fault Locations ────────────────────────────────────────────────────────
FAULT_LOCATIONS = ["IR", "B", "OR"]

# OR positions
OR_POSITIONS = [6, 3, 12]   # clock positions

# ── Fault Severities ───────────────────────────────────────────────────────
# All sizes available per system
FAULT_SIZES = {
    "DE": {
        "IR": [0.007, 0.014, 0.021, 0.028],
        "B":  [0.007, 0.014, 0.021, 0.028],
        "OR": [0.007, 0.014, 0.021]
    },
    "FE": {
        "IR": [0.007, 0.014, 0.021],
        "B":  [0.007, 0.014, 0.021],
        "OR": [0.007, 0.014, 0.021]
    }
}

# ── Data Duration ──────────────────────────────────────────────────────────
SOURCE_DATA_DURATION = 10   # seconds — we use only 10s from each file

DISTRIBUTIONS = ["weibull", "normal"]