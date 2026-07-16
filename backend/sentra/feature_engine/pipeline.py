"""Doc 06 §5 overall pipeline: ProcessedWindow + SignalQuality -> FeatureVector."""
from __future__ import annotations

from ..models import FeatureVector, ProcessedWindow, QualityFeatures, SignalQuality
from .derived_features import compute_derived_features
from .imu_features import extract_motion_features
from .ppg_features import extract_cardiac_features, extract_respiratory_features
from .temperature_features import extract_temperature_features


def extract_features(window: ProcessedWindow, quality: SignalQuality,
                      baseline_temp: float | None = None) -> FeatureVector:
    cardiac = extract_cardiac_features(window, quality)
    respiratory = extract_respiratory_features(window, quality)
    motion = extract_motion_features(window)
    temperature = extract_temperature_features(window, baseline_temp)
    derived = compute_derived_features(cardiac, respiratory, motion, temperature)

    quality_features = QualityFeatures(
        ppg_sqi=quality.ppg_sqi,
        imu_sqi=quality.imu_sqi,
        temperature_sqi=quality.temperature_sqi,
        overall_sqi=quality.overall_sqi,
    )

    return FeatureVector(
        window_id=window.window_id,
        patient_id=window.patient_id,
        cardiac=cardiac,
        respiratory=respiratory,
        motion=motion,
        temperature=temperature,
        derived=derived,
        quality=quality_features,
    )
