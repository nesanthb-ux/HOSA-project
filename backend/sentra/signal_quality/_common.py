"""Shared helpers for the per-modality SQI evaluators."""
from __future__ import annotations

import numpy as np


def stability_score(values: list[float], typical_std: float) -> float:
    """0-1: 1.0 if the series varies no more than `typical_std`, decaying
    toward 0 as variance grows well beyond that."""
    if len(values) < 2:
        return 0.5
    std = float(np.std(values))
    if typical_std <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (std / (typical_std * 4))))


def detection_rate(values: list[float], expected_count: int) -> float:
    if expected_count <= 0:
        return 0.0
    return max(0.0, min(1.0, len(values) / expected_count))


def jitter_score(values: list[float], typical_jitter: float) -> float:
    """Second-difference based proxy for high-frequency sensor noise, as
    distinct from genuine slower-moving trends (which stability_score would
    also penalize even though they may be real physiology/motion)."""
    if len(values) < 3:
        return 0.5
    diffs = np.diff(values, n=2)
    jitter = float(np.std(diffs))
    if typical_jitter <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (jitter / (typical_jitter * 4))))
