"""Doc 08 §16 multimodal rules. MM-001/MM-004's respiratory-rate terms are
dropped (unavailable, see HARDWARE_SCOPE.md §4b). MM-003 ("Recovery
Pattern -> Decrease Severity") is not implemented as a standalone rule: with
persistence-gated triggering, CR-001/TMP-001/etc. simply stop triggering on
their own once physiology normalizes, achieving the same effect without a
rule whose entire job is to counteract other rules. MM-005 ("Sensor Failure
-> Ignore Clinical Rule") is implemented as a pre-check guard in engine.py,
not a rule that produces a ClinicalRuleResult."""
from __future__ import annotations

from ..models import ClinicalRuleResult, RulePriority, SensorType
from ._confidence import rule_confidence
from .context import RuleContext

_HIGH_HR_BPM = 100
_LOW_SPO2 = 94


def mm001_cardiorespiratory_stress(ctx: RuleContext) -> ClinicalRuleResult:
    hr = ctx.features.cardiac.heart_rate
    spo2 = ctx.features.respiratory.spo2
    condition = hr is not None and spo2 is not None and hr > _HIGH_HR_BPM and spo2 < _LOW_SPO2
    duration = ctx.persistence.update(ctx.patient_id, "MM-001", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.8, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="MM-001", rule_name="Cardiorespiratory Stress", priority=RulePriority.HIGH,
        severity=0.75 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate", "spo2"], supporting_sensors=[SensorType.PPG],
        recommended_action="Immediate Assessment",
    )


def mm002_possible_infection(ctx: RuleContext) -> ClinicalRuleResult:
    fever = (ctx.features.temperature.skin_temperature or 0) > 38.0
    hr_rising = (ctx.trend.heart_rate_slope or 0) > 0
    hrv_falling = (ctx.trend.hrv_slope or 0) < 0
    condition = fever and hr_rising and hrv_falling
    duration = ctx.persistence.update(ctx.patient_id, "MM-002", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.7, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="MM-002", rule_name="Possible Infection", priority=RulePriority.MODERATE,
        severity=0.65 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["skin_temperature", "heart_rate_trend", "hrv_slope"],
        supporting_sensors=[SensorType.PPG, SensorType.TEMPERATURE],
        recommended_action="Notify Clinical Staff",
    )


def mm004_possible_deterioration(ctx: RuleContext) -> ClinicalRuleResult:
    hr_rising = (ctx.trend.heart_rate_slope or 0) > 0
    hrv_falling = (ctx.trend.hrv_slope or 0) < 0
    condition = hr_rising and hrv_falling
    min_duration = 15 * 60
    duration = ctx.persistence.update(ctx.patient_id, "MM-004", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, 0.75, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="MM-004", rule_name="Possible Clinical Deterioration", priority=RulePriority.HIGH,
        severity=0.70 if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate_trend", "hrv_slope"], supporting_sensors=[SensorType.PPG],
        recommended_action="Immediate Assessment",
    )


RULES = [mm001_cardiorespiratory_stress, mm002_possible_infection, mm004_possible_deterioration]
