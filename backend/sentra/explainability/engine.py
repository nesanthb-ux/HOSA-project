"""Doc 12 §7/§23 explainability pipeline: PriorityResult + evidence -> ExplanationResult."""
from __future__ import annotations

from ..models import (BaselineDeviation, BaselineProfile, ExplanationResult, FusionResult,
                       PriorityResult, StateHistory, TrendSummary)
from .summary_generator import baseline_comparison, confidence_summary, natural_language_summary, trend_explanation
from .timeline import build_timeline


def explain(priority: PriorityResult, fusion: FusionResult, trend: TrendSummary,
            deviation: BaselineDeviation, baseline: BaselineProfile,
            state_history: list[StateHistory], overall_sqi: float) -> ExplanationResult:
    ranked = fusion.evidence_ranking
    primary = ranked[0].label if ranked else ""
    secondary = [e.label for e in ranked[1:4]]

    conf_text = confidence_summary(priority.confidence, overall_sqi)
    summary_text = natural_language_summary(priority, primary, conf_text)

    return ExplanationResult(
        patient_id=priority.patient_id,
        priority_summary=summary_text,
        primary_reason=primary or "No significant findings",
        secondary_reasons=secondary + [trend_explanation(trend), baseline_comparison(deviation, baseline)],
        evidence=ranked,
        confidence_summary=conf_text,
        recommended_action=priority.recommended_action,
        timeline=build_timeline(state_history),
    )
