#pragma once
#include <MAX30105.h>  // SparkFun MAX3010x Pulse and Proximity Sensor Library
#include <math.h>

// MAX30102 pulse oximeter - heart rate + pulse waveform + SpO2 (Doc 03 §3,
// mapped to the PPG sensor type — see docs/HARDWARE_SCOPE.md). FIFO access
// comes from the SparkFun library; beat detection and the SpO2 estimate
// below are our own on top of the raw IR/Red samples it provides.
namespace HrSpo2 {

MAX30105 particleSensor;

constexpr int RATE_SAMPLES = 4;      // beats averaged for a stable BPM reading
float rateHistory[RATE_SAMPLES] = {0};
int rateIdx = 0;
unsigned long lastBeatMs = 0;

// Simple DC-tracking low-pass so beat detection works on the AC component
// without needing an external DSP library.
float irDcEstimate = 0;
bool irDcInitialized = false;
bool aboveBaseline = false;

inline bool begin() {
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) return false;
  particleSensor.setup(/*power*/ 0x1F, /*avg*/ 4, /*mode*/ 2 /*red+IR*/,
                        /*sampleRate*/ 100, /*pulseWidth*/ 411, /*adcRange*/ 4096);
  return true;
}

// Call every loop iteration. Returns true and fills bpm/spo2 when a new
// beat was detected (values stay at the last known average otherwise).
inline bool poll(float &bpmOut, float &spo2Out) {
  long irValue = particleSensor.getIR();
  long redValue = particleSensor.getRed();

  if (irValue < 5000) {
    // No finger/skin contact - nothing meaningful to report.
    return false;
  }

  if (!irDcInitialized) {
    irDcEstimate = irValue;
    irDcInitialized = true;
  } else {
    irDcEstimate = irDcEstimate * 0.95f + irValue * 0.05f;  // slow-moving baseline
  }

  bool nowAbove = irValue > irDcEstimate;
  bool beatDetected = false;

  // Rising edge through the DC baseline, with a refractory period so one
  // pulse waveform doesn't get counted twice.
  if (nowAbove && !aboveBaseline) {
    unsigned long nowMs = millis();
    unsigned long delta = nowMs - lastBeatMs;
    if (delta > 300 && delta < 2000) {  // 30-200 bpm plausible range
      float instantBpm = 60000.0f / delta;
      rateHistory[rateIdx] = instantBpm;
      rateIdx = (rateIdx + 1) % RATE_SAMPLES;
      beatDetected = true;
    }
    lastBeatMs = nowMs;
  }
  aboveBaseline = nowAbove;

  if (beatDetected) {
    float sum = 0;
    for (float v : rateHistory) sum += v;
    bpmOut = sum / RATE_SAMPLES;

    // Ratio-of-ratios approximation (R = (redAC/redDC)/(irAC/irDC),
    // SpO2 ~ 110 - 25*R). Widely-used rough estimate for a prototype, NOT a
    // calibrated clinical SpO2 reading — real calibration needs an
    // empirical lookup table per the datasheet (see firmware/README.md).
    float irAc = fabsf((float)irValue - irDcEstimate);
    float redAc = fabsf((float)redValue - irDcEstimate);
    float r = (irDcEstimate > 0) ? (redAc / irDcEstimate) / (irAc / irDcEstimate + 1e-6f) : 1.0f;
    spo2Out = constrain(110.0f - 25.0f * r, 70.0f, 100.0f);
    return true;
  }
  return false;
}

}  // namespace HrSpo2
