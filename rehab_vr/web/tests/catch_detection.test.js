// Run from rehab_vr/web:  node --test "tests/*.test.js"
import assert from "node:assert/strict";
import { test } from "node:test";

import { CatchAttempt, catchHandFor, wristPoint } from "../src/catch_detection.js";

// A ball flying straight at a hand parked at x = 1. Positions are in one
// shared space; the units only have to match the catch radius.
function ballAt(t) {
  return { x: 2 - t, y: 0, z: 0 };
}

function runAttempt(handAt, { radius = 0.12, frames = 11, step = 0.1 } = {}) {
  const attempt = new CatchAttempt({ thrownAtSeconds: 0, catchRadius: radius });
  for (let i = 0; i < frames; i += 1) {
    const t = i * step;
    attempt.update(handAt(t), ballAt(t), t);
  }
  return attempt.result();
}

test("a hand that meets the ball is a catch", () => {
  const r = runAttempt(() => ({ x: 1, y: 0, z: 0 })); // ball passes exactly through
  assert.equal(r.judged, true);
  assert.equal(r.caught, true);
  assert.ok(r.closestDistance < 0.12);
});

test("a hand that never gets near the ball is a miss", () => {
  const r = runAttempt(() => ({ x: 1, y: 5, z: 0 })); // way off to the side
  assert.equal(r.judged, true);
  assert.equal(r.caught, false);
  assert.ok(r.closestDistance > 0.12);
});

test("the catch radius decides a near miss", () => {
  const justOutside = () => ({ x: 1, y: 0.2, z: 0 });
  assert.equal(runAttempt(justOutside, { radius: 0.12 }).caught, false);
  assert.equal(runAttempt(justOutside, { radius: 0.3 }).caught, true);
});

test("reaction time is measured from the throw to the first real hand movement", () => {
  // Hand sits still until t = 0.3, then moves a long way.
  const r = runAttempt((t) => ({ x: 1, y: t < 0.3 ? 0 : 1, z: 0 }), { radius: 0.5 });
  assert.ok(Math.abs(r.reactionSeconds - 0.3) < 1e-9);
});

test("tiny jitter does not count as the athlete starting to move", () => {
  const r = runAttempt((t) => ({ x: 1, y: (t % 0.2) * 0.02, z: 0 }));
  assert.equal(r.reactionSeconds, null, "a hand that never really moved has no reaction time");
});

test("a hand that never moves still gets judged on position", () => {
  const r = runAttempt(() => ({ x: 1, y: 0, z: 0 }));
  assert.equal(r.caught, true);
  assert.equal(r.reactionSeconds, null); // it was already in the right place
});

// ---------------------------------------------------------- lost tracking --
test("an attempt with no tracked frames is NOT JUDGED, not a miss", () => {
  const attempt = new CatchAttempt({ thrownAtSeconds: 0 });
  for (let i = 0; i < 10; i += 1) attempt.update(null, ballAt(i * 0.1), i * 0.1);
  const r = attempt.result();
  assert.equal(r.judged, false);
  assert.equal(r.caught, null, "a lost camera must never be scored against the athlete");
  assert.equal(r.samples, 0);
});

test("frames with bad numbers are skipped, and the rest still judge the attempt", () => {
  const attempt = new CatchAttempt({ thrownAtSeconds: 0, catchRadius: 0.12 });
  attempt.update({ x: NaN, y: 0, z: 0 }, ballAt(0), 0);
  attempt.update({ x: 1, y: 0, z: 0 }, ballAt(0.5), 0.5);
  attempt.update({ x: 1, y: 0, z: 0 }, ballAt(1.0), 1.0); // ball at x = 1: contact
  const r = attempt.result();
  assert.equal(r.judged, true);
  assert.equal(r.caught, true);
  assert.equal(r.samples, 2);
});

test("a missing ball position is skipped too", () => {
  const attempt = new CatchAttempt({ thrownAtSeconds: 0 });
  attempt.update({ x: 1, y: 0, z: 0 }, undefined, 0);
  assert.equal(attempt.result().judged, false);
});

test("two-dimensional points work, z is optional", () => {
  const attempt = new CatchAttempt({ thrownAtSeconds: 0, catchRadius: 0.12 });
  attempt.update({ x: 1, y: 0 }, { x: 1, y: 0 }, 0);
  assert.equal(attempt.result().caught, true);
});

// ------------------------------------------------------------- which hand --
test("the glove hand is the arm the athlete does NOT throw with", () => {
  assert.equal(catchHandFor("right"), "left");
  assert.equal(catchHandFor("left"), "right");
});

test("a bare-hand drill puts the ball back in the operated arm's hand", () => {
  assert.equal(catchHandFor("right", { bareHand: true }), "right");
});

test("wristPoint picks the right landmark and refuses a broken one", () => {
  const landmarks = [];
  landmarks[15] = { x: 0.1, y: 0.2 };
  landmarks[16] = { x: 0.8, y: 0.3 };
  assert.deepEqual(wristPoint(landmarks, "left"), { x: 0.1, y: 0.2 });
  assert.deepEqual(wristPoint(landmarks, "right"), { x: 0.8, y: 0.3 });
  assert.equal(wristPoint(landmarks, "nope"), null);
  assert.equal(wristPoint(null, "left"), null);
  landmarks[15] = { x: NaN, y: 0.2 };
  assert.equal(wristPoint(landmarks, "left"), null);
});
