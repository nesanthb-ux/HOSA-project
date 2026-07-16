# SENTRA Technical Design Specification
## Document 08 — Clinical Rule Engine

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies
- 06_Feature_Extraction.md
- 07_Baseline_Engine.md

Required By
- 09_Subsystem_Scoring.md
- 10_Confidence_Fusion.md
- 11_Priority_Engine.md

---

# 1. Purpose

The Clinical Rule Engine (CRE) applies deterministic, explainable medical logic to continuously evaluate patient physiology.

Unlike machine learning models, every Clinical Rule is transparent, traceable, configurable, and independently validated.

The Clinical Rule Engine SHALL never diagnose disease.

Instead, it identifies clinically significant physiological abnormalities that increase patient priority.

The Clinical Rule Engine serves as SENTRA's "clinical reasoning layer."

---

# 2. Design Philosophy

Machine Learning excels at recognizing complex patterns.

Clinical Rules excel at recognizing known physiological danger.

SENTRA combines both.

```
Feature Vector

↓

Clinical Rule Engine

↓

Evidence

↓

Machine Learning

↓

Evidence

↓

Confidence Fusion

↓

Priority Engine
```

Neither subsystem independently determines patient priority.

---

# 3. Responsibilities

The Clinical Rule Engine SHALL

• Evaluate deterministic physiological rules

• Compare features against personalized baselines

• Calculate rule severity

• Calculate rule confidence

• Track rule persistence

• Resolve conflicting rules

• Produce explainable evidence

---

# 4. Inputs

```
FeatureVector

BaselineProfile

BaselineDeviation

TrendSummary

SignalQuality
```

---

# 5. Outputs

```
ClinicalRuleResult[]

ClinicalEvidence

ClinicalSeverityScore

RuleConfidence
```

---

# 6. Rule Evaluation Pipeline

```
Feature Vector

↓

Eligibility Check

↓

Threshold Evaluation

↓

Persistence Check

↓

Severity Calculation

↓

Confidence Assignment

↓

Evidence Generation

↓

Clinical Rule Results
```

---

# 7. Rule Structure

Every rule SHALL implement the following schema.

```typescript
ClinicalRule{

ruleID

ruleName

description

enabled

priority

requiredFeatures[]

conditions[]

minimumDuration

severityWeight

confidenceWeight

recommendedAction

}
```

---

# 8. Rule Priorities

| Priority | Meaning |
|----------|---------|
| Critical | Immediate evaluation |
| High | Rapid evaluation |
| Moderate | Monitor closely |
| Low | Informational |

Priority does NOT determine patient state.

Priority contributes to the Priority Engine.

---

# 9. Rule Severity

Each triggered rule receives a severity score.

Range

```
0.0

↓

1.0
```

Interpretation

```
0.20

Minor abnormality

0.50

Moderate abnormality

0.75

Severe abnormality

1.00

Critical abnormality
```

---

# 10. Rule Confidence

Confidence depends on

• Signal Quality

• Feature Confidence

• Baseline Confidence

• Persistence

Algorithm

```
Rule Confidence

=

SignalQuality

×

FeatureConfidence

×

BaselineConfidence

×

PersistenceScore
```

---

# 11. Persistence Engine

Transient abnormalities SHALL NOT immediately trigger severe rules.

Every rule defines

```
Minimum Duration

Minimum Consecutive Windows
```

Example

```
Heart Rate >120

One Window

↓

Monitor

Heart Rate >120

Five Consecutive Windows

↓

Trigger Rule
```

---

# 12. Cardiac Rules

### CR-001 Persistent Tachycardia

Condition

Heart Rate

>

120 BPM

Persistence

3 Windows

Severity

0.70

---

### CR-002 Severe Tachycardia

Heart Rate

>

150 BPM

Persistence

2 Windows

Severity

0.95

---

### CR-003 Bradycardia

Heart Rate

<50 BPM

Persistence

3 Windows

Severity

0.70

---

### CR-004 Rapid HR Increase

Heart Rate Increase

>

30 BPM

Within

5 Minutes

---

### CR-005 Low HRV

RMSSD

Below Personalized Baseline

By

40%

Persistence

10 Minutes

---

### CR-006 QT Prolongation

QTc

>

470 ms

---

### CR-007 Irregular Rhythm

Beat Regularity

Below Threshold

---

# 13. Respiratory Rules

### RR-001 Tachypnea

Respiratory Rate

>

24 breaths/min

---

### RR-002 Bradypnea

Respiratory Rate

