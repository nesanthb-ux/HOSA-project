# SENTRA Technical Design Specification
## Document 11 — Priority Engine

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies

- 07_Baseline_Engine.md
- 08_Clinical_Rules.md
- 09_Subsystem_Scoring.md
- 10_Confidence_Fusion.md

Required By

- 12_Explainability.md
- Dashboard
- Alert Manager
- Notification Service

---

# 1. Purpose

The Priority Engine (PE) is the central decision-making system within SENTRA.

Every upstream module generates physiological evidence.

The Priority Engine integrates this evidence into one standardized clinical priority that determines which patients require attention first.

Unlike traditional Early Warning Scores, the Priority Engine does not rely upon a single physiological score.

Instead, it continuously evaluates multiple evidence streams, confidence estimates, patient-specific baselines, and temporal deterioration patterns to generate an explainable patient priority.

The Priority Engine SHALL NOT diagnose disease.

The Priority Engine SHALL prioritize patients.

---

# 2. Design Philosophy

Traditional monitoring systems produce alarms.

SENTRA produces evidence.

The Priority Engine converts evidence into action.

```
Feature Extraction

↓

Clinical Rule Engine

↓

Subsystem Scoring

↓

Confidence Fusion

↓

Baseline Comparison

↓

Trend Analysis

↓

Priority Engine

↓

Priority State

↓

Explainability

↓

Dashboard
```

Every module contributes evidence.

Only the Priority Engine determines patient priority.

---

# 3. Responsibilities

The Priority Engine SHALL

• Receive evidence from all upstream modules

• Weight evidence according to confidence

• Evaluate physiological deterioration

• Compare physiology against personalized baselines

• Track persistent abnormalities

• Suppress transient artifacts

• Determine patient priority

• Maintain patient state

• Generate explainable outputs

• Trigger downstream alerts

---

# 4. Inputs

```
SubsystemResults[]

ClinicalRuleResults[]

ConfidenceFusionResult

BaselineDeviation

TrendSummary

SignalQuality

ContextState

PatientHistory

WindowStatistics
```

---

# 5. Outputs

```typescript
PriorityResult{

priorityScore

priorityLevel

confidence

state

trend

reasonCodes[]

topContributors[]

recommendedAction

alertRequired

timestamp

}
```

---

# 6. Design Goals

The Priority Engine shall

• Produce deterministic outputs

• Be clinically explainable

• Operate continuously

• Support personalized medicine

• Minimize false alarms

• Detect gradual deterioration

• Detect rapid deterioration

• Operate independently of any individual AI model

• Remain modular

---

# 7. High Level Architecture

```
Clinical Rules
          │
          │
Subsystem Risk
          │
          │
Baseline Deviation
          │
          │
Trend Analysis
          │
          │
Confidence Fusion
          │
          ▼
 ------------------------
|    Priority Engine      |
 ------------------------
          │
          ▼
 Priority Result
          │
          ▼
 Explainability
          │
          ▼
 Dashboard
```

---

# 8. Clinical Priority Levels

| Level | Score | Description |
|---------|---------|------------------------|
| Normal | 0–20 | Stable physiology |
| Watch | 21–40 | Mild concern |
| Concern | 41–60 | Moderate deterioration |
| High Priority | 61–80 | Significant deterioration |
| Critical | 81–100 | Immediate intervention |

Priority levels are configurable.

---

# 9. Evidence Sources

The Priority Engine consumes six independent evidence streams.

```
Clinical Rules

Subsystem Scores

Baseline Deviation

Trend Analysis

Confidence

Context
```

No evidence source independently determines patient priority.

---

# 10. Evidence Weighting

Default MVP weighting

| Evidence | Weight |
|-----------|---------|
| Clinical Rules | 30% |
| Subsystem Risk | 25% |
| Trend Analysis | 15% |
| Baseline Deviation | 15% |
| Confidence Fusion | 10% |
| Context | 5% |

Weights SHALL remain configurable using YAML.

---

# 11. Priority Equation

```
PriorityRaw =

0.30 × ClinicalSeverity

+

0.25 × SubsystemRisk

+

0.15 × TrendScore

+

0.15 × BaselineDeviation

+

0.10 × ConfidenceScore

+

0.05 × ContextModifier
```

Final Priority

```
PriorityScore

=

Clamp(

PriorityRaw,

0,

100

)
```

---

# 12. Clinical Rule Contribution

Triggered clinical rules contribute according to severity and confidence.

```
RuleContribution =

RuleSeverity

×

RuleConfidence

×

PersistenceWeight

×

PriorityWeight
```

Overall Rule Score

```
ClinicalSeverity =

Σ RuleContribution

/

Σ RuleWeights
```

Persistent rules dominate transient abnormalities.

---

# 13. Subsystem Contribution

Subsystem risk is calculated from four physiological domains.

