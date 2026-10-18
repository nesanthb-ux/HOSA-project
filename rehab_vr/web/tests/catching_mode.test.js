// Run from rehab_vr/web:  node --test "tests/*.test.js"
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CATCHES_TO_SPEED_UP,
  CatchingModeEngine,
  FLOOR_SPEED_MPH,
  MISSES_TO_SLOW_DOWN,
  SPEED_STEP_MPH,
  flightSeconds,
  speedBand,
} from "../src/catching_mode.js";
import { RETREAT_ABOVE } from "../src/exposure_levels.js";

const CAUGHT = { caught: true, arousalScore: 0.2 };
const MISSED = { caught: false, arousalScore: 0.2 };

function engine(options = {}) {
  return new CatchingModeEngine({ startSpeedMph: 35, trainerCapMph: 55, ...options });
}

// ---------------------------------------------------------------- physics ---
test("flight time is distance over speed, in real units", () => {
  // 60.5 ft at 60 mph. 60 mph = 88 ft/s exactly, so 60.5/88 s.
  assert.ok(Math.abs(flightSeconds(60.5, 60) - 60.5 / 88) < 1e-9);
  // Faster ball, less time.
  assert.ok(flightSeconds(46, 80) < flightSeconds(46, 40));
});

test("flight time refuses nonsense instead of returning a number", () => {
  assert.equal(flightSeconds(0, 50), null);
  assert.equal(flightSeconds(46, 0), null);
  assert.equal(flightSeconds(46, -10), null);
});

test("speed bands cover every speed and rise in order", () => {
  assert.equal(speedBand(30).label, "Soft toss");
  assert.equal(speedBand(95).label, "Game speed");
  let previous = -1;
  for (const mph of [25, 35, 45, 55, 65, 75, 100]) {
    assert.ok(speedBand(mph).id >= previous);
    previous = speedBand(mph).id;
  }
});

// ------------------------------------------------------------ performance ---
test("a streak of catches raises the speed by one step", () => {
  const e = engine();
  for (let i = 0; i < CATCHES_TO_SPEED_UP - 1; i += 1) {
    e.update(CAUGHT);
    assert.equal(e.state().speedMph, 35, "must not move before the streak is complete");
  }
  assert.equal(e.update(CAUGHT).speedMph, 35 + SPEED_STEP_MPH);
});

test("a miss breaks the catch streak", () => {
  const e = engine();
  e.update(CAUGHT);
  e.update(CAUGHT);
  e.update(MISSED); // resets the streak
  e.update(CAUGHT);
  e.update(CAUGHT);
  assert.equal(e.state().speedMph, 35, "two catches after a miss is not a streak of three");
});

test("consecutive misses lower the speed", () => {
  const e = engine({ startSpeedMph: 45 });
  e.update(MISSED);
  assert.equal(e.state().speedMph, 45, "one miss is not enough");
  assert.equal(e.update(MISSED).speedMph, 45 - SPEED_STEP_MPH);
});

test("the speed never goes below the floor", () => {
  const e = engine({ startSpeedMph: FLOOR_SPEED_MPH });
  for (let i = 0; i < 20; i += 1) e.update(MISSED);
  assert.equal(e.state().speedMph, FLOOR_SPEED_MPH);
});

// --------------------------------------------------------- trainer limits ---
test("the trainer cap is a hard ceiling that catches cannot pass", () => {
  const e = engine({ startSpeedMph: 50, trainerCapMph: 55 });
  for (let i = 0; i < 30; i += 1) e.update(CAUGHT);
  assert.equal(e.state().speedMph, 55);
  assert.equal(e.state().atCap, true);
});

test("a start speed above the cap is pulled down to the cap", () => {
  assert.equal(engine({ startSpeedMph: 90, trainerCapMph: 40 }).state().speedMph, 40);
});

test("lowering the cap mid-session lowers the current speed at once", () => {
  const e = engine({ startSpeedMph: 55, trainerCapMph: 55 });
  const seen = [];
  e.onChange = (_state, event) => seen.push(event.reason);
  e.setTrainerCap(40);
  assert.equal(e.state().speedMph, 40);
  assert.deepEqual(seen, ["trainer_cap_lowered"]);
});

// ------------------------------------------------------- arousal as brake ---
test("a stress spike lowers the speed at once, even on a caught ball", () => {
  const e = engine({ startSpeedMph: 45 });
  const state = e.update({ caught: true, arousalScore: RETREAT_ABOVE });
  assert.equal(state.speedMph, 45 - SPEED_STEP_MPH);
});

test("a stress spike clears the catch streak so it cannot speed up next", () => {
  const e = engine({ startSpeedMph: 45 });
  e.update(CAUGHT);
  e.update(CAUGHT);
  e.update({ caught: true, arousalScore: 0.9 }); // spike: down one, streak cleared
  e.update(CAUGHT);
  e.update(CAUGHT);
  assert.equal(e.state().speedMph, 40, "only two catches since the spike");
});

test("arousal never raises the speed, it only lowers it", () => {
  const e = engine({ startSpeedMph: 40 });
  for (let i = 0; i < 20; i += 1) e.update({ caught: null, arousalScore: 0.0 });
  assert.equal(e.state().speedMph, 40, "perfect calm with no catches changes nothing");
});

test("partial sensor data blocks speeding up but still allows slowing down", () => {
  const up = engine();
  for (let i = 0; i < 9; i += 1) up.update({ ...CAUGHT, canAdvance: false });
  assert.equal(up.state().speedMph, 35);

  const down = engine({ startSpeedMph: 45 });
  down.update({ ...MISSED, canAdvance: false });
  down.update({ ...MISSED, canAdvance: false });
  assert.equal(down.state().speedMph, 40);
});

