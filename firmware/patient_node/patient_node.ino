// SENTRA Patient Node firmware (ESP32)
//
// Reads MAX30102 (PPG: HR+SpO2), MAX30205 (Temperature), and MPU6050 (IMU:
// motion), then notifies one compact JSON packet per sensor per second over
// BLE. Field names match backend/sentra/models.py's SensorPacket so a
// future hub/ble_manager.py can parse a notification straight into
// SensorPacket.model_validate_json() after filling in the three fields
// only the Hub can know (see "Packet contract" in firmware/README.md):
// packet_id, timestamp, connection_strength.
//
// Two things from the architecture docs this file is specifically
// responsible for:
//  - Graceful degradation (docs/03_Sensor_Input.md §16): keeps sampling and
//    buffering locally while BLE is disconnected, then flushes the backlog
//    on reconnect.
//  - The onboard RGB LED alerts off *local* thresholds only, so a patient
//    still gets a visual warning even with no Hub in range.
//
// Board: ESP32 Dev Module. Libraries: SparkFun MAX3010x Pulse and Proximity
// Sensor Library (for hr_spo2_max30102.h); everything else uses Wire.h and
// the built-in ESP32 BLE Arduino stack.

#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#include "hr_spo2_max30102.h"
#include "temp_max30205.h"
#include "motion_mpu6050.h"

// ---- Identity -------------------------------------------------------------
static const char *PATIENT_ID = "P-A";      // assigned at intake, matches the Hub's patient_id
static const char *DEVICE_ID = "node-A";    // unique per physical wearable
static const char *FIRMWARE_VERSION = "1.0.0";

// ---- Pins -------------------------------------------------------------
constexpr int PIN_LED_R = 25;
constexpr int PIN_LED_G = 26;
constexpr int PIN_LED_B = 27;
constexpr int PIN_BATTERY_ADC = 34;  // through a resistor divider from LiPo+

// ---- BLE ---------------------------------------------------------------
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHARACTERISTIC_UUID "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

BLEServer *bleServer = nullptr;
BLECharacteristic *bleCharacteristic = nullptr;
volatile bool bleConnected = false;

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { bleConnected = true; }
  void onDisconnect(BLEServer *server) override {
    bleConnected = false;
    server->getAdvertising()->start();  // keep advertising so the Hub can reconnect
  }
};

// ---- Local buffering for graceful degradation ------------------------------
struct Sample {
  unsigned long seq;
  float hr, spo2, temp, motion, battery;
};

constexpr int BUFFER_CAPACITY = 300;  // ~5 min at 1 Hz while out of range
Sample buffer[BUFFER_CAPACITY];
int bufferCount = 0;
unsigned long sequenceNumber = 0;

inline void bufferSample(const Sample &s) {
  if (bufferCount < BUFFER_CAPACITY) {
    buffer[bufferCount++] = s;
  } else {
    // Buffer full: drop the oldest reading rather than the newest one.
    memmove(&buffer[0], &buffer[1], sizeof(Sample) * (BUFFER_CAPACITY - 1));
    buffer[BUFFER_CAPACITY - 1] = s;
  }
}

// ---- Battery ----------------------------------------------------------
constexpr float BATTERY_EMPTY_V = 3.3f;
constexpr float BATTERY_FULL_V = 4.2f;

inline float readBatteryPercent() {
  int raw = analogRead(PIN_BATTERY_ADC);
  float voltage = (raw / 4095.0f) * 3.3f * 2.0f;  // 2:1 divider to fit the 3.3V ADC
  float pct = (voltage - BATTERY_EMPTY_V) / (BATTERY_FULL_V - BATTERY_EMPTY_V) * 100.0f;
  return constrain(pct, 0.0f, 100.0f);
}

// ---- Local RGB alert ----------------------------------------------------
// Deliberately simple, fixed local thresholds - NOT the Hub's adaptive
// per-patient baseline (docs/07_Baseline_Engine.md). This only has to
// answer "does this one patient look obviously wrong right now," so the
// wearable itself is never silent even with zero connectivity.
inline void setLed(bool red, bool green, bool blue) {
  digitalWrite(PIN_LED_R, red ? HIGH : LOW);
  digitalWrite(PIN_LED_G, green ? HIGH : LOW);
  digitalWrite(PIN_LED_B, blue ? HIGH : LOW);
}

inline void updateLocalAlert(float hr, float motionMag, bool sensorsOk) {
  if (!sensorsOk) {
    setLed(true, true, false);  // yellow: no valid reading
    return;
  }
  bool critical = hr > 140 || hr < 40 || Mpu6050::isFallLike(motionMag) || Mpu6050::isSeizureLike();
  bool warning = hr > 120 || hr < 50;

  if (critical) setLed(true, false, false);        // red: local emergency
  else if (warning) setLed(true, true, false);      // yellow: warning
  else setLed(false, true, false);                  // green: stable
}

