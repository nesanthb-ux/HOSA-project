"""Doc 09 §10 Mobility Engine."""
from __future__ import annotations

from ..models import (BaselineDeviation, BaselineProfile, ClinicalRuleResult, FeatureVector,
                       SignalQuality, Subsystem, SubsystemResult, TrendSummary)
from ._scoring import combine_risk, compute_confidence, deviation_component, rule_component

_RULE_IDS = {"MOT-001", "MOT-002", "MOT-004"}


def score_mobility(features: FeatureVector, deviation: BaselineDeviation, trend: TrendSummary,
                    rules: list[ClinicalRuleResult], quality: SignalQuality,
                    baseline: BaselineProfile) -> SubsystemResult:
    rule_part, rule_names = rule_component(rules, _RULE_IDS)
    dev_part = deviation_component(deviation.motion_deviation)
    # No motion slope in TrendSummary (Doc 07 §19 doesn't define one) —
    # mobility risk relies on rules + deviation only.
    trend_part = 0.0

    risk = combine_risk(rule_part, dev_part, trend_part)
    confidence = compute_confidence(
        signal_quality=quality.imu_sqi,
        baseline_confidence=baseline.confidence,
        feature_confidence=quality.imu_sqi,
        rule_agreement=1.0 if rule_names else 0.5,
    )

    top_features = [f for f in ("activity_level", "fall_probability", "motion_intensity")
                     if getattr(features.motion, f, None) is not None]

    return SubsystemResult(
        subsystem=Subsystem.MOBILITY, risk_score=risk, confidence=confidence,
        severity=risk / 100.0, top_features=top_features,
        baseline_deviation=deviation.motion_deviation, clinical_evidence=rule_names,
    )
