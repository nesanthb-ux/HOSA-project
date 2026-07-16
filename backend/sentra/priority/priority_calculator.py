"""Doc 11 §11 priority equation + §13-16 component scores."""
from __future__ import annotations

from .. import config
from ..models import BaselineDeviation, FusionResult, Subsystem, SubsystemResult, TrendSummary
from .context import compute_context_modifier

_TREND_HR_FULL_SCALE = 1.0     # bpm per ~15s history sample — matches subsystem_scoring's convention
_TREND_TEMP_FULL_SCALE = 0.05  # degC per ~15s sample


def subsystem_risk_score(subsystem_results: list[SubsystemResult]) -> float:
    """Doc 11 §13: weighted average across the four subsystems."""
    split = config.get_weights()["priority"]["subsystem_split"]
    by_subsystem = {s.subsystem: s.risk_score for s in subsystem_results}
    return (
        split["cardiac"] * by_subsystem.get(Subsystem.CARDIAC, 0.0)
        + split["respiratory"] * by_subsystem.get(Subsystem.RESPIRATORY, 0.0)
        + split["temperature"] * by_subsystem.get(Subsystem.TEMPERATURE, 0.0)
        + split["mobility"] * by_subsystem.get(Subsystem.MOBILITY, 0.0)
    )


def trend_score(trend: TrendSummary) -> float:
    """Doc 11 §15: TrendScore = Slope x Velocity x Persistence, normalized
    0-100. The dominant worsening signal (HR or temperature) drives the
    score rather than averaging them together, so one clearly worsening
    vital isn't diluted by a stable one."""
    hr_component = max(0.0, min(1.0, (trend.heart_rate_slope or 0.0) / _TREND_HR_FULL_SCALE))
    temp_component = max(0.0, min(1.0, (trend.temperature_slope or 0.0) / _TREND_TEMP_FULL_SCALE))
    return max(hr_component, temp_component) * 100.0


def baseline_deviation_score(deviation: BaselineDeviation) -> float:
    """Doc 11 §14: normalized deviation (already in std units from
    Doc 07 §11) scaled to 0-100, saturating at 3 std."""
    if deviation.overall_deviation is None:
        return 0.0
    return max(0.0, min(100.0, (deviation.overall_deviation / 3.0) * 100.0))


def calculate_priority(clinical_severity: float, subsystem_results: list[SubsystemResult],
                        trend: TrendSummary, deviation: BaselineDeviation,
                        fusion: FusionResult, features) -> tuple[float, float]:
    """Returns (raw_score, adjusted_score) per Doc 11 §11 and §16."""
    w = config.get_weights()["priority"]

    subsystem_score = subsystem_risk_score(subsystem_results)
    trend_component = trend_score(trend)
    baseline_component = baseline_deviation_score(deviation)
    confidence_component = fusion.overall_confidence * 100.0
    context_component = compute_context_modifier(features) * 100.0

    raw = (
        w["clinical_weight"] * (clinical_severity * 100.0)
        + w["subsystem_weight"] * subsystem_score
        + w["trend_weight"] * trend_component
        + w["baseline_weight"] * baseline_component
        + w["confidence_weight"] * confidence_component
        + w["context_weight"] * context_component
    )
    raw = max(0.0, min(100.0, raw))

    # Doc 11 §16: confidence may only reduce priority, never increase it
    # beyond the raw calculated score.
    adjusted = raw * fusion.overall_confidence
    adjusted = min(adjusted, raw)

    return raw, adjusted
