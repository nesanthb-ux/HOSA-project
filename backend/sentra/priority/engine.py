"""Doc 11 §32 processing pipeline: the central SENTRA decision-making module."""
from __future__ import annotations

from datetime import datetime

from .. import config
from ..models import (BaselineDeviation, ClinicalRuleResult, FeatureVector, FusionResult,
                       PatientState, PriorityResult, SignalQuality, SubsystemResult, TrendSummary)
from .escalation import check_critical_override
from .priority_calculator import calculate_priority
from .state_machine import PriorityStateMachine
from .suppression import should_suppress

_RECOMMENDATIONS = {
    PatientState.NORMAL: "Continue Monitoring",
    PatientState.WATCH: "Increase Observation",
    PatientState.CONCERN: "Notify Clinical Staff",
    PatientState.HIGH_PRIORITY: "Immediate Assessment",
    PatientState.CRITICAL: "Emergency Response",
}


def _level_for_score(score: float) -> PatientState:
    t = config.get_weights()["priority"]["thresholds"]
    if score >= t["critical"]:
        return PatientState.CRITICAL
    if score >= t["high_priority"]:
        return PatientState.HIGH_PRIORITY
    if score >= t["concern"]:
        return PatientState.CONCERN
    if score >= t["watch"]:
        return PatientState.WATCH
    return PatientState.NORMAL


class PriorityEngine:
    def __init__(self):
        self.state_machine = PriorityStateMachine()

    def evaluate(self, patient_id: str, ts: datetime, features: FeatureVector,
                 deviation: BaselineDeviation, trend: TrendSummary,
                 rules: list[ClinicalRuleResult], clinical_severity: float,
                 subsystem_results: list[SubsystemResult], fusion: FusionResult,
                 quality: SignalQuality) -> PriorityResult:
        critical_override, override_reason = check_critical_override(features, rules)

        raw_score, adjusted_score = calculate_priority(
            clinical_severity, subsystem_results, trend, deviation, fusion, features
        )

        target_level = PatientState.CRITICAL if critical_override else _level_for_score(adjusted_score)
        reason = override_reason or "priority score threshold"
        state = self.state_machine.transition(patient_id, target_level, ts, reason, critical_override)

        suppressed = should_suppress(quality, adjusted_score / 100.0, critical_override)
        alert_required = (not suppressed) and state != PatientState.NORMAL

        top_contributors = [e.label for e in fusion.evidence_ranking[:3]]
        reason_codes = [r.rule_id for r in rules if r.triggered]
        if critical_override:
            reason_codes.insert(0, "CRITICAL_OVERRIDE")

        return PriorityResult(
            patient_id=patient_id,
            priority_score=adjusted_score,
            priority_level=target_level,
            confidence=fusion.overall_confidence,
            state=state,
            trend=trend.overall_trend,
            reason_codes=reason_codes,
            top_contributors=top_contributors,
            recommended_action=_RECOMMENDATIONS[state],
            alert_required=alert_required,
        )
