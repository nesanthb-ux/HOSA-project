"""Fuses EDA, PPG-derived heart rate, and skin temperature into a single
0-1 arousal/fear score.

This is a simple, documented weighted-deviation formula for prototype use —
not a validated clinical instrument. Every weight and baseline below is an
explicit assumption, stated here so it can be checked, argued with, or
replaced with something clinically validated later. See PIVOT_PLAN.md §5.

Missing channels: a real wearable drops readings (PPG especially, during
motion). A channel passed as None is treated as *unavailable*, never as
zero — the remaining channels' weights are renormalized so they still sum to
1.0. That renormalization is itself an assumption (a partial score is not
the same distribution as a full one), which is why the result also reports
how many channels were available, so callers can be more conservative on
partial data (the exposure engine refuses to escalate on it).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Baseline:
    """Per-athlete resting baseline, established during a calm warm-up period."""

    eda_us: float = 2.0  # microsiemens, resting skin conductance
    heart_rate_bpm: float = 70.0
    skin_temp_c: float = 33.5


# Weights sum to 1.0. EDA weighted highest: it's the most fear-specific of
# the three signals — heart rate also rises from exertion (throwing itself),
# not just fear, and skin temp is slower-moving, more useful for trend than
# an instant reading.
WEIGHT_EDA = 0.5
WEIGHT_HEART_RATE = 0.35
WEIGHT_SKIN_TEMP = 0.15

CHANNEL_COUNT = 3

# The reading dict uses unit-suffixed keys ("eda_us"); the fused detail dict
# uses short names ("eda"). One map, so nothing has to guess the other's
# spelling.
READING_TO_CHANNEL = {
    "eda_us": "eda",
    "heart_rate_bpm": "heart_rate",
    "skin_temp_c": "skin_temp",
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def normalize_eda(eda_us: float, baseline: Baseline) -> float:
    """Skin conductance rises with sympathetic arousal."""
    deviation = (eda_us - baseline.eda_us) / max(baseline.eda_us, 0.1)
    return _clamp01(deviation / 2.0)  # +200% over baseline -> fully saturated


def normalize_heart_rate(heart_rate_bpm: float, baseline: Baseline) -> float:
    deviation = (heart_rate_bpm - baseline.heart_rate_bpm) / max(baseline.heart_rate_bpm, 1.0)
    return _clamp01(deviation / 0.6)  # +60% over baseline -> fully saturated


def normalize_skin_temp(skin_temp_c: float, baseline: Baseline) -> float:
    """Fear/stress classically *drops* peripheral skin temperature
    (vasoconstriction), so this contributes on a falling-temperature axis."""
    deviation = baseline.skin_temp_c - skin_temp_c
    return _clamp01(deviation / 1.5)  # -1.5C from baseline -> fully saturated


def fuse(
    eda_us: float | None,
    heart_rate_bpm: float | None,
    skin_temp_c: float | None,
    baseline: Baseline | None = None,
) -> dict:
    """Returns the fused arousal score plus each channel's own contribution,
    so the explainability layer always has real per-channel numbers behind
    the single score — never just the score alone.

    Any channel passed as None is unavailable and excluded (see module
    docstring). If every channel is None, arousal_score is None — there is
    no honest number to report.
    """
    baseline = baseline or Baseline()
    channels = {
        "eda": (eda_us, normalize_eda, WEIGHT_EDA),
        "heart_rate": (heart_rate_bpm, normalize_heart_rate, WEIGHT_HEART_RATE),
        "skin_temp": (skin_temp_c, normalize_skin_temp, WEIGHT_SKIN_TEMP),
    }

    detail = {}
    weighted_sum = 0.0
    weight_total = 0.0
    for name, (raw, normalize, weight) in channels.items():
        if raw is None:
            detail[name] = {"raw": None, "normalized": None, "weight": weight, "available": False}
            continue
        normalized = normalize(raw, baseline)
        weighted_sum += weight * normalized
        weight_total += weight
        detail[name] = {"raw": raw, "normalized": round(normalized, 3), "weight": weight, "available": True}

    available = sum(1 for d in detail.values() if d["available"])
    score = round(weighted_sum / weight_total, 3) if weight_total > 0 else None
    return {
        "arousal_score": score,
        "channels_available": available,
        "channels": detail,
    }
