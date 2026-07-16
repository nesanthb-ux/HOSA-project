#pragma once
#include <Wire.h>

// MAX30205 human body temperature sensor - skin temperature (Doc 03 §3).
// Talked to over plain I2C register reads; no vendor library needed.
namespace Max30205 {

constexpr uint8_t I2C_ADDR = 0x48;       // ADD0/ADD1/ADD2 tied low on most breakouts
constexpr uint8_t REG_TEMPERATURE = 0x00;

inline bool begin() {
  Wire.beginTransmission(I2C_ADDR);
  return Wire.endTransmission() == 0;
}

// Returns skin temperature in degrees C, or NAN if the sensor didn't ACK.
inline float readCelsius() {
  Wire.beginTransmission(I2C_ADDR);
  Wire.write(REG_TEMPERATURE);
  if (Wire.endTransmission(false) != 0) return NAN;

  if (Wire.requestFrom((int)I2C_ADDR, 2) != 2) return NAN;
  uint16_t raw = (Wire.read() << 8) | Wire.read();

  // 16-bit two's complement, LSB = 1/256 degC (MAX30205 datasheet).
  int16_t signedRaw = (int16_t)raw;
  return signedRaw * 0.00390625f;
}

}  // namespace Max30205
