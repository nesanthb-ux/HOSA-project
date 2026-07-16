"""Doc 04 §7 missing-data handling, adapted to per-second scalar streams
(see docs/HARDWARE_SCOPE.md §4) rather than raw-waveform sample gaps.

Doc 04's tier boundaries (250ms / 2s) are defined for a high-frequency
waveform where a single dropped sample is a few milliseconds. Our real
cadence is roughly one packet per second per sensor (docs/HARDWARE_SCOPE.md
§4), so a single missing sample already represents a ~1s gap. We keep the
spec's *three-tier shape* (interpolate freely / interpolate with penalty /
give up and flag incomplete) but express the tier boundaries in missing
sample counts appropriate to a ~1 Hz stream instead of literal milliseconds.
"""
from __future__ import annotations

import numpy as np

LEVEL_1_MAX_MISSING = 1   # single dropped sample: interpolate, no penalty
LEVEL_2_MAX_MISSING = 5   # a few seconds of dropout: interpolate, apply penalty


def interpolate_to_expected(values: list[float], expected_count: int) -> tuple[list[float], dict]:
    """Pads `values` up to `expected_count` samples via linear interpolation
    across the existing samples' positions. Returns (values, metadata)."""
    actual = len(values)
    missing = max(0, expected_count - actual)

    if missing == 0:
        return values, {"missing_samples": 0, "interpolated_samples": 0, "gap_tier": "none"}

    if actual < 2:
        # Not enough anchor points to interpolate — do not fabricate data.
        return values, {"missing_samples": missing, "interpolated_samples": 0, "gap_tier": "level_3"}

    if missing <= LEVEL_1_MAX_MISSING:
        tier = "level_1"
    elif missing <= LEVEL_2_MAX_MISSING:
        tier = "level_2"
    else:
        # Level 3: too much of the window is missing to trust an interpolation.
        return values, {"missing_samples": missing, "interpolated_samples": 0, "gap_tier": "level_3"}

    original_x = np.linspace(0, expected_count - 1, num=actual)
    target_x = np.arange(expected_count)
    interpolated = np.interp(target_x, original_x, values)

    return list(interpolated), {
        "missing_samples": missing,
        "interpolated_samples": missing,
        "gap_tier": tier,
    }
