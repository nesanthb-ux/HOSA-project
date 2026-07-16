from __future__ import annotations

import numpy as np


def linear_slope(values: list[float]) -> float | None:
    """Least-squares slope of values against sample index (per-sample units)."""
    if len(values) < 2:
        return None
    x = np.arange(len(values))
    slope, _intercept = np.polyfit(x, np.asarray(values, dtype=float), 1)
    return float(slope)


def normalized_variability(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = float(np.mean(values))
    if mean == 0:
        return None
    return float(np.std(values) / abs(mean))
