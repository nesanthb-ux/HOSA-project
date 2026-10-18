// Run from rehab_vr/web:  node --test "tests/*.test.js"
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ARM_LANDMARKS,
  PROFILES,
  ReleaseDetector,
  TORSO_LANDMARKS,
  classifyOverheadThrowPhase,
  elbowAngleDeg,
  hipShoulderSeparationDeg,
  isArmRaised,
  classifyGenericOverheadRelease,
  pointsForTorso,
  pointsFromLandmarks,
} from "../src/activity_profiles.js";

// Image coordinates: y grows downward.
const P = (x, y) => ({ x, y });
// A real wind-up keeps the elbow BENT (see bug #2 in activity_profiles.js) —
// this fixture is deliberately bent, not straight, unlike the old fixture.
const COCKING = { shoulder: P(0.5, 0.5), elbow: P(0.65, 0.4), wrist: P(0.5, 0.2) }; // bent arm, wrist raised
const FOLLOW = { shoulder: P(0.5, 0.4), elbow: P(0.5, 0.55), wrist: P(0.5, 0.7) }; // wrist well below shoulder
const REST = { shoulder: P(0.5, 0.4), elbow: P(0.5, 0.5), wrist: P(0.5, 0.45) };

// Disables smoothing so a test can feed one exact frame per call and get an
// immediate, deterministic response — the smoothing behavior itself is
// tested separately, further down.
const INSTANT = { smoothing: 1 };

test("elbow angle: straight arm is 180, right angle is 90", () => {
  assert.equal(Math.round(elbowAngleDeg(P(0, 0), P(1, 0), P(2, 0))), 180);
  assert.equal(Math.round(elbowAngleDeg(P(0, 0), P(1, 0), P(1, 1))), 90);
});

test("isArmRaised only looks at wrist-vs-shoulder height, not elbow angle", () => {
  assert.equal(isArmRaised(COCKING), true);
  assert.equal(isArmRaised(REST), false);
  assert.equal(isArmRaised(FOLLOW), false);
  // A bent elbow raised well above the shoulder still counts as raised —
  // this is exactly the real wind-up shape the old angle-gated version missed.
  const bentAndRaised = { shoulder: P(0.5, 0.5), elbow: P(0.7, 0.4), wrist: P(0.5, 0.25) };
  assert.equal(isArmRaised(bentAndRaised), true);
});

test("the raw, single-frame classifier only ever says raised or rest — never follow-through", () => {
  // This is the direct fix for bug #1: a lowered-arm shape (like FOLLOW) is
  // NOT enough, by itself, to say "follow-through". Only ReleaseDetector,
  // which remembers whether the arm was raised a moment ago, may say that.
  assert.equal(classifyOverheadThrowPhase(COCKING), "cocking/acceleration");
  assert.equal(classifyOverheadThrowPhase(FOLLOW), "rest");
  assert.equal(classifyOverheadThrowPhase(REST), "rest");
});

test("pointsFromLandmarks picks the right joints for each arm", () => {
  const landmarks = Array.from({ length: 33 }, (_, i) => ({ x: i, y: i }));
  const right = pointsFromLandmarks(landmarks, "right");
  assert.deepEqual([right.shoulder.x, right.elbow.x, right.wrist.x], [12, 14, 16]);
  const left = pointsFromLandmarks(landmarks, "left");
  assert.deepEqual([left.shoulder.x, left.elbow.x, left.wrist.x], [11, 13, 15]);
  assert.equal(ARM_LANDMARKS.left.shoulder, 11);
});

test("pointsFromLandmarks returns null for bad input", () => {
  assert.equal(pointsFromLandmarks(null, "right"), null);
  assert.equal(pointsFromLandmarks([], "right"), null);
  assert.equal(pointsFromLandmarks(Array(33).fill({ x: 0, y: 0 }), "both"), null);
});

// --------------------------------------------------- ReleaseDetector -------
test("one throw produces exactly one release, and the phase label is right at every step", () => {
  // followThroughHoldSeconds set short relative to the 0.1s frame spacing.
  // The last COCKING frame (re-arming the hold) is at t=0.2, so the hold
  // must cover the two FOLLOW frames at t=0.3/0.4 but expire before t=0.5.
  const d = new ReleaseDetector(PROFILES.overhead_throw, { ...INSTANT, followThroughHoldSeconds: 0.25 });
  const seq = [REST, COCKING, COCKING, FOLLOW, FOLLOW, REST];
  const out = seq.map((pts, i) => d.update(pts, i * 0.1));
  assert.deepEqual(
    out.map((o) => o.phase),
    ["rest", "cocking/acceleration", "cocking/acceleration", "follow-through", "follow-through", "rest"]
  );
  assert.deepEqual(
    out.map((o) => o.justReleased),
    [false, false, false, true, false, false]
  );
});

