// Copy this file to wifi_config.h (same folder) and fill in your real
// values — wifi_config.h is gitignored so real credentials never get
// committed. aria_sensor_node.ino #includes "wifi_config.h", not this file.
#pragma once

#define WIFI_SSID "your-wifi-name"
#define WIFI_PASSWORD "your-wifi-password"

// The laptop running `python -m rehab_vr.sensor_service.server --hardware`
// — find it with `ipconfig` (Windows) and use the IPv4 address of whatever
// network interface is on the SAME WiFi network as this board. Do not use
// "localhost" here — that means the ESP32 itself, not your laptop.
#define INGEST_HOST "192.168.1.100"
#define INGEST_PORT 8766
