"""Doc 01 §3 / ARCHITECTURE.md full system pipeline, wired end to end:

    SensorPacket -> [sensor_layer] -> SignalWindow -> [preprocessing]
    -> ProcessedWindow -> [signal_quality] -> SignalQuality
    -> [feature_engine] -> FeatureVector
    -> [baseline_engine + clinical_rules] (two-phase, see baseline_engine/manager.py)
    -> [subsystem_scoring] -> [confidence_fusion] -> [priority] -> [explainability]
    -> DashboardObject

One SentraPipeline instance owns all per-patient state and is the single
entry point real firmware (via a future BLE central) or the simulator
feeds packets into.
"""
from __future__ import annotations

from datetime import datetime

from .baseline_engine import BaselineEngine
from .clinical_rules import ClinicalRuleEngine
from .confidence_fusion import fuse_confidence
from .explainability import explain
from .feature_engine import extract_features
from .models import DashboardObject, SensorPacket, SensorStatus, SignalWindow
from .preprocessing import preprocess
from .priority import PriorityEngine
from .sensor_layer import DeviceManager, RingBuffer, WindowBuilder, validate_packet
from .signal_quality import evaluate_signal_quality
from .subsystem_scoring import evaluate_subsystems


class SentraPipeline:
    def __init__(self):
        self.ring_buffer = RingBuffer()
        self.window_builder = WindowBuilder(self.ring_buffer)
        self.device_manager = DeviceManager()
        self.baseline_engine = BaselineEngine()
        self.clinical_rules = ClinicalRuleEngine()
        self.priority_engine = PriorityEngine()

        self._last_temperature: dict[str, float] = {}
        self._device_for_patient: dict[str, str] = {}

    def calibrate_patient(self, patient_id: str, age_band: str | None) -> None:
        """User-input calibration (Doc 07 §17): seed a new patient's
        baseline from a national-standard age-band reference range."""
        self.baseline_engine.calibrate(patient_id, age_band)

    def on_packet(self, packet: SensorPacket) -> DashboardObject | None:
        """Feed one raw SensorPacket in. Returns a DashboardObject once
        enough packets have accumulated to close a window (Doc 03 §8), else
        None — most calls won't produce an output."""
        is_valid, errors = validate_packet(packet)
        if not is_valid:
            self.device_manager.record_invalid_packet(packet)
            return None

        self.device_manager.record_valid_packet(packet)
        self._device_for_patient[packet.patient_id] = packet.device_id
        self.ring_buffer.add(packet)

        window = self.window_builder.maybe_build_window(packet.patient_id, packet.timestamp)
        if window is None:
            return None

        return self._process_window(window)

    def _process_window(self, window: SignalWindow) -> DashboardObject:
        patient_id = window.patient_id

        processed = preprocess(window)
        quality = evaluate_signal_quality(processed)
        baseline_temp = self._last_temperature.get(patient_id)
        features = extract_features(processed, quality, baseline_temp=baseline_temp)
        if features.temperature.skin_temperature is not None:
            self._last_temperature[patient_id] = features.temperature.skin_temperature

        # Phase 1: evidence against the baseline as it stood before this
        # window (see baseline_engine/manager.py's evidence_for() docstring
        # for why this has to happen before clinical rule evaluation).
        profile, deviation, trend = self.baseline_engine.evidence_for(features)

        rules, clinical_severity = self.clinical_rules.evaluate(
            patient_id, window.end_time, features, profile, deviation, trend, quality
        )

        # Phase 2: now that this window's severity is known, let the
        # baseline decide whether to actually absorb it (Doc 07 §16).
        current_state = self.priority_engine.state_machine.current_state(patient_id)
        profile = self.baseline_engine.observe(
            window.end_time, features, quality.overall_sqi, clinical_severity, current_state
        )

        subsystem_results = evaluate_subsystems(features, deviation, trend, rules, quality, profile)
        fusion = fuse_confidence(quality, profile, rules, subsystem_results, trend)
        priority = self.priority_engine.evaluate(
            patient_id, window.end_time, features, deviation, trend, rules,
            clinical_severity, subsystem_results, fusion, quality,
        )

        history = self.priority_engine.state_machine.history_for(patient_id)
        explanation = explain(priority, fusion, trend, deviation, profile, history, quality.overall_sqi)

        sensor_status = self._sensor_status_for(patient_id)
        alerts = [priority.recommended_action] if priority.alert_required else []

        current_readings = {
            k: v for k, v in {
                "heart_rate": features.cardiac.heart_rate,
                "hrv": features.cardiac.heart_rate_variability,
                "spo2": features.respiratory.spo2,
                "temperature": features.temperature.skin_temperature,
                "motion_intensity": features.motion.motion_intensity,
            }.items() if v is not None
        }

        return DashboardObject(
            patient_id=patient_id,
            patient_state=priority.state,
            priority=priority.priority_score,
            confidence=priority.confidence,
            trend=trend.overall_trend,
            explanation=explanation,
            sensor_status=sensor_status,
            alerts=alerts,
            subsystem_results=subsystem_results,
            triggered_rules=[r for r in rules if r.triggered],
            baseline_deviation=deviation,
            baseline_profile=profile,
            current_readings=current_readings,
        )

    def _sensor_status_for(self, patient_id: str) -> list[SensorStatus]:
        device_id = self._device_for_patient.get(patient_id)
        if device_id is None:
            return []
        return [s for s in self.device_manager.all_statuses() if s.device_id == device_id]