test("bug #1 regression: a lowered arm that was NEVER raised reads as rest, not follow-through", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  assert.equal(d.update(REST, 0).phase, "rest");
  const out = d.update(FOLLOW, 0.1);
  assert.equal(out.phase, "rest"); // not "follow-through" — this is the exact bug reported live
  assert.equal(out.justReleased, false);
});

test("bug #2 regression: a bent, cocked arm reads as cocking, not follow-through", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  assert.equal(d.update(COCKING, 0).phase, "cocking/acceleration");
});

test("follow-through decays back to rest after the hold window, without a new raise", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, { ...INSTANT, followThroughHoldSeconds: 0.5 });
  d.update(COCKING, 0);
  assert.equal(d.update(FOLLOW, 0.1).phase, "follow-through");
  assert.equal(d.update(FOLLOW, 0.4).phase, "follow-through"); // still inside the hold window
  assert.equal(d.update(FOLLOW, 0.7).phase, "rest"); // hold window elapsed, arm never re-raised
});

test("pose flicker inside the cooldown does not double-count", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, { ...INSTANT, cooldownSeconds: 0.8 });
  const frames = [
    [COCKING, 0.0],
    [FOLLOW, 0.1], // release
    [COCKING, 0.2], // flicker back
    [FOLLOW, 0.3], // would be a second release 0.2s after the first
  ];
  const fired = frames.map(([pts, t]) => d.update(pts, t).justReleased);
  assert.deepEqual(fired, [false, true, false, false]);
});

test("a second real throw after the cooldown is detected", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, { ...INSTANT, cooldownSeconds: 0.8 });
  d.update(COCKING, 0);
  assert.equal(d.update(FOLLOW, 0.1).justReleased, true);
  d.update(REST, 1);
  d.update(COCKING, 2);
  assert.equal(d.update(FOLLOW, 2.1).justReleased, true);
});

test("losing tracking between cocking and follow-through cannot create a phantom release", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  d.update(COCKING, 0);
  d.reset(); // pose lost for a while — also clears the "recently raised" memory
  const out = d.update(FOLLOW, 5);
  assert.equal(out.justReleased, false);
  assert.equal(out.phase, "rest"); // no memory of being raised survives a reset
});

test("planned activities are registered but do not pretend to detect anything", () => {
  for (const id of ["tennis_serve", "basketball_shot"]) {
    const profile = PROFILES[id];
    assert.equal(profile.status, "planned");
    assert.equal(profile.classify, undefined);
    const d = new ReleaseDetector(profile);
    assert.equal(d.supported(), false);
    const out = d.update(FOLLOW, 0);
    assert.equal(out.justReleased, false);
    assert.equal(out.phase, "not implemented");
  }
  assert.equal(new ReleaseDetector(PROFILES.overhead_throw).supported(), true);
});

test("cricket bowling is implemented, but explicitly as the same generic release model as baseball", () => {
  const profile = PROFILES.cricket_bowl;
  assert.equal(profile.status, "implemented");
  // Same underlying function, not a separate bowling-specific classifier —
  // this is a documented reuse, not a hidden duplicate implementation.
  assert.equal(profile.classify, classifyGenericOverheadRelease);
  assert.equal(profile.classify, classifyOverheadThrowPhase);
});

test("a cricket bowling delivery fires a release and a relative speed, same as a baseball throw", () => {
  const d = new ReleaseDetector(PROFILES.cricket_bowl, INSTANT);
  d.update(COCKING, 0);
  const out = d.update(FOLLOW, 0.1);
  assert.equal(out.justReleased, true);
  assert.ok(out.releaseVelocity.speed > 0);
});

