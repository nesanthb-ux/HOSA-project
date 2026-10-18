// Heart rate from a raw reflectance-PPG stream (upper-arm band over the
// brachial artery). Works with ANY PPG source that gives a steady sample
// stream: a MAX30102/MAX30101 raw IR FIFO, or a simple analog pulse sensor
// read through the ADC. Polarity does not matter (autocorrelation is the same
// whether the pulse points up or down).
//
// Method: keep the last ~4 s of samples, remove slow drift with a 1 s
// moving-average high-pass, and find the strongest repeat period with a
// normalized autocorrelation. The peak height is a quality score; below the
// threshold there is NO heart rate. This replaced an earlier beat-interval
// detector that the host tests showed would lock onto pure noise and could
// lock onto half the true rate.
//
// Portable C++ with no Arduino headers, unit tested on a PC against synthetic
// signals (test/test_firmware.cpp). It has NOT been run on a real arm yet.
// Every number in PpgConfig is a tuning parameter to set from a real
// recording, not a clinical value.
//
// Design rule: report a heart rate only with evidence. During motion, without
// contact, without a pulse-sized signal, when the signal is not clearly
// periodic, or while the estimate is still settling, hasValidBpm() is false
// and the caller must OMIT the channel. This class never returns a guess.
#pragma once

#include <math.h>
#include <stddef.h>
#include <stdint.h>

namespace aria {

struct PpgConfig {
  float sampleRateHz = 100.0f;      // the rate samples are pushed at (steady)
  uint32_t contactMinRaw = 0;       // raw level below this = not on skin. 0 disables (analog sensors)
  int smoothN = 3;                  // moving-average length in samples (max kMaxSmooth)
  int windowSamples = 400;          // analysis window (~4 s at 100 Hz, max kMaxWindow)
  int minFillSamples = 300;         // clean samples needed before any estimate (~3 s)
  int evalEverySamples = 50;        // re-estimate every ~0.5 s
  float highPassSeconds = 1.0f;     // moving-average high-pass width
  float minBpm = 35.0f;
  float maxBpm = 200.0f;
  float minRms = 5.0f;              // detrended RMS in raw counts; smaller = no pulse to find
  float minQuality = 0.60f;         // normalized autocorrelation peak needed to trust an estimate
  float agreeFraction = 0.12f;      // two consecutive estimates must agree within this
  uint32_t motionHoldoffMs = 1500;  // distrust the PPG this long after the IMU reports motion
  uint32_t maxAgeMs = 3000;         // a reading is stale if not re-confirmed this recently
};

class PpgHeartRate {
 public:
  static constexpr int kMaxWindow = 512;
  static constexpr int kMaxSmooth = 8;
  static constexpr int kMaxLag = 260;

  explicit PpgHeartRate(const PpgConfig& cfg = PpgConfig()) : cfg_(cfg) {
    if (cfg_.smoothN < 1) cfg_.smoothN = 1;
    if (cfg_.smoothN > kMaxSmooth) cfg_.smoothN = kMaxSmooth;
    if (cfg_.windowSamples > kMaxWindow) cfg_.windowSamples = kMaxWindow;
    if (cfg_.windowSamples < 16) cfg_.windowSamples = 16;
    if (cfg_.minFillSamples > cfg_.windowSamples) cfg_.minFillSamples = cfg_.windowSamples;
    clearWindow();
  }

  // Feed one sample at the configured steady rate. nowMs is a monotonic
  // millisecond clock (wraps safely). motionOk is false while the IMU says
  // the arm is moving.
  void push(uint32_t raw, uint32_t nowMs, bool motionOk) {
    if (!motionOk) {
      lastMotionMs_ = nowMs;
      motionSeen_ = true;
      clearWindow();
      return;
    }
    if (motionSeen_ && (nowMs - lastMotionMs_) < cfg_.motionHoldoffMs) return;  // not collected, window stays empty

    if (cfg_.contactMinRaw != 0 && raw < cfg_.contactMinRaw) {
      onSkin_ = false;
      clearWindow();
      return;
    }
    onSkin_ = true;

    smoothBuf_[smoothIdx_] = static_cast<float>(raw);
    smoothIdx_ = (smoothIdx_ + 1) % cfg_.smoothN;
    if (smoothCount_ < cfg_.smoothN) smoothCount_++;
    float sum = 0;
    for (int i = 0; i < smoothCount_; i++) sum += smoothBuf_[i];

    window_[wIdx_] = sum / smoothCount_;
    wIdx_ = (wIdx_ + 1) % cfg_.windowSamples;
    if (wCount_ < cfg_.windowSamples) wCount_++;

    if (++sinceEval_ >= cfg_.evalEverySamples) {
      sinceEval_ = 0;
      evaluate(nowMs);
    }
  }

  bool hasValidBpm(uint32_t nowMs) const {
    if (!valid_ || !onSkin_) return false;
    if (motionSeen_ && (nowMs - lastMotionMs_) < cfg_.motionHoldoffMs) return false;
    if ((nowMs - lastValidMs_) > cfg_.maxAgeMs) return false;
    return true;
  }

  // Only meaningful when hasValidBpm() is true.
  float bpm() const { return bpm_; }
  // Autocorrelation peak of the latest estimate, 0..1. Log it during bring-up.
  float quality() const { return quality_; }
  bool onSkin() const { return onSkin_; }

