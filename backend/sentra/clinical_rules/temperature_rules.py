"""Doc 08 §14 temperature rules: TMP-001..003."""
from __future__ import annotations

from .. import config
from ..models import ClinicalRuleResult, RulePriority, SensorType
from ._confidence import rule_confidence
from .context import RuleContext


def _temp_cfg():
    return config.get_weights()["clinical_rules"]["temperature"]


def tmp001_fever_trend(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _temp_cfg()
    temp = ctx.features.temperature.skin_temperature
    condition = temp is not None and temp > cfg["tmp001_fever_c"]
    duration = ctx.persistence.update(ctx.patient_id, "TMP-001", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.9, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="TMP-001", rule_name="Fever Trend", priority=RulePriority.MODERATE,
        severity=0.55 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["skin_temperature"], supporting_sensors=[SensorType.TEMPERATURE],
        recommended_action="Increase Observation",
    )


def tmp002_rapid_rise(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _temp_cfg()
    slope_per_sample = ctx.trend.temperature_slope  # degC per ~15s history sample
    slope_per_hour = (slope_per_sample * (3600 / 15)) if slope_per_sample is not None else None
    condition = slope_per_hour is not None and slope_per_hour > cfg["tmp002_rapid_rise_c_per_hour"]
    duration = ctx.persistence.update(ctx.patient_id, "TMP-002", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.7, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="TMP-002", rule_name="Rapid Temperature Rise", priority=RulePriority.MODERATE,
        severity=0.60 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["temperature_slope"], supporting_sensors=[SensorType.TEMPERATURE],
        recommended_action="Notify Clinical Staff",
    )


def tmp003_persistent_elevated(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _temp_cfg()
    temp = ctx.features.temperature.skin_temperature
    baseline_temp = ctx.baseline.temperature_baseline
    condition = temp is not None and baseline_temp is not None and temp > baseline_temp + 1.0
    min_duration = cfg["tmp003_persistence_minutes"] * 60
    duration = ctx.persistence.update(ctx.patient_id, "TMP-003", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, 0.85, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="TMP-003", rule_name="Persistent Elevated Temperature", priority=RulePriority.MODERATE,
        severity=0.60 if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["skin_temperature", "baseline_deviation"], supporting_sensors=[SensorType.TEMPERATURE],
        recommended_action="Notify Clinical Staff",
    )


RULES = [tmp001_fever_trend, tmp002_rapid_rise, tmp003_persistent_elevated]
