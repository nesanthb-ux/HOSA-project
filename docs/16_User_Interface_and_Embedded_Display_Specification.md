# SENTRA Technical Design Specification
## Document 16 — User Interface & Embedded Display Specification

# PART 1 — Product Design System & Dashboard Architecture

Version: MVP v0.1

Status: Draft

Owner: SENTRA Product Design Team

Dependencies

- 00_Project_Overview.md
- 01_System_Architecture.md
- 02_Data_Model.md
- 03_Sensor_Layer.md
- 04_Signal_Preprocessing.md
- 05_Feature_Extraction.md
- 06_Baseline_Engine.md
- 07_Clinical_Rules.md
- 08_Subsystem_Scoring.md
- 09_Confidence_Fusion.md
- 10_Priority_Engine.md
- 11_Explainability_Engine.md
- 12_Model_Training_and_Validation.md
- 13_Development_Architecture.md
- 14_MVP_Deployment_Roadmap.md
- 15_System_Integration_and_Operations.md

---

# 1. Purpose

The SENTRA User Interface serves as the primary interaction layer between clinicians and the SENTRA AI platform.

Unlike conventional Electronic Health Record (EHR) dashboards that prioritize documentation, the SENTRA interface is designed around **real-time physiological awareness**, enabling clinicians to recognize patient deterioration within seconds.

Every design decision is guided by three principles:

• Rapid recognition

• Minimal cognitive load

• Complete explainability

The interface SHALL never hide important clinical information behind unnecessary navigation or complex workflows.

---

# 2. Design Philosophy

The interface is inspired by

• Apple Human Interface Guidelines

• Tesla vehicle interfaces

• Linear.app workflow simplicity

• Modern ICU monitoring systems

• Aviation cockpit ergonomics

The UI SHALL feel

• Modern

• Clean

• Calm

• Clinical

• High-performance

NOT

❌ Busy

❌ Flashy

❌ Corporate

❌ Cluttered

❌ Difficult to learn

---

# 3. Design Goals

The clinician should understand

within **3 seconds**

• Which patients require attention

within **5 seconds**

• Why the patient is deteriorating

within **10 seconds**

• What action should be taken

Everything else is secondary.

---

# 4. User Types

### Nurse

Responsibilities

• Monitor assigned patients

• Acknowledge alerts

• Review trends

• Escalate concerns

---

### Physician

Responsibilities

• Clinical assessment

• Decision support

• Review explanations

• Analyze historical deterioration

---

### Administrator

Responsibilities

• User management

• Device monitoring

• System configuration

• Analytics

---

### Biomedical Technician

Responsibilities

• Hub diagnostics

• Sensor pairing

• Firmware updates

• Device maintenance

---

# 5. Embedded Hub Design

The MVP is designed around a dedicated SENTRA Hub.

Characteristics

✓ Always On

✓ Touchscreen

✓ Fanless

✓ Silent

✓ Medical Grade

✓ Continuous Operation

The interface SHALL adapt automatically to displays ranging from 7–24 inches.

---

# 6. Navigation Architecture

```
HOME

│

├── Patient Queue

│      │

│      ├── Patient Details

│      │        │

│      │        ├── Live Monitoring

│      │        ├── Trends

│      │        ├── Explainability

│      │        ├── Clinical Rules

│      │        ├── Timeline

│      │        └── History

│

├── Alerts

├── Analytics

├── Devices

├── Diagnostics

├── Settings

└── Administration
```

Maximum navigation depth

```
3 Levels
```

No workflow shall require more than three taps.

---

# 7. Dashboard Layout

```
┌───────────────────────────────────────────────┐
│ SENTRA                     09:42             │
├───────────────────────────────────────────────┤
│                                               │
│ Priority Queue          Live Overview         │
│                                               │
│ Critical Patients       Device Status         │
│                                               │
│ High Priority           Alerts               │
│                                               │
│ Watch                   Statistics           │
│                                               │
├───────────────────────────────────────────────┤
│ Bottom Navigation                           │
└───────────────────────────────────────────────┘
```

---

# 8. Home Dashboard Components

The dashboard SHALL contain

## Patient Queue

Automatically sorted by Priority Score.

---

## Live Patient Count

```
Patients Online

34
```

---

## Critical Count

```
Critical

2
```

---

## Active Alerts

```
Alerts

5
```

---

## Device Health

```
Hub

Healthy

Sensors

Connected

Cloud

Online
```

---

## System Status

```
Processing

Normal

Latency

43 ms

Uptime

127 Hours
```

