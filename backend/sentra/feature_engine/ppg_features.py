"""Doc 06 §6-7 cardiac + respiratory features, sourced from PPG per
docs/HARDWARE_SCOPE.md. True beat-to-beat HRV (RMSSD/SDNN/pNN50) and
PPG-derived respiratory rate need the raw waveform and are left unavailable
(see HARDWARE_SCOPE.md §4b) rather than estimated from data that can't
support them.
"""
from __future__ import annotations

import numpy as np

from ..models import CardiacFeatures, ProcessedWindow, RespiratoryFeatures, SignalQuality
from ._utils import linear_slope, normalized_variability


def extract_cardiac_features(window: ProcessedWindow, quality: SignalQuality) -> CardiacFeatures:
    if not window.ppg:
        return CardiacFeatures()

    hr_series = window.ppg
    heart_rate = float(hr_series[-1])
    trend = linear_slope(hr_series)
    variability = normalized_variability(hr_series)

    return CardiacFeatures(
        heart_rate=heart_rate,
        # Coarse proxy only: std of a 1Hz-averaged HR trace, NOT true
        # beat-to-beat HRV. See HARDWARE_SCOPE.md §4b.
        heart_rate_variability=float(np.std(hr_series)) if len(hr_series) > 1 else None,
        mean_nn=(60_000.0 / heart_rate) if heart_rate else None,
        heart_rate_trend=trend,
        beat_regularity=(1.0 - min(1.0, variability)) if variability is not None else None,
        rr_variability=variability,
        heart_rate_acceleration=(trend if trend is not None else None),
        beat_detection_confidence=quality.ppg_sqi,
        # rmssd/sdnn/pnn50/qt*/qrs*/pr_interval intentionally None — unavailable, see HARDWARE_SCOPE.md
    )


def extract_respiratory_features(window: ProcessedWindow, quality: SignalQuality) -> RespiratoryFeatures:
    spo2_series = window.ppg_spo2
    features = RespiratoryFeatures()
    if spo2_series:
        features.spo2 = float(spo2_series[-1])
        features.oxygen_trend = linear_slope(spo2_series)
    # respiratory_rate / respiratory_variability / breathing_regularity /
    # perfusion_index / pulse_arrival_time need raw PPG waveform — left
    # unavailable rather than fabricated. See HARDWARE_SCOPE.md §4b.
    return features