// -------------------------------------------------------- smoothing --------
// Bug #3: the elbow-angle readout jumped around with a genuinely still arm,
// because raw webcam pose landmarks jitter a little frame to frame even at
// rest. These use the REAL default smoothing (no INSTANT override).
test("smoothing meaningfully reduces angle jitter compared to reading the raw frame directly", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw);
  const truePose = { shoulder: P(0.5, 0.5), elbow: P(0.5, 0.35), wrist: P(0.5, 0.2) }; // ~180 degrees
  const trueAngle = elbowAngleDeg(truePose.shoulder, truePose.elbow, truePose.wrist);

  // A small deterministic wobble around the true position, applied to every
  // joint every frame, standing in for real camera/lighting jitter — this is
  // literally "my arm is steady but the angle keeps changing."
  let lastSmoothedAngle, lastRawAngle;
  for (let i = 0; i < 40; i += 1) {
    const wobble = (i % 2 === 0 ? 1 : -1) * 0.02;
    const jittered = {
      shoulder: P(truePose.shoulder.x + wobble, truePose.shoulder.y),
      elbow: P(truePose.elbow.x - wobble, truePose.elbow.y + wobble),
      wrist: P(truePose.wrist.x + wobble, truePose.wrist.y),
    };
    lastSmoothedAngle = d.update(jittered, 1 + i * 0.03).elbowAngleDeg;
    lastRawAngle = elbowAngleDeg(jittered.shoulder, jittered.elbow, jittered.wrist);
  }
  const smoothedError = Math.abs(lastSmoothedAngle - trueAngle);
  const rawError = Math.abs(lastRawAngle - trueAngle);
  assert.ok(
    smoothedError < rawError * 0.6,
    `expected smoothing to cut the jitter meaningfully: raw off by ${rawError}, smoothed off by ${smoothedError}`
  );
});

test("smoothing does not flip raised/rest on a single noisy outlier frame", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw);
  // Settle on a genuinely resting arm first.
  for (let i = 0; i < 10; i += 1) d.update(REST, i * 0.1);
  // One single wild outlier frame that looks raised, on its own.
  const outlierPhase = d.update({ shoulder: P(0.5, 0.4), elbow: P(0.5, 0.3), wrist: P(0.5, 0.1) }, 1.0).phase;
  assert.equal(outlierPhase, "rest", "a single noisy frame should not read as a real wind-up on a resting arm");
});

// ------------------------------------------- hip-shoulder separation -------
// Hips and shoulders squared to the camera (both lines horizontal) — no
// rotation yet, separation should read ~0.
const TORSO_SQUARED = {
  leftShoulder: P(0.4, 0.4), rightShoulder: P(0.6, 0.4),
  leftHip: P(0.42, 0.7), rightHip: P(0.58, 0.7),
};
// Shoulders rotated ~30 degrees relative to the hips (a real wind-up: the
// hips have already turned toward the target, the shoulders haven't caught
// up yet) — well past HIP_SEPARATION_LOADING_DEG.
const TORSO_LOADED = {
  leftShoulder: P(0.4134, 0.35), rightShoulder: P(0.5866, 0.45),
  leftHip: P(0.42, 0.7), rightHip: P(0.58, 0.7),
};
// Only ~8 degrees of rotation — a normal standing sway, not a real load.
const TORSO_SMALL_ROTATION = {
  leftShoulder: P(0.40097, 0.38608), rightShoulder: P(0.59903, 0.41392),
  leftHip: P(0.42, 0.7), rightHip: P(0.58, 0.7),
};

test("hipShoulderSeparationDeg reads ~0 when squared, and the real rotation when loaded", () => {
  assert.ok(Math.abs(hipShoulderSeparationDeg(TORSO_SQUARED)) < 1);
  assert.ok(Math.abs(hipShoulderSeparationDeg(TORSO_LOADED) - 30) < 1);
});

test("pointsForTorso picks both shoulders and both hips by MediaPipe index", () => {
  const landmarks = Array.from({ length: 33 }, (_, i) => ({ x: i, y: i }));
  const torso = pointsForTorso(landmarks);
  assert.equal(torso.leftShoulder.x, TORSO_LANDMARKS.leftShoulder);
  assert.equal(torso.rightShoulder.x, TORSO_LANDMARKS.rightShoulder);
  assert.equal(torso.leftHip.x, TORSO_LANDMARKS.leftHip);
  assert.equal(torso.rightHip.x, TORSO_LANDMARKS.rightHip);
});

test("pointsForTorso returns null if any of the four landmarks is missing", () => {
  assert.equal(pointsForTorso(null), null);
  assert.equal(pointsForTorso(Array(20).fill({ x: 0, y: 0 })), null); // too short to have a hip
});

test("hip rotation alone — no raised arm — is enough to count as loading", () => {
  // REST arm shape (defined above), so only the hip signal can be driving this.
  assert.equal(classifyOverheadThrowPhase(REST, TORSO_LOADED), "cocking/acceleration");
});

test("a small rotation below the threshold, with the arm down, stays rest", () => {
  assert.equal(classifyOverheadThrowPhase(REST, TORSO_SMALL_ROTATION), "rest");
  assert.equal(classifyOverheadThrowPhase(REST, TORSO_SQUARED), "rest");
});

