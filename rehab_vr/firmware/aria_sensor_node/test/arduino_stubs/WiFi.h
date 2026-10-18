#pragma once
#include "Arduino.h"

enum { WL_CONNECTED = 3 };
enum { WIFI_STA = 1 };

struct IPAddressStub { String toString() const { return String("0.0.0.0"); } };
struct WiFiStub {
  int status() { return 0; }
  void mode(int) {}
  void begin(const char*, const char*) {}
  IPAddressStub localIP() { return IPAddressStub(); }
};
extern WiFiStub WiFi;
