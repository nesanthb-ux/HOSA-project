"""Interim UI covering Doc 16 Part 1's home-dashboard concepts (priority
queue, patient cards, confidence, live refresh) — the full embedded
touchscreen UI (Doc 16 Parts 1-3: Alert Center, Device Management,
Administration, multi-role auth) is not built. See README.md "What's
Implemented vs. Deferred"."""
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentra import database  # noqa: E402
from sentra.baseline_engine import reference_ranges  # noqa: E402

st.set_page_config(page_title="SENTRA Priority Dashboard", layout="wide")
database.init_db()

STATE_STYLE = {
    "CRITICAL": ("\U0001F534", "Critical"),
    "HIGH_PRIORITY": ("\U0001F7E0", "High Priority"),
    "CONCERN": ("\U0001F7E1", "Concern"),
    "WATCH": ("\U0001F535", "Watch"),
    "NORMAL": ("\U0001F7E2", "Normal"),
}
STATE_ORDER = {"CRITICAL": 0, "HIGH_PRIORITY": 1, "CONCERN": 2, "WATCH": 3, "NORMAL": 4}

st.title("SENTRA - Priority Dashboard")
st.caption(
    "Explainable AI patient prioritization — every score traces back to clinical rules, "
    "subsystem risk, baseline deviation, and confidence (docs/11_Priority_Engine.md)."
)

with st.sidebar:
    st.header("Patient intake")
    st.caption(
        "Calibrate a new patient's starting baseline from a national-standard age-band "
        "reference range (Doc 07 §17) instead of a cold start."
    )
    with st.form("calibration_form", clear_on_submit=True):
        patient_id = st.text_input("Patient ID", placeholder="P-E")
        name = st.text_input("Patient name / label", placeholder="Bed 7")
        band_key = st.selectbox(
            "Age band",
            options=[key for key, _ in reference_ranges.choices()],
            format_func=lambda key: reference_ranges.get(key)["label"],
        )
        submitted = st.form_submit_button("Calibrate patient")
        if submitted and patient_id:
            database.set_patient_calibration(patient_id.strip(), name.strip(), band_key)
            st.success(f"{patient_id} calibrated to {reference_ranges.get(band_key)['label']}")
            st.info("Restart the simulator/pipeline process to pick up this new patient.")

placeholder = st.empty()


def render():
    snapshots = database.get_latest_snapshots()
    snapshots.sort(key=lambda s: (STATE_ORDER.get(s["state"], 9), -s["priority"]))

    with placeholder.container():
        if not snapshots:
            st.info("Waiting for patients... start `python -m sentra.run_simulation`.")
            return

        for rank, snap in enumerate(snapshots, start=1):
            patient_id = snap["patient_id"]
            patient = database.get_patient(patient_id) or {}
            icon, label = STATE_STYLE.get(snap["state"], ("⚪", "Unknown"))
            explanation = snap.get("explanation") or {}
            history = database.get_priority_history(patient_id, limit=60)

            with st.container(border=True):
                cols = st.columns([3, 2, 2])
                with cols[0]:
                    st.subheader(f"{icon} #{rank}  {patient.get('name', patient_id)}")
                    st.markdown(
                        f"**{label}**  ·  Priority {snap['priority']:.0f}  ·  "
                        f"Confidence {snap['confidence'] * 100:.0f}%"
                    )
                    if explanation.get("primary_reason"):
                        st.markdown(f"- **{explanation['primary_reason']}**")
                    for reason in explanation.get("secondary_reasons", [])[:3]:
                        st.markdown(f"- {reason}")
                    if patient.get("age_band"):
                        band_label = reference_ranges.get(patient["age_band"])["label"]
                        st.caption(f"Calibrated: {band_label}")
                with cols[1]:
                    if history:
                        df = pd.DataFrame(history)[["ts", "priority"]].set_index("ts")
                        st.line_chart(df, height=140)
                with cols[2]:
                    st.metric("Trend", (snap.get("trend") or "stable").title())
                    if explanation.get("confidence_summary"):
                        st.caption(explanation["confidence_summary"])
                    for alert in snap.get("alerts", []):
                        st.warning(alert)


render()
time.sleep(1)
st.rerun()
