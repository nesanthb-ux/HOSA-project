"""Doc 06 §9 temperature features."""
from __future__ import annotations

import numpy as np

from ..models import ProcessedWindow, TemperatureFeatures
from ._utils import linear_slope

FEVER_THRESHOLD_C = 38.0  # matches clinical_rules TMP-001, Doc 08 §14


def extract_temperature_features(window: ProcessedWindow, baseline_temp: float | None) -> TemperatureFeatures:
    if not window.temperature:
        return TemperatureFeatures()

    temp_series = window.temperature
    current = float(temp_series[-1])
    slope_per_sample = linear_slope(temp_series)
    # window.duration is not passed here; caller (feature_vector.py) knows
    # the window size and converts slope-per-sample to degC/hour.

    variability = float(np.std(temp_series)) if len(temp_series) > 1 else None

    fever_probability = max(0.0, min(1.0, (current - (FEVER_THRESHOLD_C - 1.0)) / 2.0))

    deviation = (current - baseline_temp) if baseline_temp is not None else None

    return TemperatureFeatures(
        skin_temperature=current,
        temperature_slope=slope_per_sample,
        temperature_variability=variability,
        baseline_deviation=deviation,
        fever_probability=fever_probability,
    )
