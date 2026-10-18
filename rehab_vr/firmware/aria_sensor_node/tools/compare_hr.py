"""Compares the arm-PPG heart rate against the ECG reference from a bench
recording, so any accuracy claim rests on measured error.

Record the Serial Monitor output of a sketch built with ENABLE_ECG_REFERENCE=1
to a text file, then:

    python tools/compare_hr.py recording.txt
    python tools/compare_hr.py recording.txt --json

Input lines it uses (everything else in the log is ignored):

    CMP,<millis>,<ppg_bpm|nan>,<ppg_quality>,<ecg_bpm|nan>,<motionOk 0|1>

What it reports, and what it deliberately does not:
  - Agreement statistics use ONLY seconds where both estimates exist, since
    error against a missing reference is undefined.
  - Coverage (how often the PPG produced a reading when the ECG did) is
    reported separately, split by still vs moving, because a PPG that is
    accurate but almost never available is a different result from one that
    is available and wrong.
  - "Confident but wrong" counts PPG readings that were reported yet more than
    10 bpm off. Those are the dangerous ones (a wrong number fed to the
    exposure engine), so they are called out on their own.
  - No pass/fail verdict. What error is acceptable is a judgment for whoever
    reads the numbers, and it depends on how the score is used.

The ECG reference is itself unvalidated software here (see ecg_reference.h);
check a few seconds against a finger pulse count before trusting the run.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from typing import Iterable, Optional

CONFIDENT_WRONG_BPM = 10.0
WITHIN_BPM = 5.0


@dataclass(frozen=True)
class Sample:
    millis: int
    ppg_bpm: Optional[float]
    ppg_quality: float
    ecg_bpm: Optional[float]
    motion_ok: bool


def _bpm(text: str) -> Optional[float]:
    text = text.strip().lower()
    if text in ("nan", "", "inf", "-inf"):
        return None
    value = float(text)
    return value if math.isfinite(value) else None


def parse_line(line: str) -> Optional[Sample]:
    """A Sample, or None if this is not a well-formed CMP line."""
    line = line.strip()
    if not line.startswith("CMP,"):
        return None
    parts = line.split(",")
    if len(parts) != 6:
        return None
    try:
        return Sample(
            millis=int(parts[1]),
            ppg_bpm=_bpm(parts[2]),
            ppg_quality=float(parts[3]),
            ecg_bpm=_bpm(parts[4]),
            motion_ok=parts[5].strip() == "1",
        )
    except ValueError:
        return None


def parse(lines: Iterable[str]) -> tuple[list[Sample], int]:
    """(samples, malformed_cmp_count). Non-CMP lines are ignored, not counted."""
    samples: list[Sample] = []
    malformed = 0
    for line in lines:
        if not line.strip().startswith("CMP,"):
            continue
        sample = parse_line(line)
        if sample is None:
            malformed += 1
        else:
            samples.append(sample)
    return samples, malformed


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return math.nan
    k = (len(sorted_values) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return sorted_values[int(k)]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def _coverage(samples: list[Sample]) -> dict:
    ref = [s for s in samples if s.ecg_bpm is not None]
    got = [s for s in ref if s.ppg_bpm is not None]
    return {"reference_seconds": len(ref), "ppg_available": len(got),
            "coverage": (len(got) / len(ref)) if ref else None}


def analyze(samples: list[Sample], malformed: int = 0) -> dict:
    pairs = [s for s in samples if s.ppg_bpm is not None and s.ecg_bpm is not None]
    errors = [s.ppg_bpm - s.ecg_bpm for s in pairs]
    abs_errors = sorted(abs(e) for e in errors)

    result: dict = {
        "samples": len(samples),
        "malformed_lines": malformed,
        "paired_seconds": len(pairs),
        "coverage_overall": _coverage(samples),
        "coverage_still": _coverage([s for s in samples if s.motion_ok]),
        "coverage_moving": _coverage([s for s in samples if not s.motion_ok]),
        "ppg_reported_while_moving": sum(1 for s in samples if not s.motion_ok and s.ppg_bpm is not None),
    }
    if pairs:
        bias = statistics.fmean(errors)
        sd = statistics.pstdev(errors) if len(errors) > 1 else 0.0
        result.update({
            "bias_bpm": bias,
            "mean_abs_error_bpm": statistics.fmean(abs_errors),
            "rmse_bpm": math.sqrt(statistics.fmean(e * e for e in errors)),
            "p95_abs_error_bpm": _percentile(abs_errors, 0.95),
            "limits_of_agreement_bpm": [bias - 1.96 * sd, bias + 1.96 * sd],
            "within_5_bpm_fraction": sum(1 for a in abs_errors if a <= WITHIN_BPM) / len(abs_errors),
            "confident_but_wrong": sum(1 for a in abs_errors if a > CONFIDENT_WRONG_BPM),
        })
    return result


def format_report(r: dict) -> str:
    def pct(x: Optional[float]) -> str:
        return "n/a" if x is None else f"{100 * x:.0f}%"

    lines = [
        f"Samples: {r['samples']} one-second rows ({r['malformed_lines']} malformed CMP lines skipped)",
        f"Seconds with both PPG and ECG: {r['paired_seconds']}",
        "",
        "Availability (PPG produced a reading when the ECG did)",
        f"  overall: {pct(r['coverage_overall']['coverage'])}  "
        f"({r['coverage_overall']['ppg_available']}/{r['coverage_overall']['reference_seconds']})",
        f"  arm still:  {pct(r['coverage_still']['coverage'])}  "
        f"({r['coverage_still']['ppg_available']}/{r['coverage_still']['reference_seconds']})",
        f"  arm moving: {pct(r['coverage_moving']['coverage'])}  "
        f"({r['coverage_moving']['ppg_available']}/{r['coverage_moving']['reference_seconds']})",
        f"  PPG readings reported while the IMU said moving: {r['ppg_reported_while_moving']} (should be 0)",
    ]
    if r["paired_seconds"]:
        lo, hi = r["limits_of_agreement_bpm"]
        lines += [
            "",
            "Agreement (PPG minus ECG, paired seconds only)",
            f"  bias: {r['bias_bpm']:+.2f} bpm",
            f"  mean absolute error: {r['mean_abs_error_bpm']:.2f} bpm",
            f"  RMSE: {r['rmse_bpm']:.2f} bpm",
            f"  95th percentile absolute error: {r['p95_abs_error_bpm']:.2f} bpm",
            f"  95% limits of agreement: {lo:+.1f} to {hi:+.1f} bpm",
            f"  within {WITHIN_BPM:.0f} bpm: {pct(r['within_5_bpm_fraction'])}",
            f"  confident but wrong (> {CONFIDENT_WRONG_BPM:.0f} bpm off): {r['confident_but_wrong']}",
        ]
    else:
        lines += ["", "No seconds had both a PPG and an ECG reading, so there is nothing to compare."]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", help="text file with the Serial Monitor output (or - for stdin)")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args(argv)

    handle = sys.stdin if args.log == "-" else open(args.log, encoding="utf-8", errors="replace")
    with handle:
        samples, malformed = parse(handle)
    if not samples:
        print("No CMP lines found. Was the sketch built with ENABLE_ECG_REFERENCE=1?", file=sys.stderr)
        return 2
    result = analyze(samples, malformed)
    print(json.dumps(result, indent=2) if args.json else format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
