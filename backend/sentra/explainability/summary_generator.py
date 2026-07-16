"""Doc 12 §12-19: confidence summary, trend explanation, baseline
comparison, and natural-language summary generation."""
from __future__ import annotations

from .. import config
from ..models import BaselineDeviation, BaselineProfile, PriorityResult, TrendSummary


def confidence_summary(confidence: float, overall_sqi: float) -> str:
    categories = config.get_weights()["confidence_fusion"]["categories"]
    if confidence >= categories["very_high"]:
        label = "Very High"
    elif confidence >= categories["high"]:
        label = "High"
    elif confidence >= categories["moderate"]:
        label = "Moderate"
    elif confidence >= categories["low"]:
        label = "Low"
    else:
        label = "Very Low"
    quality_word = "Excellent" if overall_sqi >= 0.9 else "Good" if overall_sqi >= 0.75 else "Reduced"
    return f"{label} ({confidence * 100:.0f}%) — {quality_word} signal quality"


def trend_explanation(trend: TrendSummary) -> str:
    if trend.overall_trend == "worsening":
        return "Physiology trending worse over the recent monitoring window"
    if trend.overall_trend == "improving":
        return "Physiology trending toward recovery"
    return "Physiology stable over the recent monitoring window"


def baseline_comparison(deviation: BaselineDeviation, baseline: BaselineProfile) -> str:
    if not baseline.learning_complete:
        return "Personal baseline still learning — reference range not yet fully established"
    if deviation.overall_deviation is None:
        return "No baseline comparison available"
    if deviation.overall_deviation < 1.0:
        return "Within personal baseline range"
    return f"{deviation.overall_deviation:.1f} standard deviations from personal baseline"


def natural_language_summary(priority: PriorityResult, primary_reason: str, confidence_text: str) -> str:
    if not primary_reason or priority.state.value == "NORMAL":
        return f"Patient physiology is stable. {confidence_text}."
    return (
        f"Patient priority is {priority.state.value.replace('_', ' ').title()} "
        f"due to {primary_reason.lower()}. {confidence_text}."
    )
