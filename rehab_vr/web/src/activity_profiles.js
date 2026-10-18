// Sport-neutral release detection. Pure functions and classes with no
// browser or MediaPipe dependency, so they can be unit tested in Node with
// synthetic joint positions (rehab_vr/web/tests/).
//
// A "profile" describes one arm action: how to label its raw state from
// joint positions, and which state change counts as the release (throw,
// bowl, serve, shot). Only the overhead throw is implemented. Cricket
// bowling, tennis serve, and basketball shot are registered as "planned" so
// the architecture and UI show where they go, but they have NO detection
// logic: inventing joint-angle rules for motions nobody has recorded or
// tested would be guessing, and this project does not present guesses as
// working. Each one needs real footage and a real rule before status
// becomes "implemented".
//
// Two real bugs came out of a live test session (2026-09-27, see
// PROJECT_LOG.md) and are fixed here:
//   1. A resting arm was reported as "follow-through". A single video frame
//      of "arm is down" looks the same whether the arm just finished a
//      throw or has been relaxed the whole time — there is no way to tell
//      those apart without remembering what happened a moment ago. So the
//      raw, per-frame classifier below only ever reports "raised" or "rest";
//      ReleaseDetector is the thing that turns a lowered arm into
//      "follow-through", and only for a short window after it was actually
//      raised (see FOLLOW_THROUGH_HOLD_SECONDS).
//   2. A cocked arm (winding up, elbow bent) was reported as follow-through.
//      The earlier raw test required a nearly straight elbow to count as
//      "cocking", but a real wind-up keeps the elbow bent — so a genuine
//      cocking motion never matched, fell through to the "arm is down"
//      check, and got mislabeled. The raised/not-raised test below no
//      longer looks at elbow angle at all.
//   3. The elbow-angle readout jumped around even with a still arm. Webcam
//      pose landmarks jitter a little frame to frame from camera/lighting
//      noise even when nothing moved. ReleaseDetector now smooths the
//      incoming joint positions (an exponential moving average) before any
//      angle or phase is computed from them.
//
// A follow-up session (2026-09-27, later the same day) added hip tracking
// and a release-speed estimate. Both are documented where they're defined
// below, with the same honesty rule as everything else here: named after a
// real, established concept when one applies, and never presented as more
// accurate than a single 2D webcam can actually support.

// MediaPipe Pose landmark indices for each arm.
export const ARM_LANDMARKS = {
  right: { shoulder: 12, elbow: 14, wrist: 16 },
  left: { shoulder: 11, elbow: 13, wrist: 15 },
};

// MediaPipe Pose landmark indices for the hip-shoulder separation estimate
// below. Unlike ARM_LANDMARKS this isn't per throwing-arm — it always uses
// both shoulders and both hips, regardless of which arm is throwing.
export const TORSO_LANDMARKS = { leftShoulder: 11, rightShoulder: 12, leftHip: 23, rightHip: 24 };

// Picks the throwing arm's three joints out of a full MediaPipe landmark
// list. Returns null if any is missing.
export function pointsFromLandmarks(landmarks, arm) {
  const idx = ARM_LANDMARKS[arm];
  if (!idx || !landmarks) return null;
  const shoulder = landmarks[idx.shoulder];
  const elbow = landmarks[idx.elbow];
  const wrist = landmarks[idx.wrist];
  if (!shoulder || !elbow || !wrist) return null;
  return { shoulder, elbow, wrist };
}

// Picks both shoulders and both hips out of a full MediaPipe landmark list,
// for the hip-shoulder separation estimate. Returns null if any is missing
// (e.g. the person's hips are out of frame) — a partial reading here just
// means "no hip signal this frame", never a guessed one.
export function pointsForTorso(landmarks) {
  if (!landmarks) return null;
  const leftShoulder = landmarks[TORSO_LANDMARKS.leftShoulder];
  const rightShoulder = landmarks[TORSO_LANDMARKS.rightShoulder];
  const leftHip = landmarks[TORSO_LANDMARKS.leftHip];
  const rightHip = landmarks[TORSO_LANDMARKS.rightHip];
  if (!leftShoulder || !rightShoulder || !leftHip || !rightHip) return null;
  return { leftShoulder, rightShoulder, leftHip, rightHip };
}

