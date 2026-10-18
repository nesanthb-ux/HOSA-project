// Run from rehab_vr/web:  node --test "tests/*.test.js"
import assert from "node:assert/strict";
import { test } from "node:test";

import { formatChannel, interpretReading } from "../src/sensor_view.js";

const FULL = { eda_us: 3.21, heart_rate_bpm: 72.4, skin_temp_c: 32.66, arousal_score: 0.31, channels_available: 3 };

test("formatChannel never shows a missing value as zero", () => {
  assert.equal(formatChannel(null, 2, "uS"), "—");
  assert.equal(formatChannel(undefined, 2, "uS"), "—");
  assert.equal(formatChannel(NaN, 2, "uS"), "—");
  assert.equal(formatChannel(Infinity, 2, "uS"), "—");
  assert.equal(formatChannel(0, 2, "uS"), "0.00 uS"); // a real zero is still shown
});

test("a full reading formats every channel", () => {
  const r = interpretReading(FULL);
  assert.equal(r.texts.eda, "3.21 µS");
  assert.equal(r.texts.hr, "72 bpm");
  assert.equal(r.texts.temp, "32.7 °C");
  assert.equal(r.texts.score, "0.31");
  assert.equal(r.canEscalate, true);
  assert.equal(r.status, null); // simulator: connection text left alone
});

test("a dropped heart-rate channel is shown as a dash and blocks stepping up", () => {
  const r = interpretReading({ ...FULL, heart_rate_bpm: null, channels_available: 2 });
  assert.equal(r.texts.hr, "—");
  assert.equal(r.canEscalate, false);
  assert.equal(r.status.kind, "partial");
  assert.match(r.status.text, /will not step up/);
  assert.equal(r.score, 0.31); // the partial score is still usable for RETREAT decisions
});

test("a partial reading names the channel that dropped out", () => {
  const r = interpretReading({
    ...FULL,
    heart_rate_bpm: null,
    channels_available: 2,
    channels_expected: ["eda_us", "heart_rate_bpm", "skin_temp_c"],
    channels_missing: ["heart_rate_bpm"],
    complete: false,
  });
  assert.match(r.status.text, /heart rate/);
  assert.equal(r.canEscalate, false);
});

test("no valid channels means no score, no escalation, and says so", () => {
  const r = interpretReading({
    eda_us: null, heart_rate_bpm: null, skin_temp_c: null, arousal_score: null,
    channels_available: 0, hardware_stale: false,
  });
  assert.equal(r.score, null);
  assert.equal(r.texts.score, "no data");
  assert.equal(r.canEscalate, false);
  assert.equal(r.status.kind, "none");
});

test("a stale node is reported as stale, ahead of anything else", () => {
  const r = interpretReading({
    eda_us: null, heart_rate_bpm: null, skin_temp_c: null, arousal_score: null,
    channels_available: 0, hardware_stale: true,
  });
  assert.equal(r.status.kind, "stale");
  assert.match(r.status.text, /not reporting/);
  assert.equal(r.canEscalate, false);
});

test("live hardware with all channels reports live", () => {
  const r = interpretReading({ ...FULL, hardware_stale: false });
  assert.equal(r.status.kind, "live");
  assert.equal(r.canEscalate, true);
});

test("a feed with no channels_available field is treated as fully available", () => {
  const { channels_available, ...legacy } = FULL;
  const r = interpretReading(legacy);
  assert.equal(r.canEscalate, true);
});

test("a non-numeric score is treated as no data", () => {
  assert.equal(interpretReading({ ...FULL, arousal_score: "0.3" }).score, null);
  assert.equal(interpretReading({ ...FULL, arousal_score: undefined }).score, null);
});

test("while calibrating, the status says so, shows time left, and nothing can step up", () => {
  const r = interpretReading({
    ...FULL,
    arousal_score: null,
    calibration: { state: "running", seconds_left: 12.4, personal_baseline: false, reason: null },
  });
  assert.equal(r.calibrating, true);
  assert.equal(r.canEscalate, false);
  assert.equal(r.status.kind, "calibrating");
  assert.match(r.status.text, /13 s left/);
});

test("even a stray score during calibration cannot escalate", () => {
  const r = interpretReading({ ...FULL, calibration: { state: "running", seconds_left: 5 } });
  assert.equal(r.canEscalate, false);
});

test("a failed calibration is reported with its reason and the default baseline is named", () => {
  const r = interpretReading({
    ...FULL,
    calibration: { state: "failed", seconds_left: null, personal_baseline: false, reason: "heart rate: 3 of 30 seconds valid" },
  });
  assert.equal(r.status.kind, "calibration_failed");
  assert.match(r.status.text, /default baseline/);
  assert.match(r.status.text, /heart rate: 3 of 30/);
  assert.equal(r.calibrating, false);
});

test("a finished calibration or idle state leaves normal status logic alone", () => {
  for (const state of ["idle", "done"]) {
    const r = interpretReading({ ...FULL, hardware_stale: false, calibration: { state } });
    assert.equal(r.status.kind, "live");
    assert.equal(r.canEscalate, true);
  }
});

test("a stale node outranks a failed-calibration note", () => {
  const r = interpretReading({ ...FULL, hardware_stale: true, arousal_score: null, calibration: { state: "failed", reason: "x" } });
  assert.equal(r.status.kind, "stale");
});

// ---- reduced-sensor builds -------------------------------------------------
// The two-sensor build (PPG + GSR, no skin temperature) must behave as a
// COMPLETE build. The bug this guards against is the athlete being frozen at
// level 0 forever because a channel that was never fitted counts as missing.
const MINIMAL = {
  eda_us: 3.21,
  heart_rate_bpm: 72.4,
  skin_temp_c: null,
  arousal_score: 0.31,
  channels_available: 2,
  channels_expected: ["eda_us", "heart_rate_bpm"],
  channels_missing: [],
  complete: true,
};

test("a two-sensor build is complete and CAN step up", () => {
  const r = interpretReading(MINIMAL);
  assert.equal(r.complete, true);
  assert.equal(r.canEscalate, true);
  assert.equal(r.status, null); // nothing is wrong, so nothing is announced
});

test("an unfitted channel says so instead of showing a dash", () => {
  const r = interpretReading(MINIMAL);
  assert.equal(r.texts.temp, "not fitted"); // not "—", which would mean "dropped out"
  assert.equal(r.texts.hr, "72 bpm");
});

test("a two-sensor build still blocks stepping up when a fitted channel drops", () => {
  const r = interpretReading({
    ...MINIMAL,
    heart_rate_bpm: null,
    channels_available: 1,
    channels_missing: ["heart_rate_bpm"],
    complete: false,
  });
  assert.equal(r.canEscalate, false);
  assert.equal(r.texts.hr, "—");
  assert.equal(r.texts.temp, "not fitted"); // the unfitted one is still not a dropout
  assert.match(r.status.text, /heart rate/);
});

test("calibrating still blocks a two-sensor build from stepping up", () => {
  const r = interpretReading({ ...MINIMAL, calibration: { state: "running", seconds_left: 9 } });
  assert.equal(r.canEscalate, false);
  assert.equal(r.status.kind, "calibrating");
});
