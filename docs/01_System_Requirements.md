# SENTRA Technical Design Specification
## Document 01 — System Architecture

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies:
00_Project_Overview.md

Required By:
02_Data_Model.md
03_Sensor_Input.md
04_Preprocessing.md
05_Signal_Quality.md
06_Feature_Extraction.md
07_Baseline_Engine.md
08_Clinical_Rules.md
09_Subsystem_Scoring.md
10_Confidence_Fusion.md
11_Priority_Engine.md

---

# 1. Purpose

This document defines the overall architecture of SENTRA.

It describes how data moves through the system, the responsibilities of every module, the interfaces between components, and the algorithms governing patient prioritization.

All future development SHALL conform to this architecture.

---

# 2. Design Philosophy

The architecture follows five principles.

## 2.1 Modular

Every subsystem operates independently.

Subsystems communicate only through standardized interfaces.

No subsystem directly modifies another subsystem.

---

## 2.2 Explainable

Every numerical output must be traceable.

Every alert must contain supporting evidence.

No black-box decision may directly trigger a clinical alert.

---

## 2.3 Quality Aware

Poor quality data shall never receive high confidence.

Signal quality is evaluated before any clinical reasoning.

---

## 2.4 Patient Specific

Every patient develops an adaptive physiological baseline.

All abnormality calculations compare current physiology against the patient's baseline whenever available.

---

## 2.5 Temporal

Health deterioration is rarely instantaneous.

The architecture continuously evaluates physiological trends instead of isolated measurements.

---

# 3. System Pipeline

The SENTRA pipeline SHALL execute in the following order.

```

Sensors

↓

Synchronization

↓

Preprocessing

↓

Artifact Detection

↓

Signal Quality

↓

Feature Extraction

↓

Parallel Reasoning Engines

↓

Confidence Fusion

↓

Priority Engine

↓

State Manager

↓

Explainability

↓

Dashboard

```

Every module receives standardized inputs and produces standardized outputs.

No module skips another.

---

# 4. Module Responsibilities

## Module 1

Sensor Layer

Purpose

Receive physiological data.

Responsibilities

• Receive sensor packets

• Timestamp packets

• Validate packet format

• Detect disconnected sensors

Output

Raw Sensor Stream

---

## Module 2

Synchronization Layer

Purpose

Align all incoming signals.

Responsibilities

• Correct timestamps

• Buffer streams

• Create synchronized windows

Output

Synchronized Window

---

## Module 3

Preprocessing Layer

Purpose

Prepare signals for analysis.

Responsibilities

• Remove baseline drift

• Remove powerline interference

• Normalize signals

• Fill short missing gaps

• Reject corrupted packets

Output

Clean Sensor Window

---

## Module 4

Artifact Detection

Purpose

Estimate signal corruption.

Responsibilities

Compute artifact metrics.

Examples

ECG

Motion Artifact

Baseline Drift

Powerline Noise

Beat Loss

PPG

Motion

Ambient Light

Low Perfusion

IMU

Orientation Drift

Saturation

Packet Loss

Temperature

Contact Loss

Rapid Spikes

Output

Artifact Vector

---

## Module 5

Signal Quality Engine

Purpose

Estimate sensor reliability.

Input

Artifact Vector

Output

Signal Quality Index (SQI)

Range

0.0–1.0

Interpretation

1.0

Perfect quality

0.75

Good

0.50

Usable

0.25

Poor

0

Ignore

Algorithm

SQI

=

Weighted Quality Metrics

↓

Normalize

↓

Clamp 0–1

---

## Module 6

Feature Extraction

Purpose

Convert biosignals into physiological variables.

Outputs include

Heart Rate

HRV

Respiration Rate

Activity

Temperature Trend

SpO₂

Motion Features

Feature vectors are passed to all downstream engines.

---

# 5. Parallel Reasoning Layer

The reasoning layer consists of independent engines.

Each produces its own evidence.

None produces the final decision.

```

               Features

                  │

 ┌────────────────┼────────────────┐

 │                │                │

 ▼                ▼                ▼

Baseline      Clinical Rules      ML

 │                │                │

 └────────────────┼────────────────┘

                  ▼

          Context Engine

                  ▼

          Evidence Package

```

---

# 6. Baseline Engine

Purpose

Estimate patient normal physiology.

Inputs

Feature Vector

Previous Baseline

Outputs

Baseline Deviation

Baseline Confidence

Trend

