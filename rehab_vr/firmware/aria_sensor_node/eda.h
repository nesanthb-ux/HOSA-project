// Electrodermal activity (skin conductance) from the Grove GSR sensor, worn
// on the palm/fingers. Portable C++ (unit tested on a PC).
//
// Conversion is Seeed's published reference formula for the Grove GSR
// module, which assumes an averaged 10-bit ADC reading (0..1023):
//     resistance_ohms = ((1024 + 2 * x) * 10000) / (512 - x)
//     conductance_uS  = 1e6 / resistance_ohms
// The sketch sets the ESP32 ADC to 10 bits so the formula applies as
// published. The ESP32 ADC is not perfectly linear, so absolute microsiemens
// are approximate. The fusion stage works from each athlete's own resting
// baseline, which is what makes the numbers usable; do not present them as
// calibrated lab values.
//
// Returns NAN, and the caller must then omit the channel, when the reading
// cannot be right: at/near the rails (short or open circuit) or where the
// formula's denominator goes to zero or negative.
#pragma once

#include <math.h>

namespace aria {

constexpr float kEdaMinRaw = 1.0f;     // at or below: rail / short circuit
constexpr float kEdaMaxRaw = 510.0f;   // at or above: no contact, or formula out of range

inline float edaMicrosiemens(float adc10BitMean) {
  if (!isfinite(adc10BitMean)) return NAN;
  if (adc10BitMean <= kEdaMinRaw || adc10BitMean >= kEdaMaxRaw) return NAN;
  const float resistanceOhms = ((1024.0f + 2.0f * adc10BitMean) * 10000.0f) / (512.0f - adc10BitMean);
  if (!(resistanceOhms > 0.0f)) return NAN;
  return 1000000.0f / resistanceOhms;
}

}  // namespace aria
