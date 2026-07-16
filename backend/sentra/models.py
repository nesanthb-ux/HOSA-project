"""Shared data contracts for the SENTRA pipeline (docs/02_Data_Model.md).

Every module in backend/sentra/ SHALL consume and produce only the objects
defined here (CLAUDE.md, Doc 02 §30). Do not invent parallel structures in
individual modules.

Object hierarchy (Doc 02 §3, §28):

    SensorPacket -> SignalWindow -> ProcessedWindow -> FeatureVector
    -> EvidencePackage -> ConfidenceResult -> PriorityResult -> DashboardObject

See docs/HARDWARE_SCOPE.md for why ECG fields exist here but have no
producing module: they preserve the documented schema for future hardware
without requiring a redesign (Doc 01 §18, Doc 03 §4).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class SentraModel(BaseModel):
    """Base for every SENTRA object (Doc 02 §2): timestamped, versioned,
    JSON serializable, human readable."""

    version: str = "0.1"
    timestamp: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# 4-5. SensorPacket / SensorStatus (Doc 02 §4-5)
# ---------------------------------------------------------------------------

class SensorType(str, Enum):
    ECG = "ECG"            # accepted by schema, no processing module — see HARDWARE_SCOPE.md
    PPG = "PPG"
    IMU = "IMU"
    TEMPERATURE = "TEMPERATURE"
    EDA = "EDA"             # future sensor, Doc 03 §4


class SensorPacket(SentraModel):
    packet_id: str = Field(default_factory=_new_id)
    patient_id: str
    device_id: str
    sensor_type: SensorType
    sampling_rate: float = Field(gt=0, description="Hz")
    values: list[float]
    battery_level: Optional[float] = Field(default=None, ge=0, le=100)
    connection_strength: Optional[float] = Field(default=None, description="RSSI, dBm")
    firmware_version: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class SensorStatus(SentraModel):
    device_id: str
    sensor_type: SensorType
    connected: bool
    battery: Optional[float] = Field(default=None, ge=0, le=100)
    signal_strength: Optional[float] = None
    last_seen: datetime = Field(default_factory=_utcnow)
    firmware_version: Optional[str] = None
    error_code: Optional[str] = None
    health_score: float = Field(default=100.0, ge=0, le=100, description="Doc 03 §15")


# ---------------------------------------------------------------------------
# 6-7. SignalWindow / ProcessedWindow (Doc 02 §6-7)
# ---------------------------------------------------------------------------

class SignalWindow(SentraModel):
    """NOTE: `imu` holds one motion-magnitude scalar per sample rather than
    raw 6-axis accel/gyro — the firmware computes that reduction on-device.
    See docs/HARDWARE_SCOPE.md §4."""

    window_id: str = Field(default_factory=_new_id)
    patient_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    ecg: list[float] = Field(default_factory=list)
    ppg: list[float] = Field(default_factory=list, description="heart rate, bpm")
    ppg_spo2: list[float] = Field(
        default_factory=list,
        description="SpO2 %, computed on-device alongside HR — extension to Doc 02's PPG "
        "field per Doc 02 §30 ('developers SHALL extend existing models'), see HARDWARE_SCOPE.md §4",
    )
    imu: list[float] = Field(default_factory=list, description="motion magnitude, one scalar per sample")
    temperature: list[float] = Field(default_factory=list)
    eda: list[float] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ProcessingMetadata(BaseModel):
    """Doc 04 §15. motion_contaminated/saturated_samples/spikes_removed are
    an extension (Doc 02 §30) so signal_quality can consume exact counts
    instead of re-parsing `warnings` strings."""

    processing_time_ms: float = 0.0
    filters_applied: list[str] = Field(default_factory=list)
    missing_samples: int = 0
    interpolated_samples: int = 0
    resampled: bool = False
    warnings: list[str] = Field(default_factory=list)
    expected_sample_count: int = 0
    motion_contaminated: bool = False
    saturated_samples: int = 0
    spikes_removed: int = 0


class ProcessedWindow(SentraModel):
    window_id: str
    patient_id: str
    ecg: list[float] = Field(default_factory=list)
    ppg: list[float] = Field(default_factory=list)
    ppg_spo2: list[float] = Field(default_factory=list)
    imu: list[float] = Field(default_factory=list)
    temperature: list[float] = Field(default_factory=list)
    eda: list[float] = Field(default_factory=list)
    processing_log: ProcessingMetadata = Field(default_factory=ProcessingMetadata)


# ---------------------------------------------------------------------------
# 8-9. ArtifactReport / SignalQuality (Doc 02 §8-9, Doc 05)
# ---------------------------------------------------------------------------

class QualityFlag(str, Enum):
    """Doc 05 §13."""

    HIGH_MOTION = "HIGH_MOTION"
    LOW_PERFUSION = "LOW_PERFUSION"
    ECG_DETACHED = "ECG_DETACHED"
    SIGNAL_CLIPPED = "SIGNAL_CLIPPED"
    POWERLINE_NOISE = "POWERLINE_NOISE"
    TEMPERATURE_SPIKE = "TEMPERATURE_SPIKE"
    LOW_BATTERY = "LOW_BATTERY"
    LOW_SIGNAL = "LOW_SIGNAL"
    PACKET_LOSS = "PACKET_LOSS"
    CLOCK_DRIFT = "CLOCK_DRIFT"


class ArtifactReport(SentraModel):
    window_id: str
    ppg_artifact: float = Field(default=0.0, ge=0, le=1)
    imu_artifact: float = Field(default=0.0, ge=0, le=1)
    temperature_artifact: float = Field(default=0.0, ge=0, le=1)
    overall_artifact: float = Field(default=0.0, ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class SignalQuality(SentraModel):
    window_id: str
    ppg_sqi: float = Field(ge=0, le=1)
    imu_sqi: float = Field(ge=0, le=1)
    temperature_sqi: float = Field(ge=0, le=1)
    overall_sqi: float = Field(ge=0, le=1)
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


# ---------------------------------------------------------------------------
# 10-15. FeatureVector and modality feature groups (Doc 02 §10-15, Doc 06)
# ---------------------------------------------------------------------------

class CardiacFeatures(BaseModel):
    """Doc 02 §11, Doc 06 §6. heart_rate/rr_mean/rmssd/sdnn/pnn50/mean_nn
    are sourced from PPG on this hardware (docs/HARDWARE_SCOPE.md) rather
    than ECG. qt_interval/qrs_duration/pr_interval require ECG and stay
    None until that sensor exists."""

    heart_rate: Optional[float] = None
    heart_rate_variability: Optional[float] = None
    rr_mean: Optional[float] = None
    rmssd: Optional[float] = None
    sdnn: Optional[float] = None
    pnn50: Optional[float] = None
    mean_nn: Optional[float] = None
    heart_rate_trend: Optional[float] = None
    beat_regularity: Optional[float] = None
    rr_variability: Optional[float] = None
    heart_rate_acceleration: Optional[float] = None
    qt_interval: Optional[float] = None      # ECG-only, unavailable
    qrs_duration: Optional[float] = None      # ECG-only, unavailable
    pr_interval: Optional[float] = None       # ECG-only, unavailable
    qtc: Optional[float] = None               # ECG-only, unavailable
    beat_detection_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class RespiratoryFeatures(BaseModel):
    """Doc 02 §12, Doc 06 §7. Estimated from PPG."""

    respiratory_rate: Optional[float] = None
    spo2: Optional[float] = Field(default=None, ge=0, le=100)
    respiratory_variability: Optional[float] = None
    breathing_regularity: Optional[float] = None
    oxygen_trend: Optional[float] = None
    perfusion_index: Optional[float] = None
    pulse_arrival_time: Optional[float] = None


class MotionFeatures(BaseModel):
    """Doc 02 §13, Doc 06 §8."""

    activity_level: Optional[str] = None      # sedentary/light/moderate/high
    step_rate: Optional[float] = None
    posture: Optional[str] = None
    orientation: Optional[str] = None
    fall_probability: Optional[float] = Field(default=None, ge=0, le=1)
    motion_intensity: Optional[float] = None
    motion_variability: Optional[float] = None
    sleep_probability: Optional[float] = Field(default=None, ge=0, le=1)


class TemperatureFeatures(BaseModel):
    """Doc 02 §14, Doc 06 §9."""

    skin_temperature: Optional[float] = None
    temperature_slope: Optional[float] = None
    temperature_variability: Optional[float] = None
    baseline_deviation: Optional[float] = None
    fever_probability: Optional[float] = Field(default=None, ge=0, le=1)


class QualityFeatures(BaseModel):
    """Doc 02 §15."""

    ppg_sqi: float = 0.0
    imu_sqi: float = 0.0
    temperature_sqi: float = 0.0
    overall_sqi: float = 0.0


class DerivedFeatures(BaseModel):
    """Doc 06 §11."""

    cardiorespiratory_ratio: Optional[float] = None
    motion_adjusted_heart_rate: Optional[float] = None
    temperature_corrected_heart_rate: Optional[float] = None
    oxygen_recovery_rate: Optional[float] = None
    activity_corrected_respiratory_rate: Optional[float] = None


class FeatureVector(SentraModel):
    window_id: str
    patient_id: str
    cardiac: CardiacFeatures = Field(default_factory=CardiacFeatures)
    respiratory: RespiratoryFeatures = Field(default_factory=RespiratoryFeatures)
    motion: MotionFeatures = Field(default_factory=MotionFeatures)
    temperature: TemperatureFeatures = Field(default_factory=TemperatureFeatures)
    derived: DerivedFeatures = Field(default_factory=DerivedFeatures)
    quality: QualityFeatures = Field(default_factory=QualityFeatures)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 16-17. BaselineProfile / BaselineDeviation (Doc 02 §16-17, Doc 07)
# ---------------------------------------------------------------------------

class BaselineProfile(SentraModel):
    patient_id: str
    heart_rate_baseline: Optional[float] = None
    heart_rate_std: Optional[float] = None
    hrv_baseline: Optional[float] = None
    respiratory_baseline: Optional[float] = None
    respiratory_std: Optional[float] = None
    spo2_baseline: Optional[float] = None
    temperature_baseline: Optional[float] = None
    temperature_std: Optional[float] = None
    activity_baseline: Optional[float] = None
    motion_std: Optional[float] = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    learning_complete: bool = False
    last_updated: datetime = Field(default_factory=_utcnow)


class BaselineDeviation(BaseModel):
    heart_rate_deviation: Optional[float] = None
    hrv_deviation: Optional[float] = None
    respiratory_deviation: Optional[float] = None
    temperature_deviation: Optional[float] = None
    motion_deviation: Optional[float] = None
    overall_deviation: Optional[float] = None


class TrendSummary(BaseModel):
    """Doc 07 §14, §19."""

    heart_rate_slope: Optional[float] = None
    respiratory_slope: Optional[float] = None
    temperature_slope: Optional[float] = None
    hrv_slope: Optional[float] = None
    overall_trend: Optional[str] = None  # "improving" | "stable" | "worsening"


# ---------------------------------------------------------------------------
# 18. ClinicalRuleResult (Doc 02 §18, Doc 08)
# ---------------------------------------------------------------------------

class RulePriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class ClinicalRuleResult(SentraModel):
    rule_id: str
    rule_name: str
    priority: RulePriority
    severity: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    triggered: bool
    duration_seconds: float = 0.0
    supporting_features: list[str] = Field(default_factory=list)
    supporting_sensors: list[SensorType] = Field(default_factory=list)
    recommended_action: Optional[str] = None


# ---------------------------------------------------------------------------
# 19-21. MLPrediction / Evidence / EvidencePackage (Doc 02 §19-21)
# ---------------------------------------------------------------------------

class Subsystem(str, Enum):
    CARDIAC = "CARDIAC"
    RESPIRATORY = "RESPIRATORY"
    TEMPERATURE = "TEMPERATURE"
    MOBILITY = "MOBILITY"


class MLPrediction(BaseModel):
    subsystem: Subsystem
    probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    model_version: str = "rule-based-v1"  # see docs/HARDWARE_SCOPE.md / Doc 13


class Evidence(BaseModel):
    source: str
    value: float
    confidence: float = Field(ge=0, le=1)
    weight: float = Field(default=0.0, ge=0, le=1)
    supporting_features: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utcnow)


class EvidencePackage(BaseModel):
    baseline_evidence: list[Evidence] = Field(default_factory=list)
    clinical_evidence: list[Evidence] = Field(default_factory=list)
    ml_evidence: list[Evidence] = Field(default_factory=list)
    context_evidence: list[Evidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Doc 09 — SubsystemResult
# ---------------------------------------------------------------------------

class SubsystemResult(SentraModel):
    subsystem: Subsystem
    risk_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    severity: float = Field(default=0.0, ge=0, le=1)
    top_features: list[str] = Field(default_factory=list)
    baseline_deviation: Optional[float] = None
    clinical_evidence: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 22. ConfidenceResult / Doc 10 FusionResult
# ---------------------------------------------------------------------------

class ConfidenceFlag(str, Enum):
    """Doc 10 §10."""

    LOW_SENSOR_CONFIDENCE = "LOW_SENSOR_CONFIDENCE"
    LOW_BASELINE_CONFIDENCE = "LOW_BASELINE_CONFIDENCE"
    MODEL_DISAGREEMENT = "MODEL_DISAGREEMENT"
    HIGH_SENSOR_NOISE = "HIGH_SENSOR_NOISE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    HIGH_PACKET_LOSS = "HIGH_PACKET_LOSS"
    UNSTABLE_PREDICTION = "UNSTABLE_PREDICTION"


class ConfidenceResult(SentraModel):
    overall_confidence: float = Field(ge=0, le=1)
    sensor_confidence: float = Field(ge=0, le=1)
    baseline_confidence: float = Field(ge=0, le=1)
    model_confidence: float = Field(ge=0, le=1)
    temporal_confidence: float = Field(ge=0, le=1)


class RankedEvidence(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    influence: float = Field(default=0.0, ge=0, le=1)


class FusionResult(SentraModel):
    overall_confidence: float = Field(ge=0, le=1)
    weighted_subsystem_scores: dict[str, float] = Field(default_factory=dict)
    evidence_ranking: list[RankedEvidence] = Field(default_factory=list)
    confidence_flags: list[ConfidenceFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 23-25. PriorityScore / PatientState / StateHistory (Doc 02 §23-25, Doc 11)
# ---------------------------------------------------------------------------

class PatientState(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    CONCERN = "CONCERN"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    CRITICAL = "CRITICAL"


_STATE_ORDER = [
    PatientState.NORMAL,
    PatientState.WATCH,
    PatientState.CONCERN,
    PatientState.HIGH_PRIORITY,
    PatientState.CRITICAL,
]


def state_rank(state: PatientState) -> int:
    return _STATE_ORDER.index(state)


class PriorityScore(BaseModel):
    raw_score: float = Field(ge=0, le=100)
    weighted_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class StateHistory(BaseModel):
    previous_state: PatientState
    current_state: PatientState
    transition_time: datetime = Field(default_factory=_utcnow)
    transition_reason: str = ""


class PriorityResult(SentraModel):
    patient_id: str
    priority_score: float = Field(ge=0, le=100)
    priority_level: PatientState
    confidence: float = Field(ge=0, le=1)
    state: PatientState
    trend: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list)
    top_contributors: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    alert_required: bool = False


# ---------------------------------------------------------------------------
# 26-27. ExplainabilityReport / DashboardObject (Doc 02 §26-27, Doc 12)
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    timestamp: datetime
    description: str


class ExplanationResult(SentraModel):
    patient_id: str
    priority_summary: str
    primary_reason: str
    secondary_reasons: list[str] = Field(default_factory=list)
    evidence: list[RankedEvidence] = Field(default_factory=list)
    confidence_summary: str = ""
    recommended_action: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)


class DashboardObject(SentraModel):
    patient_id: str
    patient_state: PatientState
    priority: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    trend: Optional[str] = None
    explanation: Optional[ExplanationResult] = None
    sensor_status: list[SensorStatus] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Physiological validity bounds (Doc 04 §6) — used by preprocessing/validation.py
# ---------------------------------------------------------------------------

PHYSIOLOGICAL_BOUNDS = {
    "heart_rate": (20.0, 300.0),
    "respiratory_rate": (4.0, 80.0),
    "spo2": (40.0, 100.0),
    "skin_temperature": (25.0, 45.0),
}


class ValidationError(ValueError):
    """Raised when a value fails Doc 04 §6 integrity validation."""
