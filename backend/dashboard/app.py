"""SENTRA Hub bedside display.

Physical deployment: one small touchscreen (Doc 16 §5 — 7-24", touch,
always-on) mounted between two patient beds, wired to that bed pair's
Patient Nodes. A hospital ward runs many of these Hub units, each showing
only the two beds it's physically positioned between — not a scrolling
ward-wide list. Every Hub points at the same backend/database and is
deep-linked via URL query params to the two patients it's responsible for,
e.g. `?hub=HUB-03&bed_a=P-A&bed_b=P-B`, so the same app.py is what every
physical unit in the ward runs.

This covers Doc 16 §3's design goal directly: a nurse walking past should
know within 3 seconds which of these two patients (if either) needs
attention, within 5 seconds why, within 10 seconds what to do — there is
no ward-wide overview here to scan past, by design.

The Doc 16 Parts 1-3 concepts not built: Alert Center, Device Management,
Administration, multi-role auth, and a central ward-wide overview screen.
See README.md "What's Implemented vs. Deferred".
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentra import database  # noqa: E402
from sentra.baseline_engine import reference_ranges  # noqa: E402

st.set_page_config(
    page_title="SENTRA Hub", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed"
)
database.init_db()

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
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 1400px; }

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
    .hub-live {
        display: flex; align-items: center; gap: 7px; color: #8B92A0; font-size: 0.82rem;
        font-family: var(--font-mono);
    }
    .hub-live-dot {
        width: 8px; height: 8px; border-radius: 50%; background: #22D3B8;
        box-shadow: 0 0 0 4px rgba(34,211,184,0.15); animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

    /* Bed panel */
    .bed-panel {
        border: 1px solid #1A1C22; border-radius: 16px; background: #060708;
        padding: 22px 26px; min-height: 480px;
    }
    .bed-panel.critical { border-color: #8E0000; box-shadow: 0 0 0 1px #8E0000, 0 0 24px rgba(142,0,0,0.35); }
    .bed-panel.high { border-color: #E74C3C; box-shadow: 0 0 0 1px #E74C3C, 0 0 18px rgba(231,76,60,0.2); }

    .bed-label {
        color: #5A6272; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.1em; margin-bottom: 10px;
    }
    .badge-xl {
        display: inline-block; padding: 7px 18px; border-radius: 999px;
        font-size: 1rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .patient-name-xl { font-size: 2.1rem; font-weight: 700; color: #F4F5F7; margin: 14px 0 4px 0; line-height: 1.1; }
    .calibration-chip {
        display: inline-block; font-size: 0.78rem; color: #6B7280;
        border: 1px solid #1A1C22; border-radius: 6px; padding: 2px 9px; background: #0A0A0C;
    }

    .priority-row { display: flex; align-items: baseline; gap: 14px; margin: 22px 0 6px 0; }
    .priority-number { font-family: var(--font-mono); font-size: 3.4rem; font-weight: 700; color: #F4F5F7; line-height: 1; }
    .priority-of { color: #4C5566; font-size: 1.1rem; font-family: var(--font-mono); }
    .priority-meter-track { width: 100%; height: 10px; border-radius: 999px; background: #16181E; overflow: hidden; margin: 10px 0 22px 0; }
    .priority-meter-fill { height: 100%; border-radius: 999px; transition: width 0.4s ease; }

    .primary-reason {
        font-size: 1.3rem; font-weight: 600; color: #F4F5F7; line-height: 1.35;
        border-left: 4px solid #22D3B8; padding-left: 14px; margin-bottom: 10px;
    }
    .secondary-reason { color: #8B92A0; font-size: 0.95rem; padding: 3px 0 3px 18px; }

    .bed-footer {
        display: flex; align-items: center; justify-content: space-between;
        margin-top: 20px; padding-top: 16px; border-top: 1px solid #16181E;
    }
    .footer-metric-label { color: #4C5566; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .footer-metric-value { font-family: var(--font-mono); color: #C4C9D2; font-size: 1.05rem; font-weight: 600; }
    .conn-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 5px; }

    .empty-bed {
        display: flex; align-items: center; justify-content: center; min-height: 480px;
        color: #3A3F4A; font-size: 1rem; border: 1px dashed #1A1C22; border-radius: 16px;
    }

    [data-testid="stForm"] { border: 1px solid #1F2430; border-radius: 10px; background: #0E1118; }
    button[kind="secondary"], button[kind="primary"] { min-height: 48px; }
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

# ---------------------------------------------------------------------------
# Hub header strip
# ---------------------------------------------------------------------------
st.markdown(
    f'<div class="hub-bar">'
    f'<div><span class="hub-wordmark">SENTRA<span>.</span></span><span class="hub-id">{hub_id}</span></div>'
    f'<div class="hub-live"><span class="hub-live-dot"></span>{datetime.now(timezone.utc).strftime("%H:%M:%S")} UTC</div>'
    f'</div>',
    unsafe_allow_html=True,
)

placeholder = st.empty()


def _bed_panel(bed_label: str, patient_id: str | None, snapshots_by_id: dict):
    if patient_id is None:
        st.markdown(f'<div class="empty-bed">{bed_label} — no patient assigned</div>', unsafe_allow_html=True)
        return

    patient = database.get_patient(patient_id) or {}
    snap = snapshots_by_id.get(patient_id)

    if snap is None:
        st.markdown(
            f'<div class="empty-bed">{bed_label} · {patient.get("name", patient_id)}<br/>'
            f'<span style="font-size:0.85rem;">waiting for first reading…</span></div>',
            unsafe_allow_html=True,
        )
        return

    state = snap["state"]
    color = STATE_COLORS.get(state, "#4C5566")
    text_color = STATE_TEXT.get(state, "#FFFFFF")
    label = STATE_LABEL.get(state, state)
    explanation = snap.get("explanation") or {}
    panel_class = "critical" if state == "CRITICAL" else ("high" if state == "HIGH_PRIORITY" else "")

    # Windows close roughly every 15s (Doc 03 §8's 50%-overlap step); no
    # fresh snapshot in the last 45s means this bed's node has likely gone
    # quiet, not just that the model hasn't recomputed yet.
    seconds_since_update = datetime.now(timezone.utc).timestamp() - snap["ts"]
    connected = seconds_since_update < 45
    conn_color = "#2ECC71" if connected else "#E74C3C"

    st.markdown(f'<div class="bed-panel {panel_class}">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="bed-label">{bed_label}</div>'
        f'<span class="badge-xl" style="background:{color};color:{text_color};">{label}</span>'
        f'<div class="patient-name-xl">{patient.get("name", patient_id)}</div>'
        f'<span class="calibration-chip">'
        f'{reference_ranges.get(patient["age_band"])["label"] if patient.get("age_band") else "No calibration on file"}'
        f'</span>',
        unsafe_allow_html=True,
    )

    fill_pct = max(0, min(100, snap["priority"]))
    st.markdown(
        f'<div class="priority-row"><span class="priority-number">{snap["priority"]:.0f}</span>'
        f'<span class="priority-of">/ 100 priority</span></div>'
        f'<div class="priority-meter-track">'
        f'<div class="priority-meter-fill" style="width:{fill_pct}%;background:{color};"></div></div>',
        unsafe_allow_html=True,
    )

    if explanation.get("primary_reason"):
        st.markdown(f'<div class="primary-reason">{explanation["primary_reason"]}</div>', unsafe_allow_html=True)
    for reason in explanation.get("secondary_reasons", [])[:2]:
        st.markdown(f'<div class="secondary-reason">— {reason}</div>', unsafe_allow_html=True)

    history = database.get_priority_history(patient_id, limit=40)
    if history:
        df = pd.DataFrame(history)[["ts", "priority"]]
        df["ts"] = pd.to_datetime(df["ts"], unit="s")
        df = df.set_index("ts")
        st.line_chart(df, height=90, color=[color])

    st.markdown(
        f'<div class="bed-footer">'
        f'<div><div class="footer-metric-label">Confidence</div>'
        f'<div class="footer-metric-value">{snap["confidence"] * 100:.0f}%</div></div>'
        f'<div><div class="footer-metric-label">Trend</div>'
        f'<div class="footer-metric-value">{(snap.get("trend") or "stable").title()}</div></div>'
        f'<div><span class="conn-dot" style="background:{conn_color};"></span>'
        f'<span class="footer-metric-value" style="font-size:0.85rem;">{"Connected" if connected else "Signal lost"}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    for alert in snap.get("alerts", []):
        st.warning(alert, icon="⚠️")


def render():
    snapshots = database.get_latest_snapshots()
    snapshots_by_id = {s["patient_id"]: s for s in snapshots}

    with placeholder.container():
        if not patient_ids:
            st.info("Waiting for patients... calibrate one in the sidebar, then start `python -m sentra.run_simulation`.")
            return

        col_a, col_b = st.columns(2, gap="large")
        with col_a:
            _bed_panel("BED A", bed_a_id, snapshots_by_id)
        with col_b:
            _bed_panel("BED B", bed_b_id, snapshots_by_id)


render()
time.sleep(1)
st.rerun()
