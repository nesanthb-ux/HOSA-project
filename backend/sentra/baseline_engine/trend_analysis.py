"""Doc 07 §14 trend detection, computed over the patient's recent history buffer."""
from __future__ import annotations

import numpy as np

from ..models import TrendSummary
from .profile import PatientBaseline

WORSENING_SLOPE_HR = 0.5     # bpm per sample, over the ~20-window history buffer
WORSENING_SLOPE_TEMP = 0.02  # degC per sample


def _slope(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    x = np.arange(len(values))
    slope, _ = np.polyfit(x, np.asarray(values, dtype=float), 1)
    return float(slope)


def compute_trend(baseline: PatientBaseline) -> TrendSummary:
    hr_series = [f.cardiac.heart_rate for _, f in baseline.history if f.cardiac.heart_rate is not None]
    temp_series = [f.temperature.skin_temperature for _, f in baseline.history if f.temperature.skin_temperature is not None]
    hrv_series = [f.cardiac.heart_rate_variability for _, f in baseline.history if f.cardiac.heart_rate_variability is not None]

    hr_slope = _slope(hr_series)
    temp_slope = _slope(temp_series)
    hrv_slope = _slope(hrv_series)

    worsening = (hr_slope is not None and hr_slope > WORSENING_SLOPE_HR) or \
                (temp_slope is not None and temp_slope > WORSENING_SLOPE_TEMP)
    improving = (hr_slope is not None and hr_slope < -WORSENING_SLOPE_HR) and \
                (temp_slope is None or temp_slope <= 0)

    overall = "worsening" if worsening else ("improving" if improving else "stable")

    return TrendSummary(
        heart_rate_slope=hr_slope,
        temperature_slope=temp_slope,
        hrv_slope=hrv_slope,
        respiratory_slope=None,  # respiratory_rate unavailable, see HARDWARE_SCOPE.md §4b
        overall_trend=overall,
    )
