// Two audiences, one set of facts. Both phrasings are built from the same
// structured event the exposure engine emits — never from parsing a
// pre-written sentence back apart — so they can never silently drift out of
// sync with each other or with what the system actually did.

export function technicalReason(event) {
  const pct = Math.round(event.score * 100);
  if (event.action === "retreat") {
    return `Retreated one level — arousal reading ${event.score.toFixed(2)} crossed the retreat threshold (${event.threshold}).`;
  }
  return `Advanced one level — arousal stayed below ${event.threshold} for ${event.holdSeconds}s straight (last reading ${event.score.toFixed(2)}, ${pct}%).`;
}

export function athleteReason(event) {
  if (event.action === "retreat") {
    return "We eased back a step — your body showed some stress there. Totally normal, let's reset and try again.";
  }
  return "Nice and steady. Since you held calm for a while, we're stepping it up a notch.";
}

// ---------------------------------------------------------- catching mode --
// Same rule as above: both wordings are built from the structured event the
// catching engine emits, so they cannot drift apart or away from what the
// system did. Catching mode changes BALL SPEED, not an exposure level, and
// the reasons are different, so it gets its own pair of functions rather than
// bending the throwing wording to fit.

export function technicalCatchReason(event) {
  switch (event.reason) {
    case "catch_streak":
      return `Ball speed ${event.fromMph} to ${event.toMph} mph — ${event.catches} catches in a row.`;
    case "miss_streak":
      return `Ball speed ${event.fromMph} to ${event.toMph} mph — ${event.misses} misses in a row.`;
    case "arousal_spike":
      return `Ball speed ${event.fromMph} to ${event.toMph} mph — arousal ${event.score.toFixed(2)} reached the retreat threshold (${event.threshold}).`;
    case "trainer_cap_lowered":
      return `Ball speed ${event.fromMph} to ${event.toMph} mph — trainer lowered the cap.`;
    default:
      return `Ball speed ${event.fromMph} to ${event.toMph} mph.`;
  }
}

export function athleteCatchReason(event) {
  switch (event.reason) {
    case "catch_streak":
      return "You've got a streak going, so the ball is coming a little quicker now.";
    case "miss_streak":
      return "Slowing the ball down a bit so you can get your timing back.";
    case "arousal_spike":
      return "Easing off the speed — your body showed some stress there. That's normal.";
    case "trainer_cap_lowered":
      return "Your trainer set a slower speed for this part.";
    default:
      return "Ball speed changed.";
  }
}

// Status line between catches. It never tells the athlete how many throws to
// take: throw volume and distance are the trainer's call, not the system's.
export function athleteCatchStatus(state) {
  if (state.atCap) return "Holding at the speed your trainer set.";
  if (state.missStreak > 0) return "Reset and watch the ball all the way in.";
  if (state.catchStreak === 0) return "Track the ball and catch when you're ready.";
  const left = state.catchesToSpeedUp;
  return left > 0
    ? `${state.catchStreak} in a row — ${left} more before the ball speeds up.`
    : `${state.catchStreak} in a row.`;
}

// A short, level-agnostic status line shown even between adaptation events,
// so the panel never looks broken/frozen while waiting for the next one.
export function athleteIdleStatus(secondsCalm, holdTarget, isMaxLevel) {
  if (isMaxLevel) return "Full game intensity — holding here.";
  if (secondsCalm <= 0) return "Reading your response to this level.";
  const remaining = Math.max(0, Math.ceil(holdTarget - secondsCalm));
  return remaining > 0
    ? `Staying steady — ${remaining}s more at this level before we step it up.`
    : "Holding here.";
}
