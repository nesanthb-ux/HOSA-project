// Run from rehab_vr/web:  node --test tests/
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  AdaptiveExposureEngine,
  ESCALATE_BELOW,
  ESCALATE_HOLD_SECONDS,
  EXPOSURE_LEVELS,
  MAX_TICK_GAP_SECONDS,
  RETREAT_ABOVE,
} from "../src/exposure_levels.js";
import { athleteIdleStatus, athleteReason, technicalReason } from "../src/explain.js";

const CALM = 0.1;
const SPIKE = 0.9;

function makeEngine() {
  const events = [];
  const engine = new AdaptiveExposureEngine(EXPOSURE_LEVELS, (level, event) => events.push({ level, event }));
  return { engine, events };
}

// Feeds `seconds` one-second ticks of the same score.
function feed(engine, score, seconds, opts = {}) {
  for (let i = 0; i < seconds; i++) engine.update(score, { dtSeconds: 1, ...opts });
}

test("starts at level 0", () => {
  const { engine } = makeEngine();
  assert.equal(engine.currentLevel().id, 0);
});

test("does not advance until the full calm hold has elapsed", () => {
  const { engine, events } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS - 1);
  assert.equal(engine.currentLevel().id, 0);
  assert.equal(events.length, 0);
  feed(engine, CALM, 1);
  assert.equal(engine.currentLevel().id, 1);
  assert.equal(events.length, 1);
});

test("advance event carries the facts the explanation layer needs", () => {
  const { engine, events } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS);
  const { event } = events[0];
  assert.equal(event.action, "advance");
  assert.equal(event.threshold, ESCALATE_BELOW);
  assert.equal(event.holdSeconds, ESCALATE_HOLD_SECONDS);
  assert.equal(event.score, CALM);
});

test("retreats immediately on a single high reading", () => {
  const { engine, events } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS * 2); // up to level 2
  assert.equal(engine.currentLevel().id, 2);
  engine.update(SPIKE, { dtSeconds: 1 });
  assert.equal(engine.currentLevel().id, 1);
  const last = events.at(-1).event;
  assert.equal(last.action, "retreat");
  assert.equal(last.threshold, RETREAT_ABOVE);
});

test("escalation is slower than retreat (the asymmetry is the safety property)", () => {
  const { engine } = makeEngine();
  let ticksToAdvance = 0;
  while (engine.currentLevel().id === 0) {
    engine.update(CALM, { dtSeconds: 1 });
    ticksToAdvance++;
  }
  engine.update(SPIKE, { dtSeconds: 1 });
  assert.equal(engine.currentLevel().id, 0); // retreated in exactly one tick
  assert.ok(ticksToAdvance > 1);
  assert.equal(ticksToAdvance, ESCALATE_HOLD_SECONDS);
});

test("never retreats below level 0", () => {
  const { engine, events } = makeEngine();
  engine.update(SPIKE, { dtSeconds: 1 });
  assert.equal(engine.currentLevel().id, 0);
  assert.equal(events.length, 0);
});

test("a mid-range reading resets the calm counter", () => {
  const { engine } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS - 1);
  engine.update(0.5, { dtSeconds: 1 }); // between the thresholds: neither calm nor a spike
  assert.equal(engine.getCalmSeconds(), 0);
  feed(engine, CALM, ESCALATE_HOLD_SECONDS - 1);
  assert.equal(engine.currentLevel().id, 0);
});

test("thresholds are strict on the calm side and inclusive on the retreat side", () => {
  const a = makeEngine();
  feed(a.engine, ESCALATE_BELOW, ESCALATE_HOLD_SECONDS * 3); // exactly at threshold is not calm
  assert.equal(a.engine.currentLevel().id, 0);

  const b = makeEngine();
  feed(b.engine, CALM, ESCALATE_HOLD_SECONDS);
  b.engine.update(RETREAT_ABOVE, { dtSeconds: 1 }); // exactly at threshold retreats
  assert.equal(b.engine.currentLevel().id, 0);
});

test("climbs one level at a time and stops at the top", () => {
  const { engine, events } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS * (EXPOSURE_LEVELS.length + 3));
  assert.equal(engine.currentLevel().id, EXPOSURE_LEVELS.length - 1);
  assert.equal(events.length, EXPOSURE_LEVELS.length - 1);
  events.forEach((e, i) => assert.equal(e.level.id, i + 1)); // no skipped levels
});

test("no data earns no calm credit and never advances", () => {
  const { engine, events } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS - 1);
  engine.update(null, { dtSeconds: 1 });
  assert.equal(engine.getCalmSeconds(), 0);
  feed(engine, null, 50);
  assert.equal(engine.currentLevel().id, 0);
  assert.equal(events.length, 0);
  engine.update(NaN, { dtSeconds: 1 });
  engine.update(undefined, { dtSeconds: 1 });
  assert.equal(engine.currentLevel().id, 0);
});

test("a long gap between readings is not credited as calm time", () => {
  const { engine } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS - 1);
  engine.update(CALM, { dtSeconds: MAX_TICK_GAP_SECONDS + 1 }); // connection dropped for a while
  assert.equal(engine.currentLevel().id, 0);
  assert.equal(engine.getCalmSeconds(), 0);
});

test("normal network jitter is still credited", () => {
  const { engine } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS - 1);
  engine.update(CALM, { dtSeconds: MAX_TICK_GAP_SECONDS }); // slow but within tolerance
  assert.equal(engine.currentLevel().id, 1);
});

test("a partial reading (canEscalate=false) can never step the athlete up", () => {
  const { engine, events } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS * 3, { canEscalate: false });
  assert.equal(engine.currentLevel().id, 0);
  assert.equal(events.length, 0);
});

test("a partial reading can still retreat", () => {
  const { engine } = makeEngine();
  feed(engine, CALM, ESCALATE_HOLD_SECONDS); // level 1
  engine.update(SPIKE, { dtSeconds: 1, canEscalate: false });
  assert.equal(engine.currentLevel().id, 0);
});

// ---------------------------------------------------------- explanations ---
test("technical and athlete text are both built from the same event", () => {
  const advance = { action: "advance", score: 0.12, threshold: 0.35, holdSeconds: 8 };
  const retreat = { action: "retreat", score: 0.81, threshold: 0.75 };
  assert.match(technicalReason(advance), /0\.35/);
  assert.match(technicalReason(advance), /8s/);
  assert.match(technicalReason(retreat), /0\.81/);
  assert.match(technicalReason(retreat), /0\.75/);
  assert.match(athleteReason(advance), /stepping it up/);
  assert.match(athleteReason(retreat), /eased back/);
});

test("idle status handles every state without lying", () => {
  assert.match(athleteIdleStatus(0, 8, true), /Full game intensity/);
  assert.match(athleteIdleStatus(0, 8, false), /Reading your response/);
  assert.match(athleteIdleStatus(3, 8, false), /5s more/);
  assert.match(athleteIdleStatus(8, 8, false), /Holding here/);
});