// ---- Packet building & transmission ----------------------------------
// One JSON object per sensor type per second, matching
// backend/sentra/models.py::SensorPacket field names. packet_id,
// timestamp, and connection_strength are intentionally absent - the Hub
// fills those in on receipt (see firmware/README.md).
inline void sendPacket(const char *sensorType, float samplingRate, const float *values,
                        int valueCount, float batteryPct, unsigned long seq, bool isBuffered) {
  char valuesBuf[64];
  int offset = 0;
  valuesBuf[offset++] = '[';
  for (int i = 0; i < valueCount; i++) {
    offset += snprintf(valuesBuf + offset, sizeof(valuesBuf) - offset, "%s%.2f", i ? "," : "", values[i]);
  }
  valuesBuf[offset++] = ']';
  valuesBuf[offset] = '\0';

  char payload[220];
  snprintf(payload, sizeof(payload),
           "{\"patient_id\":\"%s\",\"device_id\":\"%s\",\"sensor_type\":\"%s\","
           "\"sampling_rate\":%.0f,\"values\":%s,\"battery_level\":%.1f,"
           "\"firmware_version\":\"%s\",\"metadata\":{\"seq\":%lu,\"is_buffered\":%s}}",
           PATIENT_ID, DEVICE_ID, sensorType, samplingRate, valuesBuf, batteryPct,
           FIRMWARE_VERSION, seq, isBuffered ? "true" : "false");

  bleCharacteristic->setValue((uint8_t *)payload, strlen(payload));
  bleCharacteristic->notify();
}

void sendSample(const Sample &s, bool isBuffered) {
  float ppgValues[2] = {s.hr, s.spo2};
  sendPacket("PPG", 1, ppgValues, 2, s.battery, s.seq, isBuffered);
  delay(15);
  float imuValues[1] = {s.motion};
  sendPacket("IMU", 1, imuValues, 1, s.battery, s.seq, isBuffered);
  delay(15);
  float tempValues[1] = {s.temp};
  sendPacket("TEMPERATURE", 1, tempValues, 1, s.battery, s.seq, isBuffered);
}

void flushBufferIfConnected() {
  if (!bleConnected || bufferCount == 0) return;
  for (int i = 0; i < bufferCount; i++) {
    sendSample(buffer[i], /*isBuffered=*/true);
    delay(20);  // small gap so notifications don't overrun the BLE stack
  }
  bufferCount = 0;
}

// ---- Setup / loop -------------------------------------------------------
void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  analogReadResolution(12);

  if (!HrSpo2::begin()) Serial.println("MAX30102 not detected");
  if (!Max30205::begin()) Serial.println("MAX30205 not detected");
  if (!Mpu6050::begin()) Serial.println("MPU6050 not detected");

  BLEDevice::init(DEVICE_ID);
  bleServer = BLEDevice::createServer();
  bleServer->setCallbacks(new ServerCallbacks());

  BLEService *service = bleServer->createService(SERVICE_UUID);
  bleCharacteristic = service->createCharacteristic(
      CHARACTERISTIC_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  bleCharacteristic->addDescriptor(new BLE2902());
  service->start();

  bleServer->getAdvertising()->start();
  Serial.println("SENTRA patient node advertising over BLE");
}

unsigned long lastSampleMs = 0;
float lastBpm = 0, lastSpo2 = 0;

void loop() {
  float accelMag = Mpu6050::readAccelMagnitudeG();
  if (!isnan(accelMag)) Mpu6050::pushSample(accelMag);

  float bpm, spo2;
  if (HrSpo2::poll(bpm, spo2)) {
    lastBpm = bpm;
    lastSpo2 = spo2;
  }

  if (millis() - lastSampleMs >= 1000) {
    lastSampleMs = millis();

    float temp = Max30205::readCelsius();
    float motion = isnan(accelMag) ? 0.0f : Mpu6050::motionMetric(accelMag);
    bool sensorsOk = !isnan(temp) && !isnan(accelMag) && lastBpm > 0;

    Sample s{sequenceNumber++, lastBpm, lastSpo2, temp, motion, readBatteryPercent()};
    updateLocalAlert(lastBpm, isnan(accelMag) ? 1.0f : accelMag, sensorsOk);

    if (bleConnected) {
      flushBufferIfConnected();  // catch up on anything from a prior disconnect
      sendSample(s, /*isBuffered=*/false);
    } else {
      bufferSample(s);  // graceful degradation: keep sampling, sync later
    }
  }
}
