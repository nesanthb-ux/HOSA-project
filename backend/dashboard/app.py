"""Interim UI covering Doc 16 Part 1's home-dashboard concepts (priority
queue, patient cards, confidence, live refresh) — the full embedded
touchscreen UI (Doc 16 Parts 1-3: Alert Center, Device Management,
Administration, multi-role auth) is not built. See README.md "What's
Implemented vs. Deferred".

Visual design: dark, dense clinical-ops dashboard (stat-tile header, card
grid, monospace vitals) in the style of modern bio/clinical-startup
tooling. Priority badge colors are Doc 16 §14's exact documented values,
not invented ones.
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

st.set_page_config(page_title="SENTRA | Priority Dashboard", page_icon="🩺", layout="wide")
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
STATE_ORDER = {"CRITICAL": 0, "HIGH_PRIORITY": 1, "CONCERN": 2, "WATCH": 3, "NORMAL": 4}

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    .mono { font-family: 'JetBrains Mono', 'SF Mono', monospace; }

    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
    .block-container { padding-top: 1.75rem; padding-bottom: 2rem; max-width: 1400px; }

    [data-testid="stSidebar"] {
        background: #0E1118;
        border-right: 1px solid #1F2430;
    }

    /* Top bar */
    .sentra-topbar {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 1.5rem;
    }
    .sentra-wordmark {
        font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; color: #F4F5F7;
    }
    .sentra-wordmark span { color: #22D3B8; }
    .sentra-tagline { color: #8B92A0; font-size: 0.85rem; margin-top: -2px; }
    .sentra-live {
        display: flex; align-items: center; gap: 6px; color: #8B92A0; font-size: 0.8rem;
        border: 1px solid #1F2430; border-radius: 999px; padding: 5px 12px; background: #12151D;
    }
    .sentra-live-dot {
        width: 7px; height: 7px; border-radius: 50%; background: #22D3B8;
        box-shadow: 0 0 0 3px rgba(34,211,184,0.15);
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

    /* Stat tiles */
    .stat-tile {
        background: #12151D; border: 1px solid #1F2430; border-radius: 10px;
        padding: 14px 18px;
    }
    .stat-label {
        color: #8B92A0; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
        font-weight: 600; margin-bottom: 4px;
    }
    .stat-value {
        font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 600; color: #F4F5F7;
    }

    /* Patient cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #12151D; border: 1px solid #1F2430 !important; border-radius: 12px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: #2A3040 !important; }

    .badge {
        display: inline-block; padding: 3px 11px; border-radius: 999px;
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .patient-name { font-size: 1.05rem; font-weight: 600; color: #F4F5F7; }
    .patient-rank { color: #4C5566; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
    .evidence-item {
        color: #C4C9D2; font-size: 0.85rem; padding: 2px 0; border-left: 2px solid #2A3040;
        padding-left: 8px; margin-bottom: 3px;
    }
    .evidence-item.primary { border-left-color: #22D3B8; color: #F4F5F7; font-weight: 500; }
    .meta-label { color: #4C5566; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .meta-value { font-family: 'JetBrains Mono', monospace; color: #C4C9D2; font-size: 0.95rem; }
    .calibration-chip {
        display: inline-block; margin-top: 6px; font-size: 0.72rem; color: #8B92A0;
        border: 1px solid #1F2430; border-radius: 6px; padding: 2px 8px; background: #0E1118;
    }

    [data-testid="stForm"] { border: 1px solid #1F2430; border-radius: 10px; background: #0E1118; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------
top_l, top_r = st.columns([3, 1])
with top_l:
    st.markdown(
        '<div class="sentra-wordmark">SENTRA<span>.</span></div>'
        '<div class="sentra-tagline">Explainable AI patient prioritization — '
        'every score traces to clinical rules, subsystem risk, baseline deviation, and confidence</div>',
        unsafe_allow_html=True,
    )
with top_r:
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;margin-top:6px;">'
        f'<div class="sentra-live"><span class="sentra-live-dot"></span>'
        f'Live · {datetime.now(timezone.utc).strftime("%H:%M:%S")} UTC</div></div>',
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.markdown("#### Patient intake")
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
        submitted = st.form_submit_button("Calibrate patient", use_container_width=True)
        if submitted and patient_id:
            database.set_patient_calibration(patient_id.strip(), name.strip(), band_key)
            st.success(f"{patient_id} calibrated to {reference_ranges.get(band_key)['label']}")
            st.info("Restart the simulator/pipeline process to pick up this new patient.")

placeholder = st.empty()


def render():
    snapshots = database.get_latest_snapshots()
    snapshots.sort(key=lambda s: (STATE_ORDER.get(s["state"], 9), -s["priority"]))

    with placeholder.container():
        # ---- Stat tiles ----
        total = len(snapshots)
        critical = sum(1 for s in snapshots if s["state"] in ("CRITICAL", "HIGH_PRIORITY"))
        alerts = sum(len(s.get("alerts", [])) for s in snapshots)
        avg_conf = (sum(s["confidence"] for s in snapshots) / total * 100) if total else 0.0

        c1, c2, c3, c4 = st.columns(4)
        for col, label, value in (
            (c1, "Patients Monitored", str(total)),
            (c2, "Critical / High Priority", str(critical)),
            (c3, "Active Alerts", str(alerts)),
            (c4, "Avg. Confidence", f"{avg_conf:.0f}%"),
        ):
            col.markdown(
                f'<div class="stat-tile"><div class="stat-label">{label}</div>'
                f'<div class="stat-value">{value}</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        if not snapshots:
            st.info("Waiting for patients... start `python -m sentra.run_simulation`.")
            return

        for rank, snap in enumerate(snapshots, start=1):
            patient_id = snap["patient_id"]
            patient = database.get_patient(patient_id) or {}
            state = snap["state"]
            color = STATE_COLORS.get(state, "#4C5566")
            text_color = STATE_TEXT.get(state, "#FFFFFF")
            label = STATE_LABEL.get(state, state)
            explanation = snap.get("explanation") or {}
            history = database.get_priority_history(patient_id, limit=60)

            with st.container(border=True):
                cols = st.columns([3, 2, 1.4])
                with cols[0]:
                    st.markdown(
                        f'<span class="patient-rank">#{rank}</span>&nbsp;&nbsp;'
                        f'<span class="badge" style="background:{color};color:{text_color};">{label}</span>'
                        f'<div class="patient-name" style="margin-top:6px;">{patient.get("name", patient_id)}</div>',
                        unsafe_allow_html=True,
                    )
                    reasons_html = ""
                    if explanation.get("primary_reason"):
                        reasons_html += f'<div class="evidence-item primary">{explanation["primary_reason"]}</div>'
                    for reason in explanation.get("secondary_reasons", [])[:3]:
                        reasons_html += f'<div class="evidence-item">{reason}</div>'
                    st.markdown(f'<div style="margin-top:8px;">{reasons_html}</div>', unsafe_allow_html=True)
                    if patient.get("age_band"):
                        band_label = reference_ranges.get(patient["age_band"])["label"]
                        st.markdown(f'<span class="calibration-chip">Calibrated · {band_label}</span>', unsafe_allow_html=True)

                with cols[1]:
                    st.markdown('<div class="meta-label">Priority trend</div>', unsafe_allow_html=True)
                    if history:
                        df = pd.DataFrame(history)[["ts", "priority"]]
                        df["ts"] = pd.to_datetime(df["ts"], unit="s")
                        df = df.set_index("ts")
                        st.line_chart(df, height=130, color=["#22D3B8"])
                    else:
                        st.markdown('<div class="meta-value">—</div>', unsafe_allow_html=True)

                with cols[2]:
                    st.markdown(
                        f'<div class="meta-label">Priority score</div>'
                        f'<div class="stat-value mono" style="font-size:1.3rem;">{snap["priority"]:.0f}</div>'
                        f'<div class="meta-label" style="margin-top:10px;">Confidence</div>'
                        f'<div class="meta-value">{snap["confidence"] * 100:.0f}%</div>'
                        f'<div class="meta-label" style="margin-top:10px;">Trend</div>'
                        f'<div class="meta-value">{(snap.get("trend") or "stable").title()}</div>',
                        unsafe_allow_html=True,
                    )
                    for alert in snap.get("alerts", []):
                        st.warning(alert, icon="⚠️")


render()
time.sleep(1)
st.rerun()
