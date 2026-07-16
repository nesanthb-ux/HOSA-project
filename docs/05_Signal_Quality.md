# SENTRA Technical Design Specification
## Document 05 — Signal Quality Engine

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies
- 03_Sensor_Input.md
- 04_Preprocessing.md

Required By
- 06_Feature_Extraction.md
- 09_Subsystem_Scoring.md
- 10_Confidence_Fusion.md
- 11_Priority_Engine.md

---

# 1. Purpose

The Signal Quality Engine (SQE) evaluates the reliability of every physiological signal before any clinical reasoning occurs.

Rather than determining patient health, this module determines whether incoming data is trustworthy enough to influence downstream decision-making.

The Signal Quality Engine is one of the most critical safety layers in SENTRA.

Its output directly influences feature extraction, subsystem scoring, confidence fusion, and patient prioritization.

---

# 2. Design Philosophy

Clinical decisions are only as reliable as the data used to make them.

Poor quality physiological signals SHALL never generate high-confidence recommendations.

Instead of discarding an entire patient window when one sensor performs poorly, SENTRA evaluates each sensor independently and dynamically adjusts its contribution.

---

# 3. Responsibilities

The Signal Quality Engine SHALL

• Evaluate every sensor independently

• Detect motion contamination

• Detect electrical interference

• Detect signal clipping

• Detect signal dropout

• Detect sensor detachment

• Generate sensor-specific SQIs

• Compute overall window quality

• Produce quality metadata

• Forward quality scores to downstream modules

---

# 4. Inputs

Input

```
ProcessedWindow
```

Contains

• Filtered ECG

• Filtered PPG

• Filtered IMU

• Filtered Temperature

• Processing Metadata

---

# 5. Outputs

Output

```
SignalQuality
```

Contains

```typescript
SignalQuality{

ECGSQI

PPGSQI

IMUSQI

TemperatureSQI

OverallSQI

QualityFlags[]

Confidence

}
```

---

# 6. Overall Architecture

```

Processed Window

        │

        ▼

Quality Metric Extraction

        │

        ▼

Sensor Quality Evaluation

        │

        ▼

Individual SQIs

        │

        ▼

Overall SQI

        │

        ▼

Quality Report

```

---

# 7. ECG Quality Evaluation

The ECG SQI is calculated using multiple metrics.

Metrics

• Signal-to-Noise Ratio

• Baseline Wander

• Powerline Noise

• Beat Detection Success

• Motion Correlation

• Flatline Detection

• Saturation Detection

Algorithm

```
ECGSQI

=

0.25(SNR)

+

0.20(Baseline Stability)

+

0.15(Beat Detection)

+

0.15(Motion Score)

+

0.15(Powerline Score)

+

0.10(Amplitude Stability)

↓

Normalize

↓

Clamp

0–1
```

---

# 8. PPG Quality Evaluation

Metrics

• Pulse Morphology

• Pulse Amplitude

• Motion Artifact

• Ambient Light Noise

• Perfusion Index

• Pulse Detection Rate

Algorithm

```
PPGSQI

=

0.25(Pulse Shape)

+

0.20(Motion)

+

0.20(Perfusion)

+

0.15(Pulse Detection)

+

0.10(Ambient Light)

+

0.10(Amplitude Stability)

↓

Normalize

↓

Clamp
```

---

# 9. IMU Quality Evaluation

Metrics

• Packet Loss

• Sensor Saturation

• Orientation Stability

• Noise

• Calibration Status

Algorithm

```
IMUSQI

=

0.30(Packet Quality)

+

0.25(Calibration)

+

0.20(Saturation)

+

0.15(Noise)

+

0.10(Orientation Stability)
```

---

# 10. Temperature Quality Evaluation

Metrics

• Contact Stability

• Sudden Spikes

• Sensor Drift

• Sampling Continuity

Algorithm

```
TemperatureSQI

=

0.35(Contact)

+

0.30(Stability)

+

0.20(Drift)

+

0.15(Continuity)
```

---

# 11. Overall SQI

Instead of averaging sensors equally, SENTRA weights sensors according to clinical importance.

```
OverallSQI

=

0.40(ECGSQI)

+

0.30(PPGSQI)

+

0.20(IMUSQI)

+

0.10(TemperatureSQI)
```

