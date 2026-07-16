"""Doc 10 §6-7 fusion pipeline."""
from __future__ import annotations

from .. import config
from ..models import (BaselineProfile, ClinicalRuleResult, FusionResult, SignalQuality,
                       SubsystemResult, TrendSummary)
from .flags import compute_flags
from .weighting import rank_evidence, weighted_subsystem_scores


def _clinical_confidence(rules: list[ClinicalRuleResult]) -> float:
    triggered = [r for r in rules if r.triggered]
    if not triggered:
        return 1.0  # nothing triggered to be uncertain about
    return sum(r.confidence for r in triggered) / len(triggered)


def _ml_confidence(subsystem_results: list[SubsystemResult]) -> float:
    if not subsystem_results:
        return 0.0
    return sum(s.confidence for s in subsystem_results) / len(subsystem_results)


def _trend_confidence(trend: TrendSummary) -> float:
    """Doc 10 §6 'Trend Confidence: measures consistency of deterioration
    over time' — approximated here by whether enough history exists to
    compute a trend at all (Doc 07 §14's slopes are None below 3 samples)."""
    available_slopes = [s for s in (trend.heart_rate_slope, trend.temperature_slope, trend.hrv_slope) if s is not None]
    return min(1.0, len(available_slopes) / 3.0) if available_slopes else 0.3


def fuse_confidence(quality: SignalQuality, baseline: BaselineProfile, rules: list[ClinicalRuleResult],
                     subsystem_results: list[SubsystemResult], trend: TrendSummary) -> FusionResult:
    weights = config.get_weights()["confidence_fusion"]

    signal_confidence = quality.overall_sqi
    baseline_confidence = baseline.confidence
    clinical_confidence = _clinical_confidence(rules)
    ml_confidence = _ml_confidence(subsystem_results)
    trend_confidence = _trend_confidence(trend)

    overall = (
        weights["signal"] * signal_confidence
        + weights["baseline"] * baseline_confidence
        + weights["clinical"] * clinical_confidence
        + weights["ml"] * ml_confidence
        + weights["trend"] * trend_confidence
    )
    overall = max(0.0, min(1.0, overall))

    return FusionResult(
        overall_confidence=overall,
        weighted_subsystem_scores=weighted_subsystem_scores(subsystem_results),
        evidence_ranking=rank_evidence(rules, subsystem_results),
        confidence_flags=compute_flags(quality, baseline, subsystem_results, rules),
    )
