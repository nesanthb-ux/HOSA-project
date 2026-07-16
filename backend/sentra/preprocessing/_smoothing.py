"""Shared moving-average helper. Pads with edge values (not zero) before
convolving so the first/last samples of a window don't get dragged toward
zero by the convolution boundary — a zero-padded 'same' convolve would
otherwise fabricate a fake dip at the start of every window."""
from __future__ import annotations

import numpy as np


def moving_average(values: list[float], window: int) -> list[float]:
    arr = np.asarray(values, dtype=float)
    if len(arr) < window:
        return list(arr)

    pad = window // 2
    padded = np.pad(arr, (pad, pad), mode="edge")
    kernel = np.ones(window) / window
    smoothed = np.convolve(padded, kernel, mode="valid")
    return list(smoothed[: len(arr)])
