# SENTRA Technical Design Specification
## Document 09 — Physiological Subsystem Scoring Engine

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies

- 06_Feature_Extraction.md
- 07_Baseline_Engine.md
- 08_Clinical_Rules.md

Required By

- 10_Confidence_Fusion.md
- 11_Priority_Engine.md

---

# 1. Purpose

The Physiological Subsystem Scoring Engine (PSSE) converts physiological features into independent subsystem risk estimates.

Unlike traditional AI systems that generate a single black-box prediction, SENTRA decomposes patient physiology into multiple physiological domains.

Each subsystem independently evaluates one aspect of human physiology before forwarding its assessment to the Confidence Fusion Engine.

This architecture improves

• Explainability

• Modularity

• Clinical transparency

• Debugging

• Future model replacement

---

# 2. Design Philosophy

Patient deterioration rarely occurs within one physiological system.

Instead,

multiple systems gradually become abnormal.

SENTRA therefore evaluates

```
Cardiac

Respiratory

Thermoregulatory

Mobility
```

independently before combining their evidence.

Each subsystem acts as an independent clinical specialist.

---

# 3. Responsibilities

The PSSE SHALL

• Analyze physiological features

• Calculate subsystem risk

• Estimate model confidence

• Produce explainability metadata

• Weight predictions using Signal Quality

• Forward standardized evidence

---

# 4. Inputs

```
FeatureVector

BaselineDeviation

ClinicalRuleResults

SignalQuality

TrendSummary
```

---

# 5. Outputs

Each subsystem returns

```typescript
SubsystemResult{

subsystem

riskScore

confidence

severity

topFeatures[]

baselineDeviation

clinicalEvidence

timestamp

}
```

Risk Score

```
0–100
```

Confidence

```
0–1
```

---

# 6. Overall Architecture

```
Feature Vector

        │

        ▼

 ┌──────────────┐
 │ Cardiac AI   │
 └──────────────┘

 ┌──────────────┐
 │Respiratory AI│
 └──────────────┘

 ┌──────────────┐
 │Temperature AI│
 └──────────────┘

 ┌──────────────┐
 │ Mobility AI  │
 └──────────────┘

        │

        ▼

Subsystem Results

        │

        ▼

Confidence Fusion
```

Every subsystem executes independently.

---

# 7. Cardiac Risk Engine

Purpose

Evaluate cardiovascular instability.

Input Features

Heart Rate

HRV

RR Interval

QT Interval

QTc

Beat Regularity

Heart Rate Trend

Heart Rate Acceleration

Baseline Deviation

Triggered Cardiac Rules

Outputs

```
Cardiac Risk

0–100
```

Example

```
Risk

81

Confidence

0.94

Reason

Persistent tachycardia

Reduced HRV

Increasing HR trend
```

---

# 8. Respiratory Risk Engine

Purpose

Evaluate pulmonary physiology.

Input Features

Respiratory Rate

SpO₂

Respiratory Variability

Oxygen Trend

Perfusion Index

Motion Corrected RR

Respiratory Baseline

Triggered Respiratory Rules

Output

```
Respiratory Risk

0–100
```

---

# 9. Thermoregulation Engine

Purpose

Evaluate temperature regulation.

Features

Skin Temperature

Temperature Trend

Temperature Variability

Baseline Temperature

Fever Probability

Clinical Temperature Rules

Output

```
Temperature Risk

0–100
```

---

# 10. Mobility Engine

Purpose

Evaluate movement physiology.

Features

Activity

Orientation

Fall Probability

Step Rate

Motion Variability

Sleep Probability

Baseline Motion

Motion Rules

Output

```
Mobility Risk

0–100
```

---

# 11. Risk Interpretation

| Score | Interpretation |
|---------|----------------|
| 0–20 | Normal |
| 21–40 | Mild Concern |
| 41–60 | Moderate Concern |
| 61–80 | High Concern |
| 81–100 | Critical Concern |

These scores DO NOT directly determine patient priority.

---

# 12. Model Confidence

Confidence depends upon

Signal Quality

Feature Confidence

Model Stability

Baseline Confidence

Clinical Rule Agreement

Algorithm

