// ARIA arm sensor node — ESP32 firmware.
//
// Worn as a sleeve-and-glove harness. Placement (see docs/HARDWARE_DESIGN.md):
//   - PPG heart rate    upper-arm band over the brachial artery
//   - IMU (MPU6050)     same band; tells the firmware when the arm is moving
//   - Skin temperature  forearm, just proximal to the radial artery
//   - EDA (Grove GSR)   palm / fingers (distal)
//
// Once a second it POSTs whatever it can trust to the laptop running
//   python -m rehab_vr.sensor_service.server --hardware
// A channel that is not currently trustworthy is OMITTED from the message and
// the service treats it as "no reading". This firmware never sends a made-up
// resting value to fill a gap. Heart rate in particular is omitted whenever
// the arm is moving, the sensor has no contact, or the pulse is not clearly
// periodic.
//
// Choose the parts you actually have with the switches just below.
//
// STATUS: the signal-processing headers are unit tested on a PC against
// synthetic signals (test/). This sketch itself has only been syntax-checked
// against stub headers. It has not run on hardware, and the thresholds in
// makePpgConfig() are starting points to tune from a real recording.
//
// Before uploading, copy wifi_config.example.h to wifi_config.h and fill it in.

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>

#include "wifi_config.h"

// ------------------------------------------------------------ build options
#ifndef PPG_SOURCE_MAX3010X
#define PPG_SOURCE_MAX3010X 1   // 1 = MAX30102/MAX30101 breakout (I2C), 0 = simple analog pulse sensor
#endif
#ifndef ENABLE_IMU
#define ENABLE_IMU 1            // MPU6050 on the band. Without it PPG cannot be motion-gated.
#endif
#ifndef ENABLE_ECG_REFERENCE
#define ENABLE_ECG_REFERENCE 0  // 1 = AD8232 bench reference; logs PPG-vs-ECG lines (see README). NEVER on mains USB.
#endif
#ifndef STREAM_RAW_PPG
#define STREAM_RAW_PPG 0        // 1 = print the raw PPG at 100 Hz for the Serial Plotter (bring-up)
#endif

#if PPG_SOURCE_MAX3010X
#include <MAX30105.h>  // SparkFun MAX3010x library; also drives the MAX30102 and MAX30101
#endif

#include "ecg_reference.h"
#include "eda.h"
#include "max30205.h"
#include "motion_gate.h"
#include "mpu6050.h"
#include "payload.h"
#include "ppg_heart_rate.h"

// --------------------------------------------------------------------- pins
// ADC1 pins only: ADC2 stops working while WiFi is on.
constexpr int kGsrPin = 34;        // Grove GSR signal
constexpr int kPpgAnalogPin = 35;  // simple analog pulse sensor signal (PPG_SOURCE_MAX3010X 0)
constexpr int kEcgOutPin = 36;     // AD8232 OUTPUT
constexpr int kEcgLoPlusPin = 32;  // AD8232 LO+
constexpr int kEcgLoMinusPin = 33; // AD8232 LO-
// I2C (default pins): SDA = GPIO21, SCL = GPIO22.
//   MAX30102 0x57, MAX30205 0x48, MPU6050 0x68 — no address clashes.

// ------------------------------------------------------------------- timing
constexpr float kPpgRateHz = 100.0f;
constexpr uint32_t kPpgPeriodUs = 10000;
constexpr uint32_t kImuPeriodMs = 20;    // 50 Hz
constexpr uint32_t kEcgPeriodUs = 4000;  // 250 Hz
constexpr uint32_t kReportPeriodMs = 1000;

// ------------------------------------------------------------------ objects
aria::PpgConfig makePpgConfig() {
  aria::PpgConfig c;
  c.sampleRateHz = kPpgRateHz;
#if PPG_SOURCE_MAX3010X
  c.contactMinRaw = 3000;  // raw level below which nothing is in front of the sensor. TUNE.
  c.minRms = 15.0f;        // 18-bit counts. TUNE from a recording on the upper arm.
#else
  c.contactMinRaw = 0;     // an analog sensor has no absolute "no contact" level
  c.minRms = 5.0f;         // 12-bit ADC counts. TUNE from a recording.
#endif
  return c;
}

aria::PpgHeartRate ppg(makePpgConfig());
aria::MotionGate motionGate;
aria::Mpu6050 mpu;
aria::EcgRPeakRate ecg;
#if PPG_SOURCE_MAX3010X
MAX30105 particleSensor;
#endif

struct Reading {
  float edaUs;
  float heartRateBpm;
  float skinTempC;
};
QueueHandle_t readingQueue = nullptr;