```
Cardiac

Respiratory

Temperature

Mobility
```

Subsystem weighting

```
Cardiac

35%

Respiratory

30%

Temperature

20%

Mobility

15%
```

Formula

```
SubsystemRisk =

0.35(Cardiac)

+

0.30(Respiratory)

+

0.20(Temperature)

+

0.15(Mobility)
```

Future physiological subsystems may be added without changing the interface.

---

# 14. Baseline Deviation

The Priority Engine compares every physiological variable against the personalized baseline.

```
Current Value

↓

Baseline Value

↓

Deviation

↓

Normalized Score
```

Deviation

```
Deviation =

Current

-

Baseline
```

Large deviations increase priority.

Small deviations have minimal influence.

Baseline confidence modifies deviation weighting.

---

# 15. Trend Analysis

Trend analysis detects deterioration over time.

Priority depends upon

• Direction

• Velocity

• Persistence

• Magnitude

Example

```
Heart Rate

85

90

98

110

122

↓

Increasing Trend

↓

Higher Priority
```

Trend Formula

```
TrendScore =

Slope

×

Velocity

×

Persistence
```

Trend scores are normalized between

```
0

↓

100
```

---

# 16. Confidence Adjustment

Confidence determines how strongly evidence influences patient priority.

High confidence increases trust.

Low confidence suppresses unreliable evidence.

```
AdjustedPriority =

PriorityScore

×

Confidence
```

Example

```
Priority

82

Confidence

0.95

↓

78

Priority

82

Confidence

0.35

↓

29
```

Confidence SHALL never increase patient priority beyond the calculated score.

It may only reduce unreliable recommendations.

---

# 17. Context Awareness

Physiology must always be interpreted within context.

Examples

```
Heart Rate

160

Running

↓

Expected

↓

Small Modifier
```

```
Heart Rate

160

Sleeping

↓

Unexpected

↓

Large Modifier
```

Supported contexts

• Resting

• Walking

• Running

• Sleeping

• Recovery

• Unknown

Context SHALL modify priority without overriding physiological evidence.

---

# 18. Temporal Persistence

Transient abnormalities SHALL NOT immediately escalate patient priority.

Each abnormality must satisfy persistence requirements.

Example

```
One Window

↓

Watch

Three Windows

↓

Concern

Five Windows

↓

High Priority
```

Persistence prevents motion artifacts and isolated sensor noise from triggering alerts.

---
# 19. Priority State Machine

The Priority Engine SHALL maintain a continuous patient state.

Patient state SHALL prevent oscillation between priority levels caused by transient physiological changes.

```
NORMAL
   │
   ▼
WATCH
   │
   ▼
CONCERN
   │
   ▼
HIGH PRIORITY
   │
   ▼
CRITICAL
```

Each state transition SHALL require evidence persistence.

Patients SHALL never transition more than one priority level per processing window unless a Critical Override Rule is triggered.

---

# 20. Escalation Logic

Priority escalation SHALL occur when all required conditions are satisfied.

Required Conditions

• Physiological deterioration detected

• Confidence above threshold

• Signal quality acceptable

• Persistence criteria satisfied

• Trend worsening

Escalation Example

```
Minute 0

Priority = WATCH

↓

Minute 5

Persistent Tachycardia

↓

Minute 10

Respiratory Risk Increasing

↓

Priority

CONCERN
```

Rapid deterioration may bypass intermediate states when Critical Rules are activated.

---

# 21. De-escalation Logic

Priority SHALL decrease only after sustained physiological recovery.

Required Recovery Conditions

• Clinical rules resolved

• Trend improving

• Confidence acceptable

• Stable physiological signals

• Recovery persistence achieved

Example

```
Critical

↓

High Priority

↓

Concern

↓

Watch

↓

Normal
```

Priority SHALL NOT immediately return to Normal after one healthy measurement.

Recovery must be gradual.

---

# 22. Alert Suppression

The Priority Engine SHALL minimize unnecessary clinical alerts.

Alert suppression SHALL occur when

• Signal quality is poor

• Motion artifact detected

• Confidence below threshold

• Abnormality duration too short

• Duplicate alert recently generated

Suppression SHALL NEVER hide Critical Events.

Critical Rules always override suppression logic.

---

# 23. Priority Persistence

Persistent abnormalities indicate greater clinical importance.

Persistence Weight

```
<30 seconds

↓

Very Low

30-120 seconds

↓

Low

2-5 minutes

↓

Medium

5-15 minutes

↓

High

>15 minutes

↓

Maximum
```

Persistence SHALL increase contribution to Priority Score.

---

# 24. Critical Override Rules

Certain physiological events bypass normal priority calculations.

Examples

• Severe hypoxemia

• Extreme bradycardia

• Extreme tachycardia

• Cardiac arrest indicators

• Sensor-confirmed collapse

Critical Override SHALL immediately assign

