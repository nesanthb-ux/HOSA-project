"""Doc 10 §10 confidence flags."""
from __future__ import annotations

from ..models import BaselineProfile, ClinicalRuleResult, ConfidenceFlag, SignalQuality, SubsystemResult

LOW_SENSOR_THRESHOLD = 0.60
LOW_BASELINE_THRESHOLD = 0.40
HIGH_NOISE_SQI = 0.50
DISAGREEMENT_SPREAD = 40.0  # risk-score points between subsystems' cardiac/respiratory reads


def compute_flags(quality: SignalQuality, baseline: BaselineProfile,
                   subsystem_results: list[SubsystemResult], rules: list[ClinicalRuleResult]) -> list[ConfidenceFlag]:
    flags: list[ConfidenceFlag] = []

    if quality.overall_sqi < LOW_SENSOR_THRESHOLD:
        flags.append(ConfidenceFlag.LOW_SENSOR_CONFIDENCE)
    if quality.overall_sqi < HIGH_NOISE_SQI:
        flags.append(ConfidenceFlag.HIGH_SENSOR_NOISE)
    if baseline.confidence < LOW_BASELINE_THRESHOLD:
        flags.append(ConfidenceFlag.LOW_BASELINE_CONFIDENCE)
    if not baseline.learning_complete:
        flags.append(ConfidenceFlag.INSUFFICIENT_HISTORY)

    scores = [s.risk_score for s in subsystem_results]
    if scores and (max(scores) - min(scores)) > DISAGREEMENT_SPREAD:
        flags.append(ConfidenceFlag.MODEL_DISAGREEMENT)

    unstable = [s for s in subsystem_results if s.confidence < 0.4 and s.risk_score > 50]
    if unstable:
        flags.append(ConfidenceFlag.UNSTABLE_PREDICTION)

    return flags
