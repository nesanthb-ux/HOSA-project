"""Doc 09 §6 overall architecture: four independent subsystem engines run
in parallel off the same FeatureVector."""
from __future__ import annotations

from ..models import BaselineDeviation, BaselineProfile, ClinicalRuleResult, FeatureVector, SignalQuality, SubsystemResult, TrendSummary
from .cardiac_engine import score_cardiac
from .mobility_engine import score_mobility
from .respiratory_engine import score_respiratory
from .temperature_engine import score_temperature


def evaluate_subsystems(features: FeatureVector, deviation: BaselineDeviation, trend: TrendSummary,
                         rules: list[ClinicalRuleResult], quality: SignalQuality,
                         baseline: BaselineProfile) -> list[SubsystemResult]:
    return [
        score_cardiac(features, deviation, trend, rules, quality, baseline),
        score_respiratory(features, deviation, trend, rules, quality, baseline),
        score_temperature(features, deviation, trend, rules, quality, baseline),
        score_mobility(features, deviation, trend, rules, quality, baseline),
    ]
