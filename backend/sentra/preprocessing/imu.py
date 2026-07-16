"""Doc 04 §10 IMU preprocessing. The Patient Node firmware already computes
motion magnitude and gravity-relative deviation on-device
(firmware/patient_node/motion_mpu6050.h); this stage only clips saturation
and smooths sensor noise on the resulting scalar stream."""
from __future__ import annotations

import numpy as np

from ._smoothing import moving_average

SATURATION_LIMIT = 50.0  # motion-magnitude units firmware would never legitimately report


def filter_imu(motion_values: list[float]) -> tuple[list[float], int]:
    """Returns (filtered_values, saturated_count)."""
    if not motion_values:
        return [], 0

    arr = np.array(motion_values)
    saturated = int(np.sum(arr > SATURATION_LIMIT))
    clipped = np.clip(arr, 0.0, SATURATION_LIMIT)
    smoothed = moving_average(list(clipped), 3)

    return smoothed, saturated