---

# 9. Dashboard Widgets

Each widget SHALL be modular.

Widgets include

• Patient Queue

• Live Statistics

• Alert Feed

• System Status

• Connectivity

• Device Health

• AI Processing

• Quick Actions

Widgets SHALL be independently refreshable.

---

# 10. Patient Queue

Patients SHALL automatically reorder.

Priority

```
CRITICAL

↓

HIGH

↓

CONCERN

↓

WATCH

↓

NORMAL
```

Sorting options

• Priority

• Room

• Name

• Last Update

• Time Since Alert

• Heart Rate

• Respiratory Rate

• Confidence

---

# 11. Patient Card

Every patient SHALL appear as a modern information card.

Example

```
────────────────────────────

John Smith

Room 12

Priority

HIGH

HR

124 BPM

RR

28

SpO₂

93%

Confidence

96%

Updated

2 sec ago

────────────────────────────
```

Touching anywhere on the card SHALL open the Patient Detail View.

---

# 12. Priority Indicators

Priority SHALL use

Large badge

Color

Icon

Animation

Text

Example

🟥 HIGH PRIORITY

rather than relying solely on color.

---

# 13. Dashboard Refresh

Live vitals

1 second

Priority

Immediate

Alerts

Immediate

Device Status

5 seconds

Analytics

30 seconds

No manual refresh button shall be required.

---

# 14. Color System

```
NORMAL

#2ECC71

WATCH

#F1C40F

CONCERN

#E67E22

HIGH

#E74C3C

CRITICAL

#8E0000
```

Neutral colors

Dark Gray

Light Gray

White

Blue (Information)

Colors SHALL satisfy accessibility contrast requirements.

---

# 15. Typography

Heading

32 px

Section

24 px

Card Title

20 px

Vitals

18 px

Body

16 px

Critical Values

36 px

Typography SHALL prioritize readability from 1–2 meters.

---

# 16. Spacing System

Base Grid

```
8 px
```

Spacing

8

16

24

32

48

64

No arbitrary spacing values SHALL be used.

---

# 17. Card System

Every information block SHALL use reusable cards.

Example

```
┌──────────────────────┐

Heart Rate

124 BPM

Normal Range

60-100

└──────────────────────┘
```

Cards SHALL support

• Hover (future desktop)

• Touch

• Loading

• Error

• Expanded

• Collapsed

---

# 18. Bottom Navigation

```
Dashboard

Patients

Alerts

Analytics

Devices

Settings
```

Icons SHALL accompany labels.

---

# 19. Loading States

Instead of blank screens

Skeleton Loading SHALL be used.

Example

██████████

██████

██████████████

No spinner-only interfaces.

---

# 20. Empty States

Examples

"No Active Alerts"

"No Connected Patients"

"No Sensor Issues"

Every empty state SHALL explain what the user is seeing.

---

# 21. Error States

The interface SHALL gracefully handle

• Sensor offline

• API unavailable

• Lost Wi-Fi

• Low battery

• Cloud disconnected

Errors SHALL never crash the interface.

Instead they SHALL display recovery guidance.

---

# 22. Microinteractions

Animations SHALL be subtle.

Examples

Patient priority increases

↓

Card gently moves upward

New alert

↓

Soft pulse

Critical alert

↓

Controlled red border animation

Animations SHALL never distract clinicians.

---

# 23. Touch Targets

Minimum size

```
48x48 px
```

Preferred

```
56x56 px
```

Supports gloved operation.

---

# 24. Performance Targets

Touch Response

<100 ms

Dashboard Refresh

<1 sec

Navigation

<200 ms

Screen Load

<500 ms

The interface SHALL feel instantaneous.

---

# End of Part 1

Part 2 contains the complete Patient Detail View, Explainability Interface, Historical Analytics, Clinical Timeline, Baseline Comparison, Confidence Engine visualization, and every interaction available after selecting a patient from the dashboard.
# PART 2 — Patient Workspace & Clinical Interface

---

# 25. Patient Detail View

Selecting a patient SHALL open the complete clinical workspace.

This screen represents the primary working environment for nurses and physicians.

The Patient Detail View SHALL integrate outputs from

• Baseline Engine

• Clinical Rules Engine

• Subsystem Scoring

• Confidence Fusion

• Priority Engine

• Explainability Engine

• Trend Analysis

• Historical Timeline

No information generated by SENTRA shall be inaccessible from this page.

---

