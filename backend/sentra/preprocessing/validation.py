"""Doc 04 §6 integrity validation. Runs before any filtering/interpolation."""
from __future__ import annotations

import math

from ..models import PHYSIOLOGICAL_BOUNDS, SignalWindow


def _clean(values: list[float], bounds: tuple[float, float] | None) -> tuple[list[float], int]:
    """Drops NaN/Inf and out-of-bounds values. Returns (clean_values, rejected_count)."""
    out: list[float] = []
    rejected = 0
    lo, hi = bounds if bounds else (-math.inf, math.inf)
    for v in values:
        if v is None or math.isnan(v) or math.isinf(v) or not (lo <= v <= hi):
            rejected += 1
            continue
        out.append(v)
    return out, rejected


def validate_window(window: SignalWindow) -> tuple[SignalWindow, dict]:
    """Returns (window with invalid samples stripped, validation report)."""
    ppg, ppg_rejected = _clean(window.ppg, bounds=(20.0, 300.0))  # PPG carries HR-scale values, see HARDWARE_SCOPE.md
    spo2, spo2_rejected = _clean(window.ppg_spo2, PHYSIOLOGICAL_BOUNDS["spo2"])
    temp, temp_rejected = _clean(window.temperature, PHYSIOLOGICAL_BOUNDS["skin_temperature"])
    imu_clean, imu_rejected = _clean(window.imu, bounds=(0.0, 100.0))  # motion magnitude, see HARDWARE_SCOPE.md

    report = {
        "ppg_rejected": ppg_rejected,
        "spo2_rejected": spo2_rejected,
        "temperature_rejected": temp_rejected,
        "imu_rejected": imu_rejected,
        "is_empty": not (ppg or temp or imu_clean),
    }

    cleaned = window.model_copy(
        update={"ppg": ppg, "ppg_spo2": spo2, "temperature": temp, "imu": imu_clean}
    )
    return cleaned, report
