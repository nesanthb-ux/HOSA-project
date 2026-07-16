"""Doc 11: state machine escalation cap, critical override bypass, suppression."""
from datetime import datetime, timedelta, timezone

from sentra.baseline_engine import BaselineEngine
from sentra.clinical_rules import ClinicalRuleEngine
from sentra.confidence_fusion import fuse_confidence
from sentra.models import (CardiacFeatures, FeatureVector, MotionFeatures, PatientState,
                            RespiratoryFeatures, SignalQuality, TemperatureFeatures, state_rank)
from sentra.priority import PriorityEngine
from sentra.subsystem_scoring import evaluate_subsystems

SQ = SignalQuality(window_id="w", ppg_sqi=0.9, imu_sqi=0.9, temperature_sqi=0.9, overall_sqi=0.9, confidence=0.9)


def _fv(hr, spo2=97.0):
    return FeatureVector(
        window_id="w", patient_id="P1",
        cardiac=CardiacFeatures(heart_rate=hr, heart_rate_variability=5.0, beat_detection_confidence=0.9),
        respiratory=RespiratoryFeatures(spo2=spo2),
        motion=MotionFeatures(activity_level="sedentary", motion_intensity=0.5),
        temperature=TemperatureFeatures(skin_temperature=36.8),
    )


def _run_one_window(baseline, rules_engine, priority_engine, ts, hr, spo2=97.0):
    fv = _fv(hr, spo2)
    current_state = priority_engine.state_machine.current_state("P1")
    profile, deviation, trend = baseline.process(ts, fv, 0.9, 0.0, current_state)
    rules, severity = rules_engine.evaluate("P1", ts, fv, profile, deviation, trend, SQ)
    subsystems = evaluate_subsystems(fv, deviation, trend, rules, SQ, profile)
    fusion = fuse_confidence(SQ, profile, rules, subsystems, trend)
    return priority_engine.evaluate("P1", ts, fv, deviation, trend, rules, severity, subsystems, fusion, SQ)


def test_state_never_jumps_more_than_one_level_without_override():
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    rules_engine = ClinicalRuleEngine()
    priority_engine = PriorityEngine()
    now = datetime.now(timezone.utc)

    # A single moderately-elevated-but-not-critical reading shouldn't be
    # able to jump straight past WATCH into CONCERN/HIGH_PRIORITY.
    result = _run_one_window(baseline, rules_engine, priority_engine, now, hr=130.0)
    assert state_rank(result.state) <= state_rank(PatientState.WATCH)


def test_critical_override_bypasses_gradual_escalation():
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    rules_engine = ClinicalRuleEngine()
    priority_engine = PriorityEngine()
    now = datetime.now(timezone.utc)

    # Severe tachycardia (CR-002, >150bpm) needs 2 persistence windows
    # (30s); once satisfied it's a Doc 11 §24 Critical Override and should
    # jump straight to CRITICAL even from a cold start at NORMAL.
    result = None
    for i in range(4):
        ts = now + timedelta(seconds=15 * i)
        result = _run_one_window(baseline, rules_engine, priority_engine, ts, hr=165.0, spo2=90.0)

    assert result.state == PatientState.CRITICAL
    assert result.alert_required is True
    assert "CRITICAL_OVERRIDE" in result.reason_codes


def test_stable_patient_stays_normal():
    baseline = BaselineEngine()
    baseline.calibrate("P1", "adult_18_64yr")
    rules_engine = ClinicalRuleEngine()
    priority_engine = PriorityEngine()
    now = datetime.now(timezone.utc)

    result = None
    for i in range(5):
        ts = now + timedelta(seconds=15 * i)
        result = _run_one_window(baseline, rules_engine, priority_engine, ts, hr=75.0)

    assert result.state == PatientState.NORMAL
    assert result.alert_required is False


def test_confidence_never_increases_priority_above_raw_score():
    from sentra.priority.priority_calculator import calculate_priority
    from sentra.models import BaselineDeviation, FusionResult, TrendSummary

    deviation = BaselineDeviation(overall_deviation=2.5)  # some raw priority to work with
    trend = TrendSummary(overall_trend="worsening", heart_rate_slope=0.8)
    fusion_full_confidence = FusionResult(overall_confidence=1.0, weighted_subsystem_scores={})
    fusion_low_confidence = FusionResult(overall_confidence=0.2, weighted_subsystem_scores={})
    fv = _fv(75.0)

    raw_a, adjusted_a = calculate_priority(0.0, [], trend, deviation, fusion_full_confidence, fv)
    assert adjusted_a <= raw_a

    raw_b, adjusted_b = calculate_priority(0.0, [], trend, deviation, fusion_low_confidence, fv)
    assert adjusted_b < raw_b  # low confidence must strictly reduce, never raise, priority
    assert adjusted_b < adjusted_a
