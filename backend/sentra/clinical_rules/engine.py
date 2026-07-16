"""Doc 08 §6 rule evaluation pipeline + §19 severity aggregation."""
from __future__ import annotations

from datetime import datetime

from ..models import BaselineDeviation, BaselineProfile, ClinicalRuleResult, FeatureVector, SignalQuality, TrendSummary
from . import cardiac_rules, motion_rules, multimodal_rules, respiratory_rules, temperature_rules
from .context import RuleContext
from .persistence import PersistenceTracker

IGNORE_SQI_THRESHOLD = 0.40  # Doc 05 §12/§17, enacts Doc 08 §16 MM-005

ALL_RULES = (
    cardiac_rules.RULES + respiratory_rules.RULES + temperature_rules.RULES
    + motion_rules.RULES + multimodal_rules.RULES
)

_PRIORITY_WEIGHT = {"CRITICAL": 1.0, "HIGH": 0.75, "MODERATE": 0.5, "LOW": 0.25}


def aggregate_severity(triggered: list[ClinicalRuleResult]) -> float:
    """Doc 08 §19: weighted average of triggered rules, weighted by
    priority x confidence so persistent, well-supported rules dominate
    transient or low-confidence ones (Doc 08 §11, §18)."""
    if not triggered:
        return 0.0
    weighted_sum = 0.0
    total_weight = 0.0
    for r in triggered:
        weight = _PRIORITY_WEIGHT.get(r.priority.value, 0.5) * max(r.confidence, 0.05)
        weighted_sum += weight * r.severity
        total_weight += weight
    return weighted_sum / total_weight if total_weight else 0.0


class ClinicalRuleEngine:
    def __init__(self):
        self.persistence = PersistenceTracker()

    def evaluate(self, patient_id: str, ts: datetime, features: FeatureVector,
                 baseline: BaselineProfile, deviation: BaselineDeviation,
                 trend: TrendSummary, quality: SignalQuality) -> tuple[list[ClinicalRuleResult], float]:
        if quality.overall_sqi < IGNORE_SQI_THRESHOLD:
            return [], 0.0

        ctx = RuleContext(
            patient_id=patient_id, ts=ts, features=features, baseline=baseline,
            deviation=deviation, trend=trend, quality=quality, persistence=self.persistence,
        )

        results = [rule(ctx) for rule in ALL_RULES]
        triggered = [r for r in results if r.triggered]
        severity = aggregate_severity(triggered)
        return results, severity
