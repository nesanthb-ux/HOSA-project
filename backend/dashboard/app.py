"""SENTRA Hub bedside display.

Physical deployment: one small touchscreen (Doc 16 §5 — 7-24", touch,
always-on) mounted between two patient beds, wired to that bed pair's
Patient Nodes. A hospital ward runs many of these Hub units, each showing
only the two beds it's physically positioned between — not a scrolling
ward-wide list. Every Hub points at the same backend/database and is
deep-linked via URL query params to the two patients it's responsible for,
e.g. `?hub=HUB-03&bed_a=P-A&bed_b=P-B`, so the same app.py is what every
physical unit in the ward runs.

Two screens, both routed via query params (no separate pages/ dir needed):
  - Hub view (default): the two-bed monitor, PPG waveform + vitals + a
    compact AI risk panel per bed — Doc 16 §3's "3s who / 5s why / 10s
    what to do" goal.
  - Patient detail view (?view=detail&patient=P-A): full-screen drill-down
    with the full explainability picture (Doc 16 §43).

The Doc 16 Parts 1-3 concepts not built: Alert Center, Device Management,
Administration, multi-role auth, and a central ward-wide overview screen.
See README.md "What's Implemented vs. Deferred".
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/, for `sentra`
sys.path.insert(0, str(Path(__file__).resolve().parent))  # this dir, for the sibling modules below

from sentra import database  # noqa: E402
from sentra.baseline_engine import reference_ranges  # noqa: E402

from timezones import TIMEZONES, format_iso, format_ts, now_in  # noqa: E402
from waveform import render_ppg_waveform  # noqa: E402

st.set_page_config(
    page_title="SENTRA Hub", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed"
)
database.init_db()

REFRESH_SECONDS = 2  # how often the live data (not the page structure) re-polls the database

# ---------------------------------------------------------------------------
# Doc 16 §14 color system — used exactly as documented, not restyled.
# ---------------------------------------------------------------------------
STATE_COLORS = {
    "NORMAL": "#2ECC71",
    "WATCH": "#F1C40F",
    "CONCERN": "#E67E22",
    "HIGH_PRIORITY": "#E74C3C",
    "CRITICAL": "#8E0000",
}
STATE_TEXT = {
    "NORMAL": "#0B2818",
    "WATCH": "#2B2205",
    "CONCERN": "#2B1704",
    "HIGH_PRIORITY": "#FFFFFF",
    "CRITICAL": "#FFFFFF",
}
STATE_LABEL = {
    "NORMAL": "Normal",
    "WATCH": "Watch",
    "CONCERN": "Concern",
    "HIGH_PRIORITY": "High Priority",
    "CRITICAL": "Critical",
}

# Readable labels for the flat current_readings/baseline_profile keys
# (Doc 16 §33 Baseline Comparison: Baseline | Current | Difference per variable).
_COMPARISON_ROWS = [
    ("Heart Rate", "heart_rate", "heart_rate_baseline", "heart_rate_deviation", "bpm"),
    ("HRV (proxy)", "hrv", "hrv_baseline", "hrv_deviation", ""),
    ("SpO2", "spo2", "spo2_baseline", None, "%"),
    ("Skin Temperature", "temperature", "temperature_baseline", "temperature_deviation", "°C"),
    ("Motion", "motion_intensity", "activity_baseline", "motion_deviation", ""),
]

# ---------------------------------------------------------------------------
# Theme — near-true-black base (OLED: black pixels draw ~no power and give
# effectively infinite contrast, which is what this screen actually is).
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* System font stacks only, deliberately — this runs on an offline
    embedded kiosk (Doc 03: no internet/cloud dependency), so a Google
    Fonts @import would silently fail on real hardware and isn't worth
    depending on even for the browser-based demo. */
    :root {
        --font-sans: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        --font-mono: 'Cascadia Code', 'SF Mono', Consolas, 'Liberation Mono', monospace;
    }
    html, body, [class*="css"] { font-family: var(--font-sans); }
    .stApp { background: #000000; }
    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1500px; }

    [data-testid="stSidebar"] { background: #0A0A0C; border-right: 1px solid #1F2430; }

    /* Hub header strip */
    .hub-bar {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 18px; border: 1px solid #1A1C22; border-radius: 10px;
        background: #08090B; margin-bottom: 14px;
    }
    .hub-wordmark { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.01em; color: #F4F5F7; }
    .hub-wordmark span { color: #22D3B8; }
    .hub-id { color: #5A6272; font-family: var(--font-mono); font-size: 0.85rem; margin-left: 10px; }
    .hub-subtitle { color: #4C5566; font-size: 0.72rem; margin-left: 10px; }
    .hub-live {
        display: flex; align-items: center; gap: 7px; color: #8B92A0; font-size: 0.82rem;
        font-family: var(--font-mono);
    }
    .hub-live-dot {
        width: 8px; height: 8px; border-radius: 50%; background: #22D3B8;
        box-shadow: 0 0 0 4px rgba(34,211,184,0.15); animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(div.bed-panel-marker) {
        border: 1px solid #1A1C22 !important; border-radius: 16px; background: #060708;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div.bed-panel-marker) > div {
        padding: 18px 22px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div.bed-panel-marker.critical) {
        border-color: #8E0000 !important; box-shadow: 0 0 0 1px #8E0000, 0 0 24px rgba(142,0,0,0.35);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div.bed-panel-marker.high) {
        border-color: #E74C3C !important; box-shadow: 0 0 0 1px #E74C3C, 0 0 18px rgba(231,76,60,0.2);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div.bed-panel-marker.empty) {
        border: 1px dashed #1A1C22 !important; background: transparent;
    }
    .bed-panel-marker { display: none; }

    .bed-label {
        color: #5A6272; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.1em; margin-bottom: 8px;
    }
    .badge-xl {
        display: inline-block; padding: 6px 16px; border-radius: 999px;
        font-size: 0.92rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .patient-name-xl { font-size: 1.7rem; font-weight: 700; color: #F4F5F7; margin: 10px 0 2px 0; line-height: 1.1; }
    .calibration-chip {
        display: inline-block; font-size: 0.75rem; color: #6B7280;
        border: 1px solid #1A1C22; border-radius: 6px; padding: 2px 9px; background: #0A0A0C;
    }

    .waveform-caption {
        color: #4C5566; font-size: 0.7rem; text-align: center; margin-top: 4px; letter-spacing: 0.02em;
    }
    .waveform-section-label {
        color: #8B92A0; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; margin: 14px 0 6px 0;
    }

    /* Vitals grid — real-time monitoring readout, the visual co-star next to the waveform */
    .vitals-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0 16px 0; }
    .vital-tile {
        background: #0A0A0C; border: 1px solid #16181E; border-radius: 10px; padding: 10px 12px;
    }
    .vital-label { color: #6B7280; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
    .vital-value { font-family: var(--font-mono); color: #F4F5F7; font-size: 1.35rem; font-weight: 700; margin-top: 2px; }
    .vital-unit { color: #6B7280; font-size: 0.78rem; font-weight: 500; margin-left: 3px; }
    .vital-tile.status-connected .vital-value { color: #2ECC71; font-size: 1.05rem; }
    .vital-tile.status-disconnected .vital-value { color: #E74C3C; font-size: 1.05rem; }

    /* AI risk panel — an important clinical metric, not the hero element */
    .risk-panel {
        border: 1px solid #1F2430; border-radius: 12px; padding: 12px 16px;
        background: linear-gradient(180deg, #0D0F14 0%, #08090B 100%); margin: 4px 0 12px 0;
    }
    .risk-panel-header {
        display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;
    }
    .risk-panel-label {
        color: #8B92A0; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
    }
    .risk-score-row { display: flex; align-items: baseline; gap: 10px; }
    .risk-score-number { font-family: var(--font-mono); font-size: 2rem; font-weight: 700; color: #F4F5F7; line-height: 1; }
    .risk-score-of { color: #4C5566; font-size: 0.9rem; font-family: var(--font-mono); }
    .risk-meter-track { width: 100%; height: 7px; border-radius: 999px; background: #16181E; overflow: hidden; margin: 8px 0 4px 0; }
    .risk-meter-fill { height: 100%; border-radius: 999px; transition: width 0.4s ease; }

    .primary-reason {
        font-size: 1.05rem; font-weight: 600; color: #F4F5F7; line-height: 1.35;
        border-left: 3px solid #22D3B8; padding-left: 12px; margin: 8px 0;
    }
    .secondary-reason { color: #8B92A0; font-size: 0.88rem; padding: 2px 0 2px 15px; }

    [data-testid="stForm"] { border: 1px solid #1F2430; border-radius: 10px; background: #0E1118; }
    button[kind="secondary"], button[kind="primary"] { min-height: 46px; }

    .empty-bed {
        display: flex; align-items: center; justify-content: center; min-height: 380px;
        color: #3A3F4A; font-size: 1rem; text-align: center;
    }

    /* ---- Full-screen patient detail page (Doc 16 §43) ---- */
    .detail-top-bar {
        display: flex; align-items: center; justify-content: space-between;
        padding-bottom: 14px; margin-bottom: 18px; border-bottom: 1px solid #1A1C22;
    }
    .detail-identity { display: flex; align-items: baseline; gap: 14px; }
    .detail-patient-name { font-size: 1.8rem; font-weight: 700; color: #F4F5F7; }
    .detail-bed-tag { color: #5A6272; font-family: var(--font-mono); font-size: 0.85rem; }

    .detail-card {
        border: 1px solid #1A1C22; border-radius: 14px; background: #060708;
        padding: 20px 24px; margin-bottom: 18px;
    }
    .detail-card-title {
        color: #F4F5F7; font-size: 1rem; font-weight: 700; margin-bottom: 14px;
        display: flex; align-items: center; gap: 8px;
    }
    .detail-card-title .dot { width: 7px; height: 7px; border-radius: 50%; background: #22D3B8; }

    .detail-bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .detail-bar-label { width: 170px; flex-shrink: 0; color: #C4C9D2; font-size: 0.9rem; }
    .detail-bar-track { flex-grow: 1; height: 9px; border-radius: 999px; background: #16181E; overflow: hidden; }
    .detail-bar-fill { height: 100%; border-radius: 999px; }
    .detail-bar-value { width: 52px; text-align: right; font-family: var(--font-mono); color: #F4F5F7; font-size: 0.9rem; }

    .rule-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 0; border-bottom: 1px solid #16181E; font-size: 0.92rem;
    }
    .rule-row:last-child { border-bottom: none; }
    .rule-name { color: #F4F5F7; font-weight: 500; }
    .rule-meta { color: #6B7280; font-family: var(--font-mono); font-size: 0.82rem; }

    .compare-row {
        display: flex; justify-content: space-between; padding: 9px 0;
        border-bottom: 1px solid #16181E; font-size: 0.92rem;
    }
    .compare-row:last-child { border-bottom: none; }
    .compare-label { color: #8B92A0; }
    .compare-value { font-family: var(--font-mono); color: #F4F5F7; }

    .timeline-item { display: flex; gap: 12px; padding: 6px 0; font-size: 0.88rem; }
    .timeline-time { color: #4C5566; font-family: var(--font-mono); flex-shrink: 0; width: 70px; }
    .timeline-desc { color: #C4C9D2; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Hub / bed-pair configuration — read from the URL so each physical Hub
# device can be deep-linked to its assigned bed pair.
# ---------------------------------------------------------------------------
all_patients = database.list_patients()
patient_ids = [p["patient_id"] for p in all_patients]

hub_id = st.query_params.get("hub", "HUB-01")
bed_a_id = st.query_params.get("bed_a")
bed_b_id = st.query_params.get("bed_b")

if bed_a_id not in patient_ids:
    bed_a_id = patient_ids[0] if patient_ids else None
if bed_b_id not in patient_ids or bed_b_id == bed_a_id:
    remaining = [p for p in patient_ids if p != bed_a_id]
    bed_b_id = remaining[0] if remaining else None


def _bed_label_for(patient_id: str) -> str:
    if patient_id == bed_a_id:
        return "BED A"
    if patient_id == bed_b_id:
        return "BED B"
    return "—"


if "tz_key" not in st.session_state:
    st.session_state.tz_key = "UTC"

with st.sidebar:
    st.markdown("#### Hub configuration")
    st.caption(
        "Each physical SENTRA Hub is deep-linked to the two beds it sits between, e.g. "
        "`?hub=HUB-03&bed_a=P-A&bed_b=P-B`. This panel is for setup, not routine nursing use."
    )
    if patient_ids:

        def _fmt(pid):
            p = database.get_patient(pid) or {}
            return f"{p.get('name', pid)} ({pid})"

        new_hub_id = st.text_input("Hub ID", value=hub_id)
        new_bed_a = st.selectbox("Bed A patient", options=patient_ids,
                                  index=patient_ids.index(bed_a_id) if bed_a_id in patient_ids else 0,
                                  format_func=_fmt)
        remaining_for_b = [p for p in patient_ids if p != new_bed_a]
        new_bed_b = st.selectbox("Bed B patient", options=remaining_for_b,
                                  index=remaining_for_b.index(bed_b_id) if bed_b_id in remaining_for_b else 0,
                                  format_func=_fmt) if remaining_for_b else None
        if st.button("Apply hub configuration", use_container_width=True):
            st.query_params["hub"] = new_hub_id
            st.query_params["bed_a"] = new_bed_a
            if new_bed_b:
                st.query_params["bed_b"] = new_bed_b
            st.rerun()
    else:
        st.info("No patients calibrated yet — add one below first.")

    st.divider()
    st.markdown("#### Patient intake")
    st.caption(
        "Calibrate a new patient's starting baseline from a national-standard age-band "
        "reference range (Doc 07 §17) instead of a cold start."
    )
    with st.form("calibration_form", clear_on_submit=True):
        new_patient_id = st.text_input("Patient ID", placeholder="P-E")
        name = st.text_input("Patient name / label", placeholder="Bed 7")
        band_key = st.selectbox(
            "Age band",
            options=[key for key, _ in reference_ranges.choices()],
            format_func=lambda key: reference_ranges.get(key)["label"],
        )
        submitted = st.form_submit_button("Calibrate patient", use_container_width=True)
        if submitted and new_patient_id:
            database.set_patient_calibration(new_patient_id.strip(), name.strip(), band_key)
            st.success(f"{new_patient_id} calibrated to {reference_ranges.get(band_key)['label']}")
            st.info("Restart the simulator/pipeline process to pick up this new patient.")


def _vital_tile(label: str, value: str, unit: str = "", status_class: str = "") -> str:
    return (
        f'<div class="vital-tile {status_class}"><div class="vital-label">{label}</div>'
        f'<div class="vital-value">{value}<span class="vital-unit">{unit}</span></div></div>'
    )


def _risk_panel_html(snap: dict, color: str, label: str) -> str:
    fill_pct = max(0, min(100, snap["priority"]))
    return (
        f'<div class="risk-panel"><div class="risk-panel-header">'
        f'<span class="risk-panel-label">AI Cardiac Risk Score</span>'
        f'<span class="badge-xl" style="background:{color};color:{STATE_TEXT.get(snap["state"], "#FFFFFF")};'
        f'padding:3px 12px;font-size:0.72rem;">{label}</span></div>'
        f'<div class="risk-score-row"><span class="risk-score-number">{snap["priority"]:.0f}</span>'
        f'<span class="risk-score-of">/ 100</span></div>'
        f'<div class="risk-meter-track"><div class="risk-meter-fill" '
        f'style="width:{fill_pct}%;background:{color};"></div></div></div>'
    )


# ---------------------------------------------------------------------------
# Hub header strip
# ---------------------------------------------------------------------------
top_l, top_r = st.columns([3, 1.4])
with top_l:
    st.markdown(
        f'<div class="hub-bar" style="margin-bottom:0;">'
        f'<div><span class="hub-wordmark">SENTRA<span>.</span></span><span class="hub-id">{hub_id}</span>'
        f'<span class="hub-subtitle">Real-time patient monitoring + AI cardiac risk assessment</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with top_r:
    tz_col1, tz_col2 = st.columns([1.3, 1])
    with tz_col1:
        st.selectbox("Time zone", options=list(TIMEZONES.keys()), key="tz_key", label_visibility="collapsed")
    with tz_col2:
        st.markdown(
            f'<div class="hub-live" style="height:38px;align-items:center;">'
            f'<span class="hub-live-dot"></span>{now_in(st.session_state.tz_key).strftime("%H:%M:%S")} {st.session_state.tz_key}</div>',
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)


def _go_to_detail(patient_id: str) -> None:
    st.query_params["view"] = "detail"
    st.query_params["patient"] = patient_id
    # scope="app": this is called from inside an @st.fragment (the bed
    # panel's button), where a plain st.rerun() would only re-execute the
    # fragment — the top-level `view` routing below lives outside any
    # fragment and needs a full-app rerun to actually switch screens.
    st.rerun(scope="app")


def _go_to_hub() -> None:
    st.query_params.pop("view", None)
    st.query_params.pop("patient", None)
    st.rerun(scope="app")


# ---------------------------------------------------------------------------
# Bed panel (hub view)
# ---------------------------------------------------------------------------
def _bed_panel(bed_label: str, patient_id: str | None, snapshots_by_id: dict):
    """Everything in here runs inside one `with st.container(border=True):`
    block — a real Streamlit container, not a hand-spanned <div> (Streamlit
    renders each st.markdown() call as its own isolated HTML fragment, so a
    <div> opened in one call and closed in a later one gets auto-closed
    empty by the browser the moment it's parsed)."""
    if patient_id is None:
        st.markdown('<div class="bed-panel-marker empty"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="empty-bed">{bed_label}<br/>No patient assigned</div>', unsafe_allow_html=True)
        return

    patient = database.get_patient(patient_id) or {}
    snap = snapshots_by_id.get(patient_id)

    if snap is None:
        st.markdown('<div class="bed-panel-marker empty"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="empty-bed">{bed_label} · {patient.get("name", patient_id)}<br/>'
            f'<span style="font-size:0.85rem;">Waiting for first reading…</span></div>',
            unsafe_allow_html=True,
        )
        return

    state = snap["state"]
    color = STATE_COLORS.get(state, "#4C5566")
    label = STATE_LABEL.get(state, state)
    explanation = snap.get("explanation") or {}
    detail = snap.get("detail") or {}
    current = detail.get("current_readings") or {}
    panel_class = "critical" if state == "CRITICAL" else ("high" if state == "HIGH_PRIORITY" else "")

    seconds_since_update = now_in("UTC").timestamp() - snap["ts"]
    connected = seconds_since_update < 45

    st.markdown(f'<div class="bed-panel-marker {panel_class}"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="bed-label">{bed_label}</div>'
        f'<span class="badge-xl" style="background:{color};color:{STATE_TEXT.get(state, "#FFFFFF")};">{label}</span>'
        f'<div class="patient-name-xl">{patient.get("name", patient_id)}</div>'
        f'<span class="calibration-chip">'
        f'{reference_ranges.get(patient["age_band"])["label"] if patient.get("age_band") else "No calibration on file"}'
        f'</span>',
        unsafe_allow_html=True,
    )

    # ---- The ECG-equivalent hero element: real-time PPG waveform ----
    render_ppg_waveform(current.get("heart_rate"), color, height=110, connected=connected, key=f"bed_{patient_id}")
    st.markdown(
        '<div class="waveform-caption">PPG / PULSE WAVEFORM — rhythm at measured HR, not a raw captured trace</div>',
        unsafe_allow_html=True,
    )

    # ---- Vitals ----
    conn_status = "Connected" if connected else "Signal Lost"
    conn_class = "status-connected" if connected else "status-disconnected"
    tiles = (
        _vital_tile("Heart Rate", f'{current["heart_rate"]:.0f}' if "heart_rate" in current else "—", "bpm")
        + _vital_tile("SpO2", f'{current["spo2"]:.0f}' if "spo2" in current else "—", "%")
        + _vital_tile("Skin Temp", f'{current["temperature"]:.1f}' if "temperature" in current else "—", "°C")
        + _vital_tile("Sensor", conn_status, "", conn_class)
    )
    st.markdown(f'<div class="vitals-grid">{tiles}</div>', unsafe_allow_html=True)

    # ---- AI risk score: present, not dominant ----
    st.markdown(_risk_panel_html(snap, color, label), unsafe_allow_html=True)

    if explanation.get("primary_reason"):
        st.markdown(f'<div class="primary-reason">{explanation["primary_reason"]}</div>', unsafe_allow_html=True)

    for alert in snap.get("alerts", []):
        st.warning(alert, icon="⚠️")

    if st.button("View full patient detail →", key=f"detail_btn_{patient_id}", use_container_width=True):
        _go_to_detail(patient_id)


@st.fragment(run_every=REFRESH_SECONDS)
def _hub_fragment():
    snapshots = database.get_latest_snapshots()
    snapshots_by_id = {s["patient_id"]: s for s in snapshots}
    col_a, col_b = st.columns(2, gap="large")
    with col_a, st.container(border=True):
        _bed_panel("BED A", bed_a_id, snapshots_by_id)
    with col_b, st.container(border=True):
        _bed_panel("BED B", bed_b_id, snapshots_by_id)


# ---------------------------------------------------------------------------
# Full-screen patient detail page (Doc 16 §43)
# ---------------------------------------------------------------------------
@st.fragment(run_every=REFRESH_SECONDS)
def _detail_fragment(patient_id: str, bed_label: str):
    patient = database.get_patient(patient_id) or {}
    snapshots_by_id = {s["patient_id"]: s for s in database.get_latest_snapshots()}
    snap = snapshots_by_id.get(patient_id)

    if snap is None:
        st.info("Waiting for this patient's first reading…")
        return

    state = snap["state"]
    color = STATE_COLORS.get(state, "#4C5566")
    label = STATE_LABEL.get(state, state)
    explanation = snap.get("explanation") or {}
    detail = snap.get("detail") or {}
    current = detail.get("current_readings") or {}
    seconds_since_update = now_in("UTC").timestamp() - snap["ts"]
    connected = seconds_since_update < 45

    st.markdown(
        f'<div class="detail-top-bar"><div class="detail-identity">'
        f'<span class="detail-bed-tag">{bed_label}</span>'
        f'<span class="detail-patient-name">{patient.get("name", patient_id)}</span>'
        f'<span class="badge-xl" style="background:{color};color:{STATE_TEXT.get(state, "#FFFFFF")};">{label}</span>'
        f'</div><div style="color:#4C5566;font-family:var(--font-mono);font-size:0.85rem;">'
        f'Last updated {format_ts(snap["ts"], st.session_state.tz_key)} {st.session_state.tz_key}</div></div>',
        unsafe_allow_html=True,
    )

    wave_col, risk_col = st.columns([2, 1], gap="large")
    with wave_col:
        st.markdown('<div class="waveform-section-label">Live Monitoring</div>', unsafe_allow_html=True)
        render_ppg_waveform(current.get("heart_rate"), color, height=200, connected=connected, key=f"detail_{patient_id}")
        st.markdown(
            '<div class="waveform-caption">PPG / PULSE WAVEFORM — rhythm at measured HR, not a raw captured trace '
            '(no ECG electrodes installed on this hardware)</div>',
            unsafe_allow_html=True,
        )
        conn_status = "Connected" if connected else "Signal Lost"
        conn_class = "status-connected" if connected else "status-disconnected"
        tiles = (
            _vital_tile("Heart Rate", f'{current["heart_rate"]:.0f}' if "heart_rate" in current else "—", "bpm")
            + _vital_tile("SpO2", f'{current["spo2"]:.0f}' if "spo2" in current else "—", "%")
            + _vital_tile("Skin Temperature", f'{current["temperature"]:.1f}' if "temperature" in current else "—", "°C")
            + _vital_tile("Motion", f'{current["motion_intensity"]:.1f}' if "motion_intensity" in current else "—", "")
            + _vital_tile("Sensor Status", conn_status, "", conn_class)
        )
        st.markdown(f'<div class="vitals-grid" style="grid-template-columns:repeat(3,1fr);margin-top:14px;">{tiles}</div>', unsafe_allow_html=True)

    with risk_col:
        st.markdown('<div class="waveform-section-label">AI Clinical Assessment</div>', unsafe_allow_html=True)
        st.markdown(_risk_panel_html(snap, color, label), unsafe_allow_html=True)
        st.markdown(f'<div style="color:#8B92A0;font-size:0.85rem;">Confidence: '
                    f'<span style="color:#F4F5F7;font-family:var(--font-mono);">{snap["confidence"]*100:.0f}%</span></div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div style="color:#8B92A0;font-size:0.85rem;margin-top:4px;">Trend: '
                    f'<span style="color:#F4F5F7;">{(snap.get("trend") or "stable").title()}</span></div>',
                    unsafe_allow_html=True)
        if explanation.get("recommended_action"):
            st.markdown(f'<div style="margin-top:12px;padding:10px 12px;background:#0A0A0C;'
                        f'border:1px solid #1A1C22;border-radius:8px;color:#F4F5F7;font-size:0.9rem;">'
                        f'<strong>Recommended:</strong> {explanation["recommended_action"]}</div>', unsafe_allow_html=True)
        for alert in snap.get("alerts", []):
            st.warning(alert, icon="⚠️")

    if explanation.get("primary_reason"):
        st.markdown(f'<div class="primary-reason" style="font-size:1.15rem;margin-top:18px;">{explanation["primary_reason"]}</div>', unsafe_allow_html=True)

    # ---- Evidence ranking ----
    evidence = explanation.get("evidence") or []
    st.markdown('<div class="detail-card">', unsafe_allow_html=True)
    st.markdown('<div class="detail-card-title"><span class="dot"></span>Evidence Ranking</div>', unsafe_allow_html=True)
    if evidence:
        for e in evidence:
            pct = max(0, min(100, e["influence"] * 100))
            st.markdown(
                f'<div class="detail-bar-row"><div class="detail-bar-label">{e["label"]}</div>'
                f'<div class="detail-bar-track"><div class="detail-bar-fill" '
                f'style="width:{pct}%;background:#22D3B8;"></div></div>'
                f'<div class="detail-bar-value">{pct:.0f}%</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div style="color:#4C5566;font-size:0.9rem;">No significant findings</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ---- Subsystem risk ----
    subsystem_results = detail.get("subsystem_results") or []
    if subsystem_results:
        st.markdown('<div class="detail-card">', unsafe_allow_html=True)
        st.markdown('<div class="detail-card-title"><span class="dot"></span>Subsystem Risk</div>', unsafe_allow_html=True)
        for s in subsystem_results:
            pct = max(0, min(100, s["risk_score"]))
            st.markdown(
                f'<div class="detail-bar-row"><div class="detail-bar-label">{s["subsystem"].title()}</div>'
                f'<div class="detail-bar-track"><div class="detail-bar-fill" '
                f'style="width:{pct}%;background:{color};"></div></div>'
                f'<div class="detail-bar-value">{pct:.0f}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Triggered clinical rules ----
    rules = detail.get("triggered_rules") or []
    st.markdown('<div class="detail-card">', unsafe_allow_html=True)
    st.markdown('<div class="detail-card-title"><span class="dot"></span>Triggered Clinical Rules</div>', unsafe_allow_html=True)
    if rules:
        for r in rules:
            duration_min = r["duration_seconds"] / 60
            duration_text = f"{duration_min:.1f} min" if duration_min >= 1 else f"{r['duration_seconds']:.0f}s"
            st.markdown(
                f'<div class="rule-row"><span class="rule-name">{r["rule_name"]}</span>'
                f'<span class="rule-meta">severity {r["severity"]:.2f} · confidence {r["confidence"]*100:.0f}% · {duration_text}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div style="color:#4C5566;font-size:0.9rem;">None currently triggered</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ---- Baseline comparison ----
    baseline_profile = detail.get("baseline_profile") or {}
    baseline_deviation = detail.get("baseline_deviation") or {}
    if current and baseline_profile:
        st.markdown('<div class="detail-card">', unsafe_allow_html=True)
        st.markdown('<div class="detail-card-title"><span class="dot"></span>Baseline Comparison</div>', unsafe_allow_html=True)
        for comp_label, cur_key, base_key, dev_key, unit in _COMPARISON_ROWS:
            if cur_key not in current or baseline_profile.get(base_key) is None:
                continue
            cur_val = current[cur_key]
            base_val = baseline_profile[base_key]
            dev_val = baseline_deviation.get(dev_key) if dev_key else None
            dev_text = f" ({dev_val:.1f}σ)" if dev_val is not None else ""
            st.markdown(
                f'<div class="compare-row"><span class="compare-label">{comp_label}</span>'
                f'<span class="compare-value">{cur_val:.1f}{unit} vs {base_val:.1f}{unit} baseline{dev_text}</span></div>',
                unsafe_allow_html=True,
            )
        if not baseline_profile.get("learning_complete"):
            st.caption("Personal baseline still learning — reference range not yet fully established.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Timeline ----
    timeline = explanation.get("timeline") or []
    if timeline:
        st.markdown('<div class="detail-card">', unsafe_allow_html=True)
        st.markdown('<div class="detail-card-title"><span class="dot"></span>Timeline</div>', unsafe_allow_html=True)
        for t in timeline[-10:]:
            ts_text = format_iso(t["timestamp"], st.session_state.tz_key) if isinstance(t["timestamp"], str) else str(t["timestamp"])
            st.markdown(
                f'<div class="timeline-item"><span class="timeline-time">{ts_text}</span>'
                f'<span class="timeline-desc">{t["description"]}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def render_detail_page(patient_id: str):
    if st.button("← Back to Hub", key="back_to_hub"):
        _go_to_hub()
    _detail_fragment(patient_id, _bed_label_for(patient_id))


def render_hub_view():
    if not patient_ids:
        st.info("Waiting for patients... calibrate one in the sidebar, then start `python -m sentra.run_simulation`.")
        return
    _hub_fragment()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
view = st.query_params.get("view", "hub")
detail_patient = st.query_params.get("patient")

if view == "detail" and detail_patient in patient_ids:
    render_detail_page(detail_patient)
else:
    render_hub_view()