```
Confidence

=

0.30(Signal Quality)

+

0.25(Baseline)

+

0.20(Model Stability)

+

0.15(Feature Confidence)

+

0.10(Rule Agreement)

↓

Clamp

0–1
```

---

# 13. Explainability

Every subsystem SHALL explain itself.

Example

```json
{

"Subsystem":"Cardiac",

"Risk":82,

"Confidence":0.93,

"Top Features":[

"Heart Rate",

"HRV",

"RR Variability"

],

"Triggered Rules":[

"Persistent Tachycardia",

"Low HRV"

]

}
```

No subsystem may produce unexplained predictions.

---

# 14. Risk Calculation

Each subsystem computes

```
Weighted Feature Score

↓

Trend Score

↓

Baseline Score

↓

Clinical Rule Score

↓

Quality Adjustment

↓

Risk Score
```

Generic Formula

```
Risk

=

FeatureScore

+

TrendScore

+

BaselineDeviation

+

RuleContribution

↓

Quality Weighting

↓

Clamp

0–100
```

---

# 15. Dynamic Feature Weighting

Feature importance changes depending on physiology.

Example

Patient Running

↓

Activity Weight ↑

Resting HR Weight ↓

Patient Sleeping

↓

Heart Rate ↑

Respiration ↑

Activity ↓

Dynamic weighting reduces false alarms.

---

# 16. Missing Features

If a feature cannot be extracted

↓

Ignore Feature

↓

Redistribute Weight

↓

Reduce Confidence

Never terminate the subsystem.

---

# 17. Sensor Failure Handling

Example

```
ECG Lost

↓

Cardiac Confidence Reduced

↓

Respiratory Engine Continues

↓

Temperature Continues

↓

Mobility Continues
```

Subsystem independence improves robustness.

---

# 18. Future ML Models

The MVP SHALL initially use lightweight supervised models.

Recommended Models

Gradient Boosted Trees

Random Forest

Logistic Regression

Future versions may replace these with

LSTM

Transformer

Temporal CNN

Graph Neural Networks

without changing subsystem interfaces.

---

# 19. Technology Stack

Programming Language

Python 3.12

Machine Learning

scikit-learn

PyTorch

Feature Processing

NumPy

SciPy

Pandas

Model Serialization

ONNX

or

Joblib

Testing

Pytest

---

# 20. Folder Structure

```
subsystem_scoring/

├── cardiac_engine.py

├── respiratory_engine.py

├── temperature_engine.py

├── mobility_engine.py

├── confidence.py

├── explainability.py

├── weighting.py

├── pipeline.py

├── interfaces.py

└── models.py
```

---

# 21. Standard Interface

Input

```
FeatureVector

BaselineDeviation

ClinicalRuleResults

SignalQuality
```

Output

```typescript
SubsystemResult{

subsystem

riskScore

confidence

topFeatures[]

clinicalEvidence

baselineDeviation

timestamp

}
```

Maximum Latency

100 milliseconds

---

# 22. Pseudocode

```python
def evaluate_subsystems(feature_vector):

    cardiac = cardiac_engine.predict(feature_vector)

    respiratory = respiratory_engine.predict(feature_vector)

    temperature = temperature_engine.predict(feature_vector)

    mobility = mobility_engine.predict(feature_vector)

    return [

        cardiac,

        respiratory,

        temperature,

        mobility

    ]
```

---

# 23. Success Criteria

The Physiological Subsystem Scoring Engine is successful when it

• Produces independent physiological risk estimates

• Generates explainable subsystem predictions

• Maintains modular architecture

• Supports future model replacement

• Handles missing features gracefully

• Operates in real time

• Produces standardized SubsystemResult objects

---

# 24. Summary

The Physiological Subsystem Scoring Engine transforms physiological biomarkers into four independent, explainable risk assessments representing cardiac, respiratory, thermoregulatory, and mobility health. Rather than relying on a single opaque model, SENTRA distributes reasoning across specialized subsystem engines that independently evaluate patient physiology, quantify confidence, explain their predictions, and generate standardized evidence for downstream fusion. This modular architecture improves transparency, maintainability, extensibility, and clinical trust while enabling future machine learning models to be upgraded without altering the surrounding system architecture.