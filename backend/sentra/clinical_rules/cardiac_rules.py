"""Doc 08 §12 cardiac rules, CR-001 through CR-005 (CR-006/007 need ECG,
see docs/HARDWARE_SCOPE.md §3). CR-002 (severe tachycardia) is also wired
as a Doc 11 §24 Critical Override in priority/escalation.py — a rule
firing on an absolute physiological threshold shouldn't wait on baseline
confidence to ramp up (see _confidence.py's docstring)."""
from __future__ import annotations

from .. import config
from ..models import ClinicalRuleResult, RulePriority, SensorType
from ._confidence import rule_confidence
from .context import RuleContext


def _cardiac_cfg():
    return config.get_weights()["clinical_rules"]["cardiac"]


def cr001_persistent_tachycardia(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _cardiac_cfg()
    hr = ctx.features.cardiac.heart_rate
    condition = hr is not None and hr > cfg["cr001_tachycardia_bpm"]
    min_duration = cfg["cr001_persistence_windows"] * 15  # ~15s/window step, Doc 03 §8
    duration = ctx.persistence.update(ctx.patient_id, "CR-001", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, ctx.features.cardiac.beat_detection_confidence or 0.0, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="CR-001", rule_name="Persistent Tachycardia", priority=RulePriority.HIGH,
        severity=cfg["cr001_severity"] if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate"], supporting_sensors=[SensorType.PPG],
        recommended_action="Increase Observation",
    )


def cr002_severe_tachycardia(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _cardiac_cfg()
    hr = ctx.features.cardiac.heart_rate
    condition = hr is not None and hr > cfg["cr002_severe_tachycardia_bpm"]
    min_duration = cfg["cr002_persistence_windows"] * 15
    duration = ctx.persistence.update(ctx.patient_id, "CR-002", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, ctx.features.cardiac.beat_detection_confidence or 0.0, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="CR-002", rule_name="Severe Tachycardia", priority=RulePriority.CRITICAL,
        severity=cfg["cr002_severity"] if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate"], supporting_sensors=[SensorType.PPG],
        recommended_action="Emergency Response",
    )


def cr003_bradycardia(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _cardiac_cfg()
    hr = ctx.features.cardiac.heart_rate
    condition = hr is not None and hr < cfg["cr003_bradycardia_bpm"]
    min_duration = cfg["cr003_persistence_windows"] * 15
    duration = ctx.persistence.update(ctx.patient_id, "CR-003", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, ctx.features.cardiac.beat_detection_confidence or 0.0, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="CR-003", rule_name="Bradycardia", priority=RulePriority.HIGH,
        severity=cfg["cr003_severity"] if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate"], supporting_sensors=[SensorType.PPG],
        recommended_action="Immediate Assessment",
    )


def cr004_rapid_hr_increase(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _cardiac_cfg()
    slope = ctx.trend.heart_rate_slope  # bpm per history sample (~15s step)
    window_minutes = cfg["cr004_window_minutes"]
    samples_per_window = max(1, round(window_minutes * 60 / 15))
    projected_increase = (slope * samples_per_window) if slope is not None else None
    condition = projected_increase is not None and projected_increase > cfg["cr004_rapid_increase_bpm"]
    duration = ctx.persistence.update(ctx.patient_id, "CR-004", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.8, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="CR-004", rule_name="Rapid HR Increase", priority=RulePriority.MODERATE,
        severity=0.55 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate_trend"], supporting_sensors=[SensorType.PPG],
        recommended_action="Notify Clinical Staff",
    )


def cr005_low_hrv(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _cardiac_cfg()
    hrv = ctx.features.cardiac.heart_rate_variability
    baseline_hrv = ctx.baseline.hrv_baseline
    condition = (
        hrv is not None and baseline_hrv is not None and baseline_hrv > 0
        and hrv < baseline_hrv * (1 - cfg["cr005_hrv_drop_fraction"])
    )
    min_duration = cfg["cr005_persistence_minutes"] * 60
    duration = ctx.persistence.update(ctx.patient_id, "CR-005", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, 0.6, duration, min_duration)  # HRV proxy only, see HARDWARE_SCOPE.md §4b
    return ClinicalRuleResult(
        rule_id="CR-005", rule_name="Low HRV", priority=RulePriority.MODERATE,
        severity=0.50 if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["heart_rate_variability"], supporting_sensors=[SensorType.PPG],
        recommended_action="Increase Observation",
    )


RULES = [cr001_persistent_tachycardia, cr002_severe_tachycardia, cr003_bradycardia,
         cr004_rapid_hr_increase, cr005_low_hrv]
