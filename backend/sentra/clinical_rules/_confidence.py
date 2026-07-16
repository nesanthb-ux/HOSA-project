"""Doc 08 §10: Rule Confidence = SignalQuality x FeatureConfidence x
BaselineConfidence x PersistenceScore."""
from __future__ import annotations

from .context import RuleContext


def rule_confidence(ctx: RuleContext, feature_confidence: float, duration_seconds: float,
                     min_duration_seconds: float) -> float:
    persistence_score = min(1.0, duration_seconds / min_duration_seconds) if min_duration_seconds > 0 else 1.0
    confidence = (
        ctx.quality.overall_sqi
        * feature_confidence
        * (ctx.baseline.confidence or 0.0)
        * persistence_score
    )
    return max(0.0, min(1.0, confidence))
