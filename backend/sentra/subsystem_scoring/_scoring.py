"""Shared scoring helpers for the four subsystem engines (Doc 09 §14
generic risk formula: Risk = FeatureScore + TrendScore + BaselineDeviation +
RuleContribution -> Quality Weighting -> Clamp 0-100).

Since the Clinical Rule Engine (Doc 08) already encodes the clinically
meaningful thresholds for each subsystem, "FeatureScore" and
"RuleContribution" are combined here into one rule-driven component rather
than re-deriving separate raw-threshold logic — avoiding two independently
tuned copies of the same clinical knowledge.
"""
from __future__ import annotations

from .. import config
from ..models import ClinicalRuleResult, SubsystemResult


def rule_component(rules: list[ClinicalRuleResult], rule_ids: set[str]) -> tuple[float, list[str]]:
    """Max severity*confidence among this subsystem's triggered rules (max,
    not sum/average, so one clearly critical rule isn't diluted by several
    mild ones) + the names of contributing rules."""
    relevant = [r for r in rules if r.triggered and r.rule_id in rule_ids]
    if not relevant:
        return 0.0, []
    best = max(relevant, key=lambda r: r.severity * r.confidence)
    return best.severity * best.confidence, [r.rule_name for r in relevant]


def deviation_component(deviation: float | None, full_scale_std: float = 3.0) -> float:
    """0-1: baseline deviation expressed in std units, saturating at
    full_scale_std (Doc 07 §11's normalized deviation IS already in std
    units, so this just caps it to a 0-1 contribution)."""
    if deviation is None:
        return 0.0
    return max(0.0, min(1.0, deviation / full_scale_std))


def trend_component(slope: float | None, worsening_direction: int, full_scale: float) -> float:
    """0-1: how much the trend is moving in the worsening direction
    (+1 = higher is worse, -1 = lower is worse)."""
    if slope is None or full_scale <= 0:
        return 0.0
    signed = slope * worsening_direction
    return max(0.0, min(1.0, signed / full_scale))


def combine_risk(rule_part: float, deviation_part: float, trend_part: float) -> float:
    risk_fraction = 0.55 * rule_part + 0.25 * deviation_part + 0.20 * trend_part
    return max(0.0, min(100.0, risk_fraction * 100.0))


def compute_confidence(signal_quality: float, baseline_confidence: float, feature_confidence: float,
                        rule_agreement: float, model_stability: float = 0.9) -> float:
    """Doc 09 §12."""
    w = config.get_weights()["subsystem_scoring"]["confidence"]
    confidence = (
        w["signal_quality"] * signal_quality
        + w["baseline"] * baseline_confidence
        + w["model_stability"] * model_stability
        + w["feature_confidence"] * feature_confidence
        + w["rule_agreement"] * rule_agreement
    )
    return max(0.0, min(1.0, confidence))
