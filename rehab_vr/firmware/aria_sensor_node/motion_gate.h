// Decides whether the arm is still enough to trust the PPG, from the band's
// accelerometer. Portable C++ (unit tested on a PC).
//
// Feed it |acceleration| in g at a steady rate (about 50 Hz). At rest the
// magnitude is ~1 g (gravity). Any movement pushes it away from 1 g, and the
// PPG picks up motion artifact well before it looks dramatic on the IMU, so
// the threshold is deliberately small. It is a tuning parameter to be set
// against real recordings of the band on an arm, not a clinical value.
#pragma once

#include <math.h>

namespace aria {

struct MotionGateConfig {
  float thresholdG = 0.12f;  // deviation from 1 g that counts as "moving"
  float decay = 0.98f;       // per-sample decay of the motion level (~1 s at 50 Hz)
};

class MotionGate {
 public:
  explicit MotionGate(const MotionGateConfig& cfg = MotionGateConfig()) : cfg_(cfg) {}

  // accelMagnitudeG < 0 or NaN means the IMU read failed. A failed read is
  // treated as motion: with no IMU we cannot vouch that the arm is still.
  void push(float accelMagnitudeG) {
    if (!(accelMagnitudeG >= 0.0f) || !isfinite(accelMagnitudeG)) {
      level_ = cfg_.thresholdG * 10.0f;
      return;
    }
    const float dev = fabsf(accelMagnitudeG - 1.0f);
    level_ *= cfg_.decay;
    if (dev > level_) level_ = dev;
  }

  bool ok() const { return level_ < cfg_.thresholdG; }
  float level() const { return level_; }

 private:
  MotionGateConfig cfg_;
  // Start "not ok" (just above the threshold) until real samples show the
  // arm is still; it clears in well under a second of stillness.
  float level_ = 0.18f;
};

}  // namespace aria
