"""Doc 06 §8 motion features, from the firmware's motion-magnitude scalar
(docs/HARDWARE_SCOPE.md §4). step_rate/posture/orientation need raw
accelerometer axes the firmware doesn't transmit and are left unavailable.
"""
from __future__ import annotations

import numpy as np

from ..models import MotionFeatures, ProcessedWindow

# Thresholds are magnitude-of-deviation-from-1g units as computed by
# firmware/patient_node/motion_mpu6050.h's motionMetric() — not a clinical
# standard, an engineering choice made when that firmware was written.
_SEDENTARY_MAX = 0.5
_LIGHT_MAX = 2.0
_MODERATE_MAX = 5.0
_FALL_LIKE_THRESHOLD = 3.0   # matches Mpu6050::isFallLike in firmware


def _activity_level(mean_motion: float) -> str:
    if mean_motion < _SEDENTARY_MAX:
        return "sedentary"
    if mean_motion < _LIGHT_MAX:
        return "light"
    if mean_motion < _MODERATE_MAX:
        return "moderate"
    return "high"


def extract_motion_features(window: ProcessedWindow) -> MotionFeatures:
    mag = window.imu
    if not mag:
        return MotionFeatures()

    mean_motion = float(np.mean(mag))
    peak_motion = float(np.max(mag))
    variability = float(np.std(mag))

    fall_probability = 0.0
    if peak_motion > _FALL_LIKE_THRESHOLD:
        fall_probability = max(0.0, min(1.0, (peak_motion - _FALL_LIKE_THRESHOLD) / 6.0))

    sleep_probability = max(0.0, min(1.0, 1.0 - mean_motion / _LIGHT_MAX))

    return MotionFeatures(
        activity_level=_activity_level(mean_motion),
        motion_intensity=mean_motion,
        motion_variability=variability,
        fall_probability=fall_probability,
        sleep_probability=sleep_probability,
        # step_rate/posture/orientation unavailable — see module docstring
    )