test("a missing arousal score does not block ordinary progression", () => {
  const e = engine();
  for (let i = 0; i < CATCHES_TO_SPEED_UP; i += 1) e.update({ caught: true, arousalScore: null });
  assert.equal(e.state().speedMph, 40);
});

// ------------------------------------------------------------- unjudged ----
test("an attempt that could not be judged counts as neither catch nor miss", () => {
  const e = engine({ startSpeedMph: 45 });
  for (let i = 0; i < 10; i += 1) e.update({ caught: null, arousalScore: 0.2 });
  const s = e.state();
  assert.equal(s.speedMph, 45);
  assert.equal(s.attempts, 0, "a lost camera is not an attempt by the athlete");
});

// -------------------------------------------------- optional reaction gate --
test("with no trainer reaction limit, a slow catch still counts", () => {
  const e = engine();
  for (let i = 0; i < CATCHES_TO_SPEED_UP; i += 1) e.update({ caught: true, reactionSeconds: 3.0 });
  assert.equal(e.state().speedMph, 40);
});

test("a trainer reaction limit makes a slow catch not count toward speeding up", () => {
  const e = engine({ qualifyingReactionSeconds: 0.6 });
  for (let i = 0; i < 5; i += 1) e.update({ caught: true, reactionSeconds: 1.2 });
  assert.equal(e.state().speedMph, 35);
  assert.equal(e.state().caughtTotal, 5, "it was still caught, and still counted as caught");
  assert.equal(e.state().missStreak, 0, "a slow catch is not a miss either");
});

// ------------------------------------------------------------- reporting ---
test("state reports what the athlete needs next and the flight time", () => {
  const e = engine({ startSpeedMph: 40, distanceFeet: 46 });
  e.update(CAUGHT);
  const s = e.state();
  assert.equal(s.catchesToSpeedUp, CATCHES_TO_SPEED_UP - 1);
  assert.ok(Math.abs(s.flightSeconds - 46 / (40 * (5280 / 3600))) < 1e-9);
  assert.equal(s.band.label, speedBand(40).label);
});

test("every speed change reports where it came from and why", () => {
  const events = [];
  const e = new CatchingModeEngine({ startSpeedMph: 40, trainerCapMph: 60, onChange: (_s, ev) => events.push(ev) });
  for (let i = 0; i < CATCHES_TO_SPEED_UP; i += 1) e.update(CAUGHT);
  for (let i = 0; i < MISSES_TO_SLOW_DOWN; i += 1) e.update(MISSED);
  assert.deepEqual(
    events.map((ev) => [ev.action, ev.reason, ev.fromMph, ev.toMph]),
    [
      ["speed_up", "catch_streak", 40, 45],
      ["slow_down", "miss_streak", 45, 40],
    ]
  );
});

test("no event fires when the speed does not actually change", () => {
  const events = [];
  const e = new CatchingModeEngine({ startSpeedMph: 30, trainerCapMph: 30, onChange: (_s, ev) => events.push(ev) });
  for (let i = 0; i < 10; i += 1) e.update(CAUGHT); // already at the cap
  assert.deepEqual(events, []);
});

// ------------------------------------------------- explanations of events ---
import { athleteCatchReason, athleteCatchStatus, technicalCatchReason } from "../src/explain.js";

test("every speed change the engine can emit produces both wordings", () => {
  const events = [];
  const e = new CatchingModeEngine({
    startSpeedMph: 40,
    trainerCapMph: 60,
    onChange: (_s, ev) => events.push(ev),
  });
  for (let i = 0; i < CATCHES_TO_SPEED_UP; i += 1) e.update(CAUGHT); // catch_streak
  for (let i = 0; i < MISSES_TO_SLOW_DOWN; i += 1) e.update(MISSED); // miss_streak
  e.update({ caught: true, arousalScore: 0.9 }); // arousal_spike
  e.setTrainerCap(30); // trainer_cap_lowered

  assert.deepEqual(
    events.map((ev) => ev.reason),
    ["catch_streak", "miss_streak", "arousal_spike", "trainer_cap_lowered"]
  );
  for (const ev of events) {
    const tech = technicalCatchReason(ev);
    const athlete = athleteCatchReason(ev);
    assert.match(tech, /\d+ to \d+ mph/, `technical text names both speeds: ${tech}`);
    assert.ok(athlete.length > 10 && !/mph|threshold|arousal \d/.test(athlete), `athlete text stays plain: ${athlete}`);
    assert.notEqual(tech, athlete);
  }
});

test("the technical text for a stress spike names the score and threshold", () => {
  const events = [];
  const e = new CatchingModeEngine({ startSpeedMph: 45, onChange: (_s, ev) => events.push(ev) });
  e.update({ caught: false, arousalScore: 0.82 });
  const text = technicalCatchReason(events[0]);
  assert.match(text, /0\.82/);
  assert.match(text, new RegExp(String(RETREAT_ABOVE)));
});

test("the athlete status never prescribes how many throws to take", () => {
  const e = engine();
  for (const state of [e.state(), e.update(CAUGHT), e.update(MISSED)]) {
    const text = athleteCatchStatus(state);
    assert.ok(text.length > 0);
    assert.doesNotMatch(text, /throw \d+|\d+ throws|reps|sets/i);
  }
});

test("the status counts down to the next speed increase", () => {
  const e = engine();
  e.update(CAUGHT);
  assert.match(athleteCatchStatus(e.state()), new RegExp(`${CATCHES_TO_SPEED_UP - 1} more`));
  assert.match(athleteCatchStatus(engine({ trainerCapMph: 35 }).state()), /trainer/i);
});
