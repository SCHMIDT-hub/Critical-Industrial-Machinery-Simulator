import os

# ── Paths (Force Absolute Working Directory Resolution) ────────────────────
# Locks root context precisely to where config.py lives on disk
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(BASE_DIR, "Data")
OUTPUT_PATH = os.path.join(BASE_DIR, "outputs")

# ── Asset Management Type Flags ────────────────────────────────────────────
MACHINE_TYPES = ["bearing", "gearbox"]
DISTRIBUTIONS = ["weibull", "normal"]

# ── Dynamic Multi-Component Metadata Architecture ──────────────────────────
COMPONENTS = {
    "bearing": {
        "systems": ["DE", "FE", "NU205"],
        "sampling_rates": {
            "DE": [12000, 48000],
            "FE": [12000],
            "NU205": [12000]
        },
        "fault_locations": ["IR", "B", "OR"],
        "or_positions": [6, 3, 12],
        "available_loads": [0, 1, 2, 3],
        "load_mapping": {
            0: 1797,
            1: 1772,
            2: 1750,
            3: 1730
        },
        "fault_sizes": {
            "DE": {
                "IR": [0.007, 0.014, 0.021, 0.028],
                "B":  [0.007, 0.014, 0.021, 0.028],
                "OR": [0.007, 0.014, 0.021]
            },
            "FE": {
                "IR": [0.007, 0.014, 0.021],
                "B":  [0.007, 0.014, 0.021],
                "OR": [0.007, 0.014, 0.021]
            },
            "NU205": {
                "IR": [0.007, 0.014, 0.021, 0.028],
                "B":  [0.007, 0.014, 0.021, 0.028],
                "OR": [0.007, 0.014, 0.021]
            }
        },
        "source_data_duration": 10,
        "sensor_channels": ["de_time", "fe_time"]
    },

    "gearbox": {
        "systems": ["parallel"],
        "sampling_rates": {
            "parallel": [16000]
        },
        "fault_locations": ["eccentric gear", "gear surface wear", "gear tooth break"],
        "or_positions": None,
        "available_loads": [20],
        "load_mapping": {
            1200: 1200,
            1800: 1800,
            2400: 2400,
            "200-2400-200": "variable"
        },
        "fault_sizes": {
            "parallel": {
                "eccentric gear": [0.2],
                "gear surface wear": [0.2],
                "gear tooth break": [0.2]
            }
        },
        "source_data_duration": 30,
        "sensor_channels": ["ch 1", "ch 2", "ch 3"] 
    }
}

# ── Excel Asset Deployment Matrix (Robust Path Wrapping) ──────────────────
ASSET_MENU = {
    "1": {
        "machine_type": "bearing", 
        "sub_system": "DE", 
        "config_file": os.path.join(BASE_DIR, "Templates", "config_DE_bearing.xlsx"),
        "profile_file": os.path.join(BASE_DIR, "Templates", "Operational_Profile_DE_FE.xlsx")
    },
    "2": {
        "machine_type": "bearing", 
        "sub_system": "FE", 
        "config_file": os.path.join(BASE_DIR, "Templates", "config_FE_bearing.xlsx"),
        "profile_file": os.path.join(BASE_DIR, "Templates", "Operational_Profile_DE_FE.xlsx")
    },
    "3": {
        "machine_type": "bearing", 
        "sub_system": "NU205", 
        "config_file": os.path.join(BASE_DIR, "Templates", "config_NU205_bearing.xlsx"),
        "profile_file": os.path.join(BASE_DIR, "Templates", "Operational_Profile_NU_Gear.xlsx")
    },
    "4": {
        "machine_type": "gearbox", 
        "sub_system": "parallel", 
        "config_file": os.path.join(BASE_DIR, "Templates", "config_gearbox.xlsx"),
        "profile_file": os.path.join(BASE_DIR, "Templates", "Operational_Profile_NU_Gear.xlsx")
    }
}

# ── Backward Compatibility Fallbacks ──────────────────────────────────────
SAMPLING_RATES  = COMPONENTS["bearing"]["sampling_rates"]
AVAILABLE_LOADS = COMPONENTS["bearing"]["available_loads"]
LOAD_RPM        = COMPONENTS["bearing"]["load_mapping"]
FAULT_LOCATIONS = COMPONENTS["bearing"]["fault_locations"]
OR_POSITIONS    = COMPONENTS["bearing"]["or_positions"]
FAULT_SIZES     = COMPONENTS["bearing"]["fault_sizes"]
SOURCE_DATA_DURATION = COMPONENTS["bearing"]["source_data_duration"]