uint32_t nextPpgUs = 0;
uint32_t nextEcgUs = 0;
uint32_t lastImuMs = 0;
uint32_t lastReportMs = 0;
bool ppgReady = false;
bool tempReady = false;

// ------------------------------------------------------------------ helpers
bool motionOkNow() {
#if ENABLE_IMU
  return motionGate.ok();
#else
  return true;  // no IMU: cannot vouch for stillness, see the boot warning
#endif
}

void formatBpm(char* out, size_t n, float v) {
  if (isfinite(v)) snprintf(out, n, "%.1f", v);
  else snprintf(out, n, "nan");
}

// ------------------------------------------------------------ WiFi + posting
void ensureWifi(uint32_t timeoutMs) {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeoutMs) delay(250);
}

// Runs on core 0 so a slow network can never stall the 100 Hz sampling on
// core 1. The queue holds only the newest reading; if posting falls behind,
// old readings are dropped, not queued up.
void postTask(void*) {
  Reading r;
  for (;;) {
    if (xQueueReceive(readingQueue, &r, portMAX_DELAY) != pdTRUE) continue;
    ensureWifi(5000);
    if (WiFi.status() != WL_CONNECTED) continue;

    char body[128];
    if (!aria::buildPayload(body, sizeof body, r.edaUs, r.heartRateBpm, r.skinTempC)) continue;

    HTTPClient http;
    http.setConnectTimeout(1500);
    http.setTimeout(1500);
    http.begin(String("http://") + INGEST_HOST + ":" + String(INGEST_PORT) + "/ingest");
    http.addHeader("Content-Type", "application/json");
    const int status = http.POST(reinterpret_cast<uint8_t*>(body), strlen(body));
    if (status != 204) {
      Serial.printf("POST problem: %d (%s)\n", status, status <= 0 ? http.errorToString(status).c_str() : "server rejected");
    }
    http.end();
  }
}

// -------------------------------------------------------------- PPG sampling
#if PPG_SOURCE_MAX3010X
bool initPpg() {
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) return false;
  const byte ledPower = 0x5F;  // roughly 19 mA. Raise until the raw IR sits mid-scale without clipping.
  particleSensor.setup(ledPower, /*sampleAverage*/ 1, /*ledMode: red+IR*/ 2, /*rate*/ 100, /*pulseWidth*/ 411,
                       /*adcRange*/ 16384);
  particleSensor.setPulseAmplitudeRed(0);  // heart rate only needs IR
  particleSensor.setPulseAmplitudeGreen(0);
  return true;
}

// The sensor's own FIFO delivers samples at exactly 100/s, so each drained
// sample is timestamped back from "now" instead of all sharing one instant.
void samplePpg(uint32_t nowMs, uint32_t /*nowUs*/) {
  if (!ppgReady) return;
  particleSensor.check();
  const int n = particleSensor.available();
  const bool ok = motionOkNow();
  for (int i = 0; i < n; i++) {
    const uint32_t t = nowMs - static_cast<uint32_t>((n - 1 - i) * (kPpgPeriodUs / 1000));
    const uint32_t ir = particleSensor.getFIFOIR();
    ppg.push(ir, t, ok);
#if STREAM_RAW_PPG
    Serial.println(ir);
#endif
    particleSensor.nextSample();
  }
}
#else
bool initPpg() {
  pinMode(kPpgAnalogPin, INPUT);
  analogSetPinAttenuation(kPpgAnalogPin, ADC_11db);
  nextPpgUs = micros();
  return true;
}

// The ESP32 ADC is noisy, so each sample is the mean of 4 reads.
void samplePpg(uint32_t nowMs, uint32_t nowUs) {
  if (!ppgReady) return;
  if (static_cast<int32_t>(nowUs - nextPpgUs) < 0) return;
  nextPpgUs += kPpgPeriodUs;
  if (static_cast<int32_t>(nowUs - nextPpgUs) > static_cast<int32_t>(3 * kPpgPeriodUs)) nextPpgUs = nowUs + kPpgPeriodUs;  // fell behind, resync

  uint32_t sum = 0;
  for (int i = 0; i < 4; i++) sum += analogRead(kPpgAnalogPin);
  const uint32_t raw = sum / 4;
  ppg.push(raw, nowMs, motionOkNow());
#if STREAM_RAW_PPG
  Serial.println(raw);
#endif
}
#endif

