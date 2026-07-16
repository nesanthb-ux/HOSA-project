"""Doc 10: confidence weighting and flags."""
from sentra.baseline_engine.profile import PatientBaseline
from sentra.confidence_fusion import fuse_confidence
from sentra.models import ConfidenceFlag, SignalQuality, TrendSummary


def test_low_signal_quality_flags_and_lowers_confidence():
    baseline = PatientBaseline("P1", age_band="adult_18_64yr")
    profile = baseline.to_profile()
    trend = TrendSummary(overall_trend="stable")

    good_quality = SignalQuality(window_id="w", ppg_sqi=0.95, imu_sqi=0.95, temperature_sqi=0.95,
                                  overall_sqi=0.95, confidence=0.95)
    poor_quality = SignalQuality(window_id="w", ppg_sqi=0.2, imu_sqi=0.2, temperature_sqi=0.2,
                                  overall_sqi=0.2, confidence=0.2)

    good_result = fuse_confidence(good_quality, profile, [], [], trend)
    poor_result = fuse_confidence(poor_quality, profile, [], [], trend)

    assert poor_result.overall_confidence < good_result.overall_confidence
    assert ConfidenceFlag.LOW_SENSOR_CONFIDENCE in poor_result.confidence_flags
    assert ConfidenceFlag.HIGH_SENSOR_NOISE in poor_result.confidence_flags


def test_new_patient_flagged_insufficient_history():
    baseline = PatientBaseline("P1")  # no calibration, no observations yet
    profile = baseline.to_profile()
    trend = TrendSummary(overall_trend="stable")
    quality = SignalQuality(window_id="w", ppg_sqi=0.9, imu_sqi=0.9, temperature_sqi=0.9,
                             overall_sqi=0.9, confidence=0.9)

    result = fuse_confidence(quality, profile, [], [], trend)
    assert ConfidenceFlag.INSUFFICIENT_HISTORY in result.confidence_flags
