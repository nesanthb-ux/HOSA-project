"""Doc 05 §10 temperature signal quality."""
from __future__ import annotations

from .. import config
from ..models import ProcessedWindow, QualityFlag
from ._common import detection_rate, stability_score


def evaluate_temperature(window: ProcessedWindow, expected_count: int, spikes_removed: int) -> tuple[float, list[QualityFlag]]:
    weights = config.get_weights()["signal_quality"]["temperature"]
    flags: list[QualityFlag] = []

    if not window.temperature:
        return 0.0, [QualityFlag.LOW_SIGNAL]

    # Spikes already removed by preprocessing indicate contact instability.
    contact = max(0.0, 1.0 - min(1.0, spikes_removed / 3.0))
    if spikes_removed:
        flags.append(QualityFlag.TEMPERATURE_SPIKE)

    stability = stability_score(window.temperature, typical_std=0.3)

    # Drift: a large net change across a single 30s window is itself
    # suspicious (real body temperature doesn't move that fast).
    drift_c = abs(window.temperature[-1] - window.temperature[0]) if len(window.temperature) >= 2 else 0.0
    drift = max(0.0, 1.0 - min(1.0, drift_c / 1.0))

    continuity = detection_rate(window.temperature, expected_count)

    sqi = (
        weights["contact"] * contact
        + weights["stability"] * stability
        + weights["drift"] * drift
        + weights["continuity"] * continuity
    )
    return max(0.0, min(1.0, sqi)), flags
