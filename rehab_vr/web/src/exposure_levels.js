// The exposure ladder — what actually changes between levels is the social/
// consequence stakes around the mound, not the mound itself, since that's
// what UCL kinesiophobia is about: fear of re-injuring the elbow *in front
// of* a batter/crowd, not fear of the throwing motion in isolation.
//
// This is a designed prototype ladder, not a validated clinical exposure
// protocol — there is no UCL-specific instrument to validate against yet
// (PIVOT_PLAN.md §3a/§9). It encodes a reasonable, inspectable ordering;
// treat the specific thresholds as a starting point to tune against real
// athletic-trainer feedback, not a finished clinical tool.
export const EXPOSURE_LEVELS = [
  {
    id: 0,
    name: "Solo toss",
    description: "Empty field. No batter, no catcher — reacquainting with a ball in hand.",
    crowdVolume: 0,
    catcherPresent: false,
    batterPresent: false,
    batterSwinging: false,
    lightingIntensity: 0.55,
  },
  {
    id: 1,
    name: "Bullpen, catcher only",
    description: "A catcher's target is present. Quiet bullpen, no batter.",
    crowdVolume: 0,
    catcherPresent: true,
    batterPresent: false,
    batterSwinging: false,
    lightingIntensity: 0.7,
  },
  {
    id: 2,
    name: "Batter stands in, no swing",
    description: "A batter is in the box but not swinging — reintroduces a person near the release point without live-swing risk.",
    crowdVolume: 0.15,
    catcherPresent: true,
    batterPresent: true,
    batterSwinging: false,
    lightingIntensity: 0.8,
  },
  {
    id: 3,
    name: "Live batting practice",
    description: "The batter takes live swings. Light ambient crowd presence.",
    crowdVolume: 0.45,
    catcherPresent: true,
    batterPresent: true,
    batterSwinging: true,
    lightingIntensity: 0.9,
  },
  {
    id: 4,
    name: "Full game simulation",
    description: "A small crowd is watching from the fence line, bright daylight, live batter.",
    crowdVolume: 1.0,
    catcherPresent: true,
    batterPresent: true,
    batterSwinging: true,
    lightingIntensity: 1.0,
  },
];

// Documented, prototype-stage thresholds — deliberately conservative and
// asymmetric: escalation requires the athlete to hold calm for a sustained
// stretch (habituation), but retreat is immediate on a single high reading.
// That asymmetry is the actual clinical principle being encoded: never let
// the system escalate faster than it retreats.
export const ESCALATE_BELOW = 0.35;
export const ESCALATE_HOLD_SECONDS = 8;
export const RETREAT_ABOVE = 0.75;

// The sensor feed ticks about once a second. If more than this long passes
// between readings, the stretch in between was not observed, so it earns no
// calm credit — otherwise one calm reading after a dropped connection could
// count the whole gap as "held calm" and step the athlete up on no evidence.
// A data-continuity guard (allows normal network jitter), not a clinical value.
export const MAX_TICK_GAP_SECONDS = 2.5;

export class AdaptiveExposureEngine {
  constructor(levels, onChange) {
    this.levels = levels;
    this.onChange = onChange;
    this.levelIndex = 0;
    this.calmSecondsAtLevel = 0;
    this.lastTick = null;
  }

  currentLevel() {
    return this.levels[this.levelIndex];
  }

  // Exposed so the UI can show "Ns more at this level" without duplicating
  // the engine's own timing state.
  getCalmSeconds() {
    return this.calmSecondsAtLevel;
  }

  // Call once per fused sensor reading (~1Hz).
  //   arousalScore  0-1, or null/undefined when there is no usable reading.
  //   dtSeconds     seconds since the previous call; defaults to real elapsed
  //                 time. Passing it explicitly makes the engine testable.
  //   canEscalate   false when the reading is partial (a sensor dropped out).
  //                 Retreat still works on partial data — being cautious is
  //                 always allowed — but stepping up needs the full picture.
  update(arousalScore, { dtSeconds, canEscalate = true } = {}) {
    const now = performance.now();
    let dt = dtSeconds !== undefined ? dtSeconds : this.lastTick !== null ? (now - this.lastTick) / 1000 : 0;
    this.lastTick = now;

    if (dt > MAX_TICK_GAP_SECONDS) {
      this.calmSecondsAtLevel = 0;
      dt = 0;
    }

    if (arousalScore === null || arousalScore === undefined || Number.isNaN(arousalScore)) {
      this.calmSecondsAtLevel = 0; // no data earns no calm credit
      return;
    }

    if (arousalScore >= RETREAT_ABOVE && this.levelIndex > 0) {
      this.levelIndex -= 1;
      this.calmSecondsAtLevel = 0;
      this._emit({ action: "retreat", score: arousalScore, threshold: RETREAT_ABOVE });
      return;
    }

    if (arousalScore < ESCALATE_BELOW && canEscalate) {
      this.calmSecondsAtLevel += dt;
      if (this.calmSecondsAtLevel >= ESCALATE_HOLD_SECONDS && this.levelIndex < this.levels.length - 1) {
        this.levelIndex += 1;
        this.calmSecondsAtLevel = 0;
        this._emit({
          action: "advance",
          score: arousalScore,
          threshold: ESCALATE_BELOW,
          holdSeconds: ESCALATE_HOLD_SECONDS,
        });
      }
    } else {
      this.calmSecondsAtLevel = 0;
    }
  }

  // Emits a structured event, not a pre-formatted sentence — main.js builds
  // both the athlete-facing and trainer-facing phrasing from the same facts
  // rather than parsing English back out of a log string.
  _emit(event) {
    this.onChange(this.currentLevel(), event);
  }
}
