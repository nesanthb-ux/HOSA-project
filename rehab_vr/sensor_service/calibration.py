"""Resting-baseline calibration for the arousal score.

The fusion formula scores each channel as a deviation from that athlete's
resting baseline. With the generic default baseline, a real athlete's
numbers are simply offset: forearm skin temperature runs at a different level
than the default, and skin conductance differs a lot between people and with
electrode placement. Without calibration the score on real hardware would be
wrong in a way that looks plausible.

The calibrator collects one reading per tick while the athlete sits still and
relaxed, then takes the MEDIAN of each channel (robust to the odd artifact).
It refuses to produce a baseline unless every channel had enough valid
seconds: a baseline built from a handful of samples, or silently mixed with
the generic default for one channel, is worse than none. On failure the
previous baseline stays in force and the reason names the channel.

This does not check that the athlete really was at rest; the UI instructs
them to be. It is a prototype procedure, not a validated protocol.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from .fusion import Baseline

CHANNEL_LABELS = {
    "eda_us": "skin conductance (EDA)",
    "heart_rate_bpm": "heart rate",
    "skin_temp_c": "skin temperature",
}
CHANNELS = tuple(CHANNEL_LABELS)


@dataclass(frozen=True)
class CalibrationResult:
    ok: bool
    baseline: Optional[Baseline]
    reason: Optional[str]
    valid_counts: dict = field(default_factory=dict)
    total_ticks: int = 0


class BaselineCalibrator:
    """Feed it one reading per tick with add(); done() turns true after
    total_ticks calls, then result() reports success or the reason for failure."""

    def __init__(self, total_ticks: int, min_valid_fraction: float = 0.6, channels: tuple = CHANNELS):
        if total_ticks < 1:
            raise ValueError("total_ticks must be at least 1")
        if not 0.0 < min_valid_fraction <= 1.0:
            raise ValueError("min_valid_fraction must be in (0, 1]")
        unknown = [c for c in channels if c not in CHANNELS]
        if unknown:
            raise ValueError(f"unknown channels: {unknown}")
        if not channels:
            raise ValueError("at least one channel must be calibrated")
        self.total_ticks = total_ticks
        self.min_valid_fraction = min_valid_fraction
        # Only the channels this build actually has. A channel that was never
        # fitted must not make calibration fail forever (see sensor_config.py).
        self.channels = tuple(channels)
        self._values: dict[str, list[float]] = {name: [] for name in self.channels}
        self._ticks = 0

    @property
    def ticks_left(self) -> int:
        return max(0, self.total_ticks - self._ticks)

    @property
    def done(self) -> bool:
        return self._ticks >= self.total_ticks

    def add(self, reading: dict) -> None:
        """One tick. Channels that are None (not currently valid) simply do
        not contribute; they are never counted as zero."""
        if self.done:
            return
        self._ticks += 1
        for name in self.channels:
            value = reading.get(name)
            if value is not None:
                self._values[name].append(float(value))

    def result(self) -> CalibrationResult:
        if not self.done:
            raise RuntimeError("calibration is still running")
        counts = {name: len(values) for name, values in self._values.items()}
        needed = self.min_valid_fraction * self.total_ticks
        weak = [name for name in self.channels if counts[name] < needed]
        if weak:
            parts = [f"{CHANNEL_LABELS[n]}: {counts[n]} of {self.total_ticks} seconds valid" for n in weak]
            reason = "not enough valid readings (" + "; ".join(parts) + "). Sit still and check the sensors, then try again."
            return CalibrationResult(False, None, reason, counts, self.total_ticks)
        # A channel this build does not have keeps the documented default from
        # Baseline. It is never scored, so that default is never actually used.
        medians = {name: statistics.median(self._values[name]) for name in self.channels}
        baseline = Baseline(**medians)
        return CalibrationResult(True, baseline, None, counts, self.total_ticks)