# 26. Patient Workspace Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ← Dashboard     Patient 021     HIGH PRIORITY              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Live Vitals             Priority Panel                      │
│                                                             │
│ Trend Charts            Explainability                      │
│                                                             │
│ Clinical Rules          Baseline Comparison                 │
│                                                             │
│ Timeline                Recommended Actions                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Bottom Navigation                                       │
└─────────────────────────────────────────────────────────────┘
```

---

# 27. Patient Header

Displayed Information

Patient Identifier

Room Number

Monitoring Duration

Current Priority

Current Confidence

Device Connection

Sensor Status

Battery Status (if applicable)

Last Updated Timestamp

Example

```
Patient

021

Room

ICU-4

Priority

HIGH

Confidence

96%

Monitoring

18 Hours

Updated

2 Seconds Ago
```

---

# 28. Live Physiological Monitoring

Displayed continuously

Heart Rate

Heart Rate Variability

Respiratory Rate

SpO₂

Skin Temperature

Activity

Signal Quality

Confidence

Each measurement SHALL display

Current Value

Normal Range

Trend Arrow

Historical Sparkline

Example

```
Heart Rate

124 BPM

↑

Normal

60-100
```

---

# 29. Physiological Trends

Every physiological measurement SHALL include an expandable graph.

Supported graphs

Heart Rate

HRV

Respiration

Temperature

SpO₂

Activity

Signal Quality

Priority Score

Confidence

Selectable windows

5 Minutes

15 Minutes

1 Hour

6 Hours

24 Hours

7 Days

---

# 30. Priority Engine Panel

Outputs from Document 10 SHALL appear here.

Displayed

Priority Score

Priority Level

Current State

State History

Risk Trend

Escalation Status

Time Since Last Change

Example

```
Priority Score

87

HIGH PRIORITY

Trend

Increasing

State

Escalating

Time

6 Minutes
```

---

# 31. Explainability Panel

Outputs from Document 11.

Displayed

Primary Reason

Secondary Reasons

Evidence Ranking

Confidence

Clinical Summary

Context

Example

```
Primary

Persistent Tachycardia

Secondary

Reduced HRV

Elevated Respiratory Rate

Confidence

95%
```

Every recommendation SHALL include a human-readable explanation.

---

# 32. Clinical Rules Panel

Displays every active rule.

Example

```
✓ Persistent Tachycardia

Severity

High

Confidence

97%

Triggered

09:31
```

Each rule SHALL display

Status

Severity

Confidence

Trigger Time

Current State

Expected Resolution

---

# 33. Baseline Comparison

Outputs from Baseline Engine.

Example

```
Baseline HR

72 BPM

Current HR

124 BPM

Deviation

+52 BPM
```

Every monitored variable SHALL display

Baseline

Current

Difference

Percent Difference

Trend

---

# 34. Subsystem Scores

Displays independent subsystem outputs.

```
Cardiac

92

█████████

Respiratory

71

███████

Temperature

38

████

Mobility

14

█
```

Touching a subsystem SHALL open additional detail.

---

# 35. Confidence Visualization

Outputs from Confidence Fusion.

Displayed

Overall Confidence

Sensor Quality

Coverage

Missing Data

Prediction Reliability

Example

```
Confidence

96%

Excellent

Signal Quality

98%

Coverage

100%
```

---

# 36. Recommended Clinical Actions

The interface SHALL display recommendations from the Priority Engine.

Example

```
Recommended Action

Immediate Clinical Assessment

Reason

Persistent Tachycardia

Confidence

95%
```

Future versions may integrate hospital protocols.

---

# 37. Historical Timeline

Chronological event log.

Example

```
09:20

Heart Rate Increased

↓

09:26

Respiration Elevated

↓

09:31

Clinical Rule Triggered

↓

09:34

Priority Raised

↓

09:35

Alert Sent

↓

09:36

Viewed by Nurse
```

Every event SHALL be timestamped.

---

# 38. Alert History

Displays

Active Alerts

Resolved Alerts

Suppressed Alerts

Acknowledged Alerts

Each alert SHALL include

Severity

Time

Reason

Acknowledged By

Status

---

# 39. Sensor Status

Every connected sensor SHALL report

Battery

Connection

Signal Quality

Sampling Rate

Firmware

Last Packet Received

Disconnected sensors SHALL display immediately.

---

# 40. Device Health

Displays Hub diagnostics.

CPU Usage

Memory

Storage

Temperature

Network

Database

Cloud

Processing Queue

The clinician SHALL never lose awareness of device health.

---

# 41. Analytics Tab

Provides advanced patient analytics.

Charts

Heart Rate

HRV

Respiration

Temperature

SpO₂

Priority

Confidence

Clinical Rules

Baseline Deviations

Users may overlay multiple physiological signals.

---

# 42. Compare Against Baseline

Users SHALL toggle

Current Values

↓

Baseline Overlay

Example

```
Current