// ------------------------------------------------------------- ECG reference
#if ENABLE_ECG_REFERENCE
void sampleEcg(uint32_t nowMs, uint32_t nowUs) {
  if (static_cast<int32_t>(nowUs - nextEcgUs) < 0) return;
  nextEcgUs += kEcgPeriodUs;
  const bool leadsOff = digitalRead(kEcgLoPlusPin) == HIGH || digitalRead(kEcgLoMinusPin) == HIGH;
  ecg.push(static_cast<float>(analogRead(kEcgOutPin)), nowMs, leadsOff);
}
#endif

// ------------------------------------------------------------------ sensors
// The Grove GSR conversion assumes a 10-bit reading; the ESP32 ADC is 12-bit,
// so the mean is divided by 4 rather than changing the global ADC resolution
// (which would also rescale the PPG and ECG pins).
float readEdaMicrosiemens() {
  uint32_t sum = 0;
  constexpr int kReads = 16;
  for (int i = 0; i < kReads; i++) {
    sum += analogRead(kGsrPin);
    delayMicroseconds(200);
  }
  return aria::edaMicrosiemens((static_cast<float>(sum) / kReads) / 4.0f);
}

float readSkinTempC() { return tempReady ? aria::max30205ReadSkinCelsius() : NAN; }

void report(uint32_t nowMs) {
  const float hr = ppg.hasValidBpm(nowMs) ? ppg.bpm() : NAN;
  const Reading r{readEdaMicrosiemens(), hr, readSkinTempC()};
  xQueueOverwrite(readingQueue, &r);

  char hrText[16];
  formatBpm(hrText, sizeof hrText, r.heartRateBpm);
  Serial.printf("EDA=%.2f uS  HR=%s bpm  Temp=%.1f C  quality=%.2f  motionOk=%d\n", r.edaUs, hrText, r.skinTempC,
                ppg.quality(), motionOkNow() ? 1 : 0);

#if ENABLE_ECG_REFERENCE
  char ecgText[16];
  formatBpm(ecgText, sizeof ecgText, ecg.hasValidBpm(nowMs) ? ecg.bpm() : NAN);
  // One CSV line per second for tools/compare_hr.py: time, PPG bpm, PPG quality, ECG bpm, motionOk
  Serial.printf("CMP,%lu,%s,%.3f,%s,%d\n", static_cast<unsigned long>(nowMs), hrText, ppg.quality(), ecgText,
                motionOkNow() ? 1 : 0);
#endif
}

// --------------------------------------------------------------- setup/loop
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("ARIA arm sensor node starting");

  analogSetPinAttenuation(kGsrPin, ADC_11db);
#if ENABLE_ECG_REFERENCE
  pinMode(kEcgLoPlusPin, INPUT);
  pinMode(kEcgLoMinusPin, INPUT);
  analogSetPinAttenuation(kEcgOutPin, ADC_11db);
  Serial.println("ECG reference ON: run from a battery, not mains-powered USB, while electrodes are on skin.");
#endif

  Wire.begin();
  Wire.setClock(400000);

  ppgReady = initPpg();
  Serial.println(ppgReady ? "PPG sensor ready" : "PPG sensor FAILED. Check wiring; heart rate will be omitted.");

  tempReady = aria::max30205Begin();
  Serial.println(tempReady ? "Temperature sensor ready" : "Temperature sensor FAILED. Temp will be omitted.");

#if ENABLE_IMU
  if (mpu.begin()) Serial.println("IMU ready");
  else Serial.println("IMU FAILED. Heart rate will be omitted (cannot confirm the arm is still).");
#else
  Serial.println("WARNING: IMU disabled. PPG is NOT motion-gated; heart rate during movement is unreliable.");
#endif

  readingQueue = xQueueCreate(1, sizeof(Reading));
  ensureWifi(20000);
  Serial.println(WiFi.status() == WL_CONNECTED ? "WiFi connected" : "WiFi not connected yet, will keep retrying");
  xTaskCreatePinnedToCore(postTask, "aria-post", 6144, nullptr, 1, nullptr, 0);

  nextPpgUs = micros();
  nextEcgUs = micros();
}

void loop() {
  const uint32_t nowMs = millis();
  const uint32_t nowUs = micros();

#if ENABLE_IMU
  if (nowMs - lastImuMs >= kImuPeriodMs) {
    lastImuMs = nowMs;
    motionGate.push(mpu.readAccelMagnitudeG());
  }
#endif

  samplePpg(nowMs, nowUs);
#if ENABLE_ECG_REFERENCE
  sampleEcg(nowMs, nowUs);
#endif

  if (nowMs - lastReportMs >= kReportPeriodMs) {
    lastReportMs = nowMs;
    report(nowMs);
  }
}
