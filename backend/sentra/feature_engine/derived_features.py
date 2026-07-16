"""Doc 06 §11 derived multimodal features. cardiorespiratory_ratio and
activity_corrected_respiratory_rate need respiratory_rate, which is
unavailable on this hardware (HARDWARE_SCOPE.md §4b) and stay None."""
from __future__ import annotations

from ..models import CardiacFeatures, DerivedFeatures, MotionFeatures, RespiratoryFeatures, TemperatureFeatures

# "For each degree C of fever, heart rate rises roughly 8-10 bpm" is a
# widely cited clinical rule of thumb (not a SENTRA-invented constant).
_HR_RISE_PER_DEGREE_C = 9.0
_NORMAL_BODY_TEMP_C = 37.0

# Rough expected HR increase per activity tier, used only to compute
# motion_adjusted_heart_rate — an engineering approximation, not a
# validated clinical model.
_ACTIVITY_HR_OFFSET = {"sedentary": 0, "light": 10, "moderate": 25, "high": 45}


def compute_derived_features(
    cardiac: CardiacFeatures,
    respiratory: RespiratoryFeatures,
    motion: MotionFeatures,
    temperature: TemperatureFeatures,
) -> DerivedFeatures:
    derived = DerivedFeatures()

    if cardiac.heart_rate is not None and respiratory.respiratory_rate:
        derived.cardiorespiratory_ratio = cardiac.heart_rate / respiratory.respiratory_rate

    if cardiac.heart_rate is not None and motion.activity_level:
        offset = _ACTIVITY_HR_OFFSET.get(motion.activity_level, 0)
        derived.motion_adjusted_heart_rate = cardiac.heart_rate - offset

    if cardiac.heart_rate is not None and temperature.skin_temperature is not None:
        excess_temp = temperature.skin_temperature - _NORMAL_BODY_TEMP_C
        expected_rise = max(0.0, excess_temp) * _HR_RISE_PER_DEGREE_C
        derived.temperature_corrected_heart_rate = cardiac.heart_rate - expected_rise

    if respiratory.oxygen_trend is not None:
        derived.oxygen_recovery_rate = respiratory.oxygen_trend

    # activity_corrected_respiratory_rate needs respiratory_rate — unavailable.

    return derived
