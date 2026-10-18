// Catching mode: the second of the two training modes.
//
// Throwing mode is a FEAR ladder. The arousal score decides the level, and
// the athlete moves up only after holding calm (exposure_levels.js).
//
// Catching mode is different on purpose. What the athlete is rebuilding here
// is the reaction and the willingness to let a ball come at the arm, so the
// control variable is BALL SPEED and the driver is PERFORMANCE: catches make
// the ball faster, misses make it slower. The arousal score does not push the
// speed up here. It only ever pulls it down, as a safety monitor.
//
// Two hard limits that performance can never override:
//   - a trainer cap. The engine never exceeds the speed a trainer set, no
//     matter how many catches in a row the athlete makes.
//   - a stress spike (the same threshold that retreats the fear ladder)
//     lowers the speed at once and clears the streak.
// Partial sensor data can lower the speed but never raise it, matching the
// rule in the exposure engine.
//
// The ball is virtual. Nothing is physically thrown at the athlete by this
// system, so "miss" means the hand was not in the right place in the scene,
// not that anyone was hit.
//
// The step size, the streak counts and the speeds are prototype parameters
// taken from the project's own engineering plan. They are not clinical
// values, and a trainer sets the cap for each athlete.

import { RETREAT_ABOVE } from "./exposure_levels.js";

export const SPEED_STEP_MPH = 5;
export const FLOOR_SPEED_MPH = 25;
export const DEFAULT_START_SPEED_MPH = 35;
export const DEFAULT_TRAINER_CAP_MPH = 55; // deliberately low. The trainer raises it.
export const CATCHES_TO_SPEED_UP = 3;
export const MISSES_TO_SLOW_DOWN = 2;
export const DEFAULT_DISTANCE_FEET = 46; // short-toss distance, also a trainer setting

// Flight time of the ball, from distance and speed. Plain physics
// (1 mph = 5280/3600 ft per second), not an estimate of human reaction time.
// The time an athlete actually has to move is shorter than this, because
// seeing the ball and starting to move both take some of it.
export function flightSeconds(distanceFeet, speedMph) {
  if (!(distanceFeet > 0) || !(speedMph > 0)) return null;
  return distanceFeet / ((speedMph * 5280) / 3600);
}

// A coarse band for display only, so the athlete and trainer see "where we
// are" without reading a raw number. Bands are labels over the speed, not
// separate states: the engine's state is the speed itself.
export const SPEED_BANDS = [
  { id: 0, upToMph: 40, label: "Soft toss", description: "Gentle lob, easy to track." },
  { id: 1, upToMph: 50, label: "Easy toss", description: "Light catch play." },
  { id: 2, upToMph: 60, label: "Standard", description: "Ordinary practice throw." },
  { id: 3, upToMph: 75, label: "Firm", description: "Quick, predictable throws." },
  { id: 4, upToMph: Infinity, label: "Game speed", description: "Fast throws, short reaction time." },
];

export function speedBand(speedMph) {
  return SPEED_BANDS.find((band) => speedMph < band.upToMph) || SPEED_BANDS[SPEED_BANDS.length - 1];
}

export class CatchingModeEngine {
  // onChange(state, event) fires only when the speed actually changes. The
  // event is structured facts, not a sentence, so the athlete-facing and
  // trainer-facing wording are both built from it (explain.js).
  constructor({
    startSpeedMph = DEFAULT_START_SPEED_MPH,
    trainerCapMph = DEFAULT_TRAINER_CAP_MPH,
    distanceFeet = DEFAULT_DISTANCE_FEET,
    qualifyingReactionSeconds = null, // null: any catch counts. A number is a trainer setting.
    onChange = () => {},
  } = {}) {
    this.trainerCapMph = trainerCapMph;
    this.distanceFeet = distanceFeet;
    this.qualifyingReactionSeconds = qualifyingReactionSeconds;
    this.onChange = onChange;
    this.speedMph = Math.min(startSpeedMph, trainerCapMph);
    this.catchStreak = 0;
    this.missStreak = 0;
    this.attempts = 0;
    this.caughtTotal = 0;
  }

