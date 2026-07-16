"""Doc 11 §17 context awareness. Docs 00-16 reference a 'Context Engine'
(Doc 01 §9, Doc 11 §17, Doc 12 §17) but no document among 00-16 specifies
one — there is no dedicated Context Engine doc the way there is for every
other module. This is a minimal implementation of the *effect* Doc 11 §17
describes (elevated HR during activity is expected; the same HR at rest is
not) using the activity_level feature_engine already produces, scoped to
Doc 11's 5% context_weight rather than a full standalone engine."""
from __future__ import annotations

from ..models import FeatureVector

_EXPECTED_HR_BY_ACTIVITY = {"sedentary": 90, "light": 110, "moderate": 140, "high": 170}


def compute_context_modifier(features: FeatureVector) -> float:
    """Returns -1..+1: negative when elevated HR is expected given activity
    (reduces priority), positive when it's unexpected (raises priority)."""
    hr = features.cardiac.heart_rate
    activity = features.motion.activity_level
    if hr is None or activity not in _EXPECTED_HR_BY_ACTIVITY:
        return 0.0

    expected_ceiling = _EXPECTED_HR_BY_ACTIVITY[activity]
    if hr <= expected_ceiling:
        return -0.3 if activity in ("moderate", "high") else 0.0
    # HR above what's expected for this activity level — the more it
    # exceeds, the stronger the modifier, capped at +1.
    excess_fraction = (hr - expected_ceiling) / expected_ceiling
    return max(0.0, min(1.0, excess_fraction))
