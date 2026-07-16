# Hardware Scope Reconciliation

Status: Active engineering decision, not part of the original 00-16 spec set.

---

# 1. Purpose

Documents 00-16 define SENTRA's MVP sensor layer as ECG + PPG + IMU + Skin
Temperature (Document 03, Section 3). The wearable hardware actually
designed and ordered for the SENTRA Patient Node — per the original hardware
pitch and `firmware/patient_node/` — is:

| Sensor | Chip | Maps to spec modality |
|---|---|---|
| Pulse oximeter | MAX30102 | PPG (heart rate, SpO2, pulse waveform) |
| Skin temperature | MAX30205 | Temperature |
| Accelerometer/gyro | MPU6050 | IMU |

**There is no ECG sensor in the ordered hardware.** ECG requires
electrodes and dedicated front-end hardware (e.g. an ADS1292) that is not
part of the current wearable design.

---

# 2. Decision

Rather than silently dropping ECG from the implementation, or writing
ECG-specific signal processing code (bandpass/notch filtering at 250-500 Hz,
QRS/QT detection, HRV from R-R intervals) with no hardware that will ever
produce that data to validate it against, this codebase:

- **Keeps ECG in the shared data model** (`backend/sentra/models.py`) —
  `SensorType.ECG` exists, `CardiacFeatures` still has ECG-only fields
  (`QTInterval`, `QRSDuration`, `PRInterval`) — so a future ECG sensor can
  be added without a schema change, per Document 03 Section 4 ("no
  architectural changes shall be required when new sensors are added").
- **Does not implement ECG preprocessing, ECG signal quality, or
  ECG-specific clinical rules** (CR-006 QT Prolongation, CR-007 Irregular
  Rhythm, QRS/PR-based features). These are stubbed as `NotImplemented` /
  omitted rather than faked.
- **Derives cardiac features from PPG instead of ECG** — pulse rate stands
  in for heart rate, and HRV-style variability is estimated from
  peak-to-peak pulse timing rather than R-R intervals. This is a real,
  documented limitation: PPG-derived HRV is noisier and less clinically
  validated than ECG-derived HRV. It is what the ordered hardware can
  actually measure.
- **Reweights every formula in Docs 05/09/11 that assumed ECG was present**
  (Overall SQI, Subsystem Risk, Cardiac Risk Engine inputs) to drop the ECG
  term and redistribute its weight — documented per-module in
  `backend/sentra/config/weights.yaml`, not hardcoded, per CLAUDE.md.

---

# 3. What this means for each module

| Module | Spec (Docs 00-16) | This implementation |
|---|---|---|
| Sensor Layer | ECG, PPG, IMU, Temp | PPG, IMU, Temp (ECG packet type accepted, unrouted) |
| Preprocessing | ECG + PPG + IMU + Temp pipelines | PPG + IMU + Temp only |
| Signal Quality | ECG 40% / PPG 30% / IMU 20% / Temp 10% | PPG 55% / IMU 25% / Temp 20% |
| Feature Extraction | 15 ECG + 12 PPG + 9 IMU + 5 Temp | 12 PPG + 9 IMU + 5 Temp (cardiac features sourced from PPG) |
| Clinical Rules | CR-001..007 (cardiac) | CR-001..005 only (HR-based; QTc/QRS/PR rules omitted) |
| Subsystem Scoring | Cardiac 35% / Resp 30% / Temp 20% / Mobility 15% | Cardiac 30% / Resp 35% / Temp 20% / Mobility 15% (cardiac downweighted — PPG-derived HR/HRV is a weaker cardiac signal than ECG) |

---

# 4. On-node vs. Hub-side feature extraction

Docs 03/04/06 assume raw waveforms (100 Hz PPG, 50 Hz IMU) stream to the Hub
and get filtered/feature-extracted there. The actual `firmware/patient_node/`
does beat detection and motion-magnitude calculation **on the ESP32** and
transmits per-second scalar values (HR, SpO2 estimate, motion magnitude,
skin temperature) instead of raw ADC samples — a deliberate earlier design
choice to keep BLE payloads small and avoid streaming raw optical waveforms
over a constrained link.

Consequence for this codebase: `SignalWindow.ppg` / `.imu` / `.temperature`
hold per-second scalar time series, not raw waveforms. `preprocessing/`
therefore implements outlier/spike rejection, motion-based artifact
flagging, and light smoothing on those scalar streams — the same *purpose*
Doc 04 describes (remove noise before it reaches feature extraction) using
methods suited to what the hardware actually sends, rather than literal
bandpass/notch filtering of a waveform that was never transmitted.

If a future firmware revision streams raw PPG waveform instead, `ppg.py`
would need a real bandpass filter per Doc 04 §9 — the module boundary
already anticipates this; only its internals would change.

---

# 4b. Respiratory rate and true HRV are not available

Doc 06 §7 derives respiratory rate from PPG waveform modulation (RIIV/RIFV/
RIAV — the pulse amplitude/frequency subtly varies with breathing). That
technique needs the continuous optical waveform; it does not work on a
once-per-second precomputed HR/SpO2 scalar. Likewise Doc 06 §6's RMSSD/
SDNN/pNN50 need beat-to-beat interval timing, not a 1 Hz averaged HR.

This codebase leaves `RespiratoryFeatures.respiratory_rate`,
`.perfusion_index`, and `CardiacFeatures.rmssd/.sdnn/.pnn50` as `None`
rather than fabricating a value (CLAUDE.md: "Never fabricate medical
values"). `.heart_rate_variability` is populated as a coarse proxy (std
of the per-second HR trace) and is explicitly documented in
`feature_engine/ppg_features.py` as not equivalent to true beat-to-beat
HRV. Clinical rules and subsystem scoring that would depend on respiratory
rate (RR-001, RR-002, RR-005) are skipped rather than evaluated against a
missing value — see `clinical_rules/respiratory_rules.py`.

Respiratory subsystem scoring instead relies on SpO2 level/trend and
motion-adjusted context, which the hardware genuinely measures.

---

# 5. Re-adding ECG later

If ECG hardware is added to the Patient Node:

1. Implement `backend/sentra/preprocessing/ecg.py` per Document 04 Section 8.
2. Implement `backend/sentra/signal_quality/ecg_quality.py` per Document 05 Section 7.
3. Implement `backend/sentra/feature_engine/ecg_features.py` per Document 06 Section 6.
4. Add CR-006/CR-007 to `backend/sentra/clinical_rules/cardiac_rules.py`.
5. Restore the original SQI/Subsystem weight splits in `weights.yaml`.

No other module requires modification — this is the explicit guarantee
Document 01 Section 18 and Document 03 Section 4 make about future sensor
expansion, and it held in practice while writing this codebase.
