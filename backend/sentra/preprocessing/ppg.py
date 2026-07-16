"""Doc 04 §9 PPG preprocessing, adapted for a per-second HR/SpO2 scalar
stream rather than a raw optical waveform (docs/HARDWARE_SCOPE.md §4)."""
from __future__ import annotations

import numpy as np

from ._smoothing import moving_average

SMOOTHING_WINDOW = 3
OUTLIER_Z_THRESHOLD = 3.5
MOTION_CONTAMINATION_STD = 2.5  # IMU motion-magnitude stdev above which PPG is flagged unreliable


def _reject_outliers(values: list[float]) -> list[float]:
    if len(values) < 4:
        return values
    arr = np.array(values)
    median = np.median(arr)
    mad = np.median(np.abs(arr - median)) or 1e-6
    z = 0.6745 * (arr - median) / mad
    cleaned = np.where(np.abs(z) > OUTLIER_Z_THRESHOLD, median, arr)
    return list(cleaned)


def filter_ppg(ppg_values: list[float], imu_magnitude: list[float]) -> tuple[list[float], bool]:
    """Returns (filtered_ppg, motion_contaminated).

    motion_contaminated mirrors Doc 04 §9's "Motion Compensation" stage:
    since we receive a pre-extracted HR scalar rather than a raw waveform,
    we can't algorithmically subtract motion artifact from it — instead we
    flag windows where concurrent IMU variance is high enough that the PPG
    reading is unreliable, for Signal Quality (Doc 05) to act on.
    """
    if not ppg_values:
        return [], False

    filtered = _reject_outliers(ppg_values)
    filtered = moving_average(filtered, SMOOTHING_WINDOW)

    motion_contaminated = False
    if imu_magnitude:
        motion_contaminated = bool(np.std(imu_magnitude) > MOTION_CONTAMINATION_STD)

    return filtered, motion_contaminated
