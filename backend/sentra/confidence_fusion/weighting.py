"""Doc 10 §8 dynamic evidence weighting + §11 evidence ranking."""
from __future__ import annotations

from ..models import ClinicalRuleResult, RankedEvidence, SubsystemResult


def weighted_subsystem_scores(subsystem_results: list[SubsystemResult]) -> dict[str, float]:
    """Doc 10 §8: evidence with higher confidence contributes more —
    weight each subsystem's risk score by its own confidence."""
    return {s.subsystem.value: s.risk_score * s.confidence for s in subsystem_results}


def rank_evidence(rules: list[ClinicalRuleResult], subsystem_results: list[SubsystemResult]) -> list[RankedEvidence]:
    entries: list[RankedEvidence] = []

    triggered_rules = [r for r in rules if r.triggered]
    total_rule_weight = sum(r.severity * r.confidence for r in triggered_rules) or 1.0
    for r in triggered_rules:
        influence = (r.severity * r.confidence) / total_rule_weight
        entries.append(RankedEvidence(label=r.rule_name, confidence=r.confidence, influence=influence))

    total_subsystem_weight = sum(s.risk_score * s.confidence for s in subsystem_results) or 1.0
    for s in subsystem_results:
        if s.risk_score <= 0:
            continue
        influence = (s.risk_score * s.confidence) / total_subsystem_weight * 0.5  # subsystems share half the ranking weight with rules
        entries.append(RankedEvidence(label=f"{s.subsystem.value.title()} Risk", confidence=s.confidence, influence=influence))

    entries.sort(key=lambda e: e.influence, reverse=True)
    return entries
