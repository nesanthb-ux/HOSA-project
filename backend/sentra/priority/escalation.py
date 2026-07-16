"""Doc 11 §24 Critical Override Rules: certain physiological events bypass
normal confidence-weighted priority calculation entirely, addressing the
tension noted in clinical_rules/_confidence.py — an absolute critical
threshold (e.g. HR>150) shouldn't wait for baseline confidence to ramp up
over a new patient's first 30 minutes before it can raise an alarm."""
from __future__ import annotations

from ..models import ClinicalRuleResult, FeatureVector

# Severe tachycardia, persistent hypoxia, and a suspected fall are Doc 11
# §24's "severe hypoxemia / extreme tachycardia / sensor-confirmed collapse"
# examples, mapped onto the specific rules implemented in clinical_rules/.
CRITICAL_OVERRIDE_RULE_IDS = {"CR-002", "RR-003", "MOT-001"}
EXTREME_BRADYCARDIA_BPM = 35  # beyond CR-003's plain <50 bradycardia threshold


def check_critical_override(features: FeatureVector, rules: list[ClinicalRuleResult]) -> tuple[bool, str | None]:
    for r in rules:
        if r.triggered and r.rule_id in CRITICAL_OVERRIDE_RULE_IDS:
            return True, r.rule_name

    hr = features.cardiac.heart_rate
    if hr is not None and hr < EXTREME_BRADYCARDIA_BPM:
        return True, "Extreme Bradycardia"

    return False, None
