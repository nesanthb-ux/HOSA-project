"""Doc 07 §13: Confidence = History Score x Average SQI x Stability Score."""
from __future__ import annotations

import math

from .. import config


def _history_score(observation_count: int, learning_duration_minutes: float) -> float:
    """Ramps 0->1 as observations accumulate toward the learning-duration
    target (~1 observation/window; Doc 03 window step ~15s -> ~4/min)."""
    target = max(1, round(learning_duration_minutes * 4))
    return max(0.0, min(1.0, observation_count / target))


def _stability_score(heart_rate_std: float | None, heart_rate_mean: float | None) -> float:
    """Lower relative spread -> a more trustworthy (stable) baseline."""
    if not heart_rate_mean or heart_rate_std is None:
        return 0.5
    coefficient_of_variation = heart_rate_std / heart_rate_mean
    return max(0.0, min(1.0, 1.0 - coefficient_of_variation))


def compute_confidence(baseline) -> float:
    cfg = config.get_weights()["baseline_engine"]
    history = _history_score(baseline.observation_count, cfg["learning_duration_minutes"])
    avg_sqi = baseline.sqi_track.mean if baseline.sqi_track.has_data else 0.0
    stability = _stability_score(baseline.heart_rate.std, baseline.heart_rate.mean)

    confidence = history * avg_sqi * stability
    return max(0.0, min(1.0, confidence)) if not math.isnan(confidence) else 0.0
