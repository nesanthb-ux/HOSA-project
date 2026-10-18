// MAX30205 clinical-grade digital temperature sensor, worn against the skin
// on the forearm just proximal to the radial artery (thumb side of the
// wrist). This is a contact sensor, unlike the non-contact IR module in the
// first parts list, which suits a snug band far better.
//
// rawToCelsius() and skinTempOrNan() are portable and unit tested on a PC.
// The I2C read is only compiled on the ESP32.
#pragma once

#include <math.h>
#include <stdint.h>

namespace aria {

// 16-bit two's complement, 1 LSB = 1/256 degC (MAX30205 datasheet).
inline float rawToCelsius(uint16_t raw) { return static_cast<int16_t>(raw) * 0.00390625f; }

// Rejects sensor garbage (an unpowered/floating bus reads 0x0000 or 0xFFFF).
// This is a sanity range for skin on a living person, not a clinical value.
inline float skinTempOrNan(float celsius) {
  if (!isfinite(celsius)) return NAN;
  if (celsius < 15.0f || celsius > 45.0f) return NAN;
  return celsius;
}

#ifdef ARDUINO
#include <Wire.h>

constexpr uint8_t kMax30205Addr = 0x48;  // ADD0/1/2 tied low

inline bool max30205Begin() {
  Wire.beginTransmission(kMax30205Addr);
  return Wire.endTransmission() == 0;
}

// Returns NAN if the sensor does not answer or reads out of range.
inline float max30205ReadSkinCelsius() {
  Wire.beginTransmission(kMax30205Addr);
  Wire.write(static_cast<uint8_t>(0x00));  // temperature register
  if (Wire.endTransmission(false) != 0) return NAN;
  if (Wire.requestFrom(static_cast<int>(kMax30205Addr), 2) != 2) return NAN;
  const uint16_t raw = (static_cast<uint16_t>(Wire.read()) << 8) | static_cast<uint16_t>(Wire.read());
  return skinTempOrNan(rawToCelsius(raw));
}
#endif  // ARDUINO

}  // namespace aria
