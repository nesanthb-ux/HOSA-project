"""Doc 08 §13 respiratory rules. RR-001 (Tachypnea), RR-002 (Bradypnea), and
RR-005 (Respiratory Instability) all need a directly measured respiratory
rate, which this hardware cannot produce (docs/HARDWARE_SCOPE.md §4b) and
are therefore not implemented — evaluating them against a fabricated RR
value would violate CLAUDE.md's "never fabricate medical values". RR-003
and RR-004 use SpO2, which is directly measured, and are implemented."""
from __future__ import annotations

from .. import config
from ..models import ClinicalRuleResult, RulePriority, SensorType
from ._confidence import rule_confidence
from .context import RuleContext


def _resp_cfg():
    return config.get_weights()["clinical_rules"]["respiratory"]


def rr003_persistent_hypoxia(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _resp_cfg()
    spo2 = ctx.features.respiratory.spo2
    condition = spo2 is not None and spo2 < cfg["rr003_hypoxia_spo2"]
    min_duration = cfg["rr003_persistence_windows"] * 15
    duration = ctx.persistence.update(ctx.patient_id, "RR-003", condition, ctx.ts)
    triggered = condition and duration >= min_duration

    confidence = rule_confidence(ctx, 0.85, duration, min_duration)
    return ClinicalRuleResult(
        rule_id="RR-003", rule_name="Persistent Hypoxia", priority=RulePriority.CRITICAL,
        severity=0.85 if triggered else 0.0, confidence=confidence if triggered else 0.0,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["spo2"], supporting_sensors=[SensorType.PPG],
        recommended_action="Immediate Assessment",
    )


def rr004_rapid_oxygen_drop(ctx: RuleContext) -> ClinicalRuleResult:
    cfg = _resp_cfg()
    spo2_trend = ctx.features.respiratory.oxygen_trend
    window_minutes = cfg["rr004_window_minutes"]
    samples_per_window = max(1, round(window_minutes * 60 / 15))
    projected_drop = (-spo2_trend * samples_per_window) if spo2_trend is not None else None
    condition = projected_drop is not None and projected_drop > cfg["rr004_spo2_drop_pct"]
    duration = ctx.persistence.update(ctx.patient_id, "RR-004", condition, ctx.ts)
    triggered = condition

    confidence = rule_confidence(ctx, 0.75, duration, 15.0) if triggered else 0.0
    return ClinicalRuleResult(
        rule_id="RR-004", rule_name="Rapid Oxygen Drop", priority=RulePriority.HIGH,
        severity=0.70 if triggered else 0.0, confidence=confidence,
        triggered=triggered, duration_seconds=duration,
        supporting_features=["oxygen_trend"], supporting_sensors=[SensorType.PPG],
        recommended_action="Notify Clinical Staff",
    )


RULES = [rr003_persistent_hypoxia, rr004_rapid_oxygen_drop]
