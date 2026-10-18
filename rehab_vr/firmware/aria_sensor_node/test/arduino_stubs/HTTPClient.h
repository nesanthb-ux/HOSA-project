#pragma once
#include "Arduino.h"

class HTTPClient {
 public:
  void setConnectTimeout(int) {}
  void setTimeout(int) {}
  bool begin(const String&) { return true; }
  void addHeader(const char*, const char*) {}
  int POST(uint8_t*, size_t) { return 204; }
  String errorToString(int) { return String("error"); }
  void end() {}
};