<10 breaths/min

---

### RR-003 Persistent Hypoxia

SpO₂

<92%

For

3 Windows

---

### RR-004 Rapid Oxygen Drop

SpO₂ decreases

>

4%

Within

5 Minutes

---

### RR-005 Respiratory Instability

Respiratory Variability

Above Threshold

---

# 14. Temperature Rules

### TMP-001 Fever Trend

Temperature

>

38°C

---

### TMP-002 Rapid Temperature Rise

Increase

>

1°C/hour

---

### TMP-003 Persistent Elevated Temperature

Above Baseline

For

30 Minutes

---

# 15. Motion Rules

### MOT-001 Fall Suspected

Fall Probability

>

0.90

---

### MOT-002 Prolonged Inactivity

No Movement

>

2 Hours

---

### MOT-003 Sudden Collapse

Acceleration Spike

↓

No Motion

---

### MOT-004 Abnormal Activity

Activity differs from baseline

By

>300%

---

# 16. Multimodal Rules

These combine multiple physiological systems.

### MM-001 Cardiorespiratory Stress

High HR

+

Low SpO₂

+

High RR

---

### MM-002 Possible Infection

Fever

+

Increasing HR

+

Reduced HRV

---

### MM-003 Recovery Pattern

Heart Rate

↓

Temperature

↓

Respiratory Rate Stable

↓

Decrease Severity

---

### MM-004 Possible Clinical Deterioration

Heart Rate Rising

+

HRV Falling

+

Respiration Increasing

Persistence

15 Minutes

---

### MM-005 Sensor Failure

Poor SQI

+

Flatline

↓

Ignore Clinical Rule

---

# 17. Rule Dependencies

Some rules require others.

Example

```
Possible Infection

requires

Fever Rule

AND

Elevated Heart Rate Rule
```

Dependencies reduce false positives.

---

# 18. Rule Conflict Resolution

Conflicting rules are resolved using priority.

Example

```
Recovery Pattern

↓

Severity

0.20

----------------

Rapid Deterioration

↓

Severity

0.90

↓

Use Higher Severity
```

Conflicts are documented.

---

# 19. Rule Aggregation

Triggered rules produce one Clinical Severity Score.

```
Clinical Severity

=

Weighted Average

of

Triggered Rules
```

Weights depend on

Priority

Persistence

Confidence

---

# 20. Explainability

Every triggered rule SHALL include

```typescript
ClinicalRuleResult{

ruleID

ruleName

severity

confidence

supportingFeatures

supportingSensors

duration

recommendedAction

}
```

---

# 21. Technology Stack

Programming Language

Python 3.12

Configuration

YAML

Rule Engine

Native Python

Validation

Pydantic

Testing

Pytest

No external business-rule engine is required for the MVP.

---

# 22. Folder Structure

```
clinical_rules/

├── cardiac_rules.py

├── respiratory_rules.py

├── temperature_rules.py

├── motion_rules.py

├── multimodal_rules.py

├── persistence.py

├── conflict_resolution.py

├── scoring.py

├── engine.py

└── models.py
```

---

# 23. Module Interface

Input

```
FeatureVector

BaselineProfile

TrendSummary

SignalQuality
```

Output

```
ClinicalRuleResult[]

ClinicalSeverityScore

ClinicalEvidence
```

Maximum Latency

50 milliseconds

---

# 24. Pseudocode

```python
def evaluate_rules(features, baseline, trends):

    triggered = []

    for rule in RULE_LIBRARY:

        if rule.is_eligible(features):

            result = rule.evaluate(
                features,
                baseline,
                trends
            )

            if result.triggered:
                triggered.append(result)

    severity = aggregate(triggered)

    return ClinicalEvidence(
        rules=triggered,
        severity=severity
    )
```

---

# 25. Success Criteria

The Clinical Rule Engine is successful when it

• Executes deterministic medical reasoning

• Produces reproducible results

• Explains every triggered rule

• Tracks persistence over time

• Resolves conflicting evidence

• Generates standardized ClinicalRuleResult objects

• Operates in real time

---

# 26. Summary

The Clinical Rule Engine provides SENTRA with an explainable medical reasoning layer that complements machine learning. By evaluating deterministic physiological rules, enforcing persistence requirements, resolving conflicting evidence, and comparing patients against personalized baselines, the engine transforms raw physiological abnormalities into structured clinical evidence. These standardized outputs become a core input to Confidence Fusion and the Priority Engine, ensuring that every patient recommendation is supported by transparent, reproducible medical logic.