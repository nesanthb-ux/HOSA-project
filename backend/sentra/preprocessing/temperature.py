"""Doc 04 §11 temperature preprocessing: spike detection + moving average."""
from __future__ import annotations

import numpy as np

from ._smoothing import moving_average

SPIKE_DELTA_C = 1.5  # a >1.5C jump between consecutive 1s readings indicates
                       # sensor removal / poor contact, not real physiology


def filter_temperature(values: list[float]) -> tuple[list[float], int]:
    """Returns (filtered_values, spikes_removed)."""
    if len(values) < 2:
        return values, 0

    arr = np.array(values, dtype=float)
    spikes = 0
    for i in range(1, len(arr)):
        if abs(arr[i] - arr[i - 1]) > SPIKE_DELTA_C:
            arr[i] = arr[i - 1]  # hold last good value rather than fabricate a new one
            spikes += 1

    smoothed = moving_average(list(arr), 3)
    return smoothed, spikes
