# Fault Detector — Architecture

## Problem Statement

Given a sequence of vibration snapshots from a simulated rotating machine run, automatically determine:
1. **When** a bearing fault onset occurred (timestamp, matched to snapshot boundaries)
2. **Where** the fault is physically located (Drive End or Fan End)

**Out of scope by design:** fault type (Inner Race / Outer Race / Ball) and fault severity (0.007" / 0.014" / 0.021"). The system has never seen a fault example and cannot reliably name either. What it can reliably detect is that the machine's vibration character changed, and which side changed more.

---

## Core Design Principle

Train only on healthy data. Every bearing starts healthy. The only data that is guaranteed to be available before a deployment is data from a machine running normally. The system builds a model of "what healthy looks like" from the four CWRU Normal recordings and flags any deviation from that model at runtime.

No fault examples are used anywhere in the pipeline. No bearing geometry is assumed. No fault frequencies are computed. The system is therefore agnostic to which fault type appears — this is a deliberate choice, not a limitation to be fixed later.

---

## Pipeline Overview

```
Normal_0..3.csv  ──►  OFFLINE BASELINE BUILDING  ──►  baseline.pkl
                                                              │
Simulator output CSVs  ──────────────────────────────────────►│
                                                              ▼
                                               RUNTIME DETECTION
                                                              │
                                             ┌────────────────┴────────────────┐
                                             ▼                                 ▼
                                    Feature extraction               Feature extraction
                                     DE channel (×N)                  FE channel (×N)
                                             │                                 │
                                             ▼                                 ▼
                                   Auto-load T² scoring             Auto-load T² scoring
                                   (min T² across 4 loads)          (min T² across 4 loads)
                                             │                                 │
                                             └─────────────┬───────────────────┘
                                                           ▼
                                              Standardise to z-scores
                                              max(z_DE, z_FE) per snapshot
                                                           │
                                                           ▼
                                                  CUSUM on combined z
                                              (auto-calibrated k and H)
                                                           │
                                                    onset declared?
                                                    /            \
                                                  NO             YES
                                                   │               │
                                              no fault         compare mean z_DE
                                             detected          vs mean z_FE in
                                                               next 15 snapshots
                                                                     │
                                                             location = whichever
                                                             is larger by ≥ 1.3×
                                                                     │
                                                                  DE / FE / Both
```

---

## Stage 1 — Feature Extraction

**Input:** one raw vibration window (4800 samples = 0.4 s at 12 kHz)  
**Output:** 5 scalar features

| Feature | Formula | Why |
|---|---|---|
| RMS | √(mean(x²)) | Overall vibration energy; rises when a fault adds energy |
| Kurtosis | E[(x−μ)⁴]/σ⁴ − 3 | Impulsiveness; bearing impacts are sharp, kurtosis spikes |
| Crest Factor | max(|x|) / RMS | Another impulsiveness measure; robust to RMS changes |
| Shape Factor | RMS / mean(|x|) | Waveform shape; changes when periodic impacts appear |
| Envelope Kurtosis | kurtosis(|hilbert(x)|) | Kurtosis of the signal envelope, computed via FFT. Bearing faults modulate the envelope at the fault frequency; this rises for any fault type (Inner, Outer, Ball) |

Computed independently for DE and FE channels. No cross-channel assumptions.

---

## Stage 2 — Healthy Baseline Model

**One model per channel, built from Normal_0..3.csv.**

For each channel and each of the four load conditions (0, 1, 2, 3 HP):
- Extract non-overlapping windows of 4800 samples
- Compute 5-D feature vectors
- Store the mean and standard deviation of each feature (per-load statistics)

Across all loads, fit a PCA on the z-normalised features, retaining 95% of variance. The resulting PCA + per-load statistics define the healthy manifold for that channel.

**Why two separate models?** Because fault location detection requires an independent reference for each channel. A single joint model would conflate DE and FE variation and lose the ability to say which side changed more.

**Healthy T² scores** are computed for every healthy window and stored. The 99th percentile becomes the per-channel threshold. These scores are also used for the combined CUSUM calibration.

---

## Stage 3 — Auto-Load Inference and Anomaly Scoring

For each runtime snapshot, instead of consulting a manually-maintained load schedule:

```
for each load L in {0, 1, 2, 3}:
    normalise fv using per-load-L statistics
    project through PCA
    compute T² = Σ (projection² / eigenvalue)

inferred_load  = L with minimum T²
anomaly_score  = that minimum T²
```

**Why this works:** A healthy signal at load L resembles load L's model closely (small T²) and differs from other loads' models (larger T²). So the minimum T² correctly identifies the load. A faulty signal differs from *all* load models — even the best-matching one gives a large T², because the signal's impulsive character is genuinely different from anything in the healthy baseline.

This eliminates the `LOAD_SCHEDULE` parameter entirely. No configuration needs to be updated between runs with different load patterns.

---

## Stage 4 — Combined CUSUM (WHEN)

**Why not two separate per-channel CUSUMs?** The DE channel naturally has higher T² variance than the FE channel even when both are healthy. If each channel's CUSUM threshold is scaled to its own noise level, the quieter channel (FE) has a lower absolute bar and can be crossed first by chance — giving a spurious early detection that identifies the wrong channel as the fault location. This failure mode was observed empirically.

**The fix:** standardise both channels onto the same z-score scale before combining:

```
z_DE[t] = (T2_DE[t] − μ_healthy_DE) / σ_healthy_DE
z_FE[t] = (T2_FE[t] − μ_healthy_FE) / σ_healthy_FE
combined[t] = max(z_DE[t], z_FE[t])
```

CUSUM runs on `combined[t]` with a single pair of parameters (k, H).

**Auto-calibration of H:** The combined statistic is the maximum of two z-scores, which is right-skewed — it drifts upward over time even when both channels are healthy, more than a standard normal CUSUM expects. A formula-based threshold would be wrong.

Instead, H is calibrated by Monte Carlo simulation:
1. Pool all healthy combined-z values
2. Resample them with replacement to form 500 synthetic healthy runs of 3000 snapshots each
3. Record the maximum CUSUM value reached in each trial
4. Set H = 1.3 × (worst case observed)

This guarantees that pure healthy noise essentially never crosses H over a run of the configured length, regardless of the signal's exact distributional shape.

---

## Stage 5 — Location Decision (WHERE)

After onset is declared at index `i`:

```
de_level = mean(z_DE[i : i+15])
fe_level = mean(z_FE[i : i+15])

if de_level ≥ fe_level × 1.3  →  location = "DE"
if fe_level ≥ de_level × 1.3  →  location = "FE"
else                            →  location = "Both"
```

This is a magnitude comparison, not a timing race. It only runs once, after the onset is confirmed. The same combined z-scores used for CUSUM are reused here — no additional computation.

---

## Key Design Decisions and Their Justifications

| Decision | Alternative considered | Why this was chosen |
|---|---|---|
| 5 time-domain + envelope features | FFT narrow-band energies | Healthy bearings have near-zero energy at fault frequencies → std ≈ 0 → T² explodes to 10¹² when any noise appears there |
| Two separate channel models | One joint model | Joint model cannot distinguish which channel changed more |
| Auto-load inference (min T²) | Manual LOAD_SCHEDULE | Manual list was stale twice across test runs, silently breaking every comparison |
| Single combined CUSUM | Two per-channel CUSUMs | Per-channel CUSUMs with independently-scaled thresholds cause quieter channel to trigger first by chance |
| Monte Carlo threshold calibration | H = constant × σ | max(z_DE, z_FE) is right-skewed; formula-based threshold underestimates tail drift |
| Post-hoc location by magnitude | Whichever channel triggers CUSUM first | Timing race is dominated by threshold height, not signal strength |

---

## What This System Cannot Do

- **Identify fault type** (Inner Race, Outer Race, Ball) — the features are deliberately type-agnostic; no approach without fault examples can reliably distinguish types on CWRU ball faults (Smith & Randall 2015)
- **Estimate fault severity** (0.007", 0.014", 0.021") — same limitation; Smith & Randall found fault size had lower impact than test rig assembly conditions
- **Generalise beyond CWRU bearing geometry without retraining** — the healthy baseline is fitted to the specific acoustic and vibration fingerprint of the CWRU test rig; a different machine needs its own Normal recordings

---

## References

- Randall, R.B. & Antoni, J. (2011). Rolling element bearing diagnostics — a tutorial. *Mechanical Systems and Signal Processing*, 25(2), 485–520.
- Smith, W.A. & Randall, R.B. (2015). Rolling element bearing diagnostics using the Case Western Reserve University data. *Mechanical Systems and Signal Processing*, 64, 100–131.
- Pandhare et al. (2024). Autoencoder-based domain adaptation for bearing fault detection. *Journal of Manufacturing Systems*.
- Rosa et al. (2024). Benchmarking deep learning models for bearing fault diagnosis using the CWRU dataset: a multi-label approach. arXiv:2407.14625.