──────────

Baseline

- - - - - -
```

Deviation SHALL be immediately visible.

---

# 43. Explainability Drill-down

Touching any explanation SHALL reveal

Evidence

Calculation

Subsystem

Clinical Rule

Weight

Confidence

Timeline

This provides complete transparency into AI reasoning.

---

# 44. Clinical Notes (Future)

Future releases may support

Clinician Notes

Voice Notes

AI Summaries

Care Plans

These features are outside the MVP scope.

---

# 45. Patient Actions

Available actions

Acknowledge Alert

Refresh Patient

Expand Graphs

Export Report

View Timeline

Open Explainability

Mark Reviewed

Future

Notify Team

Every action SHALL require no more than two taps.

---

# 46. Screen States

The Patient View SHALL support

Loading

Offline

Sensor Error

Missing Data

No Alerts

Historical Mode

Live Mode

Maintenance Mode

Every state SHALL preserve usability.

---

# End of Part 2

Part 3 defines the remaining application: Alert Center, Device Management, Diagnostics, Administration, Settings, Design System, reusable components, API bindings, animations, accessibility, frontend architecture, and complete implementation specifications.
# PART 3 — Clinical Operations, Administration & Frontend Implementation

---

# 47. Alert Center

The Alert Center SHALL function as the centralized command interface for all patient and system alerts.

Alerts SHALL be categorized into:

### Clinical Alerts
- Patient deterioration
- Threshold violations
- Escalating Priority Score
- Confidence degradation
- Critical physiological events

### Technical Alerts
- Sensor disconnect
- Battery low
- Hub overheating
- Database unavailable
- Cloud synchronization failure

### Administrative Alerts
- Firmware updates
- Maintenance reminders
- New user requests
- Audit notifications

---

# 48. Alert Dashboard

```
┌───────────────────────────────────────────────┐
│ ALERT CENTER                                  │
├───────────────────────────────────────────────┤
│ 🔴 Critical (2)                               │
│ 🟠 High (5)                                   │
│ 🟡 Watch (8)                                  │
│ 🔵 Information (14)                           │
├───────────────────────────────────────────────┤
│ Patient 021   Tachycardia         ACKNOWLEDGE │
│ Patient 018   Low SpO₂            VIEW        │
│ Hub          Sensor Offline      DIAGNOSE    │
└───────────────────────────────────────────────┘
```

Alerts SHALL support

- Acknowledge
- Escalate
- Suppress (role dependent)
- View Patient
- View Explainability
- Export Event

---

# 49. Device Management

Every connected device SHALL expose

- Device ID
- Firmware Version
- Serial Number
- Connection Status
- Battery Level
- Signal Quality
- Last Synchronization
- Assigned Patient
- Calibration Status

Selecting a device SHALL open a detailed diagnostics page.

---

# 50. Diagnostics

The Diagnostics page SHALL display

### Hub Health

- CPU Usage
- RAM Usage
- Storage
- Temperature
- Uptime

### Network

- Wi-Fi Status
- Signal Strength
- Latency
- Packet Loss

### AI Services

- Priority Engine Status
- Explainability Engine Status
- Confidence Engine Status
- Processing Queue
- Average Inference Time

### Database

- Connection
- Response Time
- Storage Usage
- Backup Status

---

# 51. Settings

Settings SHALL include

### General

- Language
- Time Format
- Date Format

### Display

- Brightness
- Theme
- Accessibility
- Text Size

### Clinical

- Alert Thresholds
- Notification Rules
- Escalation Policy

### Devices

- Pair Sensor
- Remove Sensor
- Calibration

### Security

- Password
- MFA (Future)
- Session Timeout

---

# 52. Administration

Administrator functions

- User Management
- Role Assignment
- Device Provisioning
- Configuration Management
- Clinical Threshold Updates
- System Logs
- Backup Management
- Audit Review

---

# 53. Audit Log

Every significant action SHALL be recorded.

Examples

```
09:21

Nurse acknowledged alert

09:24

Priority Score changed

09:30

Clinical Rule activated

09:42

Administrator changed threshold

09:45

