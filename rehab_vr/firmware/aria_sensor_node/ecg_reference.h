// R-peak heart rate from an AD8232 ECG module. THIS IS A TEST REFERENCE, not
// part of the sleeve: a single-arm band cannot pick up a usable ECG (the
// electrodes have to span the heart, e.g. one on each hand or on the chest).
// Its job is to give the arm-PPG estimate a trusted answer to be compared
// against during bring-up, so the accuracy claim rests on measured error
// against ECG rather than on hope.
//
// SAFETY: the AD8232 module is not electrically isolated and is not a medical
// device. While its electrodes are on a person, run the ESP32 from a battery
// (and a laptop on battery, or a USB isolator) — never from a mains-powered
// computer through USB.
//
// Portable C++ (unit tested on a PC against synthetic ECG). Not run on a real
// AD8232 yet.
#pragma once

#include <math.h>
#include <stdint.h>

namespace aria {

struct EcgConfig {
  float sampleRateHz = 250.0f;
  float baselineAlpha = 0.005f;      // slow baseline tracker (removes wander/offset)
  float peakDecay = 0.9995f;         // per-sample decay of the running R-peak level
  float minPeak = 120.0f;            // raw ADC counts; an R wave must be at least this tall
  float thresholdFrac = 0.5f;        // fraction of the running R level that counts as a peak
  uint32_t refractoryMs = 250;       // no two R waves closer than this
  uint32_t minIntervalMs = 300;      // 200 bpm
  uint32_t maxIntervalMs = 1700;     // 35 bpm
  float intervalTolerance = 0.35f;
  float maxIntervalCv = 0.25f;
  int minIntervalsForBpm = 4;
  uint32_t maxAgeMs = 3000;
};

class EcgRPeakRate {
 public:
  static constexpr int kMaxIntervals = 8;

  explicit EcgRPeakRate(const EcgConfig& cfg = EcgConfig()) : cfg_(cfg) {}

  // leadsOff: the AD8232's LO+/LO- outputs (either high) mean an electrode is off.
  void push(float sample, uint32_t nowMs, bool leadsOff) {
    if (leadsOff) {
      reset();
      return;
    }
    if (!init_) {
      base_ = sample;
      init_ = true;
    }
    base_ += cfg_.baselineAlpha * (sample - base_);
    const float hp = sample - base_;

    peakLevel_ *= cfg_.peakDecay;
    if (hp > peakLevel_) peakLevel_ = hp;
    float thr = cfg_.thresholdFrac * peakLevel_;
    if (thr < cfg_.minPeak) thr = cfg_.minPeak;

    // A peak is confirmed one sample late: the previous sample was above
    // threshold and higher than both its neighbours.
    if (havePrev2_ && prevHp_ > thr && prevHp_ >= prev2Hp_ && prevHp_ > hp &&
        (prevMs_ - lastRMs_) >= cfg_.refractoryMs) {
      onR(prevMs_);
    }
    prev2Hp_ = prevHp_;
    prevHp_ = hp;
    prevMs_ = nowMs;
    havePrev2_ = true;
  }

  bool hasValidBpm(uint32_t nowMs) const {
    if (n_ < cfg_.minIntervalsForBpm) return false;
    if ((nowMs - lastRMs_) > cfg_.maxAgeMs) return false;
    return cv() <= cfg_.maxIntervalCv;
  }

  float bpm() const {
    const float med = median();
    return med > 0 ? 60000.0f / med : 0.0f;
  }

 private:
  void reset() {
    init_ = false;
    peakLevel_ = 0;
    havePrev2_ = false;
    haveLastR_ = false;
    n_ = 0;
    idx_ = 0;
    reject_ = 0;
  }

  void onR(uint32_t tMs) {
    if (!haveLastR_) {
      lastRMs_ = tMs;
      haveLastR_ = true;
      return;
    }
    const uint32_t interval = tMs - lastRMs_;
    lastRMs_ = tMs;
    if (interval < cfg_.minIntervalMs || interval > cfg_.maxIntervalMs) {
      n_ = 0;
      idx_ = 0;
      return;
    }
    if (n_ >= 3) {
      const float med = median();
      if (fabsf(static_cast<float>(interval) - med) > cfg_.intervalTolerance * med) {
        if (++reject_ >= 3) {  // a real rate change: relearn
          n_ = 0;
          idx_ = 0;
          reject_ = 0;
        }
        return;
      }
    }
    reject_ = 0;
    intervals_[idx_] = interval;
    idx_ = (idx_ + 1) % kMaxIntervals;
    if (n_ < kMaxIntervals) n_++;
  }

  float median() const {
    if (n_ == 0) return 0;
    uint32_t tmp[kMaxIntervals];
    for (int i = 0; i < n_; i++) tmp[i] = intervals_[i];
    for (int i = 1; i < n_; i++) {
      const uint32_t v = tmp[i];
      int j = i - 1;
      while (j >= 0 && tmp[j] > v) {
        tmp[j + 1] = tmp[j];
        j--;
      }
      tmp[j + 1] = v;
    }
    return (n_ % 2 == 1) ? static_cast<float>(tmp[n_ / 2]) : 0.5f * (tmp[n_ / 2 - 1] + tmp[n_ / 2]);
  }

  float cv() const {
    if (n_ < 2) return 0;
    float mean = 0;
    for (int i = 0; i < n_; i++) mean += intervals_[i];
    mean /= n_;
    if (mean <= 0) return 1e9f;
    float var = 0;
    for (int i = 0; i < n_; i++) {
      const float d = intervals_[i] - mean;
      var += d * d;
    }
    return sqrtf(var / n_) / mean;
  }

  EcgConfig cfg_;
  bool init_ = false;
  float base_ = 0;
  float peakLevel_ = 0;
  float prevHp_ = 0, prev2Hp_ = 0;
  uint32_t prevMs_ = 0;
  bool havePrev2_ = false;
  bool haveLastR_ = false;
  uint32_t lastRMs_ = 0;
  uint32_t intervals_[kMaxIntervals] = {0};
  int n_ = 0;
  int idx_ = 0;
  int reject_ = 0;
};

}  // namespace aria
