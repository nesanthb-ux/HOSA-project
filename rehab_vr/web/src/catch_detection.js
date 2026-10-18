// Judges one catch attempt: did the glove hand get to the ball, and how long
// did the athlete take to start moving.
//
// The ball is ours. We simulate it, so its position at every instant is known
// exactly and there is nothing to estimate about it. The only measured thing
// is where the athlete's hand is. A catch is therefore a geometry question:
// did the hand and the ball get within a catch radius of each other before
// the ball went past.
//
// Coordinate space: the caller passes the hand and the ball in ONE shared
// space and a catch radius in the units of that space. Two sources work:
//   - headset hand or controller tracking, which is already in the same world
//     space as the ball, so the comparison is exact;
//   - a webcam pose estimate, which is in normalized image coordinates and
//     needs the ball projected into the same frame first. That projection is
//     an integration step that has not been built or tested yet.
// This module does not choose between them, and it does not assume either is
// accurate. If tracking drops out for the whole attempt, the attempt is
// reported as NOT JUDGED rather than as a miss, because a lost camera is not
// a failure by the athlete.
//
// The catch radius and the movement threshold below are prototype values to
// tune against a real recording. They are not clinical or biomechanical
// constants.

export const DEFAULT_CATCH_RADIUS = 0.12; // in the caller's units
export const DEFAULT_MOVE_THRESHOLD = 0.03; // how far the hand must move to count as "started moving"

function distance(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = (a.z || 0) - (b.z || 0);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

function usable(point) {
  return (
    point &&
    Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    (point.z === undefined || Number.isFinite(point.z))
  );
}

export class CatchAttempt {
  // thrownAtSeconds: when the ball left the virtual partner's hand. Reaction
  // time is measured from here, so it includes seeing the ball, which is the
  // thing being rebuilt.
  constructor({ thrownAtSeconds, catchRadius = DEFAULT_CATCH_RADIUS, moveThreshold = DEFAULT_MOVE_THRESHOLD } = {}) {
    this.thrownAtSeconds = thrownAtSeconds;
    this.catchRadius = catchRadius;
    this.moveThreshold = moveThreshold;
    this.closestDistance = Infinity;
    this.startPoint = null;
    this.movedAtSeconds = null;
    this.samples = 0;
  }

  // Call every frame while the ball is in the air. Frames where either point
  // is missing are skipped, not counted as a miss.
  update(handPoint, ballPoint, nowSeconds) {
    if (!usable(handPoint) || !usable(ballPoint)) return;
    this.samples += 1;
    if (this.startPoint === null) this.startPoint = { ...handPoint };

    if (this.movedAtSeconds === null && distance(handPoint, this.startPoint) >= this.moveThreshold) {
      this.movedAtSeconds = nowSeconds;
    }
    const d = distance(handPoint, ballPoint);
    if (d < this.closestDistance) this.closestDistance = d;
  }

  // Call once when the ball reaches or passes the athlete.
  //   judged false  -> nothing was tracked, so the attempt is not scored at all
  //   caught        -> the hand came within the catch radius at some point
  //   reactionSeconds -> from the throw to the first real hand movement, or
  //                      null if the hand never moved
  result() {
    if (this.samples === 0) {
      return { judged: false, caught: null, closestDistance: null, reactionSeconds: null, samples: 0 };
    }
    return {
      judged: true,
      caught: this.closestDistance <= this.catchRadius,
      closestDistance: this.closestDistance,
      reactionSeconds: this.movedAtSeconds === null ? null : this.movedAtSeconds - this.thrownAtSeconds,
      samples: this.samples,
    };
  }
}

// Which hand receives the ball. An athlete throws with the operated arm and
// normally catches with the glove on the OTHER hand, so the default catch
// hand is the opposite of the throwing arm. A trainer can override it for
// bare-hand drills, in which case the operated arm is the one receiving.
export function catchHandFor(throwingArm, { bareHand = false } = {}) {
  if (bareHand) return throwingArm;
  return throwingArm === "right" ? "left" : "right";
}

// MediaPipe Pose wrist landmarks, by side.
export const WRIST_LANDMARK = { right: 16, left: 15 };

export function wristPoint(landmarks, side) {
  const index = WRIST_LANDMARK[side];
  if (index === undefined || !landmarks) return null;
  const point = landmarks[index];
  return usable(point) ? point : null;
}
