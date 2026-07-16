"""Doc 05 §6 overall architecture: ProcessedWindow -> SignalQuality."""
from __future__ import annotations

from .. import config
from ..models import ProcessedWindow, QualityFlag, SignalQuality
from .imu_quality import evaluate_imu
from .ppg_quality import evaluate_ppg
from .temperature_quality import evaluate_temperature


def evaluate_signal_quality(window: ProcessedWindow) -> SignalQuality:
    log = window.processing_log
    expected = log.expected_sample_count or 1

    ppg_sqi, ppg_flags = evaluate_ppg(window, expected, log.motion_contaminated)
    imu_sqi, imu_flags = evaluate_imu(window, expected, log.saturated_samples)
    temp_sqi, temp_flags = evaluate_temperature(window, expected, log.spikes_removed)

    overall_weights = config.get_weights()["signal_quality"]["overall"]
    overall = (
        overall_weights["ppg"] * ppg_sqi
        + overall_weights["imu"] * imu_sqi
        + overall_weights["temperature"] * temp_sqi
    )
    overall = max(0.0, min(1.0, overall))

    flags = list(dict.fromkeys(ppg_flags + imu_flags + temp_flags))  # de-duplicate, preserve order

    return SignalQuality(
        window_id=window.window_id,
        ppg_sqi=ppg_sqi,
        imu_sqi=imu_sqi,
        temperature_sqi=temp_sqi,
        overall_sqi=overall,
        quality_flags=flags,
        confidence=overall,  # Doc 05 doesn't separately define this; overall SQI IS the confidence signal it forwards
    )


def sensor_weight(sqi: float) -> float:
    """Doc 05 §14 dynamic sensor weighting: quality maps 1:1 to trust."""
    return max(0.0, min(1.0, sqi))
