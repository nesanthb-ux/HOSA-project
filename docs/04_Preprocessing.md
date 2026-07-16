# SENTRA Technical Design Specification
## Document 04 — Signal Preprocessing

Version: MVP v0.1

Status: Draft

Owner: SENTRA Architecture Team

Dependencies
- 02_Data_Model.md
- 03_Sensor_Input.md

Required By
- 05_Signal_Quality.md
- 06_Feature_Extraction.md

---

# 1. Purpose

The Signal Preprocessing Layer converts synchronized raw physiological data into clean, standardized signals suitable for feature extraction and clinical analysis.

Its objective is to maximize physiological information while minimizing sensor noise.

No downstream module SHALL receive raw wearable data.

---

# 2. Responsibilities

The preprocessing engine SHALL

• Validate incoming windows

• Detect corrupted data

• Remove baseline drift

• Remove electrical interference

• Remove high-frequency noise

• Standardize sampling rates

• Normalize signal amplitudes

• Handle missing samples

• Preserve timestamps

• Produce clean physiological signals

---

# 3. Inputs

Input Object

```
SignalWindow
```

Contains

• ECG

• PPG

• IMU

• Skin Temperature

• Metadata

---

# 4. Outputs

Output Object

```
ProcessedWindow
```

Contains

• Filtered ECG

• Filtered PPG

• Filtered IMU

• Filtered Temperature

• Processing Log

• Preprocessing Metadata

---

# 5. Overall Pipeline

Every SignalWindow SHALL execute the following pipeline.

```
Incoming Signal Window

↓

Integrity Validation

↓

Missing Data Detection

↓

Filtering

↓

Normalization

↓

Resampling

↓

Synchronization Verification

↓

Processed Window
```

Each stage produces metadata for debugging and explainability.

---

# 6. Integrity Validation

Before processing begins, every signal SHALL pass validation.

Checks include

• Empty signal

• Missing timestamps

• Invalid sampling rate

• Duplicate packets

• Corrupted values

• Out-of-range physiological values

Example

Heart Rate

```
-20 BPM
```

↓

Reject

Temperature

```
108°C
```

↓

Reject

Acceleration

```
Infinity
```

↓

Reject

---

# 7. Missing Data Handling

Missing data is categorized according to duration.

## Level 1

Gap

<250 milliseconds

Action

Linear interpolation.

---

## Level 2

Gap

250 milliseconds–2 seconds

Action

Spline interpolation.

Confidence penalty applied.

---

## Level 3

Gap

>2 seconds

Action

No interpolation.

Mark signal incomplete.

Reduce Signal Quality Index.

---

# 8. ECG Preprocessing

Purpose

Remove electrical noise while preserving cardiac morphology.

Pipeline

```
Raw ECG

↓

Bandpass Filter

↓

Notch Filter

↓

Baseline Wander Removal

↓

Amplitude Normalization

↓

Filtered ECG
```

Recommended Filters

Bandpass

0.5–40 Hz

Notch

50 Hz or 60 Hz

(depending on region)

Baseline Removal

High-pass filter

Moving median

Developers may choose the implementation provided the output characteristics remain equivalent.

---

# 9. PPG Preprocessing

Purpose

Improve pulse morphology while reducing motion contamination.

Pipeline

```
Raw PPG

↓

Bandpass Filter

↓

Motion Compensation

↓

Normalization

↓

Filtered PPG
```

Recommended Frequency

0.5–8 Hz

Future versions may incorporate adaptive filtering.

---

# 10. IMU Preprocessing

Purpose

Prepare motion signals.

Pipeline

```
Accelerometer

↓

Gravity Removal

↓

Low-pass Filter

↓

Normalization

↓

Motion Signal
```

Gyroscope

↓

Noise Filtering

↓

Angular Velocity

↓

Orientation Features

---

# 11. Temperature Preprocessing

Purpose

Remove unrealistic spikes.

Pipeline

```
Temperature

↓

Spike Detection

↓

Moving Average

↓

Filtered Temperature
```

Large discontinuities indicate

• Sensor removal

• Poor skin contact

• Device malfunction

---

# 12. Signal Normalization

Signals shall be normalized before feature extraction.

Methods

ECG

Z-score normalization

PPG

Min-max normalization

Temperature

Centered around baseline

IMU

Unit scaling

Normalization parameters are stored for reproducibility.

---

# 13. Resampling

Different sensors operate at different frequencies.

The preprocessing engine SHALL resample signals to standardized rates.

Recommended Rates

ECG

250 Hz

PPG

100 Hz

IMU

50 Hz

Temperature

1 Hz

Future sensors may define additional standards.

---

# 14. Timestamp Verification

The preprocessing engine verifies synchronization after filtering.

Checks

Maximum timestamp drift

Missing timestamps

Out-of-order samples

Duplicate samples

If synchronization exceeds tolerance

↓

Window flagged

↓

Confidence reduced

---

# 15. Processing Metadata

Every ProcessedWindow SHALL include

```typescript
ProcessingMetadata {

processingTime

filtersApplied

missingSamples

interpolatedSamples

resampled

warnings[]

}
```

This metadata supports debugging and explainability.

---

# 16. Computational Constraints

Maximum processing latency

100 milliseconds

Maximum memory usage

256 MB per patient stream

Processing SHALL occur in streaming mode.

Entire recordings SHALL NOT be loaded into memory.

---

# 17. Error Handling

If preprocessing fails

↓

Attempt recovery

↓

Log failure

↓

Forward warning

↓

Continue processing remaining sensors

No single sensor failure shall terminate the pipeline.

---

# 18. Recommended Technology Stack

Programming Language

Python 3.12

Signal Processing

SciPy

NumPy

NeuroKit2

HeartPy

WFDB

Data Models

Pydantic

Testing

Pytest

Visualization

Matplotlib (development only)

---

# 19. Suggested Folder Structure

```
preprocessing/

├── ecg.py

├── ppg.py

├── imu.py

├── temperature.py

├── interpolation.py

├── normalization.py

├── filtering.py

├── resampling.py

├── validation.py

├── pipeline.py

└── models.py
```

---

# 20. Module Interface

Input

```
SignalWindow
```

Output

```
ProcessedWindow
```

Execution

Continuous

Window Size

30 seconds

Overlap

50%

---

# 21. Pseudocode

```python
function preprocess(window):

    validate(window)

    interpolate_missing(window)

    filter_ecg()

    filter_ppg()

    filter_imu()

    filter_temperature()

    normalize()

    resample()

    verify_synchronization()

    create_processing_metadata()

    return ProcessedWindow
```

---

# 22. Success Criteria

The preprocessing layer is successful when it

• Produces clean synchronized physiological signals

• Preserves clinically relevant waveform morphology

• Correctly handles missing samples

• Maintains real-time performance

• Standardizes all sensor streams

• Produces complete preprocessing metadata

---

# 23. Summary

The Signal Preprocessing Layer is the first computational stage of the SENTRA pipeline. It transforms synchronized raw wearable data into standardized physiological signals through validation, filtering, interpolation, normalization, and resampling. By enforcing a consistent preprocessing workflow, this module ensures that all downstream algorithms operate on high-quality, reproducible inputs while maintaining real-time performance suitable for continuous patient monitoring.