 private:
  void clearWindow() {
    wIdx_ = 0;
    wCount_ = 0;
    smoothIdx_ = 0;
    smoothCount_ = 0;
    sinceEval_ = 0;
    valid_ = false;
    stable_ = 0;
    prevBpm_ = 0;
    quality_ = 0;
  }

  void evaluate(uint32_t nowMs) {
    const int n = wCount_;
    if (n < cfg_.minFillSamples) {
      valid_ = false;
      return;
    }

    // Oldest -> newest, offset by the first sample so float sums stay small.
    const int start = (wCount_ < cfg_.windowSamples) ? 0 : wIdx_;
    const float base = window_[start % cfg_.windowSamples];
    for (int i = 0; i < n; i++) scratch_[i] = window_[(start + i) % cfg_.windowSamples] - base;

    // High-pass: subtract a centered moving average (prefix sums).
    pre_[0] = 0;
    for (int i = 0; i < n; i++) pre_[i + 1] = pre_[i] + scratch_[i];
    int half = static_cast<int>(cfg_.highPassSeconds * cfg_.sampleRateHz * 0.5f);
    if (half < 1) half = 1;
    for (int i = 0; i < n; i++) {
      const int lo = i - half < 0 ? 0 : i - half;
      const int hi = i + half > n - 1 ? n - 1 : i + half;
      scratch_[i] -= (pre_[hi + 1] - pre_[lo]) / static_cast<float>(hi - lo + 1);
    }

    // Prefix energy for the normalization terms.
    pre_[0] = 0;
    for (int i = 0; i < n; i++) pre_[i + 1] = pre_[i] + scratch_[i] * scratch_[i];
    const float rms = sqrtf(pre_[n] / n);
    if (!(rms >= cfg_.minRms)) {
      quality_ = 0;
      valid_ = false;
      stable_ = 0;
      return;
    }

    int lagMin = static_cast<int>(floorf(cfg_.sampleRateHz * 60.0f / cfg_.maxBpm));
    int lagMax = static_cast<int>(ceilf(cfg_.sampleRateHz * 60.0f / cfg_.minBpm));
    if (lagMin < 3) lagMin = 3;
    if (lagMax > kMaxLag - 2) lagMax = kMaxLag - 2;
    if (lagMax > n / 2) lagMax = n / 2;
    if (lagMax <= lagMin + 2) {
      valid_ = false;
      return;
    }

    for (int lag = lagMin - 1; lag <= lagMax + 1; lag++) {
      float num = 0;
      for (int i = 0; i + lag < n; i++) num += scratch_[i] * scratch_[i + lag];
      const float den = sqrtf(pre_[n - lag] * (pre_[n] - pre_[lag]));
      r_[lag] = den > 0 ? num / den : 0;
    }

    int globalBest = lagMin;
    for (int lag = lagMin; lag <= lagMax; lag++)
      if (r_[lag] > r_[globalBest]) globalBest = lag;

    // A periodic signal repeats at 2, 3, 4... beat-periods too, and any of
    // those can be the tallest peak (the host tests caught it locking onto 3
    // periods, i.e. reporting a third of the true rate). The heart rate is
    // the FIRST strong repeat, so take the shortest-lag local peak that is
    // nearly as tall as the tallest.
    int best = globalBest;
    for (int lag = lagMin; lag <= globalBest; lag++) {
      const bool localMax = r_[lag] >= r_[lag - 1] && r_[lag] >= r_[lag + 1];
      if (localMax && r_[lag] >= 0.85f * r_[globalBest]) {
        best = lag;
        break;
      }
    }

    float lagFrac = static_cast<float>(best);
    if (best - 1 >= lagMin - 1 && best + 1 <= lagMax + 1) {
      const float a = r_[best - 1], b = r_[best], c = r_[best + 1];
      const float denom = a - 2.0f * b + c;
      if (denom < 0.0f) {
        float delta = 0.5f * (a - c) / denom;
        if (delta > 0.5f) delta = 0.5f;
        if (delta < -0.5f) delta = -0.5f;
        lagFrac += delta;
      }
    }

    quality_ = r_[best];
    const float bpm = 60.0f * cfg_.sampleRateHz / lagFrac;
    if (!(quality_ >= cfg_.minQuality) || !(bpm >= cfg_.minBpm) || !(bpm <= cfg_.maxBpm)) {
      valid_ = false;
      stable_ = 0;
      return;
    }

    // Two consecutive estimates must agree before it is reported.
    if (prevBpm_ > 0 && fabsf(bpm - prevBpm_) <= cfg_.agreeFraction * prevBpm_) stable_++;
    else stable_ = 1;
    prevBpm_ = bpm;
    if (stable_ >= 2) {
      valid_ = true;
      bpm_ = bpm;
      lastValidMs_ = nowMs;
    } else {
      valid_ = false;
    }
  }

  PpgConfig cfg_;
  bool onSkin_ = false;
  bool motionSeen_ = false;
  uint32_t lastMotionMs_ = 0;
  uint32_t lastValidMs_ = 0;

  float smoothBuf_[kMaxSmooth] = {0};
  int smoothIdx_ = 0;
  int smoothCount_ = 0;

  float window_[kMaxWindow] = {0};
  float scratch_[kMaxWindow] = {0};
  float pre_[kMaxWindow + 1] = {0};
  float r_[kMaxLag] = {0};
  int wIdx_ = 0;
  int wCount_ = 0;
  int sinceEval_ = 0;

  bool valid_ = false;
  float bpm_ = 0;
  float quality_ = 0;
  float prevBpm_ = 0;
  int stable_ = 0;
};

}  // namespace aria
