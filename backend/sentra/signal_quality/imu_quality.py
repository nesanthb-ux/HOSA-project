"""Doc 05 §9 IMU signal quality."""
from __future__ import annotations

from .. import config
from ..models import ProcessedWindow, QualityFlag
from ._common import detection_rate, jitter_score


def evaluate_imu(window: ProcessedWindow, expected_count: int, saturated_count: int) -> tuple[float, list[QualityFlag]]:
    weights = config.get_weights()["signal_quality"]["imu"]
    flags: list[QualityFlag] = []

    if not window.imu:
        return 0.0, [QualityFlag.LOW_SIGNAL]

    packet_quality = detection_rate(window.imu, expected_count)
    if packet_quality < 0.5:
        flags.append(QualityFlag.PACKET_LOSS)

    saturation_fraction = min(1.0, saturated_count / max(1, len(window.imu)))
    saturation_score = 1.0 - saturation_fraction
    if saturation_fraction > 0.1:
        flags.append(QualityFlag.SIGNAL_CLIPPED)

    # High-frequency jitter distinct from genuine (possibly real) motion —
    # see _common.jitter_score.
    noise = jitter_score(window.imu, typical_jitter=1.0)

    # Calibration status and absolute orientation aren't observable from the
    # motion-magnitude scalar the firmware sends; fixed defaults stand in.
    calibration = 1.0
    orientation_stability = 0.90

    sqi = (
        weights["packet_quality"] * packet_quality
        + weights["calibration"] * calibration
        + weights["saturation"] * saturation_score
        + weights["noise"] * noise
        + weights["orientation_stability"] * orientation_stability
    )
    return max(0.0, min(1.0, sqi)), flags
