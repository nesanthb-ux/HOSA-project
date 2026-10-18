"""Tests for the PPG-vs-ECG comparison tool.

    python -m pytest tests/test_compare_hr.py -v
"""
import importlib.util
import math
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "rehab_vr" / "firmware" / "aria_sensor_node" / "tools" / "compare_hr.py"
spec = importlib.util.spec_from_file_location("compare_hr", TOOL)
compare_hr = importlib.util.module_from_spec(spec)
sys.modules["compare_hr"] = compare_hr  # dataclasses look the module up by name
spec.loader.exec_module(compare_hr)


def rows(*specs):
    """specs: (ppg, ecg, motion_ok) per second."""
    out = []
    for i, (ppg, ecg, ok) in enumerate(specs):
        out.append(f"CMP,{1000 + i * 1000},{ppg},0.800,{ecg},{1 if ok else 0}")
    return out


def test_parses_a_valid_line_and_maps_nan_to_none():
    s = compare_hr.parse_line("CMP,12000,72.5,0.812,nan,1")
    assert s.millis == 12000
    assert s.ppg_bpm == 72.5
    assert s.ecg_bpm is None
    assert s.motion_ok is True


@pytest.mark.parametrize(
    "line",
    ["EDA=3.1 uS HR=70", "CMP,1,2,3", "CMP,abc,70,0.5,70,1", "CMP,1,seventy,0.5,70,1", ""],
)
def test_ignores_or_rejects_bad_lines(line):
    assert compare_hr.parse_line(line) is None


def test_malformed_cmp_lines_are_counted_but_other_logs_are_not():
    samples, malformed = compare_hr.parse(["boot noise", "CMP,1,70,0.9,70,1", "CMP,broken", "EDA=1 HR=nan"])
    assert len(samples) == 1
    assert malformed == 1


def test_perfect_agreement():
    samples, _ = compare_hr.parse(rows((70, 70, True), (72, 72, True), (75, 75, True)))
    r = compare_hr.analyze(samples)
    assert r["paired_seconds"] == 3
    assert r["bias_bpm"] == pytest.approx(0.0)
    assert r["mean_abs_error_bpm"] == pytest.approx(0.0)
    assert r["within_5_bpm_fraction"] == 1.0
    assert r["confident_but_wrong"] == 0


def test_bias_and_error_metrics_are_signed_correctly():
    # PPG reads 2 high, then 4 low: bias -1, MAE 3, RMSE sqrt(10)
    samples, _ = compare_hr.parse(rows((72, 70, True), (66, 70, True)))
    r = compare_hr.analyze(samples)
    assert r["bias_bpm"] == pytest.approx(-1.0)
    assert r["mean_abs_error_bpm"] == pytest.approx(3.0)
    assert r["rmse_bpm"] == pytest.approx(math.sqrt(10.0))


def test_confident_but_wrong_is_counted_separately():
    samples, _ = compare_hr.parse(rows((72, 70, True), (100, 70, True), (40, 70, True)))
    r = compare_hr.analyze(samples)
    assert r["confident_but_wrong"] == 2
    assert r["within_5_bpm_fraction"] == pytest.approx(1 / 3)


def test_missing_readings_hurt_coverage_not_error():
    # PPG absent in 2 of 4 seconds where the ECG had a value; the two present are exact.
    samples, _ = compare_hr.parse(rows((70, 70, True), ("nan", 71, True), ("nan", 72, True), (73, 73, True)))
    r = compare_hr.analyze(samples)
    assert r["coverage_overall"]["coverage"] == pytest.approx(0.5)
    assert r["paired_seconds"] == 2
    assert r["mean_abs_error_bpm"] == pytest.approx(0.0)


def test_seconds_without_a_reference_are_excluded_everywhere():
    samples, _ = compare_hr.parse(rows((70, "nan", True), (71, "nan", True)))
    r = compare_hr.analyze(samples)
    assert r["paired_seconds"] == 0
    assert r["coverage_overall"]["reference_seconds"] == 0
    assert r["coverage_overall"]["coverage"] is None
    assert "bias_bpm" not in r
    assert "nothing to compare" in compare_hr.format_report(r)


def test_coverage_is_split_by_motion_and_flags_readings_during_motion():
    samples, _ = compare_hr.parse(
        rows(
            (70, 70, True), (70, 70, True),      # still: both available
            ("nan", 90, False), ("nan", 90, False),  # moving: PPG correctly withheld
            (95, 90, False),                       # moving: PPG reported anyway (a firmware bug)
        )
    )
    r = compare_hr.analyze(samples)
    assert r["coverage_still"]["coverage"] == pytest.approx(1.0)
    assert r["coverage_moving"]["coverage"] == pytest.approx(1 / 3)
    assert r["ppg_reported_while_moving"] == 1


def test_single_pair_does_not_crash_the_spread_calculation():
    samples, _ = compare_hr.parse(rows((70, 72, True)))
    r = compare_hr.analyze(samples)
    lo, hi = r["limits_of_agreement_bpm"]
    assert lo == hi == pytest.approx(-2.0)


def test_report_is_readable_and_has_no_verdict():
    samples, _ = compare_hr.parse(rows((70, 70, True), (74, 70, True)))
    text = compare_hr.format_report(compare_hr.analyze(samples))
    assert "Availability" in text and "Agreement" in text
    assert "pass" not in text.lower() and "fail" not in text.lower()


def test_cli_exits_2_when_the_log_has_no_cmp_lines(tmp_path, capsys):
    log = tmp_path / "empty.txt"
    log.write_text("ARIA arm sensor node starting\nEDA=3 uS\n", encoding="utf-8")
    assert compare_hr.main([str(log)]) == 2
    assert "No CMP lines" in capsys.readouterr().err


def test_cli_end_to_end_json(tmp_path, capsys):
    log = tmp_path / "run.txt"
    log.write_text("\n".join(rows((70, 70, True), (72, 71, True))), encoding="utf-8")
    assert compare_hr.main([str(log), "--json"]) == 0
    assert '"paired_seconds": 2' in capsys.readouterr().out