  // A trainer may raise or lower the cap mid-session. Lowering it below the
  // current speed pulls the speed down immediately, because the cap is a
  // limit on what the athlete is being asked to do, not just on future steps.
  setTrainerCap(mph) {
    this.trainerCapMph = mph;
    if (this.speedMph > mph) {
      this._setSpeed(mph, { action: "cap", reason: "trainer_cap_lowered" });
    }
  }

  state() {
    const band = speedBand(this.speedMph);
    return {
      speedMph: this.speedMph,
      trainerCapMph: this.trainerCapMph,
      distanceFeet: this.distanceFeet,
      flightSeconds: flightSeconds(this.distanceFeet, this.speedMph),
      band,
      atCap: this.speedMph >= this.trainerCapMph,
      catchStreak: this.catchStreak,
      missStreak: this.missStreak,
      attempts: this.attempts,
      caughtTotal: this.caughtTotal,
      catchesToSpeedUp: Math.max(0, CATCHES_TO_SPEED_UP - this.catchStreak),
    };
  }

  // Call once per finished catch attempt.
  //   caught            true or false. null/undefined means the attempt could
  //                     not be judged (tracking lost); it is ignored entirely.
  //   reactionSeconds   optional, recorded and only used when the trainer set
  //                     a qualifying reaction time.
  //   arousalScore      0-1, or null when there is no usable reading.
  //   canAdvance        false when sensor data is partial. Slowing down still
  //                     works: being careful is always allowed.
  update({ caught, reactionSeconds = null, arousalScore = null, canAdvance = true } = {}) {
    // A stress spike outranks performance. Checked before the attempt is even
    // scored, so a catch made while the athlete is spiking cannot speed it up.
    if (arousalScore !== null && arousalScore !== undefined && arousalScore >= RETREAT_ABOVE) {
      this.catchStreak = 0;
      this.missStreak = 0;
      if (this.speedMph > FLOOR_SPEED_MPH) {
        this._setSpeed(Math.max(FLOOR_SPEED_MPH, this.speedMph - SPEED_STEP_MPH), {
          action: "slow_down",
          reason: "arousal_spike",
          score: arousalScore,
          threshold: RETREAT_ABOVE,
        });
      }
      return this.state();
    }

    if (caught === null || caught === undefined) return this.state(); // not judged: no credit either way

    this.attempts += 1;
    const quick =
      this.qualifyingReactionSeconds === null ||
      (Number.isFinite(reactionSeconds) && reactionSeconds <= this.qualifyingReactionSeconds);

    if (caught && quick) {
      this.caughtTotal += 1;
      this.catchStreak += 1;
      this.missStreak = 0;
      if (this.catchStreak >= CATCHES_TO_SPEED_UP && canAdvance && this.speedMph < this.trainerCapMph) {
        this.catchStreak = 0;
        this._setSpeed(Math.min(this.trainerCapMph, this.speedMph + SPEED_STEP_MPH), {
          action: "speed_up",
          reason: "catch_streak",
          catches: CATCHES_TO_SPEED_UP,
        });
      }
      return this.state();
    }

    if (caught) this.caughtTotal += 1; // caught, but slower than the trainer's qualifying time
    this.catchStreak = 0;
    if (!caught) {
      this.missStreak += 1;
      if (this.missStreak >= MISSES_TO_SLOW_DOWN && this.speedMph > FLOOR_SPEED_MPH) {
        this.missStreak = 0;
        this._setSpeed(Math.max(FLOOR_SPEED_MPH, this.speedMph - SPEED_STEP_MPH), {
          action: "slow_down",
          reason: "miss_streak",
          misses: MISSES_TO_SLOW_DOWN,
        });
      }
    }
    return this.state();
  }

  _setSpeed(mph, event) {
    if (mph === this.speedMph) return;
    const fromMph = this.speedMph;
    this.speedMph = mph;
    this.onChange(this.state(), { ...event, fromMph, toMph: mph });
  }
}
