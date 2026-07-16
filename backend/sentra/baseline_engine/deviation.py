"""Doc 07 §11-12: normalized deviation from personal baseline, weighted by
feature importance (Doc 07 §12)."""
from __future__ import annotations

from .. import config
from ..models import BaselineDeviation, FeatureVector
from .profile import PatientBaseline

_STD_FLOOR = {"heart_rate": 2.0, "hrv": 1.0, "spo2": 1.0, "temperature": 0.15, "activity": 0.2}


def _normalized(current: float | None, mean: float | None, std: float, floor: float) -> float | None:
    if current is None or mean is None:
        return None
    return abs(current - mean) / max(std, floor)


def compute_deviation(features: FeatureVector, baseline: PatientBaseline) -> BaselineDeviation:
    hr_dev = _normalized(features.cardiac.heart_rate, baseline.heart_rate.mean,
                          baseline.heart_rate.std, _STD_FLOOR["heart_rate"])
    hrv_dev = _normalized(features.cardiac.heart_rate_variability, baseline.hrv.mean,
                           baseline.hrv.std, _STD_FLOOR["hrv"])
    temp_dev = _normalized(features.temperature.skin_temperature, baseline.temperature.mean,
                            baseline.temperature.std, _STD_FLOOR["temperature"])
    motion_dev = _normalized(features.motion.motion_intensity, baseline.activity.mean,
                              baseline.activity.std, _STD_FLOOR["activity"])
    # respiratory_deviation intentionally omitted — respiratory_rate unavailable, see HARDWARE_SCOPE.md §4b

    weights = config.get_weights()["baseline_engine"]["feature_importance"]
    parts = []
    if hr_dev is not None:
        parts.append((weights["heart_rate"], hr_dev))
    if hrv_dev is not None:
        parts.append((weights["hrv"], hrv_dev))
    if temp_dev is not None:
        parts.append((weights["temperature"], temp_dev))
    if motion_dev is not None:
        parts.append((weights["activity"], motion_dev))

    overall = None
    if parts:
        total_weight = sum(w for w, _ in parts)
        overall = sum(w * d for w, d in parts) / total_weight if total_weight else None

    return BaselineDeviation(
        heart_rate_deviation=hr_dev,
        hrv_deviation=hrv_dev,
        respiratory_deviation=None,
        temperature_deviation=temp_dev,
        motion_deviation=motion_dev,
        overall_deviation=overall,
    )
