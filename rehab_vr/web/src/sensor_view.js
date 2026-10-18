// Turns one message from the sensor service into what the UI and the exposure
// engine should do with it. Pure functions with no DOM, so the rules for
// dropped channels can be unit tested in Node.
//
// Real wearables lose channels. A channel is null when it is not currently
// trustworthy (the arm was moving, a sensor came off). Nothing here ever shows
// a null as 0, and a reading missing a channel the build HAS can never step
// the athlete UP the exposure ladder.
//
// A channel the build never had fitted is a different thing entirely. The
// service says which channels it expects (sensor_config.py). On a two-sensor
// build, skin temperature is absent on every reading forever; treating that
// as a dropout would freeze the athlete at level 0 with no explanation.

export const ALL_CHANNELS = ["eda_us", "heart_rate_bpm", "skin_temp_c"];
export const CHANNELS_TOTAL = ALL_CHANNELS.length;

export function formatChannel(value, digits, unit) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)} ${unit}`;
}

// Which channels this build is expected to have. Older feeds that predate
// sensor configs send nothing, and had all three.
function expectedChannels(reading) {
  return Array.isArray(reading.channels_expected) && reading.channels_expected.length
    ? reading.channels_expected
    : ALL_CHANNELS;
}

export function interpretReading(reading) {
  const score = Number.isFinite(reading.arousal_score) ? reading.arousal_score : null;
  const expected = expectedChannels(reading);
  const available = Number.isInteger(reading.channels_available) ? reading.channels_available : CHANNELS_TOTAL;
  // "complete" means every channel this build has, arrived this second.
  const complete =
    typeof reading.complete === "boolean" ? reading.complete : available >= expected.length;
  const missing = Array.isArray(reading.channels_missing) ? reading.channels_missing : [];

  const calibration = reading.calibration && typeof reading.calibration === "object" ? reading.calibration : null;
  const calibrating = calibration !== null && calibration.state === "running";

  let status = null; // null means "leave the connection text alone" (simulator)
  if (calibrating) {
    // The service withholds the score while it measures the resting baseline,
    // so nothing can act on a half-measured baseline.
    const left = Number.isFinite(calibration.seconds_left) ? Math.ceil(calibration.seconds_left) : null;
    const suffix = left === null ? "" : ` (${left} s left)`;
    status = { kind: "calibrating", text: `calibrating: sit still and relax${suffix}` };
  } else if (reading.hardware_stale === true) {
    status = { kind: "stale", text: "sensor node not reporting, check power and WiFi" };
  } else if (score === null) {
    status = { kind: "none", text: "sensor node connected, but no valid readings right now" };
  } else if (calibration !== null && calibration.state === "failed") {
    const why = typeof calibration.reason === "string" ? calibration.reason : "not enough valid readings";
    status = { kind: "calibration_failed", text: `calibration failed, using the default baseline. ${why}` };
  } else if (!complete) {
    const which = missing.length ? ` (${missing.map(shortName).join(", ")})` : "";
    status = { kind: "partial", text: `partial data${which}, will not step up` };
  } else if (reading.hardware_stale === false) {
    status = { kind: "live", text: "sensor node connected (live hardware)" };
  }

  return {
    score,
    calibrating,
    complete,
    expected,
    // A build without a temperature sensor must still be able to advance, so
    // this asks for the channels this build HAS, not all three.
    canEscalate: !calibrating && score !== null && complete,
    status,
    texts: {
      eda: channelText(reading, "eda_us", expected, 2, "µS"),
      hr: channelText(reading, "heart_rate_bpm", expected, 0, "bpm"),
      temp: channelText(reading, "skin_temp_c", expected, 1, "°C"),
      score: score === null ? "no data" : score.toFixed(2),
    },
  };
}

// "not fitted" and "no reading right now" look identical as a dash, and they
// mean very different things to whoever is debugging the rig.
function channelText(reading, name, expected, digits, unit) {
  if (!expected.includes(name)) return "not fitted";
  return formatChannel(reading[name], digits, unit);
}

function shortName(channel) {
  return { eda_us: "EDA", heart_rate_bpm: "heart rate", skin_temp_c: "skin temp" }[channel] || channel;
}