Firmware updated
```

---

# 54. Authentication

Supported methods

- Username / Password
- Hospital SSO (Future)
- Smart Card (Future)
- Biometric Authentication (Future)

Automatic logout SHALL occur after configurable inactivity.

---

# 55. Offline Mode

If network connectivity is lost

The Hub SHALL

✓ Continue monitoring

✓ Continue processing

✓ Continue prioritization

✓ Queue synchronization

✓ Notify clinician

When connectivity returns

Queued data SHALL synchronize automatically.

---

# 56. Component Library

Reusable components

- Patient Card
- Vital Tile
- Priority Badge
- Confidence Indicator
- Trend Chart
- Timeline
- Alert Banner
- Status Chip
- Modal Dialog
- Navigation Bar
- Search Bar
- Filter Drawer
- Loading Skeleton
- Empty State
- Error State
- Action Button

All components SHALL be reusable throughout the application.

---

# 57. Design Tokens

### Border Radius

```
4 px
8 px
12 px
16 px
```

### Shadows

Small

Medium

Large

### Grid

```
8 px
```

### Icons

Outlined

Rounded

Consistent stroke width

---

# 58. Animation Standards

Animations SHALL communicate state.

Examples

Patient escalation

↓

Card elevation

New alert

↓

Soft pulse

Successful acknowledgement

↓

Brief confirmation

Animations SHALL remain under

```
250 ms
```

---

# 59. Accessibility

The interface SHALL support

- WCAG 2.1 AA
- High Contrast Mode
- Large Text
- Color-blind Safe Indicators
- Keyboard Navigation (future)
- Screen Reader Compatibility (future)

Critical information SHALL never rely solely on color.

---

# 60. Frontend Architecture

```
frontend/

app/

components/

dashboard/

patients/

alerts/

analytics/

devices/

settings/

admin/

api/

hooks/

contexts/

services/

assets/

styles/

themes/

utils/

types/
```

---

# 61. API Integration

Primary APIs

- Authentication API
- Patient API
- Sensor API
- Feature API
- Baseline API
- Clinical Rules API
- Subsystem API
- Confidence API
- Priority API
- Explainability API
- Alert API
- Device API
- Diagnostics API
- Configuration API

All communication SHALL use versioned REST APIs with strongly typed request and response models.

---

# 62. Application State

The frontend SHALL manage

- Authentication
- Active Patient
- Live Vitals
- Alerts
- Device Status
- Network Status
- User Preferences
- Theme
- Cached Historical Data

State SHALL recover gracefully after interruptions.

---

# 63. Real-Time Communication

The UI SHALL receive continuous updates for

- Live vitals
- Priority changes
- Alert generation
- Device health
- Sensor status

Polling SHALL be minimized where persistent connections are available.

---

# 64. Search & Filtering

Users SHALL search by

- Patient ID
- Room
- Name
- Priority
- Alert Status

Filters

- Critical
- High
- Watch
- Assigned Patients
- Active Alerts
- Offline Devices

---

# 65. Clinical Workflow

Typical workflow

```
Dashboard

↓

Patient Selected

↓

Review Live Vitals

↓

Review Explainability

↓

Assess Trends

↓

View Timeline

↓

Review Recommendation

↓

Take Clinical Action

↓

Acknowledge Alert

↓

Return to Dashboard
```

The interface SHALL minimize unnecessary navigation during this workflow.

---

# 66. Future Expansion

Future UI capabilities

- Multi-patient wallboard
- Remote clinician dashboard
- Tablet companion
- Mobile application
- Voice interaction
- AI-generated summaries
- Custom dashboards
- Multi-hospital overview
- Predictive analytics views

---

# 67. Success Criteria

The UI is successful when it

✓ Displays all outputs generated by Documents 00–15

✓ Supports complete patient review from a single workspace

✓ Presents explainable AI decisions

✓ Enables rapid clinical prioritization

✓ Operates continuously on the embedded Hub

✓ Maintains low cognitive load

✓ Supports scalable expansion

✓ Requires minimal training for clinical users

---

# 68. Final Product Vision

The SENTRA Hub SHALL function as a modern clinical command center rather than a traditional monitoring screen.

Every capability implemented within the SENTRA platform—from signal acquisition and feature extraction through baseline modeling, clinical rule evaluation, subsystem scoring, confidence fusion, priority generation, explainability, model validation, deployment, and operations—shall have a corresponding, intuitive, and discoverable representation within the user interface.

The result is a touch-first embedded experience that provides clinicians with continuous situational awareness, transparent AI reasoning, rapid access to patient details, and actionable decision support while remaining responsive, reliable, and scalable for future healthcare deployments.

---