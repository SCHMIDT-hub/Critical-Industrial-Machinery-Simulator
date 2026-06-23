"""
detector_features.py
----------------------
5 features per channel. No bearing geometry, no fault frequencies -- none
of that is needed because we are not naming the fault type, only detecting
that *something* changed and on *which* channel.

  0  RMS               -- overall vibration strength
  1  Kurtosis          -- time-domain impulsiveness (sharp impacts raise this)
  2  CrestFactor        -- peak / RMS, another impulsiveness measure
  3  ShapeFactor        -- RMS / mean(|signal|)
  4  EnvelopeKurtosis   -- impulsiveness of the FFT/Hilbert-derived envelope

EnvelopeKurtosis is the one FFT-based feature. The envelope is obtained via
the Hilbert transform, which is computed using the FFT internally (take FFT,
zero out negative frequencies, inverse FFT). Bearing faults produce periodic
impacts that show up as a strong, spiky envelope -- this rises for ANY fault
type (Inner/Outer/Ball), which is exactly why it's useful here: it's a
type-agnostic "something is hitting the bearing periodically" detector,
grounded in the standard envelope-analysis literature (Randall & Antoni 2011)
rather than the narrow-band approach that broke down on ball faults.
"""

import numpy as np
from scipy.stats import kurtosis as _kurt
from scipy.signal import hilbert

N_FEATURES = 5
FEATURE_NAMES = ["RMS", "Kurtosis", "CrestFactor", "ShapeFactor", "EnvelopeKurtosis"]


def channel_features(sig: np.ndarray) -> np.ndarray:
    """Return the 5-element feature vector for one channel's signal window."""
    eps = 1e-10

    rms  = max(float(np.sqrt(np.mean(sig ** 2))), eps)
    kurt = float(_kurt(sig, fisher=True))
    crest = float(np.max(np.abs(sig))) / rms
    shape = rms / max(float(np.mean(np.abs(sig))), eps)

    # Envelope via Hilbert transform (FFT-based): |analytic_signal|
    env = np.abs(hilbert(sig))
    env_kurt = float(_kurt(env, fisher=True))

    return np.array([rms, kurt, crest, shape, env_kurt], dtype=np.float64)