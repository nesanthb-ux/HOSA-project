# SENTRA Technical Design Specification
## Document 07 — Personalized Baseline Engine

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies
- 05_Signal_Quality.md
- 06_Feature_Extraction.md

Required By
- 08_Clinical_Rules.md
- 09_Subsystem_Scoring.md
- 10_Confidence_Fusion.md
- 11_Priority_Engine.md

---

# 1. Purpose

The Personalized Baseline Engine (PBE) continuously learns the normal physiological characteristics of an individual patient.

Rather than comparing every patient against population averages, SENTRA establishes a personalized physiological reference that evolves over time.

Every downstream reasoning engine SHALL compare the patient's current physiological state against their own baseline whenever sufficient historical data exists.

The Personalized Baseline Engine is one of the primary innovations of SENTRA.

---

# 2. Design Philosophy

Traditional Early Warning Scores assume that all patients share identical physiological thresholds.

Examples

Heart Rate

100 BPM

↓

Abnormal

However, this assumption is often incorrect.

Athletes

Resting HR

45 BPM

Children

Resting HR

110 BPM

Post-operative patients

Elevated HR expected

Therefore, SENTRA evaluates

```
Current Physiology

versus

Patient Baseline

NOT

Current Physiology

versus

Population Average
```

---

# 3. Responsibilities

The Personalized Baseline Engine SHALL

• Learn patient physiology

• Continuously update baselines

• Ignore unreliable data

• Detect significant deviations

• Produce baseline confidence

• Generate trend statistics

• Support new patients with limited history

---

# 4. Inputs

```
FeatureVector

SignalQuality

Patient History
```

---

# 5. Outputs

```
BaselineProfile

BaselineDeviation

BaselineConfidence

TrendSummary
```

---

# 6. Overall Architecture

```
Feature Vector

↓

Quality Check

↓

Stable Window Detection

↓

Baseline Update

↓

Deviation Analysis

↓

Trend Analysis

↓

Baseline Output
```

---

# 7. Baseline Initialization

When monitoring begins

```
Patient History

=

None
```

The system enters

```
Learning Mode
```

Learning Mode collects stable physiological observations.

Initial baseline duration

```
30 minutes
```

Future versions may shorten this using historical patient records.

---

# 8. Stable Window Detection

Not every physiological window should update the baseline.

A window SHALL be considered stable only if

Overall SQI

```
≥0.80
```

AND

Activity

```
Resting

OR

Light Activity
```

AND

No Critical Clinical Rules Triggered

AND

No Sensor Failures

If any condition fails

↓

Window SHALL NOT update the baseline.

---

# 9. Baseline Variables

The engine maintains baselines for

Heart Rate

Heart Rate Variability

Respiratory Rate

SpO₂

Skin Temperature

Activity Level

Motion

Sleep Probability

Derived Features

Every numerical feature has an associated baseline.

---

# 10. Adaptive Updating

The baseline SHALL evolve gradually.

Instead of replacing values immediately,

SENTRA uses an Exponential Moving Average.

Algorithm

```
New Baseline

=

α(Current Feature)

+

(1−α)(Previous Baseline)
```

Default

```
α = 0.05
```

This prevents sudden physiological changes from permanently shifting the baseline.

---

# 11. Baseline Deviation

Every feature is compared against baseline.

Algorithm

```
Deviation

=

Current

−

Baseline
```

Normalized

```
Deviation Score

=

|Current−Baseline|

/

Baseline Standard Deviation
```

Higher values indicate more abnormal physiology.

---

# 12. Feature Importance

Not every physiological feature contributes equally.

Example Weights

| Feature | Weight |
|----------|--------|
| Heart Rate | 0.20 |
| HRV | 0.20 |
| Respiratory Rate | 0.15 |
| SpO₂ | 0.20 |
| Temperature | 0.10 |
| Activity | 0.10 |
| Derived Features | 0.05 |

Developers SHALL expose these weights through configuration files rather than hardcoding them.