// Interior angle at the elbow in degrees (180 = fully straight arm).
export function elbowAngleDeg(shoulder, elbow, wrist) {
  const a = Math.atan2(shoulder.y - elbow.y, shoulder.x - elbow.x);
  const b = Math.atan2(wrist.y - elbow.y, wrist.x - elbow.x);
  let deg = Math.abs(((a - b) * 180) / Math.PI);
  if (deg > 180) deg = 360 - deg;
  return deg;
}

// Signed angle, in degrees, of the line from `a` to `b` relative to the
// horizontal — a plain 2D line direction, not an interior angle like
// elbowAngleDeg above.
function lineAngleDeg(a, b) {
  return (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
}

// Signed difference between two line angles, wrapped to (-180, 180] so a
// wraparound near +/-180 degrees doesn't read as a huge jump.
function angleDiffDeg(a, b) {
  let diff = a - b;
  diff = ((diff + 180) % 360 + 360) % 360 - 180;
  return diff;
}

// Hip-shoulder separation: the differential rotation between the pelvis and
// the torso during the load/stride phase of a throw, a real and named
// concept in throwing biomechanics (also called the "X-factor," borrowed
// from the same idea in golf). The pelvis rotates ahead of the shoulders to
// store rotational energy before the arm accelerates forward — that gap
// between how far the hips have turned and how far the shoulders have
// turned is the separation.
//
// This is a 2D proxy for it, not the real thing: a single camera sees the
// hip line and shoulder line rotate in the IMAGE plane as the body turns,
// and the angle between those two lines approximates (but does not equal)
// the true transverse-plane separation a motion-capture rig would measure.
// It reads best from an angled or face-on camera view and reads poorly
// from directly behind or directly side-on, where the lines foreshorten
// instead of visibly rotating. Treat the number as a relative "how much has
// the body turned so far," not a clinical or biomechanical measurement.
export function hipShoulderSeparationDeg({ leftShoulder, rightShoulder, leftHip, rightHip }) {
  const shoulderAngle = lineAngleDeg(leftShoulder, rightShoulder);
  const hipAngle = lineAngleDeg(leftHip, rightHip);
  return angleDiffDeg(shoulderAngle, hipAngle);
}

// How much separation counts as "the hips are loading," in degrees. A
// documented rough heuristic and a starting point to retune from a real
// recording (same status as RAISED_ABOVE_SHOULDER below) — not a validated
// biomechanical cutoff.
const HIP_SEPARATION_LOADING_DEG = 18;

// How far the wrist must rise above the shoulder, in normalized image units,
// to count as raised rather than jitter around a resting arm. Deliberately
// NOT an elbow-angle test — see bug #2 above. A documented rough heuristic,
// not a validated biomechanics model; tune this against a real recording
// (PIVOT_PLAN.md, Week 5/6 of the master plan), not a guess.
const RAISED_ABOVE_SHOULDER = 0.08;

// Image coordinates: y grows downward, so "above the shoulder" means a
// smaller y. Stateless, single-frame: see bug #1 above for why this never
// reports "follow-through" — that label needs history, which lives in
// ReleaseDetector below.
export function isArmRaised({ shoulder, wrist }) {
  return wrist.y < shoulder.y - RAISED_ABOVE_SHOULDER;
}

// The combined loading signal: the arm going back OR the hips already
// turning counts as loading — hip rotation in a real wind-up typically
// starts before the arm finishes rising, so requiring both at once would
// make the detector notice the load later than it actually starts, not
// more reliably. hipPoints is optional; when it isn't supplied (or hips
// aren't in frame this moment) this falls back to the arm-only signal.
export function isLoading(points, hipPoints) {
  if (isArmRaised(points)) return true;
  if (hipPoints) return Math.abs(hipShoulderSeparationDeg(hipPoints)) >= HIP_SEPARATION_LOADING_DEG;
  return false;
}

export function classifyOverheadThrowPhase(points, hipPoints) {
  return isLoading(points, hipPoints) ? "cocking/acceleration" : "rest";
}

// A cricket bowling delivery also loads (arm and hips rise/rotate back) and
// releases overarm, so the same arm-raised-or-hip-rotated signal applies —
// this is NOT a validated bowling classifier. It does not check that the
// arm stays straight through release (the actual legal definition of a fair
// delivery in cricket law), and it does not model the run-up at all; it is
// the same generic release detector as the baseball throw, reused because
// the underlying loaded-to-released geometry is genuinely shared, not
// because bowling mechanics have been studied here. Treat any speed/phase
// reading from this the same way as the baseball one: relative and
// approximate, not sport-specific analysis.
export const classifyGenericOverheadRelease = classifyOverheadThrowPhase;

export const PROFILES = {
  overhead_throw: {
    id: "overhead_throw",
    label: "Baseball / softball throw",
    status: "implemented",
    classify: classifyOverheadThrowPhase,
    releaseFrom: "cocking/acceleration",
    releaseTo: "follow-through",
  },
  cricket_bowl: {
    id: "cricket_bowl",
    label: "Cricket bowling (generic release model)",
    status: "implemented",
    classify: classifyGenericOverheadRelease,
    releaseFrom: "cocking/acceleration",
    releaseTo: "follow-through",
  },
  tennis_serve: { id: "tennis_serve", label: "Tennis serve", status: "planned" },
  basketball_shot: { id: "basketball_shot", label: "Basketball shot", status: "planned" },
};

// How long, after the arm was last raised, a lowered arm still reads as
// "follow-through" instead of "rest". Real follow-through is a brief
// deceleration right after release, not a resting stance, and it should not
// stay reported forever once the arm has actually settled. A UX/debounce
// parameter (same idea as cooldownSeconds below), not a physiological one.
const FOLLOW_THROUGH_HOLD_SECONDS = 0.6;

// EMA weight given to each new frame: 1 = no smoothing (use the raw point
// every frame), smaller = heavier smoothing and more lag. 0.35 was picked to
// visibly settle jitter within a few frames without feeling delayed; retune
// against a real recording once one exists.
const DEFAULT_SMOOTHING = 0.35;

// How many recent smoothed wrist positions are kept to estimate a release
// velocity — see _RELEASE_ below. 4 samples is enough to average out one bad
// frame without lagging the estimate behind the actual release by much.
const WRIST_HISTORY_LENGTH = 4;

function emaBlend(previous, next, a) {
  return { x: previous.x + a * (next.x - previous.x), y: previous.y + a * (next.y - previous.y) };
}

// Turns a stream of joint positions into phase labels plus one release event
// per action. A release is the single frame where the phase moves from
// profile.releaseFrom to profile.releaseTo.
export class ReleaseDetector {
  constructor(
    profile,
    { cooldownSeconds = 0.8, followThroughHoldSeconds = FOLLOW_THROUGH_HOLD_SECONDS, smoothing = DEFAULT_SMOOTHING } = {}
  ) {
    this.profile = profile;
    this.cooldownSeconds = cooldownSeconds;
    this.followThroughHoldSeconds = followThroughHoldSeconds;
    this.smoothing = smoothing;
    this.previousPhase = "rest";
    this.lastReleaseAt = -Infinity;
    this.raisedUntil = -Infinity; // still counts as "just raised" until this clock time
    this.smoothedArm = null; // lazily seeded from the first real frame — see _smooth()
    this.smoothedHips = null;
    this.wristHistory = []; // [{ x, y, t }], oldest first, capped at WRIST_HISTORY_LENGTH
  }

  supported() {
    return this.profile.status === "implemented" && typeof this.profile.classify === "function";
  }

  // Call when tracking is lost, so a stale phase (or a stale smoothed
  // position) from before the gap can't combine with the first frame after
  // it into a phantom release, a lagged jump, or a fabricated velocity
  // spanning the gap.
  reset() {
    this.previousPhase = "rest";
    this.raisedUntil = -Infinity;
    this.smoothedArm = null;
    this.smoothedHips = null;
    this.wristHistory = [];
  }

  // Exponential moving average, generalized over however many named points
  // are in `points` (arm: shoulder/elbow/wrist; hips: both shoulders and
  // both hips) — same smoothing behavior for either set. Seeds directly
  // from the first frame (no artificial ramp-up lag on frame one).
  _smooth(points, cacheKey) {
    if (!points) return null;
    const cached = this[cacheKey];
    if (this.smoothing >= 1 || !cached) {
      const seeded = {};
      for (const joint of Object.keys(points)) seeded[joint] = { ...points[joint] };
      this[cacheKey] = seeded;
      return seeded;
    }
    for (const joint of Object.keys(points)) {
      cached[joint] = emaBlend(cached[joint], points[joint], this.smoothing);
    }
    return cached;
  }

  // Relative release velocity from the smoothed wrist's recent movement —
  // NOT a physical speed. The camera gives positions in normalized image
  // coordinates (0 to 1 across the frame), and turning that into a real
  // speed (mph, m/s) needs a known real-world distance scale — how many
  // real inches one unit of image width covers at the athlete's distance
  // from the camera — which this system does not have without a
  // calibration step nobody has built yet. Reporting a fabricated mph
  // number would look precise and be meaningless, which this project's own
  // rules (CLAUDE.md: never fabricate values) rule out. So this reports a
  // speed in image-widths-per-second: internally consistent (a faster real
  // throw always gives a bigger number) and fine for driving the pitch
  // animation's visual speed, but not a claim about real ball velocity.
  _releaseVelocity(nowSeconds) {
    const history = this.wristHistory;
    if (history.length < 2) return null;
    const oldest = history[0];
    const newest = history[history.length - 1];
    const dt = newest.t - oldest.t;
    if (!(dt > 0)) return null;
    const dx = newest.x - oldest.x;
    const dy = newest.y - oldest.y;
    const speed = Math.sqrt(dx * dx + dy * dy) / dt;
    // Image y grows downward; negate dy so an upward release reads as a
    // positive launch angle, the way a real launch angle would.
    const angleDeg = (Math.atan2(-dy, dx) * 180) / Math.PI;
    // x/y: where in frame the release actually happened (the newest tracked
    // wrist position), for anything that wants to visually place the throw
    // near where the hand actually was, not always from one fixed point.
    return { speed, angleDeg, sampleSeconds: dt, x: newest.x, y: newest.y };
  }

  // points: { shoulder, elbow, wrist } in normalized image coordinates.
  // nowSeconds: any monotonic clock, in seconds.
  // hipPoints: optional { leftShoulder, rightShoulder, leftHip, rightHip },
  // from pointsForTorso() — omit or pass null when hips aren't tracked.
  update(rawPoints, nowSeconds, rawHipPoints) {
    if (!this.supported()) {
      return { phase: "not implemented", elbowAngleDeg: null, hipShoulderSeparationDeg: null, justReleased: false, releaseVelocity: null };
    }
    const points = this._smooth(rawPoints, "smoothedArm");
    const hipPoints = this._smooth(rawHipPoints ?? null, "smoothedHips");
    const rawPhase = this.profile.classify(points, hipPoints);
    const angle = elbowAngleDeg(points.shoulder, points.elbow, points.wrist);
    const separation = hipPoints ? hipShoulderSeparationDeg(hipPoints) : null;

    this.wristHistory.push({ x: points.wrist.x, y: points.wrist.y, t: nowSeconds });
    if (this.wristHistory.length > WRIST_HISTORY_LENGTH) this.wristHistory.shift();

    if (rawPhase === this.profile.releaseFrom) {
      this.raisedUntil = nowSeconds + this.followThroughHoldSeconds;
    }
    // A lowered arm reads as follow-through only if the arm was raised
    // recently — otherwise it is indistinguishable from an arm that was
    // simply never raised, i.e. rest (bug #1 above).
    const phase = rawPhase !== this.profile.releaseFrom && nowSeconds < this.raisedUntil ? this.profile.releaseTo : rawPhase;

    let justReleased = false;
    let releaseVelocity = null;
    if (
      this.previousPhase === this.profile.releaseFrom &&
      phase === this.profile.releaseTo &&
      nowSeconds - this.lastReleaseAt >= this.cooldownSeconds
    ) {
      justReleased = true;
      this.lastReleaseAt = nowSeconds;
      releaseVelocity = this._releaseVelocity(nowSeconds);
    }
    this.previousPhase = phase;
    return {
      phase,
      elbowAngleDeg: Math.round(angle),
      hipShoulderSeparationDeg: separation === null ? null : Math.round(separation),
      justReleased,
      releaseVelocity,
    };
  }
}
