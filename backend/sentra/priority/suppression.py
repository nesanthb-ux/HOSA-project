"""Doc 11 §22 alert suppression. Never suppresses a critical override."""
from __future__ import annotations

from .. import config
from ..models import SignalQuality

IGNORE_SQI_THRESHOLD = 0.40  # matches clinical_rules/engine.py's guard


def should_suppress(quality: SignalQuality, confidence: float, critical_override: bool) -> bool:
    if critical_override:
        return False  # Doc 11 §22: "Suppression SHALL NEVER hide Critical Events"
    if quality.overall_sqi < IGNORE_SQI_THRESHOLD:
        return True
    minimum_confidence = config.get_weights()["priority"]["minimum_confidence"]
    return confidence < minimum_confidence
