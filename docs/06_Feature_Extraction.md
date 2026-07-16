# SENTRA Technical Design Specification
## Document 06 — Feature Extraction Engine

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies
- 04_Preprocessing.md
- 05_Signal_Quality.md

Required By
- 07_Baseline_Engine.md
- 08_Clinical_Rules.md
- 09_Subsystem_Scoring.md
- 10_Confidence_Fusion.md

---

# 1. Purpose

The Feature Extraction Engine transforms cleaned physiological waveforms into standardized numerical features describing the patient's current physiological state.

Features are the primary input to every downstream reasoning engine.

No downstream module SHALL analyze raw waveforms directly.

---

# 2. Responsibilities

The Feature Extraction Engine SHALL

• Extract physiological biomarkers

• Preserve temporal relationships

• Normalize extracted values

• Associate every feature with signal quality

• Produce one standardized FeatureVector

• Support future feature expansion

---

# 3. Inputs

Input Objects

```
ProcessedWindow

SignalQuality
```

---

# 4. Outputs

```
FeatureVector
```

Every feature SHALL include

```typescript
Feature{

name

value

unit

quality

confidence

timestamp

}
```

---

# 5. Overall Pipeline

```
Processed Window

↓

ECG Features

↓

PPG Features

↓

IMU Features

↓

Temperature Features

↓

Feature Validation

↓

Feature Vector
```

---

# 6. ECG Features

Purpose

Describe cardiac physiology.

## Heart Rate

Unit

BPM

Method

Average RR Interval

---

## RR Interval

Milliseconds

---

## SDNN

Standard deviation of RR intervals.

---

## RMSSD

Root Mean Square of Successive Differences.

---

## pNN50

Percentage of RR intervals differing by more than 50 ms.

---

## Mean NN

Average normal RR interval.

---

## Heart Rate Trend

Current HR

−

Previous HR

---

## Beat Regularity

Measures rhythm consistency.

---

## RR Variability

Measures short-term cardiac variability.

---

## Heart Rate Acceleration

Rate of HR change.

---

## QRS Duration

Milliseconds.

---

## PR Interval

Milliseconds.

---

## QT Interval

Milliseconds.

---

## QTc

Corrected QT interval.

---

## Beat Detection Confidence

Derived from ECG SQI.

---

## Cardiac Feature Summary

ECG produces

15 standardized features.

---

# 7. PPG Features

Purpose

Describe cardiovascular and respiratory physiology.

## Pulse Rate

BPM

---

## SpO₂

%

---

## Pulse Amplitude

Normalized.

---

## Pulse Width

Milliseconds.

---

## Pulse Area

Integral of waveform.

---

## Peak Prominence

Waveform morphology.

---

## Pulse Arrival Time

Milliseconds.

---

## Respiratory Rate

Estimated from PPG.

---

## Respiratory Variability

Breathing stability.

---

## Oxygen Trend

Slope.

---

## Perfusion Index

Peripheral circulation.

---

## Pulse Detection Confidence

Derived from SQI.

---

PPG produces

12 features.

---

# 8. IMU Features

Purpose

Describe motion and physical activity.

## Activity Level

Sedentary

Light

Moderate

High

---

## Step Rate

Steps/minute

---

## Motion Magnitude

Acceleration norm.

---

## Orientation

Standing

Walking

Lying

Sitting

---

## Angular Velocity

Gyroscope.

---

## Fall Probability

0–1

---

## Motion Variability

Variance.

---

## Posture Stability

Movement consistency.

---

## Sleep Probability

Estimated.

---

IMU produces

9 features.

---

# 9. Temperature Features

Purpose

Describe thermoregulation.

## Skin Temperature

°C

---

## Temperature Trend

°C/hour

---

## Temperature Variability

Standard deviation.

---

## Fever Probability

0–1

---

## Baseline Deviation

Difference from patient baseline.

---

Temperature produces

5 features.

---

# 10. Quality Features

The Signal Quality Engine contributes quality metrics as features.

ECG SQI

PPG SQI

IMU SQI

Temperature SQI

Overall SQI

These features allow downstream models to account for signal reliability.

---

# 11. Derived Features

Additional features are computed by combining multiple modalities.

Examples

Cardiorespiratory Ratio

Heart Rate / Respiratory Rate

---

Motion Adjusted Heart Rate

Heart Rate

−

Expected Activity Increase

---

Temperature Corrected Heart Rate

Adjust HR interpretation using body temperature.

---

Oxygen Recovery Rate

Slope after activity.

---

Activity Corrected Respiratory Rate

RR adjusted for movement.

---

# 12. Feature Validation

Every feature is validated.

Checks

NaN

Infinity

Outliers

Impossible physiology

Missing values

Example

```
Heart Rate

520 BPM

↓

Reject
```

---

# 13. Feature Standardization

All features are normalized before downstream processing.

Methods

Continuous

Z-score

Bounded

Min-Max

Categorical

One-hot Encoding

Boolean

Binary

Normalization parameters are stored.

---

# 14. Feature Confidence

Each feature receives a confidence score.

```
Feature Confidence

=

Signal Quality

×

Extraction Confidence
```

Example

```
Heart Rate

98%

Extraction

95%

↓

Feature Confidence

93%
```

---

# 15. Feature Vector

The complete FeatureVector contains

```
ECG

15

PPG

12

IMU

9

Temperature

5

Quality

5

Derived

8

-----------------

Total

54 Features
```

Future versions may extend this vector.

---

# 16. Technology Stack

Programming Language

Python

Libraries

NeuroKit2

HeartPy

NumPy

SciPy

WFDB

Machine Learning

scikit-learn

PyTorch

---

# 17. Folder Structure

```
feature_engine/

├── ecg_features.py

├── ppg_features.py

├── imu_features.py

├── temperature_features.py

├── derived_features.py

├── validation.py

├── normalization.py

├── feature_vector.py

└── models.py
```

---

# 18. Module Interface

Input

```
ProcessedWindow

SignalQuality
```

Output

```
FeatureVector
```

Latency

<100 milliseconds

---

# 19. Pseudocode

```python
function extract_features(window, quality):

    ecg = extract_ecg(window.ecg)

    ppg = extract_ppg(window.ppg)

    imu = extract_imu(window.imu)

    temperature = extract_temperature(window.temperature)

    derived = calculate_multimodal_features()

    validate()

    normalize()

    assign_confidence()

    return FeatureVector()
```

---

# 20. Success Criteria

The Feature Extraction Engine is successful when it

• Produces standardized physiological biomarkers

• Preserves physiological information

• Supports multimodal reasoning

• Associates every feature with confidence

• Produces one unified FeatureVector

• Executes in real time

---

# 21. Summary

The Feature Extraction Engine converts cleaned wearable biosignals into a standardized FeatureVector containing 54 physiological and quality-aware biomarkers. This unified representation becomes the common language shared by every downstream module, enabling the Baseline Engine, Clinical Rule Engine, Machine Learning models, Confidence Fusion, and Priority Engine to reason from the same validated physiological state. By attaching confidence and signal quality to every feature, SENTRA ensures that downstream decisions remain robust even when individual sensors degrade.