#pragma once
#include "Arduino.h"
#include "Wire.h"

class MAX30105 {
 public:
  bool begin(TwoWire&, uint32_t) { return true; }
  void setup(byte, byte, byte, int, int, int) {}
  void setPulseAmplitudeRed(uint8_t) {}
  void setPulseAmplitudeGreen(uint8_t) {}
  uint16_t check() { return 0; }
  uint8_t available() { return 0; }
  uint32_t getFIFOIR() { return 0; }
  void nextSample() {}
};
