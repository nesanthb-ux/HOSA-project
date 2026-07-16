"""Doc 04 §5 overall pipeline: SignalWindow -> ProcessedWindow."""
from __future__ import annotations

import time

from ..models import ProcessedWindow, ProcessingMetadata, SignalWindow
from . import imu as imu_mod
from . import ppg as ppg_mod
from . import temperature as temperature_mod
from . import validation
from .interpolation import interpolate_to_expected


def preprocess(window: SignalWindow) -> ProcessedWindow:
    start = time.perf_counter()
    warnings: list[str] = []

    validated, val_report = validation.validate_window(window)
    if val_report["is_empty"]:
        warnings.append("window contained no valid samples after integrity validation")

    expected_count = max(1, round(window.duration_seconds))  # ~1 sample/sec, see HARDWARE_SCOPE.md §4

    ppg_interp, ppg_gap = interpolate_to_expected(validated.ppg, expected_count)
    spo2_interp, spo2_gap = interpolate_to_expected(validated.ppg_spo2, expected_count)
    imu_interp, imu_gap = interpolate_to_expected(validated.imu, expected_count)
    temp_interp, temp_gap = interpolate_to_expected(validated.temperature, expected_count)

    filtered_ppg, motion_contaminated = ppg_mod.filter_ppg(ppg_interp, imu_interp)
    filtered_spo2, _ = ppg_mod.filter_ppg(spo2_interp, imu_interp)
    filtered_imu, saturated = imu_mod.filter_imu(imu_interp)
    filtered_temp, spikes = temperature_mod.filter_temperature(temp_interp)

    missing_samples = (
        ppg_gap["missing_samples"] + spo2_gap["missing_samples"]
        + imu_gap["missing_samples"] + temp_gap["missing_samples"]
    )
    interpolated_samples = (
        ppg_gap["interpolated_samples"] + spo2_gap["interpolated_samples"]
        + imu_gap["interpolated_samples"] + temp_gap["interpolated_samples"]
    )

    if "level_2" in (ppg_gap["gap_tier"], imu_gap["gap_tier"], temp_gap["gap_tier"]):
        warnings.append("moderate data gap interpolated — confidence penalty recommended")
    if "level_3" in (ppg_gap["gap_tier"], imu_gap["gap_tier"], temp_gap["gap_tier"]):
        warnings.append("large data gap — window marked incomplete for affected sensor")
    if motion_contaminated:
        warnings.append("PPG reading concurrent with high IMU motion — likely artifact")
    if saturated:
        warnings.append(f"{saturated} IMU sample(s) saturated/clipped")
    if spikes:
        warnings.append(f"{spikes} temperature spike(s) rejected")
    for key in ("ppg_rejected", "spo2_rejected", "temperature_rejected", "imu_rejected"):
        if val_report[key]:
            warnings.append(f"{val_report[key]} sample(s) rejected by integrity validation ({key})")

    metadata = ProcessingMetadata(
        processing_time_ms=(time.perf_counter() - start) * 1000,
        filters_applied=["outlier_rejection", "moving_average", "spike_detection", "interpolation"],
        missing_samples=missing_samples,
        interpolated_samples=interpolated_samples,
        resampled=False,
        warnings=warnings,
        expected_sample_count=expected_count,
        motion_contaminated=motion_contaminated,
        saturated_samples=saturated,
        spikes_removed=spikes,
    )

    return ProcessedWindow(
        window_id=window.window_id,
        patient_id=window.patient_id,
        ppg=filtered_ppg,
        ppg_spo2=filtered_spo2,
        imu=filtered_imu,
        temperature=filtered_temp,
        processing_log=metadata,
    )