Future sensors will update these weights.

---

# 12. Quality Categories

| Score | Interpretation | Action |
|---------|----------------|-------------------------|
| 0.90–1.00 | Excellent | Full confidence |
| 0.75–0.89 | Good | Normal processing |
| 0.60–0.74 | Acceptable | Slight confidence reduction |
| 0.40–0.59 | Poor | Significant confidence penalty |
| <0.40 | Unusable | Ignore sensor |

---

# 13. Quality Flags

Each evaluation generates quality flags.

Examples

```typescript
enum QualityFlag{

HIGH_MOTION

LOW_PERFUSION

ECG_DETACHED

SIGNAL_CLIPPED

POWERLINE_NOISE

TEMPERATURE_SPIKE

LOW_BATTERY

LOW_SIGNAL

PACKET_LOSS

CLOCK_DRIFT

}
```

These flags are forwarded to the Explainability Engine.

---

# 14. Dynamic Sensor Weighting

The Signal Quality Engine determines how much influence each sensor receives.

Example

```
ECGSQI

0.95

↓

Weight

100%

----------------

PPGSQI

0.42

↓

Weight

45%

----------------

TemperatureSQI

0.91

↓

Weight

100%
```

The Priority Engine automatically trusts high-quality sensors more than low-quality sensors.

---

# 15. Confidence Penalty

Low quality decreases system confidence.

```
Overall Confidence

=

Model Confidence

×

OverallSQI
```

Example

```
Model Confidence

95%

OverallSQI

60%

↓

Final Confidence

57%
```

This prevents misleading certainty.

---

# 16. Sensor Failure Detection

The engine continuously monitors

• Flatline duration

• Zero variance

• Repeated samples

• Missing packets

• Excessive clipping

Persistent failures trigger

```
Sensor Disabled

↓

Alert Dashboard

↓

Continue Processing
```

The pipeline never stops because one sensor fails.

---

# 17. Interface with Feature Extraction

Only reliable signals are forwarded.

```
SQI > 0.60

↓

Extract Features

---------------

SQI ≤ 0.60

↓

Extract Limited Features

---------------

SQI < 0.40

↓

Ignore Signal
```

This improves downstream reliability.

---

# 18. Technology Stack

Programming Language

Python 3.12

Libraries

NumPy

SciPy

NeuroKit2

HeartPy

WFDB

Validation

Pydantic

Testing

Pytest

---

# 19. Folder Structure

```
signal_quality/

├── ecg_quality.py

├── ppg_quality.py

├── imu_quality.py

├── temperature_quality.py

├── weighting.py

├── quality_flags.py

├── scoring.py

├── pipeline.py

└── models.py
```

---

# 20. Module Interface

Input

```
ProcessedWindow
```

Output

```
SignalQuality
```

Execution Frequency

Every window

Maximum Latency

50 milliseconds

---

# 21. Pseudocode

```python
function evaluate_signal_quality(window):

    ecg_score = evaluate_ecg(window.ecg)

    ppg_score = evaluate_ppg(window.ppg)

    imu_score = evaluate_imu(window.imu)

    temp_score = evaluate_temperature(window.temperature)

    overall = weighted_quality(

        ecg_score,

        ppg_score,

        imu_score,

        temp_score

    )

    flags = detect_quality_flags()

    return SignalQuality(

        ecg_score,

        ppg_score,

        imu_score,

        temp_score,

        overall,

        flags

    )
```

---

# 22. Success Criteria

The Signal Quality Engine is considered successful when it

• Correctly identifies poor-quality physiological signals

• Produces accurate SQIs for every sensor

• Dynamically adjusts sensor weighting

• Prevents low-quality data from driving clinical decisions

• Supplies quality metadata to downstream modules

• Operates in real time

---

# 23. Summary

The Signal Quality Engine serves as SENTRA's first safety checkpoint. Rather than assuming every physiological signal is equally trustworthy, it quantifies the reliability of each sensor independently using modality-specific quality metrics. These scores dynamically influence feature extraction, machine learning, confidence fusion, and patient prioritization, ensuring that clinical recommendations are driven by the highest-quality evidence available while gracefully degrading performance when sensors become unreliable.