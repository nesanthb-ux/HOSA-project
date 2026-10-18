"""Tests for baseline calibration and the WebSocket server that runs it.

    python -m pytest tests/test_calibration_and_server.py -v
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rehab_vr.sensor_service.calibration import BaselineCalibrator  # noqa: E402
from rehab_vr.sensor_service.fusion import Baseline, fuse  # noqa: E402
from rehab_vr.sensor_service import sensor_config  # noqa: E402
from rehab_vr.sensor_service.server import SensorSession, run_server  # noqa: E402

REST = {"eda_us": 4.0, "heart_rate_bpm": 80.0, "skin_temp_c": 32.0}


def reading(eda=4.0, hr=80.0, temp=32.0):
    return {"eda_us": eda, "heart_rate_bpm": hr, "skin_temp_c": temp}


# ------------------------------------------------------------ calibrator ----
def test_baseline_is_the_median_of_each_channel():
    c = BaselineCalibrator(total_ticks=5)
    for eda in (3.0, 4.0, 5.0, 4.0, 100.0):  # one wild artifact
        c.add(reading(eda=eda))
    result = c.result()
    assert result.ok
    assert result.baseline.eda_us == 4.0  # the median ignores the 100.0
    assert result.baseline.heart_rate_bpm == 80.0
    assert result.baseline.skin_temp_c == 32.0


def test_not_done_until_all_ticks_and_result_refuses_early():
    c = BaselineCalibrator(total_ticks=3)
    c.add(reading())
    assert not c.done and c.ticks_left == 2
    with pytest.raises(RuntimeError):
        c.result()
    c.add(reading())
    c.add(reading())
    assert c.done and c.ticks_left == 0


def test_extra_readings_after_done_are_ignored():
    c = BaselineCalibrator(total_ticks=2)
    for eda in (4.0, 4.0, 999.0, 999.0):
        c.add(reading(eda=eda))
    assert c.result().baseline.eda_us == 4.0


def test_a_channel_with_too_few_valid_seconds_fails_and_names_it():
    c = BaselineCalibrator(total_ticks=10, min_valid_fraction=0.6)
    for i in range(10):
        c.add({"eda_us": 4.0, "heart_rate_bpm": 80.0 if i < 3 else None, "skin_temp_c": 32.0})
    result = c.result()
    assert not result.ok
    assert result.baseline is None
    assert "heart rate: 3 of 10" in result.reason
    assert "skin conductance" not in result.reason  # only the failing channel is named


def test_missing_channels_are_skipped_not_counted_as_zero():
    c = BaselineCalibrator(total_ticks=5)
    for i in range(5):
        c.add({"eda_us": 4.0, "heart_rate_bpm": 80.0, "skin_temp_c": 32.0 if i % 2 == 0 else None})
    result = c.result()
    assert result.ok  # 3 of 5 = 60% meets the minimum
    assert result.baseline.skin_temp_c == 32.0  # not dragged toward 0 by the gaps


def test_no_data_at_all_fails_every_channel():
    c = BaselineCalibrator(total_ticks=4)
    for _ in range(4):
        c.add({"eda_us": None, "heart_rate_bpm": None, "skin_temp_c": None})
    result = c.result()
    assert not result.ok
    for label in ("skin conductance", "heart rate", "skin temperature"):
        assert label in result.reason


@pytest.mark.parametrize("bad", [0, -3])
def test_rejects_nonsense_durations(bad):
    with pytest.raises(ValueError):
        BaselineCalibrator(total_ticks=bad)


# -------------------------------------------------------------- session -----
def test_score_uses_the_default_baseline_until_calibrated():
    s = SensorSession(tick_seconds=1.0, calibration_seconds=3, config=sensor_config.FULL)
    out = s.process(reading())
    assert out["arousal_score"] == fuse(4.0, 80.0, 32.0, Baseline())["arousal_score"]
    assert out["arousal_score"] > 0.0  # generic baseline mismatches this athlete
    assert out["calibration"]["state"] == "idle"
    assert out["calibration"]["personal_baseline"] is False


def test_calibration_withholds_the_score_then_applies_the_personal_baseline():
    s = SensorSession(tick_seconds=1.0, calibration_seconds=3)
    s.start_calibration()
    states = []
    for _ in range(3):
        out = s.process(reading())
        states.append((out["calibration"]["state"], out["arousal_score"]))
    assert states[0] == ("running", None)
    assert states[1] == ("running", None)
    assert states[2][0] == "done"
    assert states[2][1] is None  # the tick that completes it is still not scored

    after = s.process(reading())
    assert after["arousal_score"] == 0.0  # resting reading now scores as resting
    assert after["calibration"]["personal_baseline"] is True


def test_failed_calibration_keeps_the_previous_baseline_and_reports_why():
    s = SensorSession(tick_seconds=1.0, calibration_seconds=3, config=sensor_config.FULL)
    s.start_calibration()
    for _ in range(3):
        s.process({"eda_us": None, "heart_rate_bpm": None, "skin_temp_c": None})
    out = s.process(reading())
    assert out["calibration"]["state"] == "failed"
    assert out["calibration"]["personal_baseline"] is False
    assert "not enough valid readings" in out["calibration"]["reason"]
    assert out["arousal_score"] == fuse(4.0, 80.0, 32.0, Baseline())["arousal_score"]  # still the default


def test_seconds_left_counts_down():
    s = SensorSession(tick_seconds=1.0, calibration_seconds=4)
    s.start_calibration()
    left = [s.process(reading())["calibration"]["seconds_left"] for _ in range(3)]
    assert left == [3.0, 2.0, 1.0]


def test_partial_channels_still_score_outside_calibration():
    s = SensorSession(config=sensor_config.FULL)
    out = s.process({"eda_us": 6.0, "heart_rate_bpm": None, "skin_temp_c": 33.5})
    assert out["channels_available"] == 2
    assert out["arousal_score"] is not None


# --------------------------------------------------------------- server -----
class FakeReader:
    def __init__(self, values):
        self.values = values

    def read(self):
        return dict(self.values)


async def _serve_and_connect():
    ready = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(
        run_server(FakeReader(REST), host="127.0.0.1", port=0, tick_seconds=0.05, calibration_seconds=0.2, ready=ready)
    )
    port = await asyncio.wait_for(ready, timeout=3)
    return task, f"ws://127.0.0.1:{port}"


async def _recv(ws):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout=2))


def test_server_broadcasts_and_calibrates_over_a_real_websocket():
    async def scenario():
        task, url = await _serve_and_connect()
        try:
            async with websockets.connect(url) as ws:
                first = await _recv(ws)
                assert first["eda_us"] == 4.0
                assert first["calibration"]["state"] == "idle"
                assert first["arousal_score"] > 0  # default baseline vs this athlete

                await ws.send("calibrate")
                seen = set()
                final = None
                for _ in range(40):
                    msg = await _recv(ws)
                    seen.add(msg["calibration"]["state"])
                    if msg["calibration"]["state"] == "running":
                        assert msg["arousal_score"] is None
                    if msg["calibration"]["state"] == "done":
                        final = msg
                        break
                assert "running" in seen and final is not None
                assert final["calibration"]["personal_baseline"] is True

                settled = await _recv(ws)
                assert settled["arousal_score"] == 0.0
        finally:
            task.cancel()

    asyncio.run(scenario())


def test_two_browsers_share_one_calibration_and_both_see_it():
    async def scenario():
        task, url = await _serve_and_connect()
        try:
            async with websockets.connect(url) as a, websockets.connect(url) as b:
                await _recv(a)
                await _recv(b)
                await a.send("calibrate")
                got_a = got_b = False
                for _ in range(20):
                    if (await _recv(a))["calibration"]["state"] == "running":
                        got_a = True
                    if (await _recv(b))["calibration"]["state"] == "running":
                        got_b = True
                    if got_a and got_b:
                        break
                assert got_a and got_b
        finally:
            task.cancel()

    asyncio.run(scenario())


def test_junk_messages_and_a_second_calibrate_request_do_not_disturb_anything():
    async def scenario():
        task, url = await _serve_and_connect()
        try:
            async with websockets.connect(url) as ws:
                await ws.send("hello")
                await ws.send("calibrate")
                await ws.send("calibrate")  # already running: ignored, not restarted
                states = [(await _recv(ws))["calibration"]["state"] for _ in range(4)]
                assert "running" in states
        finally:
            task.cancel()

    asyncio.run(scenario())