---

# 13. Baseline Confidence

Baseline confidence increases as more reliable data becomes available.

Algorithm

```
Confidence

=

History Score

×

Average SQI

×

Stability Score
```

Example

History

0.95

Average SQI

0.97

Stability

0.94

↓

Confidence

0.87

Range

```
0–1
```

---

# 14. Trend Detection

The engine continuously evaluates physiological direction.

Metrics

Heart Rate Slope

Temperature Slope

Respiratory Slope

HRV Trend

SpO₂ Trend

Moving Average

Rate of Change

Acceleration

These values become inputs to the Priority Engine.

---

# 15. Circadian Adaptation

Human physiology changes throughout the day.

The MVP SHALL maintain

Morning Baseline

Afternoon Baseline

Night Baseline

This prevents normal circadian variation from generating unnecessary alerts.

Future versions may support fully continuous circadian modeling.

---

# 16. Baseline Drift Protection

The engine SHALL prevent abnormal physiology from becoming the new normal.

Baseline updates are suspended whenever

Clinical Rule Severity

>

Moderate

OR

Priority State

>

WATCH

OR

Overall SQI

<0.80

This prevents deterioration from contaminating the baseline.

---

# 17. New Patient Handling

Patients without sufficient history receive

```
Baseline Confidence

LOW
```

During this phase

Population reference values assist the baseline.

As patient-specific data accumulates,

Population influence decreases.

---

# 18. Baseline Aging

Older physiological observations become less influential.

Observation Weight

```
Today

100%

Yesterday

95%

Three Days

85%

One Week

70%

One Month

40%
```

This allows the baseline to adapt over time.

---

# 19. Output Objects

```typescript
BaselineProfile{

heartRateBaseline

HRVBaseline

respiratoryBaseline

temperatureBaseline

activityBaseline

confidence

lastUpdated

}
```

```typescript
BaselineDeviation{

heartRateDeviation

HRVDeviation

respiratoryDeviation

temperatureDeviation

overallDeviation

}
```

```typescript
TrendSummary{

heartRateSlope

respiratorySlope

temperatureSlope

HRVSlope

overallTrend

}
```

---

# 20. Technology Stack

Programming Language

Python 3.12

Libraries

NumPy

SciPy

Pandas

Database

TimescaleDB

Caching

Redis

Configuration

YAML

Testing

Pytest

---

# 21. Folder Structure

```
baseline_engine/

├── learning.py

├── adaptive_average.py

├── deviation.py

├── trend_analysis.py

├── confidence.py

├── circadian.py

├── profile.py

├── models.py

└── pipeline.py
```

---

# 22. Module Interface

Input

```
FeatureVector

SignalQuality

Patient History
```

Output

```
BaselineProfile

BaselineDeviation

TrendSummary

BaselineConfidence
```

Maximum Latency

50 milliseconds

---

# 23. Pseudocode

```python
function update_baseline(features, quality):

    if quality < QUALITY_THRESHOLD:
        return previous_baseline

    if patient_state > WATCH:
        freeze_baseline()

    if stable_window():

        update_exponential_average()

    calculate_deviation()

    calculate_trends()

    calculate_confidence()

    return BaselineProfile
```

---

# 24. Success Criteria

The Personalized Baseline Engine is successful when it

• Learns individualized physiology

• Adapts gradually over time

• Ignores poor-quality signals

• Prevents abnormal physiology from contaminating the baseline

• Produces accurate deviation metrics

• Generates reliable confidence estimates

• Supports real-time execution

---

# 25. Summary

The Personalized Baseline Engine transforms SENTRA from a population-based monitoring system into a patient-specific physiological intelligence platform. By continuously learning each patient's normal physiology, protecting against baseline drift, accounting for circadian variation, and quantifying deviation from individualized norms, the engine enables downstream clinical reasoning to detect meaningful deterioration earlier while substantially reducing false alarms caused by normal inter-patient variability.