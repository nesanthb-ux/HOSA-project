"""Tests for the ARIA sensor service: fusion (including dropped channels) and
the real-hardware ingest path. Run from the repo root:

    python -m pytest tests/test_rehab_sensor_service.py -v
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rehab_vr.sensor_service import fusion, hardware_reader  # noqa: E402
from rehab_vr.sensor_service.fusion import Baseline, fuse  # noqa: E402

BASE = Baseline()
NO_DATA = {"eda_us": None, "heart_rate_bpm": None, "skin_temp_c": None}


# ---------------------------------------------------------------- fusion ----
def test_weights_sum_to_one():
    total = fusion.WEIGHT_EDA + fusion.WEIGHT_HEART_RATE + fusion.WEIGHT_SKIN_TEMP
    assert total == pytest.approx(1.0)


def test_resting_baseline_scores_zero():
    result = fuse(BASE.eda_us, BASE.heart_rate_bpm, BASE.skin_temp_c)
    assert result["arousal_score"] == 0.0
    assert result["channels_available"] == 3


def test_fully_saturated_scores_one():
    # +200% EDA, +60% HR, -1.5C temp are each documented as "fully saturated".
    result = fuse(BASE.eda_us * 3, BASE.heart_rate_bpm * 1.6, BASE.skin_temp_c - 1.5)
    assert result["arousal_score"] == 1.0


def test_score_rises_with_each_channel():
    calm = fuse(BASE.eda_us, BASE.heart_rate_bpm, BASE.skin_temp_c)["arousal_score"]
    assert fuse(BASE.eda_us * 2, BASE.heart_rate_bpm, BASE.skin_temp_c)["arousal_score"] > calm
    assert fuse(BASE.eda_us, BASE.heart_rate_bpm * 1.3, BASE.skin_temp_c)["arousal_score"] > calm
    assert fuse(BASE.eda_us, BASE.heart_rate_bpm, BASE.skin_temp_c - 1.0)["arousal_score"] > calm


def test_score_is_clamped_to_unit_range():
    assert fuse(500.0, 400.0, -10.0)["arousal_score"] == 1.0
    assert fuse(0.0, 30.0, 40.0)["arousal_score"] == 0.0


def test_dropped_channel_is_excluded_not_treated_as_zero():
    # Only EDA is present and it is fully saturated. If the missing channels
    # were counted as zero the score would be 0.5, not 1.0.
    result = fuse(BASE.eda_us * 3, None, None)
    assert result["channels_available"] == 1
    assert result["arousal_score"] == 1.0
    assert result["channels"]["heart_rate"]["available"] is False
    assert result["channels"]["heart_rate"]["raw"] is None


def test_partial_score_renormalizes_remaining_weights():
    both = fuse(BASE.eda_us * 3, BASE.heart_rate_bpm, None)  # EDA=1.0, HR=0.0
    expected = fusion.WEIGHT_EDA / (fusion.WEIGHT_EDA + fusion.WEIGHT_HEART_RATE)
    assert both["arousal_score"] == pytest.approx(expected, abs=1e-3)
    assert both["channels_available"] == 2


def test_no_channels_means_no_score():
    result = fuse(None, None, None)
    assert result["arousal_score"] is None
    assert result["channels_available"] == 0


# ------------------------------------------------------------- hardware -----
@pytest.fixture(scope="module")
def ingest_url():
    port = hardware_reader.ensure_ingest_server_started(port=0)
    return f"http://127.0.0.1:{port}/ingest"


def _post(url, body):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=2).status


def test_never_reported_returns_all_none_not_baseline_values():
    # Runs before any POST (module state is fresh): honest "no data".
    if hardware_reader._last_seen is not None:
        pytest.skip("another test already posted a reading in this process")
    assert hardware_reader.is_stale() is True
    assert hardware_reader.read() == NO_DATA


def test_valid_post_is_returned(ingest_url):
    assert _post(ingest_url, {"eda_us": 3.2, "heart_rate_bpm": 88.0, "skin_temp_c": 32.1}) == 204
    assert hardware_reader.is_stale() is False
    assert hardware_reader.read() == {"eda_us": 3.2, "heart_rate_bpm": 88.0, "skin_temp_c": 32.1}


def test_omitted_channel_becomes_none_and_replaces_old_value(ingest_url):
    _post(ingest_url, {"eda_us": 3.0, "heart_rate_bpm": 90.0, "skin_temp_c": 32.0})
    # Heart rate dropped out this second (e.g. motion artifact on the PPG).
    _post(ingest_url, {"eda_us": 3.1, "skin_temp_c": 32.0})
    reading = hardware_reader.read()
    assert reading["heart_rate_bpm"] is None  # not the stale 90.0
    assert reading["eda_us"] == 3.1


def test_empty_object_is_a_heartbeat_not_a_reading(ingest_url):
    # The firmware sends {} when it has nothing trustworthy: node alive, no data.
    _post(ingest_url, {"eda_us": 3.0, "heart_rate_bpm": 80.0, "skin_temp_c": 33.0})
    assert _post(ingest_url, {}) == 204
    assert hardware_reader.is_stale() is False
    assert hardware_reader.read() == NO_DATA


def test_null_channel_is_none(ingest_url):
    _post(ingest_url, {"eda_us": 2.5, "heart_rate_bpm": None, "skin_temp_c": 33.0})
    assert hardware_reader.read()["heart_rate_bpm"] is None


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("eda_us", -1.0),
        ("eda_us", 5000.0),
        ("heart_rate_bpm", 0.0),
        ("heart_rate_bpm", 900.0),
        ("skin_temp_c", -40.0),
        ("skin_temp_c", 95.0),
    ],
)
def test_implausible_value_becomes_none(ingest_url, field, bad_value):
    body = {"eda_us": 3.0, "heart_rate_bpm": 80.0, "skin_temp_c": 33.0}
    body[field] = bad_value
    _post(ingest_url, body)
    assert hardware_reader.read()[field] is None


def test_non_finite_json_value_becomes_none(ingest_url):
    # Python's json accepts NaN/Infinity literals; a buggy firmware could send them.
    _post(ingest_url, b'{"eda_us": NaN, "heart_rate_bpm": Infinity, "skin_temp_c": 33.0}')
    reading = hardware_reader.read()
    assert reading["eda_us"] is None
    assert reading["heart_rate_bpm"] is None
    assert reading["skin_temp_c"] == 33.0


@pytest.mark.parametrize(
    "bad_body",
    [b"not json", b"[1, 2, 3]", b'{"eda_us": "abc"}', b'{"eda_us": true}'],
)
def test_malformed_payload_is_rejected_with_400(ingest_url, bad_body):
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(ingest_url, bad_body)
    assert err.value.code == 400


def test_rejected_payload_does_not_disturb_the_last_good_reading(ingest_url):
    _post(ingest_url, {"eda_us": 3.3, "heart_rate_bpm": 77.0, "skin_temp_c": 32.5})
    with pytest.raises(urllib.error.HTTPError):
        _post(ingest_url, b"not json")
    assert hardware_reader.read() == {"eda_us": 3.3, "heart_rate_bpm": 77.0, "skin_temp_c": 32.5}


def test_wrong_path_is_404_every_time_even_with_a_body(ingest_url):
    # Repeated: the original bug (answering before reading the body made
    # Windows reset the connection) only showed up some of the time.
    for _ in range(25):
        with pytest.raises(urllib.error.HTTPError) as err:
            _post(ingest_url.replace("/ingest", "/nope"), {"eda_us": 3.0, "pad": "x" * 500})
        assert err.value.code == 404


def test_oversized_body_is_refused_with_413_and_not_read(ingest_url):
    big = b'{"eda_us": 3.0, "pad": "' + b"x" * (hardware_reader.MAX_BODY_BYTES + 100) + b'"}'
    with pytest.raises((urllib.error.HTTPError, ConnectionError)) as err:
        _post(ingest_url, big)
    if isinstance(err.value, urllib.error.HTTPError):
        assert err.value.code == 413
    # Whatever happened, the oversized message must not have been accepted.
    assert hardware_reader.read()["eda_us"] != 3.0 or hardware_reader.read()["eda_us"] is None


def test_missing_content_length_is_a_clean_400(ingest_url):
    import http.client
    from urllib.parse import urlparse

    u = urlparse(ingest_url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=2)
    conn.putrequest("POST", "/ingest")
    conn.endheaders()  # no Content-Length, no body
    assert conn.getresponse().status == 400
    conn.close()


def test_reading_goes_stale_and_returns_none(ingest_url, monkeypatch):
    _post(ingest_url, {"eda_us": 3.0, "heart_rate_bpm": 80.0, "skin_temp_c": 33.0})
    assert hardware_reader.is_stale() is False
    monkeypatch.setattr(hardware_reader, "STALE_AFTER_SECONDS", 0.05)
    time.sleep(0.12)
    assert hardware_reader.is_stale() is True
    assert hardware_reader.read() == NO_DATA
