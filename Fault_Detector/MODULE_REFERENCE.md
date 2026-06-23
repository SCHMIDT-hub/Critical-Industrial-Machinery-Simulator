# Fault Detector — Module Reference

Each module has exactly one job. They are designed to be read and modified independently.

---

## `detector_config.py`

Single source of truth for every tunable parameter. The only file a new user ever needs to open. Contains paths, signal parameters, calibration settings, and output flags. **No LOAD_SCHEDULE** — load is inferred automatically from the signal itself, so nothing here needs to change between test runs except `WINDOW_SAMPLES` if the simulator's `sample_duration` changes.

---

## `detector_features.py`

Converts one raw vibration window (a numpy array of amplitude values) into a 5-number feature vector. Does this independently for each channel (DE and FE). The five features are:

| Index | Name | What it measures |
|---|---|---|
| 0 | RMS | Overall vibration energy |
| 1 | Kurtosis | Impulsiveness in time domain |
| 2 | Crest Factor | Peak sharpness relative to RMS |
| 3 | Shape Factor | RMS relative to mean absolute value |
| 4 | Envelope Kurtosis | Impulsiveness of the FFT-derived envelope (Hilbert transform) |

No bearing geometry. No fault frequencies. All five features respond to any fault type — the detector does not need to know which fault it is looking for.

---

## `detector_baseline.py`

Trains the healthy reference model. Runs once, saves `baseline.pkl`, and is reused across all subsequent test runs unless forced to rebuild.

Three things it produces:

**Two independent PCA-T² models** — one for the DE channel, one for the FE channel — each trained only on that channel's data from `Normal_0.csv` through `Normal_3.csv`. Having separate models is what makes fault location prediction possible: the system has an explicit, independent definition of what healthy DE looks like and what healthy FE looks like.

**Per-load statistics** — within each channel model, the healthy fingerprint is stored separately for each of the four motor loads (0, 1, 2, 3 HP). This is what allows load-agnostic scoring at runtime without needing an external schedule.

**Monte Carlo calibrated CUSUM threshold** — simulates 500 independent pure-healthy runs of 3000 snapshots each (longer than any realistic deployment) by resampling the actual healthy data with replacement, and sets the decision threshold safely above the worst CUSUM drift observed across all those simulations. This replaces the manually guessed `CUSUM_H_FACTOR` constant that was wrong twice.

---

## `detector_core.py`

Contains the detection logic. Five independent functions, each doing one thing:

**`load_snapshot(path)`** — reads one snapshot CSV, extracts DE and FE signal arrays and the timestamp from the filename. Uses exact column name matching (`DE_time`, `FE_time`) to avoid accidentally reading `sample_index` (which contains the substring "DE").

**`t_squared_auto_load(fv, channel_baseline)`** — computes Hotelling T² against every per-load healthy model and returns the minimum. The minimum is both the anomaly score (how different is this from the closest healthy reference?) and the load inference (which load does this signal most resemble?). No external schedule needed.

**`combined_detection(de_scores, fe_scores, ...)`** — standardises DE and FE T² scores onto the same z-score scale (so neither channel's natural noise level gives it a head start), then runs one CUSUM using the auto-calibrated k and H from the baseline. Onset is declared when the cumulative sum stays above H for `MIN_CONSECUTIVE` consecutive snapshots.

**`decide_location(z_de, z_fe, onset_idx)`** — called only after onset is confirmed. Compares the mean z-score of DE vs FE in the `LOCATION_WINDOW` snapshots immediately after onset. Whichever is larger by at least `LOCATION_RATIO` wins. This is a magnitude comparison, not a timing race between two separately-thresholded detectors.

**`evaluate(gt, times, onset_idx, location)`** — compares predicted onset time and location against the ground truth CSV. Used only for evaluation; never used as input to detection.

---

## `detector_main.py`

Orchestrates the full pipeline in order: load baseline → score all snapshots → run combined CUSUM → decide location → evaluate against ground truth → save JSON results → plot. Also prints the inferred load distribution across all snapshots, which serves as a free sanity check that auto-inference is behaving sensibly.

---

## `detector_plotter.py`

Produces a three-panel figure:

- **Panel 1** — raw DE and FE anomaly scores over time. This is what tells you WHERE. Compare the two lines by eye — whichever jumps and stays elevated is the faulty channel.
- **Panel 2** — the single combined CUSUM statistic against its auto-calibrated decision line. This is what tells you WHEN.
- **Panel 3** — ground truth state timeline (green = healthy, red = faulty) with the predicted onset overlaid as a dashed black line.

A plain-text summary box at the bottom states the predicted onset time, predicted location, true onset, detection delay, and whether the location call matched.
