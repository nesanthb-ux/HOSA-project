"""Doc 07: per-patient personalized baseline. One instance per patient_id,
owned by baseline_engine/manager.py."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from .. import config
from ..models import BaselineProfile, FeatureVector, PatientState, state_rank
from .adaptive_average import EmaStat
from .reference_ranges import get as get_reference


class PatientBaseline:
    def __init__(self, patient_id: str, age_band: str | None = None):
        cfg = config.get_weights()["baseline_engine"]
        self.patient_id = patient_id
        self.alpha = cfg["ema_alpha"]
        self.learning_duration = timedelta(minutes=cfg["learning_duration_minutes"])
        self.stable_min_sqi = cfg["stable_window_min_sqi"]
        self.freeze_severity_above = cfg["freeze_on_rule_severity_above"]
        self.freeze_state_above = PatientState[cfg["freeze_on_state_above"]]

        self.start_time: datetime | None = None
        self.learning_complete = False

        self.heart_rate = EmaStat(self.alpha)
        self.hrv = EmaStat(self.alpha)
        self.spo2 = EmaStat(self.alpha)
        self.temperature = EmaStat(self.alpha)
        self.activity = EmaStat(self.alpha)
        self.sqi_track = EmaStat(self.alpha)  # tracks average SQI for Doc 07 §13 confidence formula
        self.observation_count = 0

        self.history: deque[tuple[datetime, FeatureVector]] = deque(maxlen=20)

        if age_band:
            ref = get_reference(age_band)
            self.heart_rate.seed(ref["hr_mean"], ref["hr_std"])
            self.temperature.seed(ref["temp_mean"], ref["temp_std"])

    def is_stable_window(self, overall_sqi: float, activity_level: str | None, rule_severity: float) -> bool:
        return (
            overall_sqi >= self.stable_min_sqi
            and activity_level in ("sedentary", "light", None)
            and rule_severity < self.freeze_severity_above
        )

    def observe(self, ts: datetime, features: FeatureVector, overall_sqi: float,
                rule_severity: float, state: PatientState) -> None:
        if self.start_time is None:
            self.start_time = ts

        self.observation_count += 1
        self.sqi_track.update(overall_sqi)

        if not self.learning_complete and ts - self.start_time >= self.learning_duration:
            self.learning_complete = True

        state_frozen = state_rank(state) > state_rank(self.freeze_state_above)
        stable = self.is_stable_window(overall_sqi, features.motion.activity_level, rule_severity)

        should_update = (not self.learning_complete) or (stable and not state_frozen)

        if should_update:
            if features.cardiac.heart_rate is not None:
                self.heart_rate.update(features.cardiac.heart_rate)
            if features.cardiac.heart_rate_variability is not None:
                self.hrv.update(features.cardiac.heart_rate_variability)
            if features.respiratory.spo2 is not None:
                self.spo2.update(features.respiratory.spo2)
            if features.temperature.skin_temperature is not None:
                self.temperature.update(features.temperature.skin_temperature)
            if features.motion.motion_intensity is not None:
                self.activity.update(features.motion.motion_intensity)

        self.history.append((ts, features))

    def to_profile(self) -> BaselineProfile:
        from .confidence import compute_confidence  # local import avoids a cycle

        return BaselineProfile(
            patient_id=self.patient_id,
            heart_rate_baseline=self.heart_rate.mean,
            heart_rate_std=self.heart_rate.std or None,
            hrv_baseline=self.hrv.mean,
            spo2_baseline=self.spo2.mean,
            temperature_baseline=self.temperature.mean,
            temperature_std=self.temperature.std or None,
            activity_baseline=self.activity.mean,
            motion_std=self.activity.std or None,
            confidence=compute_confidence(self),
            learning_complete=self.learning_complete,
        )
