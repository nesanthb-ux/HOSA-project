"""Doc 09 §9 Thermoregulation Engine."""
from __future__ import annotations

from ..models import (BaselineDeviation, BaselineProfile, ClinicalRuleResult, FeatureVector,
                       SignalQuality, Subsystem, SubsystemResult, TrendSummary)
from ._scoring import combine_risk, compute_confidence, deviation_component, rule_component, trend_component

_RULE_IDS = {"TMP-001", "TMP-002", "TMP-003", "MM-002"}


def score_temperature(features: FeatureVector, deviation: BaselineDeviation, trend: TrendSummary,
                       rules: list[ClinicalRuleResult], quality: SignalQuality,
                       baseline: BaselineProfile) -> SubsystemResult:
    rule_part, rule_names = rule_component(rules, _RULE_IDS)
    dev_part = deviation_component(deviation.temperature_deviation)
    trend_part = trend_component(trend.temperature_slope, worsening_direction=+1, full_scale=0.05)

    risk = combine_risk(rule_part, dev_part, trend_part)
    confidence = compute_confidence(
        signal_quality=quality.temperature_sqi,
        baseline_confidence=baseline.confidence,
        feature_confidence=quality.temperature_sqi,
        rule_agreement=1.0 if rule_names else 0.5,
    )

    top_features = [f for f in ("skin_temperature", "temperature_slope", "fever_probability")
                     if getattr(features.temperature, f, None) is not None]

    return SubsystemResult(
        subsystem=Subsystem.TEMPERATURE, risk_score=risk, confidence=confidence,
        severity=risk / 100.0, top_features=top_features,
        baseline_deviation=deviation.temperature_deviation, clinical_evidence=rule_names,
    )
