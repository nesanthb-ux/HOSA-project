"""Doc 05 §8 PPG signal quality, adapted to a pre-extracted HR/SpO2 scalar
stream (docs/HARDWARE_SCOPE.md §4) rather than a raw optical waveform. Doc
05's six PPG metrics assume access to the waveform itself; without it,
several are approximated from what the scalar stream and its processing
metadata do reveal — each approximation is called out below rather than
presented as a direct measurement.
"""
from __future__ import annotations

from .. import config
from ..models import ProcessedWindow, QualityFlag
from ._common import detection_rate, stability_score


def evaluate_ppg(window: ProcessedWindow, expected_count: int,
                  motion_contaminated: bool) -> tuple[float, list[QualityFlag]]:
    weights = config.get_weights()["signal_quality"]["ppg"]
    flags: list[QualityFlag] = []

    if not window.ppg:
        return 0.0, [QualityFlag.LOW_SIGNAL]

    # Proxy: a well-attached sensor produces an HR trace that varies
    # smoothly; erratic sample-to-sample swings indicate poor pulse
    # morphology upstream even though we never see the waveform itself.
    pulse_shape = stability_score(window.ppg, typical_std=5.0)
    amplitude_stability = stability_score(window.ppg_spo2, typical_std=2.0) if window.ppg_spo2 else 0.5

    motion_score = 0.2 if motion_contaminated else 1.0
    if motion_contaminated:
        flags.append(QualityFlag.HIGH_MOTION)

    detect_rate = detection_rate(window.ppg, expected_count)
    if detect_rate < 0.5:
        flags.append(QualityFlag.LOW_SIGNAL)

    # Perfusion index and ambient-light rejection both happen in firmware
    # before a packet is ever sent (contact check + IR/Red thresholding in
    # hr_spo2_max30102.h) — a packet reaching the Hub at all is evidence
    # they passed. Fixed high defaults stand in for a per-sample estimate
    # we have no data to compute.
    perfusion = 0.85
    ambient_light = 0.90

    sqi = (
        weights["pulse_shape"] * pulse_shape
        + weights["motion"] * motion_score
        + weights["perfusion"] * perfusion
        + weights["pulse_detection"] * detect_rate
        + weights["ambient_light"] * ambient_light
        + weights["amplitude_stability"] * amplitude_stability
    )
    return max(0.0, min(1.0, sqi)), flags
