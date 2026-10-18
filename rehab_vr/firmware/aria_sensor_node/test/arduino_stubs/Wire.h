#pragma once
#include <stddef.h>
#include <stdint.h>

class TwoWire {
 public:
  void begin() {}
  void setClock(uint32_t) {}
  void beginTransmission(uint8_t) {}
  uint8_t endTransmission(bool = true) { return 0; }
  size_t write(uint8_t) { return 1; }
  uint8_t requestFrom(int, int) { return 0; }
  int read() { return 0; }
};
extern TwoWire Wire;
