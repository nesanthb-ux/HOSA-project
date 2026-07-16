# SENTRA Technical Design Specification
## Document 03 — Sensor Input Layer

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies
- 00_Project_Overview.md
- 01_System_Architecture.md
- 02_Data_Model.md

Required By
- 04_Preprocessing.md
- 05_Signal_Quality.md
- 06_Feature_Extraction.md

---

# 1. Purpose

The Sensor Input Layer is responsible for receiving, validating, synchronizing, and buffering incoming physiological data from wearable devices.

This layer serves as the gateway between physical hardware and the SENTRA processing pipeline.

No downstream module shall communicate directly with wearable devices.

Every sensor must first pass through the Sensor Input Layer.

---

# 2. Responsibilities

The Sensor Input Layer SHALL

• Receive streaming sensor data

• Register wearable devices

• Verify packet integrity

• Timestamp all incoming packets

• Synchronize multiple sensors

• Buffer incoming streams

• Detect hardware failures

• Monitor battery status

• Monitor connection quality

• Forward synchronized windows to preprocessing

---

# 3. Supported Sensors (MVP)

The MVP supports the following wearable sensors.

## ECG

Purpose

Electrical cardiac activity.

Primary Outputs

• Heart Rate

• HRV

• Rhythm Analysis

• Cardiac Features

Recommended Sampling Rate

250–500 Hz

Priority

Critical

---

## PPG

Purpose

Optical blood flow monitoring.

Primary Outputs

• Heart Rate

• SpO₂

• Respiratory Rate

• Pulse Morphology

Recommended Sampling Rate

100–200 Hz

Priority

Critical

---

## IMU

Components

Accelerometer

Gyroscope

Purpose

Movement detection.

Outputs

• Activity

• Motion

• Orientation

• Fall Detection

• Sleep Estimation

Recommended Sampling Rate

50–100 Hz

Priority

High

---

## Skin Temperature

Purpose

Continuous temperature monitoring.

Outputs

• Skin Temperature

• Temperature Trend

• Fever Trend

Sampling Rate

1–10 Hz

Priority

Medium

---

# 4. Future Sensor Support

The architecture supports future integration of

• Respiratory Belt

• Blood Pressure

• Continuous Glucose Monitor

• EEG

• EDA (Electrodermal Activity)

• EMG

No architectural changes shall be required when new sensors are added.

---

# 5. Sensor Registration

Every wearable device SHALL register with SENTRA before streaming.

Required Registration Information

```
Device ID

Patient ID

Sensor Type

Firmware Version

Sampling Rate

Battery Level

Connection Type

Device Manufacturer
```

Registered devices receive a unique internal identifier.

---

# 6. Packet Structure

Each incoming transmission SHALL follow the SensorPacket schema defined in Document 02.

Example

```json
{
"packetID":"PKT-20260715-0001",
"patientID":"P001",
"sensorType":"ECG",
"timestamp":"2026-07-15T10:30:22Z",
"samplingRate":250,
"values":[...]
}
```

Packets not matching the schema SHALL be rejected.

---

# 7. Streaming Architecture

The Sensor Layer uses continuous streaming.

```
Wearable Device

↓

Bluetooth LE

↓

Sensor Input Service

↓

Packet Validation

↓

Time Synchronization

↓

Ring Buffer

↓

Signal Window Builder

↓

Preprocessing
```

No downstream module receives individual packets.

Only complete windows are forwarded.

---

# 8. Window Construction

Incoming packets are collected into fixed-length windows.

MVP Window Size

30 seconds

Window Overlap

50%

Example

```
Window 1

0–30 sec

Window 2

15–45 sec

Window 3

30–60 sec
```

Window overlap enables smoother trend analysis and reduces boundary effects.

---

# 9. Time Synchronization

Different sensors sample at different frequencies.

The Sensor Layer SHALL synchronize all incoming data to a common timeline.

Synchronization Steps

1.

Receive timestamps

↓

2.

Correct clock drift

↓

3.

Align timestamps

↓

4.

Resample if necessary

↓

5.

Create synchronized window

---

# 10. Buffer Management

Every sensor owns a circular buffer.

Purpose

Store incoming packets until enough data exists to build a window.

Advantages

• Low memory usage

• Continuous streaming

• No duplicate storage

Default Buffer Size

60 seconds

---

# 11. Packet Validation

Every packet undergoes validation.

Validation Rules

Timestamp exists

Patient ID exists

Sensor ID exists

Packet not duplicated

Packet length valid

Sampling rate valid

Checksum valid (if supported)

Packet order verified

Failed packets are discarded.

---

# 12. Connection Monitoring

The Sensor Layer continuously monitors

Battery

Signal Strength

Packet Loss

Latency

Connection Status

Reconnect Attempts

These values are forwarded to the dashboard.

---

# 13. Packet Loss Handling

Packet loss is classified.

Low

<2%

Continue processing.

Moderate

2–10%

Interpolate if possible.

High

>10%

Reduce confidence.

Critical

>25%

Disable affected sensor.

---

# 14. Clock Drift Correction

Wearable devices slowly drift over time.

The synchronization engine SHALL periodically correct timestamps.

Algorithm

```
Device Time

↓

Reference Clock

↓

Calculate Offset

↓

Adjust Future Packets
```

This prevents sensor misalignment during long monitoring sessions.

---

# 15. Sensor Health Score

Every connected sensor receives a health score.

Factors

Battery

Packet Loss

Latency

Signal Stability

Connection Quality

Output

```
0–100
```

Sensors below 50 generate maintenance warnings.

---

# 16. Sensor Failure Recovery

If a sensor disconnects

↓

Pause acquisition

↓

Attempt reconnect

↓

Restore stream

↓

Resume buffering

If reconnection fails

↓

Mark sensor inactive

↓

Continue using remaining sensors

The system SHALL degrade gracefully.

---

# 17. Data Security

All packets SHALL include

Patient ID

Timestamp

Device ID

Checksum

Transmission SHALL use encrypted Bluetooth communication when available.

Raw physiological data SHALL never be modified in this layer.

---

# 18. Technology Stack

Language

Python 3.12

Streaming Framework

FastAPI

Bluetooth

Bleak

Data Validation

Pydantic

Data Serialization

JSON

Message Queue

Redis Streams (MVP)

Future Upgrade

Apache Kafka

---

# 19. Folder Structure

```
sensor_layer/

├── bluetooth.py

├── packet_validator.py

├── synchronization.py

├── ring_buffer.py

├── device_manager.py

├── sensor_health.py

├── packet_router.py

└── models.py
```

---

# 20. Module Interface

Input

```
Raw Sensor Packets
```

Output

```
SignalWindow
```

Execution Frequency

Continuous

Maximum Latency

100 milliseconds

---

# 21. Success Criteria

The Sensor Input Layer is considered successful when it

• Accepts multiple simultaneous wearable streams

• Synchronizes all modalities

• Detects packet corruption

• Handles packet loss gracefully

• Builds continuous overlapping windows

• Forwards standardized SignalWindow objects to the preprocessing layer

---

# 22. Summary

The Sensor Input Layer forms the foundation of the SENTRA pipeline by transforming asynchronous wearable streams into synchronized, validated SignalWindow objects. Every downstream algorithm relies on this layer to provide accurate timing, reliable buffering, and high-integrity physiological data while remaining hardware-agnostic and extensible for future sensor integration.