"""National-standard reference ranges used only to seed a new patient's
baseline before enough personal data exists (Doc 07 §17 "New Patient
Handling" — population reference values assist the baseline, then influence
decreases as patient-specific data accumulates). Never used as a fixed
alerting threshold.

Ported from the project's earlier hub/reference_ranges.py; see that
module's history for provenance. Approximate midpoints from commonly cited
pediatric (PALS/APLS-style) and adult normal-range charts.
"""

AGE_BANDS = {
    "newborn_0_1mo": {"label": "Newborn (0-1 mo)", "hr_mean": 140, "hr_std": 25, "temp_mean": 37.0, "temp_std": 0.3},
    "infant_1_12mo": {"label": "Infant (1-12 mo)", "hr_mean": 130, "hr_std": 20, "temp_mean": 37.0, "temp_std": 0.3},
    "toddler_1_3yr": {"label": "Toddler (1-3 yr)", "hr_mean": 115, "hr_std": 15, "temp_mean": 36.8, "temp_std": 0.3},
    "preschool_3_5yr": {"label": "Preschool (3-5 yr)", "hr_mean": 100, "hr_std": 15, "temp_mean": 36.8, "temp_std": 0.3},
    "school_6_11yr": {"label": "School age (6-11 yr)", "hr_mean": 95, "hr_std": 15, "temp_mean": 36.7, "temp_std": 0.3},
    "adolescent_12_17yr": {"label": "Adolescent (12-17 yr)", "hr_mean": 80, "hr_std": 12, "temp_mean": 36.7, "temp_std": 0.3},
    "adult_18_64yr": {"label": "Adult (18-64 yr)", "hr_mean": 75, "hr_std": 12, "temp_mean": 36.8, "temp_std": 0.3},
    "older_adult_65plus": {"label": "Older adult (65+ yr)", "hr_mean": 75, "hr_std": 12, "temp_mean": 36.6, "temp_std": 0.3},
}

DEFAULT_AGE_BAND = "adult_18_64yr"


def get(age_band: str | None) -> dict:
    return AGE_BANDS.get(age_band, AGE_BANDS[DEFAULT_AGE_BAND])


def choices() -> list[tuple[str, str]]:
    return [(key, band["label"]) for key, band in AGE_BANDS.items()]
