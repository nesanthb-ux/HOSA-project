"""Doc 07 §6 overall architecture: owns one PatientBaseline per patient and
runs the full update -> deviation -> trend -> confidence pipeline each call."""
from __future__ import annotations

from datetime import datetime

from ..models import BaselineDeviation, BaselineProfile, FeatureVector, PatientState, TrendSummary
from .deviation import compute_deviation
from .profile import PatientBaseline
from .trend_analysis import compute_trend


class BaselineEngine:
    def __init__(self):
        self._baselines: dict[str, PatientBaseline] = {}

    def calibrate(self, patient_id: str, age_band: str | None) -> None:
        """User-input calibration (Doc 07 §17): a nurse enters the
        patient's age band at intake so a brand-new baseline is seeded from
        a national-standard reference range instead of a cold start."""
        self._baselines[patient_id] = PatientBaseline(patient_id, age_band=age_band)

    def _get_or_create(self, patient_id: str) -> PatientBaseline:
        baseline = self._baselines.get(patient_id)
        if baseline is None:
            baseline = PatientBaseline(patient_id)
            self._baselines[patient_id] = baseline
        return baseline

    def evidence_for(self, features: FeatureVector) -> tuple[BaselineProfile, BaselineDeviation, TrendSummary]:
        """Phase 1 of a two-phase update (see observe()): deviation/trend/
        profile computed against the baseline as it stood *before* this
        window, per Doc 07 §11. Clinical rules (Doc 08) consume this output
        to compute the window's severity — which observe() then needs to
        decide whether this same window is allowed to update the baseline
        (Doc 07 §16 freezes updates above a severity threshold). Calling
        evidence_for() before observe() for the same window is what avoids
        that circularity.
        """
        baseline = self._get_or_create(features.patient_id)
        deviation = compute_deviation(features, baseline)
        trend = compute_trend(baseline)
        return baseline.to_profile(), deviation, trend

    def observe(self, ts: datetime, features: FeatureVector, overall_sqi: float,
                rule_severity: float, state: PatientState) -> BaselineProfile:
        """Phase 2: apply this window's observation now that its clinical
        severity is known. Call evidence_for() for the same window first."""
        baseline = self._get_or_create(features.patient_id)
        baseline.observe(ts, features, overall_sqi, rule_severity, state)
        return baseline.to_profile()

    def process(self, ts: datetime, features: FeatureVector, overall_sqi: float,
                rule_severity: float, state: PatientState
                ) -> tuple[BaselineProfile, BaselineDeviation, TrendSummary]:
        """Convenience one-shot wrapper for callers (tests, exploratory
        scripts) that already know this window's rule_severity up front and
        don't need the two-phase split observe()/evidence_for() provide."""
        _pre_update_profile, deviation, trend = self.evidence_for(features)
        profile = self.observe(ts, features, overall_sqi, rule_severity, state)
        return profile, deviation, trend

    def get_profile(self, patient_id: str) -> BaselineProfile | None:
        baseline = self._baselines.get(patient_id)
        return baseline.to_profile() if baseline else None