test("classify without any hip data at all still works exactly as before (backward compatible)", () => {
  assert.equal(classifyOverheadThrowPhase(REST), "rest");
  assert.equal(classifyOverheadThrowPhase(COCKING), "cocking/acceleration");
});

test("ReleaseDetector fires a release from hip-only loading, exactly like arm-only loading", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, { ...INSTANT, followThroughHoldSeconds: 0.25 });
  assert.equal(d.update(REST, 0, TORSO_SQUARED).phase, "rest");
  assert.equal(d.update(REST, 0.1, TORSO_LOADED).phase, "cocking/acceleration"); // hips alone, arm still down
  const out = d.update(FOLLOW, 0.2, TORSO_SQUARED);
  assert.equal(out.phase, "follow-through");
  assert.equal(out.justReleased, true);
});

test("ReleaseDetector reports the separation angle, and null when hips aren't tracked", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  assert.equal(d.update(REST, 0).hipShoulderSeparationDeg, null);
  const out = d.update(REST, 0.1, TORSO_LOADED);
  assert.ok(Math.abs(out.hipShoulderSeparationDeg - 30) < 1);
});

// ------------------------------------------------------ release velocity --
test("releaseVelocity is null on every frame except the exact release frame", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  const seq = [
    [REST, 0], [COCKING, 0.1], [COCKING, 0.2], [COCKING, 0.3], [FOLLOW, 0.4], [FOLLOW, 0.5],
  ];
  const velocities = seq.map(([pts, t]) => d.update(pts, t).releaseVelocity);
  assert.deepEqual(velocities.map((v) => v !== null), [false, false, false, false, true, false]);
});

test("a faster tracked release reports a larger release speed than a slower one", () => {
  // Same start and end wrist position, reached over less time -> faster.
  const fast = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  fast.update(COCKING, 0);
  fast.update({ ...COCKING, wrist: P(0.5, 0.3) }, 0.03);
  const fastOut = fast.update({ ...FOLLOW, wrist: P(0.5, 0.6) }, 0.06);

  const slow = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  slow.update(COCKING, 0);
  slow.update({ ...COCKING, wrist: P(0.5, 0.3) }, 0.3);
  const slowOut = slow.update({ ...FOLLOW, wrist: P(0.5, 0.6) }, 0.6);

  assert.ok(fastOut.releaseVelocity.speed > slowOut.releaseVelocity.speed);
});

test("release velocity is not a physical unit — it is relative image-space distance per second", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  d.update(COCKING, 0);
  const out = d.update({ ...FOLLOW, wrist: P(0.5, 0.6) }, 0.1);
  // The wrist moved 0.4 of the frame height in 0.1s of tracked history —
  // speed should be a plain distance/time ratio, nothing normalized to mph.
  assert.ok(out.releaseVelocity.speed > 0);
  assert.ok(Number.isFinite(out.releaseVelocity.angleDeg));
});

test("an upward-moving release reports a positive launch angle", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  // Synthetic points chosen only to produce a clean upward wrist trend
  // across a release transition, not a realistic pose — the shoulder moves
  // between frames purely so "raised" can flip at the right moment while
  // the wrist itself keeps trending up (smaller y) the whole time.
  d.update({ shoulder: P(0.5, 0.9), elbow: P(0.5, 0.7), wrist: P(0.5, 0.5) }, 0); // raised
  d.update({ shoulder: P(0.5, 0.9), elbow: P(0.55, 0.6), wrist: P(0.55, 0.35) }, 0.05); // raised
  const out = d.update({ shoulder: P(0.5, 0.2), elbow: P(0.55, 0.18), wrist: P(0.6, 0.15) }, 0.1); // not raised -> release
  assert.equal(out.justReleased, true);
  assert.ok(out.releaseVelocity.angleDeg > 0, `expected a positive (upward) angle, got ${out.releaseVelocity.angleDeg}`);
});

test("losing tracking clears the wrist history so no velocity spans the gap", () => {
  const d = new ReleaseDetector(PROFILES.overhead_throw, INSTANT);
  d.update(COCKING, 0);
  d.reset();
  d.update(COCKING, 10);
  const out = d.update(FOLLOW, 10.1);
  // Only two samples exist since the reset (10 and 10.1), both wrist
  // positions from COCKING/FOLLOW — a real velocity, just not one that
  // could have spanned back across the multi-second gap.
  assert.ok(out.releaseVelocity === null || out.releaseVelocity.sampleSeconds <= 0.2);
});
