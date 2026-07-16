"""Doc 07: adaptive EMA baseline, deviation, calibration seeding, drift protection."""
from datetime import datetime, timedelta, timezone

from sentra.baseline_engine import BaselineEngine
from sentra.models import CardiacFeatures, FeatureVector, MotionFeatures, PatientState, RespiratoryFeatures, TemperatureFeatures


def _fv(hr, temp=36.8, activity="sedentary"):
    return FeatureVector(
        window_id="w", patient_id="P1",
        cardiac=CardiacFeatures(heart_rate=hr, heart_rate_variability=5.0),
        respiratory=RespiratoryFeatures(spo2=97.0),
        motion=MotionFeatures(activity_level=activity, motion_intensity=0.5),
        temperature=TemperatureFeatures(skin_temperature=temp),
    )


def test_calibration_seeds_from_reference_range():
    engine = BaselineEngine()
    engine.calibrate("P1", "older_adult_65plus")
    profile, deviation, _trend = engine.process(
        datetime.now(timezone.utc), _fv(75.0), overall_sqi=0.9, rule_severity=0.0, state=PatientState.NORMAL
    )
    # older_adult_65plus reference hr_mean=75 — a first reading exactly at
    # that mean should show ~zero deviation, not the "no baseline yet" case.
    assert profile.heart_rate_baseline == 75.0
    assert deviation.heart_rate_deviation is not None


def test_baseline_converges_toward_true_patient_value_over_time():
    engine = BaselineEngine()
    engine.calibrate("P1", "older_adult_65plus")  # seeds hr_mean=75
    now = datetime.now(timezone.utc)
    true_hr = 88.0  # this patient's real resting HR differs from the reference

    for i in range(60):
        engine.process(now + timedelta(seconds=15 * i), _fv(true_hr), overall_sqi=0.95,
                        rule_severity=0.0, state=PatientState.NORMAL)

    profile = engine.get_profile("P1")
    # Should have moved substantially toward 88 from the seeded 75, without
    # having necessarily converged all the way after only 60 windows.
    assert 75.0 < profile.heart_rate_baseline < 88.0
    assert profile.heart_rate_baseline > 82.0  # meaningfully closer to truth than to the seed


def test_deviation_is_normalized_by_std_not_raw_difference():
    engine = BaselineEngine()
    engine.calibrate("P1", "adult_18_64yr")  # hr_mean=75, hr_std=12
    _profile, deviation, _trend = engine.process(
        datetime.now(timezone.utc), _fv(87.0), overall_sqi=0.9, rule_severity=0.0, state=PatientState.NORMAL
    )
    # (87-75)/12 = 1.0
    assert deviation.heart_rate_deviation == 1.0
