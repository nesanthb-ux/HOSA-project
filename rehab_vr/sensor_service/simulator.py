"""Synthetic EDA / PPG-heart-rate / skin-temp generator — stands in for the
ESP32 sensor node until real hardware is assembled and flashed. Every value
here is explicitly simulated, not measured; nothing from this module should
ever be presented as real physiological data. Swap `read()` for a real BLE/
serial reader later — the return shape is the contract the rest of the
service depends on.
"""
from __future__ import annotations

import random
import time

from .fusion import Baseline

_baseline = Baseline()
_t0 = time.monotonic()

# Simulated "throw events" spike arousal briefly, then decay back toward
# baseline — a rough stand-in for a fear response around each throw until
# this is actually driven by real motion-tracking event timing (Week 2).
_next_spike_at = 4.0
_spike_strength = 0.0


def _maybe_trigger_spike(elapsed: float) -> None:
    global _next_spike_at, _spike_strength
    if elapsed >= _next_spike_at:
        _spike_strength = random.uniform(0.3, 1.0)
        _next_spike_at = elapsed + random.uniform(6.0, 14.0)


def read() -> dict:
    """One simulated sample. Call at ~1Hz."""
    elapsed = time.monotonic() - _t0
    _maybe_trigger_spike(elapsed)

    global _spike_strength
    _spike_strength *= 0.85  # decay toward baseline each tick

    eda = _baseline.eda_us * (1 + _spike_strength * 1.8) + random.uniform(-0.05, 0.05)
    hr = _baseline.heart_rate_bpm * (1 + _spike_strength * 0.35) + random.uniform(-1.0, 1.0)
    temp = _baseline.skin_temp_c - _spike_strength * 1.2 + random.uniform(-0.05, 0.05)

    return {
        "eda_us": round(eda, 3),
        "heart_rate_bpm": round(hr, 1),
        "skin_temp_c": round(temp, 2),
    }
