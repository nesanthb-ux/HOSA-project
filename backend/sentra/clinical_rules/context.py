"""Shared input bundle every rule function receives (Doc 08 §7 rule
evaluation pipeline)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..models import BaselineDeviation, BaselineProfile, FeatureVector, SignalQuality, TrendSummary
from .persistence import PersistenceTracker


@dataclass
class RuleContext:
    patient_id: str
    ts: datetime
    features: FeatureVector
    baseline: BaselineProfile
    deviation: BaselineDeviation
    trend: TrendSummary
    quality: SignalQuality
    persistence: PersistenceTracker
