"""Doc 09 §8 Respiratory Risk Engine, scored from SpO2 (respiratory_rate
unavailable, see docs/HARDWARE_SCOPE.md §4b)."""
from __future__ import annotations

from ..models import (BaselineDeviation, BaselineProfile, ClinicalRuleResult, FeatureVector,
                       SignalQuality, Subsystem, SubsystemResult, TrendSummary)
from ._scoring import combine_risk, compute_confidence, deviation_component, rule_component, trend_component

_RULE_IDS = {"RR-003", "RR-004", "MM-001"}


def score_respiratory(features: FeatureVector, deviation: BaselineDeviation, trend: TrendSummary,
                       rules: list[ClinicalRuleResult], quality: SignalQuality,
                       baseline: BaselineProfile) -> SubsystemResult:
    rule_part, rule_names = rule_component(rules, _RULE_IDS)
    # No direct SpO2 baseline-deviation field in BaselineDeviation (Doc 02
    # doesn't define one); fall back to the SpO2 trend as the deviation
    # signal when a personal baseline hasn't been established.
    spo2 = features.respiratory.spo2
    spo2_deficit = max(0.0, (95.0 - spo2) / 5.0) if spo2 is not None else 0.0  # 95% baseline-ish, 5pt = full scale
    dev_part = min(1.0, spo2_deficit)
    trend_part = trend_component(features.respiratory.oxygen_trend, worsening_direction=-1, full_scale=0.5)

    risk = combine_risk(rule_part, dev_part, trend_part)
    confidence = compute_confidence(
        signal_quality=quality.ppg_sqi,
        baseline_confidence=baseline.confidence,
        feature_confidence=quality.ppg_sqi,
        rule_agreement=1.0 if rule_names else 0.5,
    )

    top_features = [f for f in ("spo2", "oxygen_trend") if getattr(features.respiratory, f, None) is not None]

    return SubsystemResult(
        subsystem=Subsystem.RESPIRATORY, risk_score=risk, confidence=confidence,
        severity=risk / 100.0, top_features=top_features,
        baseline_deviation=deviation.overall_deviation, clinical_evidence=rule_names,
    )
