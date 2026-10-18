// Host-side tests for the portable firmware headers. No Arduino, no hardware.
//
// Build and run (any C++17 compiler):
//   g++ -std=c++17 -O1 -Wall -Wextra -I.. test_firmware.cpp -o test_firmware && ./test_firmware
//
// These prove the LOGIC against synthetic signals: correct rate on clean
// pulses, no reading without a pulse, no reading during motion, recovery
// afterwards, and no bad numbers reported along the way. They do NOT prove
// the detector works on a real arm; that needs a recording from the band
// (see README bring-up).
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "eda.h"
#include "max30205.h"
#include "motion_gate.h"
#include "payload.h"
#include "ecg_reference.h"
#include "ppg_heart_rate.h"

using namespace aria;

static int g_checks = 0;
static int g_failures = 0;
#define CHECK(cond, ...)                                       \
  do {                                                         \
    g_checks++;                                                \
    if (!(cond)) {                                             \
      g_failures++;                                            \
      printf("  FAIL line %d: %s\n        ", __LINE__, #cond);  \
      printf(__VA_ARGS__);                                     \
      printf("\n");                                            \
    }                                                          \
  } while (0)

static const double kPi = 3.14159265358979323846;

// ---------------------------------------------------------- synthetic PPG ---
struct Rng {
  uint32_t s = 12345;
  float uni() {
    s = s * 1664525u + 1013904223u;
    return (s >> 8) / 16777216.0f;
  }
  float gauss() {  // approx N(0,1)
    float a = 0;
    for (int i = 0; i < 12; i++) a += uni();
    return a - 6.0f;
  }
};

static double bump(double x, double center, double width) {
  const double d = (x - center) / width;
  return exp(-d * d);
}

// One beat: a main systolic peak plus a smaller dicrotic bump, like a real
// pulse waveform (the small bump must not be mistaken for a second beat).
static double pulseShape(double phase) { return bump(phase, 0.25, 0.09) + 0.3 * bump(phase, 0.58, 0.07); }

struct Sim {
  double phase = 0;
  double t = 0;
  Rng rng;
  float dc = 50000, amp = 300, noise = 30, wander = 0, wanderHz = 0.2f;
  // Advances 10 ms (100 samples/s) at the given heart rate.
  uint32_t next(double bpm) {
    phase += 0.01 * bpm / 60.0;
    if (phase >= 1.0) phase -= 1.0;
    double v = dc + amp * pulseShape(phase) + wander * amp * sin(2 * kPi * wanderHz * t) + noise * rng.gauss();
    t += 0.01;
    if (v < 0) v = 0;
    return static_cast<uint32_t>(v);
  }
};

struct Audit {
  int validCount = 0;
  int badCount = 0;  // valid readings that were wrong by more than tol
  float worstErr = 0;
};

static void audit(Audit& a, const PpgHeartRate& det, uint32_t now, double expected, float tol) {
  if (!det.hasValidBpm(now)) return;
  a.validCount++;
  const float err = fabsf(det.bpm() - static_cast<float>(expected));
  if (err > a.worstErr) a.worstErr = err;
  if (err > tol) a.badCount++;
}

// ------------------------------------------------------------- PPG tests ---
static void testCleanRates() {
  printf("PPG: correct rate across 45-180 bpm\n");
  const double rates[] = {45, 60, 72, 90, 120, 150, 180};
  for (double bpm : rates) {
    PpgHeartRate det;
    Sim sim;
    uint32_t now = 1000;
    for (int i = 0; i < 3000; i++, now += 10) det.push(sim.next(bpm), now, true);
    CHECK(det.hasValidBpm(now), "no valid reading at %.0f bpm (quality %.2f)", bpm, det.quality());
    CHECK(fabsf(det.bpm() - static_cast<float>(bpm)) <= 3.0f, "at %.0f bpm reported %.1f", bpm, det.bpm());
  }
}

static void testPolarityAndScale() {
  printf("PPG: inverted polarity and a small-amplitude analog-style sensor\n");
  {  // pulse points DOWN (some sensors are inverted)
    PpgHeartRate det;
    Sim sim;
    sim.amp = -300;
    uint32_t now = 1000;
    for (int i = 0; i < 3000; i++, now += 10) det.push(sim.next(72), now, true);
    CHECK(det.hasValidBpm(now), "inverted sensor gave no reading");
    CHECK(fabsf(det.bpm() - 72.0f) <= 3.0f, "inverted sensor reported %.1f", det.bpm());
  }
  {  // 12-bit ADC-like: DC ~2048, pulse ~40 counts, ADC noise ~6
    PpgHeartRate det;
    Sim sim;
    sim.dc = 2048;
    sim.amp = 40;
    sim.noise = 6;
    uint32_t now = 1000;
    for (int i = 0; i < 3000; i++, now += 10) det.push(sim.next(72), now, true);
    CHECK(det.hasValidBpm(now), "analog-style sensor gave no reading (quality %.2f)", det.quality());
    CHECK(fabsf(det.bpm() - 72.0f) <= 3.0f, "analog-style sensor reported %.1f", det.bpm());
  }
}

static void testBaselineWander() {
  printf("PPG: breathing-like baseline wander at half the pulse amplitude\n");
  PpgHeartRate det;
  Sim sim;
  sim.wander = 0.5f;
  Audit a;
  uint32_t now = 1000;
  for (int i = 0; i < 3000; i++, now += 10) {
    det.push(sim.next(72), now, true);
    audit(a, det, now, 72, 4.0f);
  }
  CHECK(det.hasValidBpm(now), "lost lock under wander");
  CHECK(a.badCount == 0, "%d wrong readings, worst error %.1f bpm", a.badCount, a.worstErr);
}

static void testNoPulseNoReading() {
  printf("PPG: no pulse means no reading (noise only, DC only, weak pulse)\n");
  const float noises[] = {30.0f, 100.0f, 400.0f};
  for (float sigma : noises) {
    PpgHeartRate det;
    Sim sim;
    sim.amp = 0;
    sim.noise = sigma;
    int valid = 0;
    uint32_t now = 1000;
    for (int i = 0; i < 6000; i++, now += 10) {
      det.push(sim.next(72), now, true);
      if (det.hasValidBpm(now)) valid++;
    }
    CHECK(valid == 0, "noise sigma %.0f produced %d valid samples", sigma, valid);
  }
  {
    PpgHeartRate det;
    Sim sim;
    sim.amp = 0;
    sim.noise = 0;
    uint32_t now = 1000;
    int valid = 0;
    for (int i = 0; i < 3000; i++, now += 10) {
      det.push(sim.next(72), now, true);
      if (det.hasValidBpm(now)) valid++;
    }
    CHECK(valid == 0, "flat DC produced a reading");
  }
  {
    PpgHeartRate det;
    Sim sim;
    sim.amp = 10;  // pulse smaller than minRms
    sim.noise = 3;
    uint32_t now = 1000;
    int valid = 0;
    for (int i = 0; i < 3000; i++, now += 10) {
      det.push(sim.next(72), now, true);
      if (det.hasValidBpm(now)) valid++;
    }
    CHECK(valid == 0, "sub-threshold pulse produced a reading");
  }
}

static void testNotOnSkin() {
  printf("PPG: never reports without skin contact; recovers when contact returns\n");
  PpgConfig cfg;
  cfg.contactMinRaw = 3000;  // a MAX3010x-style sensor with a raw-level contact check
  PpgHeartRate det(cfg);
  Sim sim;
  uint32_t now = 1000;
  for (int i = 0; i < 500; i++, now += 10) det.push(100, now, true);  // unworn
  CHECK(!det.hasValidBpm(now), "reading while unworn");
  CHECK(!det.onSkin(), "onSkin true while unworn");

  for (int i = 0; i < 1500; i++, now += 10) det.push(sim.next(72), now, true);
  CHECK(det.hasValidBpm(now), "did not lock after putting the band on");

  for (int i = 0; i < 200; i++, now += 10) det.push(0, now, true);  // lifted for 2 s
  CHECK(!det.hasValidBpm(now), "reading right after contact loss");

  for (int i = 0; i < 1500; i++, now += 10) det.push(sim.next(72), now, true);
  CHECK(det.hasValidBpm(now), "did not recover after contact returned");
  CHECK(fabsf(det.bpm() - 72.0f) <= 3.0f, "bpm %.1f after recovery", det.bpm());
}

static void testMotion() {
  printf("PPG: no reading during or just after motion, recovers, never reports a wrong value\n");
  PpgHeartRate det;
  Sim sim;
  Rng artifact;
  Audit a;
  uint32_t now = 1000;
  bool validBefore = false;
  bool invalidDuring = true;
  bool invalidInHoldoff = true;
  bool recovered = false;
  for (int i = 0; i < 3000; i++, now += 10) {
    const double t = i * 0.01;
    const bool moving = t >= 10.0 && t < 11.0;
    uint32_t ir = sim.next(72);
    if (moving) {
      const double junk = 3000.0 * artifact.gauss();
      const double v = static_cast<double>(ir) + junk;
      ir = static_cast<uint32_t>(v < 0 ? 0 : v);
    }
    det.push(ir, now, !moving);
    audit(a, det, now, 72, 6.0f);
    if (i == 990) validBefore = det.hasValidBpm(now);
    if (moving && det.hasValidBpm(now)) invalidDuring = false;
    if (t >= 11.0 && t < 12.4 && det.hasValidBpm(now)) invalidInHoldoff = false;
    if (t > 26.0) recovered = det.hasValidBpm(now);
  }
  CHECK(validBefore, "no lock before the motion burst");
  CHECK(invalidDuring, "reported a heart rate DURING motion");
  CHECK(invalidInHoldoff, "reported a heart rate inside the holdoff after motion");
  CHECK(recovered, "did not recover after motion");
  CHECK(a.badCount == 0, "%d wrong readings reported, worst error %.1f bpm", a.badCount, a.worstErr);
}

static void testSingleSampleSpike() {
  printf("PPG: a one-sample glitch never yields a wrong rate, and it recovers\n");
  PpgHeartRate det;
  Sim sim;
  Audit a;
  uint32_t now = 1000;
  for (int i = 0; i < 3000; i++, now += 10) {
    uint32_t ir = sim.next(72);
    if (i == 1234) ir += 40000;
    det.push(ir, now, true);
    if (i > 1200) audit(a, det, now, 72, 6.0f);
  }
  CHECK(det.hasValidBpm(now), "did not recover after a glitch");
  CHECK(a.badCount == 0, "%d wrong readings after glitch, worst %.1f bpm", a.badCount, a.worstErr);
}

static void testRateChange() {
  printf("PPG: follows a real rate change (60 -> 100 bpm) without reporting nonsense\n");
  PpgHeartRate det;
  Sim sim;
  uint32_t now = 1000;
  float lo = 1000, hi = 0;
  for (int i = 0; i < 4000; i++, now += 10) {
    const double bpm = i < 1500 ? 60.0 : 100.0;
    det.push(sim.next(bpm), now, true);
    if (det.hasValidBpm(now)) {
      if (det.bpm() < lo) lo = det.bpm();
      if (det.bpm() > hi) hi = det.bpm();
    }
  }
  CHECK(det.hasValidBpm(now), "no lock after the rate change");
  CHECK(fabsf(det.bpm() - 100.0f) <= 4.0f, "final %.1f", det.bpm());
  CHECK(lo >= 55.0f && hi <= 105.0f, "reported outside the true range: min %.1f max %.1f", lo, hi);
}

static void testClockWraparound() {
  printf("PPG: works across the 32-bit millisecond clock wrap\n");
  PpgHeartRate det;
  Sim sim;
  uint32_t now = 0xFFFFFFFFu - 5000u;
  for (int i = 0; i < 3000; i++, now += 10) det.push(sim.next(72), now, true);
  CHECK(det.hasValidBpm(now), "no lock across wraparound");
  CHECK(fabsf(det.bpm() - 72.0f) <= 3.0f, "bpm %.1f across wraparound", det.bpm());
}

static void testStaleness() {
  printf("PPG: a reading goes away when the pulse stops\n");
  PpgHeartRate det;
  Sim sim;
  uint32_t now = 1000;
  for (int i = 0; i < 3000; i++, now += 10) det.push(sim.next(72), now, true);
  CHECK(det.hasValidBpm(now), "no lock");
  for (int i = 0; i < 700; i++, now += 10) det.push(50000, now, true);  // contact kept, pulse gone, 7 s
  CHECK(!det.hasValidBpm(now), "still reporting 7 s after the pulse vanished");
}

// ------------------------------------------------------------- ECG tests ---
static double ecgShape(double phase) {
  return 800.0 * bump(phase, 0.30, 0.012) + 200.0 * bump(phase, 0.55, 0.05) + 60.0 * bump(phase, 0.20, 0.03);
}

struct EcgSim {
  double phase = 0, t = 0;
  Rng rng;
  float dc = 2000, noise = 20, hum = 40, wander = 0;
  // Advances 4 ms (250 samples/s).
  float next(double bpm) {
    phase += (1.0 / 250.0) * bpm / 60.0;
    if (phase >= 1.0) phase -= 1.0;
    const double v = dc + ecgShape(phase) + hum * sin(2 * kPi * 50.0 * t) + wander * sin(2 * kPi * 0.3 * t) +
                     noise * rng.gauss();
    t += 1.0 / 250.0;
    return static_cast<float>(v);
  }
};

static void testEcgRates() {
  printf("ECG reference: R-peak rate across 45-180 bpm, with mains hum and baseline wander\n");
  const double rates[] = {45, 72, 100, 150, 180};
  for (double bpm : rates) {
    EcgRPeakRate det;
    EcgSim sim;
    sim.wander = 300;
    uint32_t now = 1000;
    for (int i = 0; i < 250 * 25; i++, now += 4) det.push(sim.next(bpm), now, false);
    CHECK(det.hasValidBpm(now), "no ECG reading at %.0f bpm", bpm);
    CHECK(fabsf(det.bpm() - static_cast<float>(bpm)) <= 2.0f, "ECG at %.0f bpm reported %.1f", bpm, det.bpm());
  }
}

static void testEcgLeadsOffAndNoise() {
  printf("ECG reference: leads-off and noise never produce a rate\n");
  EcgRPeakRate det;
  EcgSim sim;
  uint32_t now = 1000;
  for (int i = 0; i < 250 * 12; i++, now += 4) det.push(sim.next(72), now, false);
  CHECK(det.hasValidBpm(now), "no lock");
  for (int i = 0; i < 250; i++, now += 4) det.push(sim.next(72), now, true);  // electrode off
  CHECK(!det.hasValidBpm(now), "reading with leads off");
  for (int i = 0; i < 250 * 12; i++, now += 4) det.push(sim.next(72), now, false);
  CHECK(det.hasValidBpm(now), "did not recover after leads restored");

  EcgRPeakRate quiet;
  Rng rng;
  int valid = 0;
  now = 1000;
  for (int i = 0; i < 250 * 30; i++, now += 4) {
    quiet.push(2000.0f + 20.0f * rng.gauss(), now, false);
    if (quiet.hasValidBpm(now)) valid++;
  }
  CHECK(valid == 0, "noise with no R waves gave %d valid samples", valid);
}

static void testPpgAgreesWithEcgReference() {
  printf("Reference comparison: arm PPG vs ECG on the same simulated heart\n");
  PpgHeartRate ppg;
  EcgRPeakRate ecg;
  Sim ppgSim;
  EcgSim ecgSim;
  const double bpm = 84;
  uint32_t nowMs = 1000;
  float worst = 0;
  int compared = 0;
  // Common tick of 20 ms: five ECG samples (4 ms) and two PPG samples (10 ms).
  for (int step = 0; step < 30000 / 20; step++) {
    for (int k = 0; k < 5; k++) ecg.push(ecgSim.next(bpm), nowMs + 4 * k, false);
    for (int k = 0; k < 2; k++) ppg.push(ppgSim.next(bpm), nowMs + 10 * k, true);
    nowMs += 20;
    if (ppg.hasValidBpm(nowMs) && ecg.hasValidBpm(nowMs)) {
      compared++;
      const float diff = fabsf(ppg.bpm() - ecg.bpm());
      if (diff > worst) worst = diff;
    }
  }
  CHECK(compared > 100, "too few simultaneous readings to compare (%d)", compared);
  CHECK(worst <= 3.0f, "PPG and ECG disagreed by up to %.1f bpm", worst);
}

// ------------------------------------------------------------ other tests ---
static void testMotionGate() {
  printf("MotionGate\n");
  {
    MotionGate g;
    CHECK(!g.ok(), "must start not-ok until it has seen a still arm");
    for (int i = 0; i < 60; i++) g.push(1.0f + ((i % 2) ? 0.01f : -0.01f));
    CHECK(g.ok(), "still arm not ok");
  }
  {
    MotionGate g;
    for (int i = 0; i < 60; i++) g.push(1.0f);
    g.push(1.5f);
    CHECK(!g.ok(), "burst not detected");
    for (int i = 0; i < 30; i++) g.push(1.0f);
    CHECK(!g.ok(), "declared ok too soon after a burst");
    for (int i = 0; i < 100; i++) g.push(1.0f);
    CHECK(g.ok(), "never recovered after a burst");
  }
  {
    MotionGate g;
    for (int i = 0; i < 100; i++) g.push(1.0f + 0.05f * ((i % 2) ? 1 : -1));
    CHECK(g.ok(), "small tremor treated as motion");
  }
  {
    MotionGate g;
    for (int i = 0; i < 100; i++) g.push(1.0f);
    g.push(NAN);
    CHECK(!g.ok(), "a failed IMU read must count as motion");
    g.push(-1.0f);
    CHECK(!g.ok(), "negative (error code) must count as motion");
  }
}

static void testEda() {
  printf("EDA conversion\n");
  CHECK(isnan(edaMicrosiemens(0.0f)), "0 is a rail, should be NaN");
  CHECK(isnan(edaMicrosiemens(1.0f)), "1 is a rail, should be NaN");
  CHECK(isnan(edaMicrosiemens(510.0f)), "510 is out of range");
  CHECK(isnan(edaMicrosiemens(512.0f)), "512 divides by zero");
  CHECK(isnan(edaMicrosiemens(900.0f)), "900 gives negative resistance");
  CHECK(isnan(edaMicrosiemens(NAN)), "NaN in must be NaN out");
  CHECK(!isnan(edaMicrosiemens(509.0f)), "509 should be valid");
  CHECK(fabsf(edaMicrosiemens(400.0f) - 6.14f) < 0.02f, "400 -> %.3f (expected ~6.14 uS)", edaMicrosiemens(400.0f));
  // More sweat = higher conductance = LOWER raw reading in this circuit.
  float prev = 1e9f;
  bool monotonic = true;
  for (int x = 2; x < 510; x += 4) {
    const float us = edaMicrosiemens(static_cast<float>(x));
    if (!(us < prev)) monotonic = false;
    prev = us;
  }
  CHECK(monotonic, "conductance should fall as the raw value rises");
}

static void testTemp() {
  printf("MAX30205 conversion\n");
  CHECK(fabsf(rawToCelsius(0x2180) - 33.5f) < 1e-4f, "0x2180 -> %.4f", rawToCelsius(0x2180));
  CHECK(fabsf(rawToCelsius(0x1E00) - 30.0f) < 1e-4f, "0x1E00 -> %.4f", rawToCelsius(0x1E00));
  CHECK(rawToCelsius(0xFF00) < 0.0f, "negative temps must be signed");
  CHECK(fabsf(skinTempOrNan(rawToCelsius(0x2180)) - 33.5f) < 1e-4f, "valid skin temp rejected");
  CHECK(isnan(skinTempOrNan(rawToCelsius(0x0000))), "0x0000 (dead bus) accepted");
  CHECK(isnan(skinTempOrNan(rawToCelsius(0xFFFF))), "0xFFFF (dead bus) accepted");
  CHECK(isnan(skinTempOrNan(80.0f)), "80 C accepted");
  CHECK(isnan(skinTempOrNan(NAN)), "NaN accepted");
}

static void testPayload() {
  printf("JSON payload\n");
  char buf[128];
  CHECK(buildPayload(buf, sizeof buf, 3.2f, 88.0f, 32.1f), "build failed");
  CHECK(strcmp(buf, "{\"eda_us\":3.200,\"heart_rate_bpm\":88.0,\"skin_temp_c\":32.10}") == 0, "got %s", buf);

  CHECK(buildPayload(buf, sizeof buf, 3.2f, NAN, 32.1f), "build failed");
  CHECK(strcmp(buf, "{\"eda_us\":3.200,\"skin_temp_c\":32.10}") == 0, "hr omitted: got %s", buf);

  CHECK(buildPayload(buf, sizeof buf, NAN, 72.5f, NAN), "build failed");
  CHECK(strcmp(buf, "{\"heart_rate_bpm\":72.5}") == 0, "hr only: got %s", buf);

  CHECK(buildPayload(buf, sizeof buf, NAN, NAN, NAN), "build failed");
  CHECK(strcmp(buf, "{}") == 0, "heartbeat: got %s", buf);

  CHECK(buildPayload(buf, sizeof buf, INFINITY, 72.5f, -INFINITY), "build failed");
  CHECK(strcmp(buf, "{\"heart_rate_bpm\":72.5}") == 0, "inf omitted: got %s", buf);

  // Exact-fit boundary and overflow safety.
  const char* full = "{\"eda_us\":3.200,\"heart_rate_bpm\":88.0,\"skin_temp_c\":32.10}";
  const size_t need = strlen(full) + 1;
  char tight[256];
  memset(tight, 0x5A, sizeof tight);
  CHECK(buildPayload(tight, need, 3.2f, 88.0f, 32.1f), "exact-fit buffer rejected");
  CHECK(strcmp(tight, full) == 0, "exact fit content wrong");
  CHECK((unsigned char)tight[need] == 0x5A, "wrote past the buffer");

  memset(tight, 0x5A, sizeof tight);
  CHECK(!buildPayload(tight, need - 1, 3.2f, 88.0f, 32.1f), "one-short buffer accepted");
  CHECK(tight[0] == '\0', "failed build must leave an empty string");
  CHECK((unsigned char)tight[need - 1] == 0x5A, "wrote past the buffer on failure");

  CHECK(!buildPayload(nullptr, 10, 1, 1, 1), "null buffer accepted");
  CHECK(!buildPayload(buf, 0, 1, 1, 1), "zero-length buffer accepted");
  CHECK(!buildPayload(buf, 2, NAN, NAN, NAN), "2-byte buffer cannot hold {}");
  CHECK(buildPayload(buf, 3, NAN, NAN, NAN), "3-byte buffer holds {}");
}

int main() {
  testCleanRates();
  testPolarityAndScale();
  testBaselineWander();
  testNoPulseNoReading();
  testNotOnSkin();
  testMotion();
  testSingleSampleSpike();
  testRateChange();
  testClockWraparound();
  testStaleness();
  testEcgRates();
  testEcgLeadsOffAndNoise();
  testPpgAgreesWithEcgReference();
  testMotionGate();
  testEda();
  testTemp();
  testPayload();
  printf("\n%d checks, %d failed\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
