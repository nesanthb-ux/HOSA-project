#pragma once
#include <Wire.h>
#include <math.h>

// MPU6050 accelerometer/gyro - motion, fall detection, seizure-like rhythmic
// movement, activity level (Doc 03 §3). Raw I2C register access, no vendor
// library needed.
namespace Mpu6050 {

constexpr uint8_t I2C_ADDR = 0x68;          // AD0 tied low
constexpr uint8_t REG_PWR_MGMT_1 = 0x6B;
constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
constexpr float ACCEL_SCALE = 16384.0f;     // LSB/g at default +/-2g range

// Rolling window used to tell a brief spike (fall) apart from a sustained
// rhythmic pattern (seizure-like activity) without needing an external lib.
constexpr int WINDOW_SIZE = 20;             // ~2s at 10 Hz sampling
float windowBuf[WINDOW_SIZE] = {0};
int windowIdx = 0;
bool windowFull = false;

inline bool begin() {
  Wire.beginTransmission(I2C_ADDR);
  Wire.write(REG_PWR_MGMT_1);
  Wire.write(0x00);  // wake the sensor out of sleep mode
  return Wire.endTransmission() == 0;
}

// Magnitude of acceleration in g, so ~1.0 at rest (gravity) and away from
// 1.0 under motion. Returns NAN if the sensor didn't ACK.
inline float readAccelMagnitudeG() {
  Wire.beginTransmission(I2C_ADDR);
  Wire.write(REG_ACCEL_XOUT_H);
  if (Wire.endTransmission(false) != 0) return NAN;

  if (Wire.requestFrom((int)I2C_ADDR, 6) != 6) return NAN;
  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();

  float gx = ax / ACCEL_SCALE;
  float gy = ay / ACCEL_SCALE;
  float gz = az / ACCEL_SCALE;
  return sqrtf(gx * gx + gy * gy + gz * gz);
}

// Pushes one sample into the rolling window used for fall/seizure heuristics.
inline void pushSample(float accelMagnitudeG) {
  windowBuf[windowIdx] = accelMagnitudeG;
  windowIdx = (windowIdx + 1) % WINDOW_SIZE;
  if (windowIdx == 0) windowFull = true;
}

// "Motion" metric sent to the Hub: deviation from resting gravity (1g),
// scaled up so it's a comparable magnitude to backend/sentra's motion
// features (feature_engine/imu_features.py's activity-level thresholds
// assume this same scale — see docs/HARDWARE_SCOPE.md §4).
inline float motionMetric(float accelMagnitudeG) {
  return fabsf(accelMagnitudeG - 1.0f) * 10.0f;
}

// A single very large deviation from rest, isolated rather than sustained,
// reads as a fall/impact rather than ongoing tremor.
inline bool isFallLike(float accelMagnitudeG) {
  return fabsf(accelMagnitudeG - 1.0f) > 1.5f;
}

// Sustained oscillation across the whole window (high variance, not just one
// spike) reads as seizure-like rhythmic movement rather than a single fall.
inline bool isSeizureLike() {
  if (!windowFull) return false;
  float mean = 0;
  for (float v : windowBuf) mean += v;
  mean /= WINDOW_SIZE;

  float variance = 0;
  for (float v : windowBuf) variance += (v - mean) * (v - mean);
  variance /= WINDOW_SIZE;

  return variance > 0.5f;
}

}  // namespace Mpu6050
