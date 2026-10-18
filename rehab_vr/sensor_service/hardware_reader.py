"""Real ESP32 sensor-node reader — same read() contract as simulator.py,
except that any channel may come back as None.

The ESP32 firmware (rehab_vr/firmware/) connects to WiFi and POSTs a JSON
reading — any of {"eda_us", "heart_rate_bpm", "skin_temp_c"} — to this
process about once per second. This module runs a tiny background HTTP
server to receive those POSTs and caches the most recent one.

A wearable drops readings, especially optical heart rate during motion, so
this module never invents a value to fill a gap:
  - a channel the firmware omits, or sends as null, is None;
  - a value that is not finite, or is outside a generous plausibility range
    (a sanity check for garbage, not a clinical threshold), is None;
  - if the node hasn't reported recently, every channel is None.
A malformed request (bad JSON, non-numeric value) is rejected with HTTP 400
and never crashes the broadcast loop server.py runs read() from.
"""
from __future__ import annotations

import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

INGEST_PORT = 8766
STALE_AFTER_SECONDS = 5.0  # how long a reading is trusted before we say so

# Plausibility bounds. These only reject sensor garbage (a floating input,
# a divide-by-zero in firmware); they are not clinical reference ranges.
PLAUSIBLE_RANGE = {
    "eda_us": (0.0, 100.0),
    "heart_rate_bpm": (20.0, 250.0),
    "skin_temp_c": (15.0, 45.0),
}
CHANNELS = tuple(PLAUSIBLE_RANGE)

_lock = threading.Lock()
_latest: dict[str, float | None] = {name: None for name in CHANNELS}
_last_seen: float | None = None  # time.monotonic() of the most recent POST


def _parse_channel(name: str, value) -> float | None:
    """None for a missing/null/implausible value. Raises ValueError/TypeError
    for something that isn't a number at all (that's a malformed request)."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a number, not a boolean")
    number = float(value)
    if not math.isfinite(number):
        return None
    low, high = PLAUSIBLE_RANGE[name]
    if not (low <= number <= high):
        return None
    return number


MAX_BODY_BYTES = 2048  # a real message is ~70 bytes; this port listens on the whole network


class _IngestHandler(BaseHTTPRequestHandler):
    def _respond(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if length < 0:
            self._respond(400)
            return
        if length > MAX_BODY_BYTES:
            self._respond(413)  # refuse without reading it: never buffer an unbounded body
            return

        # Read the body BEFORE deciding anything else. Answering while request
        # bytes are still unread makes Windows reset the connection, and the
        # client never sees the response.
        body = self.rfile.read(length)
        if self.path != "/ingest":
            self._respond(404)
            return

        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TypeError("payload must be a JSON object")
            parsed = {name: _parse_channel(name, payload.get(name)) for name in CHANNELS}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._respond(400)
            print(f"hardware_reader: rejected bad payload from {self.client_address[0]}: {exc}")
            return

        global _last_seen
        with _lock:
            # Each POST fully replaces the cache, so a channel that dropped
            # out this second is None now, not its last good value.
            _latest.update(parsed)
            _last_seen = time.monotonic()

        self._respond(204)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # silence the default per-request access log — this posts every second


_server: HTTPServer | None = None


def ensure_ingest_server_started(port: int = INGEST_PORT) -> int:
    """Idempotent — safe to call multiple times (read() calls it too).
    Returns the port actually bound (pass port=0 to get a free one)."""
    global _server
    if _server is None:
        _server = HTTPServer(("0.0.0.0", port), _IngestHandler)
        thread = threading.Thread(target=_server.serve_forever, daemon=True, name="hardware-ingest")
        thread.start()
        print(f"hardware_reader: listening for the ESP32 node on http://0.0.0.0:{_server.server_port}/ingest")
    return _server.server_port


def read() -> dict:
    """Same keys as simulator.read(), but any value may be None (channel not
    currently valid). If the node has never reported, or has gone quiet, all
    three are None — never a made-up resting value."""
    ensure_ingest_server_started()
    if is_stale():
        return {name: None for name in CHANNELS}
    with _lock:
        return dict(_latest)


def seconds_since_last_reading() -> float | None:
    """None if no hardware reading has ever arrived since this process started."""
    with _lock:
        if _last_seen is None:
            return None
        return time.monotonic() - _last_seen


def is_stale() -> bool:
    """True if the node has never reported in, or hasn't in a while — the
    dashboard should say so rather than keep showing the last good number
    as if it were live."""
    age = seconds_since_last_reading()
    return age is None or age > STALE_AFTER_SECONDS
