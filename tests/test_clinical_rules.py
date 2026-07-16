"""Doc 08: persistence gating and rule triggering."""
from datetime import datetime, timedelta, timezone

from sentra.baseline_engine import BaselineEngine
from sentra.clinical_rules import ClinicalRuleEngine
from sentra.models import CardiacFeatures, FeatureVector, MotionFeatures, PatientState, RespiratoryFeatures, SignalQuality, TemperatureFeatures

SQ = SignalQuality(window_id="w", ppg_sqi=0.9, imu_sqi=0.9, temperature_sqi=0.9, overall_sqi=0.9, confidence=0.9)


def _fv(hr):
    return FeatureVector(
        window_id="w", patient_id="P1",
        cardiac=CardiacFeatures(heart_rate=hr, heart_rate_variability=5.0, beat_detection_confidence=0.9),
        respiratory=RespiratoryFeatures(spo2=97.0),
        motion=MotionFeatures(activity_level="sedentary", motion_intensity=0.5),
        temperature=TemperatureFeatures(skin_temperature=36.8),
    )


def test_tachycardia_does_not_trigger_on_a_single_window():
    engine = ClinicalRuleEngine()
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    now = datetime.now(timezone.utc)

    fv = _fv(160.0)  # well above CR-001's 120 bpm threshold
    profile, deviation, trend = baseline.process(now, fv, 0.9, 0.0, PatientState.NORMAL)
    rules, _severity = engine.evaluate("P1", now, fv, profile, deviation, trend, SQ)

    cr001 = next(r for r in rules if r.rule_id == "CR-001")
    assert cr001.triggered is False  # Doc 08 §11: needs 3 consecutive windows, not 1


def test_tachycardia_triggers_after_persistence_window():
    engine = ClinicalRuleEngine()
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    now = datetime.now(timezone.utc)

    rules = []
    for i in range(4):  # 4 windows * 15s step > CR-001's 3-window (45s) requirement
        fv = _fv(160.0)
        ts = now + timedelta(seconds=15 * i)
        profile, deviation, trend = baseline.process(ts, fv, 0.9, 0.0, PatientState.NORMAL)
        rules, _severity = engine.evaluate("P1", ts, fv, profile, deviation, trend, SQ)

    cr001 = next(r for r in rules if r.rule_id == "CR-001")
    assert cr001.triggered is True
    assert cr001.severity == 0.70


def test_condition_resolving_resets_persistence():
    engine = ClinicalRuleEngine()
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    now = datetime.now(timezone.utc)

    # Three windows of tachycardia (not quite enough to trigger CR-001's
    # 3-window requirement at exactly 3), then physiology normalizes.
    for i in range(2):
        fv = _fv(160.0)
        ts = now + timedelta(seconds=15 * i)
        profile, deviation, trend = baseline.process(ts, fv, 0.9, 0.0, PatientState.NORMAL)
        engine.evaluate("P1", ts, fv, profile, deviation, trend, SQ)

    fv_normal = _fv(75.0)
    ts = now + timedelta(seconds=30)
    profile, deviation, trend = baseline.process(ts, fv_normal, 0.9, 0.0, PatientState.NORMAL)
    rules, _severity = engine.evaluate("P1", ts, fv_normal, profile, deviation, trend, SQ)
    cr001 = next(r for r in rules if r.rule_id == "CR-001")
    assert cr001.triggered is False
    assert cr001.duration_seconds == 0.0


def test_poor_signal_quality_suppresses_all_rules():
    engine = ClinicalRuleEngine()
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    now = datetime.now(timezone.utc)
    poor_quality = SignalQuality(window_id="w", ppg_sqi=0.1, imu_sqi=0.1, temperature_sqi=0.1,
                                  overall_sqi=0.1, confidence=0.1)

    fv = _fv(200.0)  # extreme value that would otherwise obviously trigger rules
    profile, deviation, trend = baseline.process(now, fv, 0.1, 0.0, PatientState.NORMAL)
    rules, severity = engine.evaluate("P1", now, fv, profile, deviation, trend, poor_quality)

    assert rules == []
    assert severity == 0.0
