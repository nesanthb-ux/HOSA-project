"""Tests for reduced-sensor builds.

The bug these guard against: the exposure engine refuses to step an athlete UP
unless every channel arrived. On a two-sensor build (no skin temperature) the
third channel is missing on every reading, so without a notion of which
channels the build actually HAS, the athlete would be stuck at level 0 forever
and calibration would fail forever, with nothing explaining why.

    python -m pytest tests/test_sensor_config.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rehab_vr.sensor_service import sensor_config  # noqa: E402
from rehab_vr.sensor_service.calibration import BaselineCalibrator  # noqa: E402
from rehab_vr.sensor_service.fusion import READING_TO_CHANNEL, Baseline  # noqa: E402
from rehab_vr.sensor_service.server import SensorSession  # noqa: E402

FULL_READING = {"eda_us": 4.0, "heart_rate_bpm": 80.0, "skin_temp_c": 32.0}


def minimal_session(**kwargs):
    return SensorSession(config=sensor_config.MINIMAL, **kwargs)


# --------------------------------------------------------------- config -----
def test_the_default_build_is_the_two_sensor_one():
    assert sensor_config.DEFAULT is sensor_config.MINIMAL
    assert sensor_config.MINIMAL.expected == ("eda_us", "heart_rate_bpm")


def test_grip_is_never_a_scored_channel():
    # Grip force has no validated mapping to fear, so it must not reach the score.
    for config in sensor_config.CONFIGS.values():
        assert "grip_raw" not in config.expected
    assert "grip_raw" in sensor_config.MINIMAL_WITH_GRIP.telemetry


def test_a_config_cannot_expect_something_unscoreable():
    with pytest.raises(ValueError):
        sensor_config.SensorConfig(name="bad", expected=("grip_raw",))
    with pytest.raises(ValueError):
        sensor_config.SensorConfig(name="empty", expected=())


def test_unknown_config_name_is_refused_by_name():
    with pytest.raises(ValueError) as err:
        sensor_config.get("nope")
    assert "nope" in str(err.value)


def test_every_reading_key_maps_to_a_fusion_channel():
    assert set(READING_TO_CHANNEL) == set(sensor_config.SCORED_CHANNELS)


# ------------------------------------------------------------- session ------
def test_two_sensor_build_is_complete_and_can_step_up():
    out = minimal_session().process(FULL_READING)
    assert out["complete"] is True
    assert out["channels_missing"] == []
    assert out["channels_expected"] == ["eda_us", "heart_rate_bpm"]
    assert out["arousal_score"] is not None


def test_an_unfitted_channel_is_ignored_even_when_the_simulator_sends_it():
    # The simulator always produces all three. A minimal build must behave
    # exactly like the hardware it stands in for, or a demo looks better than
    # the real thing ever will.
    out = minimal_session().process(FULL_READING)
    assert out["skin_temp_c"] is None
    assert out["channels"]["skin_temp"]["available"] is False
    assert out["channels_available"] == 2


def test_a_real_dropout_on_a_fitted_channel_still_blocks_stepping_up():
    out = minimal_session().process({**FULL_READING, "heart_rate_bpm": None})
    assert out["complete"] is False
    assert out["channels_missing"] == ["heart_rate_bpm"]
    assert out["arousal_score"] is not None  # still usable for retreating


def test_the_full_build_still_needs_all_three():
    session = SensorSession(config=sensor_config.FULL)
    assert session.process(FULL_READING)["complete"] is True
    partial = session.process({**FULL_READING, "skin_temp_c": None})
    assert partial["complete"] is False
    assert partial["channels_missing"] == ["skin_temp_c"]


def test_the_score_differs_between_configs_for_the_same_reading():
    # Not a bug: the minimal build renormalizes EDA and heart rate to total 1,
    # so the same raw numbers give a different, honestly-labelled score.
    # Deliberately mid-range: a saturated reading scores 1.0 either way.
    hot = {"eda_us": 4.0, "heart_rate_bpm": 80.0, "skin_temp_c": 33.0}
    minimal = minimal_session().process(hot)
    full = SensorSession(config=sensor_config.FULL).process(hot)
    assert minimal["arousal_score"] != full["arousal_score"]
    assert minimal["channels_available"] == 2
    assert full["channels_available"] == 3


# ---------------------------------------------------------- calibration -----
def test_calibration_finishes_on_a_build_with_no_temperature_sensor():
    session = minimal_session(tick_seconds=1.0, calibration_seconds=3)
    session.start_calibration()
    for _ in range(3):
        out = session.process(FULL_READING)
    assert out["calibration"]["state"] == "done"
    assert out["calibration"]["personal_baseline"] is True


def test_that_calibration_would_have_failed_without_the_fix():
    # Same readings, but the calibrator is asked for all three channels while
    # the temperature channel never arrives. This is the old behaviour.
    calibrator = BaselineCalibrator(total_ticks=3, channels=sensor_config.SCORED_CHANNELS)
    for _ in range(3):
        calibrator.add({"eda_us": 4.0, "heart_rate_bpm": 80.0, "skin_temp_c": None})
    assert calibrator.result().ok is False


def test_an_unfitted_channel_keeps_its_documented_default_baseline():
    calibrator = BaselineCalibrator(total_ticks=2, channels=("eda_us", "heart_rate_bpm"))
    for _ in range(2):
        calibrator.add({"eda_us": 5.0, "heart_rate_bpm": 90.0, "skin_temp_c": None})
    baseline = calibrator.result().baseline
    assert baseline.eda_us == 5.0
    assert baseline.heart_rate_bpm == 90.0
    assert baseline.skin_temp_c == Baseline().skin_temp_c  # unused, never scored


def test_calibration_still_names_a_fitted_channel_that_was_too_noisy():
    session = minimal_session(tick_seconds=1.0, calibration_seconds=4)
    session.start_calibration()
    for _ in range(4):
        out = session.process({"eda_us": 4.0, "heart_rate_bpm": None, "skin_temp_c": 32.0})
    assert out["calibration"]["state"] == "failed"
    assert "heart rate" in out["calibration"]["reason"]
    assert "skin temperature" not in out["calibration"]["reason"]  # not fitted, not its fault


def test_calibrator_refuses_channels_it_cannot_score():
    with pytest.raises(ValueError):
        BaselineCalibrator(total_ticks=3, channels=("grip_raw",))
    with pytest.raises(ValueError):
        BaselineCalibrator(total_ticks=3, channels=())
