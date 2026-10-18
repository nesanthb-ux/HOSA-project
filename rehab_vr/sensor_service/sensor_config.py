"""Which sensors this particular build is expected to have.

This exists because of a real bug the reduced-sensor build would otherwise
hit. The exposure engine refuses to step an athlete UP unless every channel
contributed to the score. That rule was written when every build had all
three channels. On a two-sensor build (skin temperature not fitted) the third
channel is missing on every single reading, so the athlete could never
advance, and nothing in the UI would explain why.

So "all channels present" has to mean "all channels this build was expected
to provide", and the expected set has to travel with the reading. A channel
that the hardware HAS but that dropped out this second is still a missing
channel and still blocks advancing. A channel that was never fitted is not.

Grip force is deliberately not part of any scoring set. See GRIP_NOTE.
"""
from __future__ import annotations

from dataclasses import dataclass

# Every channel the fusion formula knows how to score.
SCORED_CHANNELS = ("eda_us", "heart_rate_bpm", "skin_temp_c")

# Measured and shown, never scored. Guarded gripping (squeezing the ball
# harder than needed) is a plausible sign of protecting the arm, but there is
# no validated mapping from a force reading to fear, and inventing one would
# put a made-up number inside a score a trainer might act on. It is carried
# as its own telemetry so it can be logged, displayed and studied first.
TELEMETRY_ONLY_CHANNELS = ("grip_raw",)

GRIP_NOTE = (
    "Grip force is recorded and displayed on its own. It is not part of the arousal "
    "score, because no validated mapping from grip force to fear exists yet."
)


@dataclass(frozen=True)
class SensorConfig:
    """name     short id used in logs and the UI
    expected    channels this build should deliver; a gap in one of these is a
                real dropout and blocks stepping up
    telemetry   extra channels recorded but never scored
    """

    name: str
    expected: tuple
    telemetry: tuple = ()
    description: str = ""

    def __post_init__(self):
        unknown = [c for c in self.expected if c not in SCORED_CHANNELS]
        if unknown:
            raise ValueError(f"not scoreable channels: {unknown}")
        if not self.expected:
            raise ValueError("a config must expect at least one channel")

    def expects(self, channel: str) -> bool:
        return channel in self.expected


# The build the team is assembling now: PPG on the upper arm, GSR on the hand,
# IMU on the band for motion gating. The IMU is not a scored channel; it
# decides whether the heart rate can be trusted at all (see the firmware).
MINIMAL = SensorConfig(
    name="minimal",
    expected=("eda_us", "heart_rate_bpm"),
    description="PPG + GSR + IMU. Fewest parts that still gives two independent arousal signals.",
)

# Adds the contact skin-temperature sensor on the forearm.
FULL = SensorConfig(
    name="full",
    expected=SCORED_CHANNELS,
    description="PPG + GSR + IMU + skin temperature.",
)

# MINIMAL plus the experimental grip sensor, still outside the score.
MINIMAL_WITH_GRIP = SensorConfig(
    name="minimal+grip",
    expected=("eda_us", "heart_rate_bpm"),
    telemetry=TELEMETRY_ONLY_CHANNELS,
    description="MINIMAL plus a grip force sensor, recorded separately and never scored.",
)

CONFIGS = {c.name: c for c in (MINIMAL, FULL, MINIMAL_WITH_GRIP)}
DEFAULT = MINIMAL


def get(name: str) -> SensorConfig:
    if name not in CONFIGS:
        raise ValueError(f"unknown sensor config {name!r}. Known: {sorted(CONFIGS)}")
    return CONFIGS[name]
