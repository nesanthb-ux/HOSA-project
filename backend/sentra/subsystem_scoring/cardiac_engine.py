"""Doc 09 §7 Cardiac Risk Engine, scored from PPG-derived HR/HRV (docs/HARDWARE_SCOPE.md)."""
from __future__ import annotations

from ..models import (BaselineDeviation, BaselineProfile, ClinicalRuleResult, FeatureVector,
                       SignalQuality, Subsystem, SubsystemResult, TrendSummary)
from ._scoring import combine_risk, compute_confidence, deviation_component, rule_component, trend_component

_RULE_IDS = {"CR-001", "CR-002", "CR-003", "CR-004", "CR-005", "MM-001", "MM-002", "MM-004"}


def score_cardiac(features: FeatureVector, deviation: BaselineDeviation, trend: TrendSummary,
                   rules: list[ClinicalRuleResult], quality: SignalQuality,
                   baseline: BaselineProfile) -> SubsystemResult:
    rule_part, rule_names = rule_component(rules, _RULE_IDS)
    dev_part = deviation_component(deviation.heart_rate_deviation)
    trend_part = trend_component(trend.heart_rate_slope, worsening_direction=+1, full_scale=1.0)

    risk = combine_risk(rule_part, dev_part, trend_part)
    confidence = compute_confidence(
        signal_quality=quality.ppg_sqi,
        baseline_confidence=baseline.confidence,
        feature_confidence=features.cardiac.beat_detection_confidence or 0.0,
        rule_agreement=1.0 if rule_names else 0.5,
    )

    top_features = [f for f in ("heart_rate", "heart_rate_trend", "heart_rate_variability")
                     if getattr(features.cardiac, f, None) is not None]

    return SubsystemResult(
        subsystem=Subsystem.CARDIAC, risk_score=risk, confidence=confidence,
        severity=risk / 100.0, top_features=top_features,
        baseline_deviation=deviation.heart_rate_deviation, clinical_evidence=rule_names,
    )