```
Priority = CRITICAL
```

while preserving explainability information.

---

# 25. Explainability Interface

Every Priority Decision SHALL generate human-readable evidence.

Output

```typescript
PriorityExplanation{

PrimaryReason

SecondaryReasons[]

Evidence[]

SubsystemContributors[]

ClinicalRules[]

TrendSummary

ConfidenceSummary

}
```

Example

```
Priority

HIGH

Reason

Persistent Tachycardia

Secondary

Increasing Respiratory Risk

Evidence

Heart Rate +42%

RR +31%

Confidence

94%
```

Every priority score must be reproducible from recorded evidence.

---

# 26. Recommended Clinical Actions

Priority SHALL include a suggested response.

| Priority | Recommendation |
|-----------|----------------|
| Normal | Continue Monitoring |
| Watch | Increase Observation |
| Concern | Notify Clinical Staff |
| High Priority | Immediate Assessment |
| Critical | Emergency Response |

Recommendations are advisory.

Final clinical decisions remain the responsibility of healthcare professionals.

---

# 27. Configuration

All Priority Engine parameters SHALL remain configurable.

Example

```yaml
priority:

clinicalWeight: 0.30

subsystemWeight: 0.25

trendWeight: 0.15

baselineWeight: 0.15

confidenceWeight: 0.10

contextWeight: 0.05

criticalThreshold: 80

highThreshold: 60

concernThreshold: 40

watchThreshold: 20

minimumConfidence: 0.60
```

No source code modification should be required to adjust weighting.

---

# 28. Error Handling

The Priority Engine SHALL remain operational despite partial failures.

Possible Errors

• Missing subsystem output

• Corrupted feature vector

• Missing baseline

• Low signal quality

• Confidence unavailable

Recovery Strategy

• Continue with available evidence

• Reduce confidence

• Log warning

• Preserve system availability

The engine SHALL fail gracefully.

---

# 29. Interfaces

### Input

```typescript
PriorityInput{

SubsystemResults[]

ClinicalRules[]

ConfidenceResult

BaselineDeviation

TrendSummary

SignalQuality

Context

PatientHistory

}
```

### Output

```typescript
PriorityResult{

PriorityScore

PriorityLevel

Confidence

RecommendedAction

AlertRequired

ReasonCodes[]

Explanation

Timestamp

}
```

---

# 30. Processing Pipeline

```
Incoming Features

↓

Clinical Rules

↓

Subsystem Scores

↓

Baseline Comparison

↓

Trend Analysis

↓

Confidence Fusion

↓

Priority Calculation

↓

State Machine

↓

Alert Decision

↓

Explainability

↓

Dashboard
```

---

# 31. Folder Structure

```
priority/

├── engine.py

├── priority_calculator.py

├── weighting.py

├── persistence.py

├── escalation.py

├── suppression.py

├── state_machine.py

├── explainability.py

├── interfaces.py

├── config.py

└── tests/
```

---

# 32. Processing Pseudocode

```python
Receive Feature Vector

↓

Load Patient Baseline

↓

Receive Clinical Rules

↓

Receive Subsystem Scores

↓

Compute Baseline Deviation

↓

Analyze Trends

↓

Apply Context Modifiers

↓

Apply Confidence Weighting

↓

Calculate Priority Score

↓

Update Patient State

↓

Evaluate Alert Rules

↓

Generate Explainability Report

↓

Return Priority Result
```

---

# 33. Performance Requirements

The Priority Engine SHALL

• Process continuously

• Support real-time monitoring

• Produce deterministic outputs

• Operate independently for each patient

• Support concurrent execution

Target latency

```
<100 milliseconds
```

per evaluation window.

---

# 34. Success Criteria

The Priority Engine is considered successful when it

✓ Correctly integrates all evidence streams

✓ Produces deterministic priority scores

✓ Generates explainable recommendations

✓ Minimizes false alarms

✓ Detects gradual deterioration

✓ Detects rapid deterioration

✓ Supports personalized monitoring

✓ Operates in real time

✓ Integrates with all SENTRA modules

---

# 35. Future Improvements

Future versions may include

• Reinforcement Learning priority optimization

• Federated learning across hospital sites

• Population-specific weighting

• ICU-specific priority profiles

• Pediatric priority models

• Predictive deterioration forecasting

• Adaptive clinician feedback weighting

• Large Language Model clinical summarization

---

# 36. Summary

The Priority Engine is the core intelligence layer of SENTRA.

Rather than relying on a single Early Warning Score, it continuously integrates clinical rules, subsystem risk, baseline deviations, temporal trends, contextual information, and confidence estimates into a single explainable patient priority.

By separating evidence generation from decision prioritization, the Priority Engine provides a modular, transparent, and clinically interpretable architecture capable of supporting real-time patient monitoring while minimizing false alarms and enabling scalable future enhancements.

---