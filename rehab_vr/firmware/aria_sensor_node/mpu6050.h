// MPU6050 accelerometer on the arm band. Its only job here is to tell the PPG
// heart-rate code when the arm is moving (see motion_gate.h). Raw I2C, no
// vendor library. Compiled on the ESP32 only.
#pragma once

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

namespace aria {

class Mpu6050 {
 public:
  // AD0 low = 0x68 (default), AD0 high = 0x69.
  explicit Mpu6050(uint8_t addr = 0x68) : addr_(addr) {}

  bool begin() {
    Wire.beginTransmission(addr_);
    Wire.write(static_cast<uint8_t>(0x6B));  // PWR_MGMT_1
    Wire.write(static_cast<uint8_t>(0x00));  // wake from sleep
    return Wire.endTransmission() == 0;
  }

  // |acceleration| in g (about 1.0 at rest). Returns -1 if the read failed;
  // MotionGate treats that as "moving", never as "still".
  float readAccelMagnitudeG() {
    Wire.beginTransmission(addr_);
    Wire.write(static_cast<uint8_t>(0x3B));  // ACCEL_XOUT_H
    if (Wire.endTransmission(false) != 0) return -1.0f;
    if (Wire.requestFrom(static_cast<int>(addr_), 6) != 6) return -1.0f;
    const int16_t ax = static_cast<int16_t>((Wire.read() << 8) | Wire.read());
    const int16_t ay = static_cast<int16_t>((Wire.read() << 8) | Wire.read());
    const int16_t az = static_cast<int16_t>((Wire.read() << 8) | Wire.read());
    constexpr float kLsbPerG = 16384.0f;  // default +/-2 g range
    const float gx = ax / kLsbPerG, gy = ay / kLsbPerG, gz = az / kLsbPerG;
    return sqrtf(gx * gx + gy * gy + gz * gz);
  }

 private:
  uint8_t addr_;
};

}  // namespace aria