Algorithm

```

Deviation

=

Current

-

Baseline

↓

Normalize

↓

Deviation Score

```

The baseline updates only during physiologically stable periods.

---

# 7. Clinical Rule Engine

Purpose

Apply deterministic medical reasoning.

Example rules

Persistent Tachycardia

Persistent Bradycardia

Respiratory Depression

Hypoxia

Fever

Low Activity

Rapid Temperature Rise

Rule Output

```

Rule ID

Severity

Confidence

Supporting Features

```

Rules never directly trigger alerts.

---

# 8. Machine Learning Engine

Purpose

Detect complex nonlinear physiological patterns.

Inputs

Feature Vector

Outputs

Subsystem Risk Scores

Example

Cardiac Risk

Respiratory Risk

Thermoregulatory Risk

Mobility Risk

Future versions may replace internal models without changing interfaces.

---

# 9. Context Engine

Purpose

Interpret physiology using environmental context.

Examples

Running

Sleeping

Walking

Standing

Resting

Motion affects interpretation.

Example

Heart Rate

160 BPM

Running

↓

Normal

Heart Rate

160 BPM

Sleeping

↓

Abnormal

Output

Context Modifier

---

# 10. Evidence Package

All reasoning engines contribute evidence.

Standard format

```

Evidence

{

Source

Value

Confidence

Timestamp

Supporting Features

}

```

Every downstream module uses the same structure.

---

# 11. Confidence Fusion Engine

Purpose

Estimate confidence in system conclusions.

Inputs

SQI

Baseline Confidence

ML Confidence

Clinical Rule Agreement

Temporal Stability

Context Reliability

Algorithm

```

Confidence

=

w1(SQI)

+

w2(Baseline)

+

w3(Model)

+

w4(Temporal Stability)

+

w5(Context)

↓

Normalize

↓

Clamp

```

Output

Confidence

0–1

---

# 12. Priority Engine

Purpose

Determine urgency.

This is the core decision-making module.

Inputs

Baseline

Clinical Rules

ML

Confidence

Context

Trend

Algorithm

```

Priority Score

=

Baseline Score

+

Rule Score

+

ML Score

+

Trend Score

+

Context Modifier

↓

Confidence Weighting

↓

Priority Score

```

Priority

0–100

State Mapping

```

0–20

NORMAL

21–40

WATCH

41–60

CONCERN

61–80

HIGH PRIORITY

81–100

CRITICAL

```

---

# 13. State Manager

Purpose

Prevent unstable alerts.

The State Manager stores patient history.

Transitions require persistence.

Example

```

NORMAL

↓

Three consecutive abnormal windows

↓

WATCH

↓

Five abnormal windows

↓

CONCERN

↓

Sustained deterioration

↓

HIGH PRIORITY

```

A single noisy reading shall not change state.

---

# 14. Explainability Engine

Every recommendation SHALL include

Priority

Confidence

Supporting Sensors

Supporting Features

Triggered Rules

ML Contributions

Baseline Deviations

Trend Summary

Example

```

Priority

72

Confidence

91%

Reason

Persistent HR increase

Reduced HRV

Respiratory instability

High ECG quality

No motion artifact

```

---

# 15. Dashboard Interface

The dashboard SHALL display

Current State

Priority

Confidence

Sensor Status

Trend Graphs

Triggered Rules

Subsystem Scores

Historical Timeline

No raw model outputs shall be displayed without explanation.

---

# 16. Standard Module Interface

Every module SHALL implement the same interface.

Input

```

Data

Metadata

Timestamp

Configuration

```

Output

```

Results

Confidence

Quality

Execution Time

Metadata

```

This allows modules to be replaced independently.

---

# 17. Error Handling

If a sensor fails

↓

Lower confidence

Do NOT stop processing.

If all sensors fail

↓

Enter Safe Mode.

Safe Mode

No alerts

Notify clinician

Continue listening

---

# 18. Future Expansion

The architecture supports

• Additional wearable sensors

• New ML models

• Edge AI deployment

• Cloud synchronization

• Hospital EMR integration

• Federated learning

without changing the core pipeline.

---

# 19. Architecture Summary

SENTRA is built around modular physiological reasoning.

No single subsystem determines patient priority.

Instead, independent evidence sources are combined through confidence-aware fusion into a single explainable priority state.

This architecture enables transparency, extensibility, robustness to noisy wearable data, and future expansion while remaining simple enough for an MVP implementation.