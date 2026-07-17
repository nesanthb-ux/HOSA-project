"""Live PPG (pulse) waveform renderer.

IMPORTANT — what this actually draws: the firmware performs beat detection
on-device and transmits a computed heart-rate value, not raw optical
waveform samples (see docs/HARDWARE_SCOPE.md §4 — a deliberate earlier
architecture decision to keep BLE payloads small). This component does not
have a captured trace to play back. It draws a standard PPG pulse
morphology (sharp systolic upstroke, dicrotic notch, diastolic decay) and
times each beat using the REAL, currently measured heart rate — the same
technique consumer fitness devices use for an animated heartbeat display.
The number driving it is genuine sensor data; the waveform *shape* is a
textbook template, not a per-patient captured signal. It is labeled
"Pulse rhythm at measured HR" everywhere it's shown specifically so it's
never mistaken for a raw captured trace, per CLAUDE.md ("never fabricate
medical values" / "never suppress uncertainty").

Uses st.components.v1.html because Streamlit's st.markdown(unsafe_allow_
html=True) does not execute embedded <script> tags — a real animated
canvas needs a genuine HTML component, not a markdown fragment.
"""
from __future__ import annotations

import json

import streamlit.components.v1 as components

# One cardiac cycle, x = fraction of cycle [0,1], y = amplitude [0,1].
# Standard PPG morphology: baseline -> sharp systolic upstroke -> peak ->
# fast fall -> dicrotic notch -> small dicrotic wave -> slow diastolic decay.
_PPG_TEMPLATE = [
    (0.00, 0.02), (0.06, 0.05), (0.14, 0.35), (0.20, 1.00), (0.26, 0.62),
    (0.32, 0.40), (0.38, 0.33), (0.44, 0.46), (0.52, 0.38), (0.65, 0.18),
    (0.80, 0.07), (1.00, 0.02),
]

_HTML_TEMPLATE = """
<div style="background:#000000;border-radius:8px;overflow:hidden;">
  <canvas id="__CANVAS_ID__" width="__WIDTH__" height="__HEIGHT__" style="display:block;width:100%;"></canvas>
</div>
<!--
st.components.v1.html() inserts this whole snippet via innerHTML, and
browsers deliberately never execute a <script> tag that arrived that way
(a built-in XSS mitigation, not a Streamlit bug) — confirmed empirically
while building this: a plain <script> here left the canvas completely
blank with no console errors, while a script element created and
appended via createElement/appendChild ran fine. The inert
type="text/plain" block below holds the real logic as inaccessible-to-
the-parser text; the <img onerror> immediately after is the one thing
HTML parsers reliably execute even from an innerHTML insertion (inline
event-handler attributes are evaluated at parse time), and its only job
is to copy that text into a real, dynamically created <script> element.
-->
<script id="__CANVAS_ID__-src" type="text/plain">
(function() {
    const canvas = document.getElementById("__CANVAS_ID__");
    const ctx = canvas.getContext("2d");
    const template = __TEMPLATE__;
    const heartRate = __HR__;
    const color = "__COLOR__";
    const connected = __CONNECTED__;
    const width = canvas.width;
    const height = canvas.height;
    const sampleRate = 120; // visual samples/sec, not a real acquisition rate
    const buffer = new Array(width).fill(0);

    function sampleAt(phase) {
        for (let i = 1; i < template.length; i++) {
            const [x0, y0] = template[i - 1];
            const [x1, y1] = template[i];
            if (phase <= x1) {
                const t = (phase - x0) / (x1 - x0 || 1);
                return y0 + (y1 - y0) * t;
            }
        }
        return template[template.length - 1][1];
    }

    // Pre-fill the buffer on load so the trace is already "full and
    // scrolling" from the very first frame, instead of sweeping up from a
    // blank canvas — this component gets recreated on every periodic
    // refresh (see app.py's st.fragment usage), so without this the
    // waveform would visibly reset every couple of seconds. Continuing
    // `elapsed` from where the pre-fill leaves off makes the transition
    // into the live animation seamless.
    const cycleDuration0 = (connected && heartRate > 0) ? 60.0 / heartRate : 1.0;
    for (let x = 0; x < width; x++) {
        const virtualElapsed = x / sampleRate;
        buffer[x] = connected ? sampleAt((virtualElapsed % cycleDuration0) / cycleDuration0) : 0;
    }
    let elapsed = width / sampleRate;
    let lastFrameTime = null;

    function drawGrid() {
        ctx.strokeStyle = "rgba(34, 211, 184, 0.06)";
        ctx.lineWidth = 1;
        for (let x = 0; x < width; x += 28) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
        }
        for (let y = 0; y < height; y += 28) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
        }
    }

    function frame() {
        const now = performance.now();
        if (lastFrameTime === null) lastFrameTime = now;
        const dt = Math.min(0.1, (now - lastFrameTime) / 1000);
        lastFrameTime = now;

        if (connected && heartRate > 0) {
            const cycleDuration = 60.0 / heartRate;
            const newSamples = Math.max(1, Math.round(dt * sampleRate));
            for (let i = 0; i < newSamples; i++) {
                elapsed += 1 / sampleRate;
                const phase = (elapsed % cycleDuration) / cycleDuration;
                buffer.shift();
                buffer.push(sampleAt(phase));
            }
        } else {
            buffer.shift();
            buffer.push(0);
        }

        ctx.clearRect(0, 0, width, height);
        drawGrid();

        if (!connected) {
            ctx.fillStyle = "#4C5566";
            ctx.font = "600 15px -apple-system, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("NO SIGNAL", width / 2, height / 2);
        }

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.4;
        ctx.lineJoin = "round";
        ctx.shadowColor = color;
        ctx.shadowBlur = connected ? 8 : 0;
        const pad = 10;
        const usableHeight = height - pad * 2;
        for (let x = 0; x < width; x++) {
            const y = height - pad - buffer[x] * usableHeight;
            if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
    }

    // setInterval rather than requestAnimationFrame: rAF is tied to the
    // paint cycle and simply never fires while a document's
    // visibilityState is "hidden" (spec-defined, e.g. an iframe not yet
    // laid out / a backgrounded kiosk display) — setInterval keeps
    // drawing regardless, so the trace is never silently stuck blank.
    frame();
    setInterval(frame, 33); // ~30fps
})();
</script>
<img src="x" alt="" style="display:none" onerror="
var s = document.createElement('script');
s.textContent = document.getElementById('__CANVAS_ID__-src').textContent;
document.body.appendChild(s);
">
"""


def render_ppg_waveform(heart_rate: float | None, color: str, height: int = 140,
                         connected: bool = True, key: str = "wave") -> None:
    """Renders an animated PPG-shaped waveform, timed by the real measured
    heart rate. See module docstring for exactly what is and isn't real
    about this visualization."""
    hr = heart_rate if (heart_rate and connected) else 0
    html = (
        _HTML_TEMPLATE
        .replace("__CANVAS_ID__", f"ppg-canvas-{key}")
        .replace("__WIDTH__", "600")
        .replace("__HEIGHT__", str(height))
        .replace("__TEMPLATE__", json.dumps(_PPG_TEMPLATE))
        .replace("__HR__", str(hr))
        .replace("__COLOR__", color)
        .replace("__CONNECTED__", "true" if connected else "false")
    )
    components.html(html, height=height + 4)
