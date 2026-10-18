// Minimal stand-ins for the Arduino-ESP32 core, ONLY so the sketch can be
// syntax/type-checked on a PC. They encode my understanding of the real API;
// they cannot tell you the real API matches. Never used in a real build.
#pragma once

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <string>

typedef uint8_t byte;
#define INPUT 0x01
#define HIGH 1
#define LOW 0
#define I2C_SPEED_FAST 400000u
enum adc_attenuation_t { ADC_0db, ADC_2_5db, ADC_6db, ADC_11db };

inline uint32_t millis() { return 0; }
inline uint32_t micros() { return 0; }
inline void delay(uint32_t) {}
inline void delayMicroseconds(uint32_t) {}
inline int analogRead(int) { return 0; }
inline int digitalRead(int) { return 0; }
inline void pinMode(int, int) {}
inline void analogSetPinAttenuation(int, adc_attenuation_t) {}

class String {
 public:
  String() {}
  String(const char* s) : s_(s) {}
  String(int v) : s_(std::to_string(v)) {}
  String operator+(const String& o) const { return String((s_ + o.s_).c_str()); }
  String operator+(const char* o) const { return String((s_ + o).c_str()); }
  const char* c_str() const { return s_.c_str(); }
 private:
  std::string s_;
};
inline String operator+(const char* a, const String& b) { return String(a) + b; }

struct SerialStub {
  void begin(unsigned long) {}
  void println(const char*) {}
  void println(uint32_t) {}
  void println(int) {}
  template <typename... A> void printf(const char*, A...) {}
};
extern SerialStub Serial;
