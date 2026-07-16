"""Doc 08 §15 motion rules: MOT-001, MOT-002, MOT-004. MOT-003 ("Sudden
Collapse": acceleration spike followed by no motion) is not implemented as
a separate rule — feature_engine/imu_features.py's fall_probability already
looks for a peak-motion spike within the window (see
motion_mpu6050.h::isFallLike in firmware), so MOT-001 covers the same
physical event MOT-003 describes rather than duplicating it."""
from __future__ import annotations

from .. import config
from ..models import ClinicalRuleResult, RulePriority, SensorType
from ._confidence import rule_confidence
from .context import RuleContext


def _motion_cfg():
    return config.get_weights()["clinical_rules"]["motion"]


def mot001_fall_suspected(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _motion_cfg()
    fall_prob = ctx.features.motion.fall_probability
    condition = fall_prob is not None and fall_prob > cfg["mot001_fall_probability"]
    duration = ctx.persistence.update(ctx.patient_id, "MOT-001", condition, ctx.ts)
    triggered = condition  # no persistence requirement — a fall is immediate

    confidence = rule_confidence(ctx, fall_prob or 0.0, 15.0, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="MOT-001", rule_name="Fall Suspected", priority=RulePriority.CRITICAL,
        severity=0.90 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["fall_probability"], supporting_sensors=[SensorType.IMU],
        recommended_action="Emergency Response",
    )


def mot002_prolonged_inactivity(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _motion_cfg()
    activity = ctx.features.motion.activity_level
    condition = activity == "sedentary"
    min_duration = cfg["mot002_inactivity_hours"] * 3600
    duration = ctx.persistence.update(ctx.patient_id, "MOT-002", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, 0.7, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="MOT-002", rule_name="Prolonged Inactivity", priority=RulePriority.LOW,
        severity=0.30 if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["activity_level"], supporting_sensors=[SensorType.IMU],
        recommended_action="Increase Observation",
    )


def mot004_abnormal_activity(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _motion_cfg()
    motion = ctx.features.motion.motion_intensity
    baseline_motion = ctx.baseline.activity_baseline
    condition = False
    if motion is not None and baseline_motion:
        deviation_pct = abs(motion - baseline_motion) / baseline_motion * 100
        condition = deviation_pct > cfg["mot004_activity_deviation_pct"]
    duration = ctx.persistence.update(ctx.patient_id, "MOT-004", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.65, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="MOT-004", rule_name="Abnormal Activity", priority=RulePriority.LOW,
        severity=0.40 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["motion_intensity"], supporting_sensors=[SensorType.IMU],
        recommended_action="Increase Observation",
    )


RULES = [mot001_fall_suspected, mot002_prolonged_inactivity, mot004_abnormal_activity]
