# SENTRA — Smart Edge Network for Triage and Response Assistance

> Explainable AI platform for continuous physiological monitoring and clinical prioritization.

Offline-first adaptive patient prioritization, built around the modular
pipeline defined in `docs/00_Project_Overview.md` through
`docs/16_User_Interface_and_Embedded_Display_Specification.md`.

---

# Documentation Hierarchy

Per `CLAUDE.md`, treat documentation in this order:

```
CLAUDE.md          (engineering constitution — read first)
ARCHITECTURE.md     (master pipeline reference)
README.md           (this file)
docs/00 -> docs/16   (per-module technical specs)
docs/HARDWARE_SCOPE.md  (reconciles the spec's sensor list against actual ordered hardware)
Source code
```

---

# Repository Structure

```
SENTRA_SOFTWARE/
  README.md
  CLAUDE.md
  ARCHITECTURE.md
  docs/            technical specification (00-16) + HARDWARE_SCOPE.md
  research/        (reserved — clinical references, validation notes)
  backend/         Python implementation of the pipeline
    sentra/
      models.py           shared data contracts (Doc 02)
      sensor_layer/        Doc 03
      preprocessing/        Doc 04
      signal_quality/        Doc 05
      feature_engine/         Doc 06
      baseline_engine/         Doc 07
      clinical_rules/           Doc 08
      subsystem_scoring/         Doc 09
      confidence_fusion/          Doc 10
      priority/                    Doc 11
      explainability/                Doc 12
      pipeline.py          orchestrates all of the above in order
      simulator.py         stands in for real wearables until hardware exists
      database.py          SQLite persistence
    config/
      weights.yaml         every tunable weight/threshold (CLAUDE.md: no hardcoded thresholds)
    dashboard/
      app.py               interim Streamlit UI (Doc 16's full embedded UI is not built yet)
  firmware/
    patient_node/          ESP32 firmware: MAX30102, MAX30205, MPU6050, BLE
  hardware/               BOM / wiring notes
  tests/                  pytest suite
```

---

# Hardware Scope

The spec (Doc 03) lists ECG + PPG + IMU + Temperature as MVP sensors. The
wearable actually being built uses **MAX30102 (PPG) + MAX30205 (Temperature)
+ MPU6050 (IMU) — no ECG.** Every module in this codebase is scoped to that
real hardware; see `docs/HARDWARE_SCOPE.md` for exactly what changed and why,
and how to re-add ECG support later without a redesign.

---

# Running It

```
cd backend
pip install -r requirements.txt

# Terminal 1: simulated patient nodes (stand-in for real BLE hardware)
python -m sentra.run_simulation

# Terminal 2: dashboard
streamlit run dashboard/app.py
```

---

# What's Implemented vs. Deferred

Implemented this pass, per `docs/00-12`:

- Full deterministic pipeline: sensor input -> preprocessing -> signal
  quality -> feature extraction -> baseline engine -> clinical rules ->
  subsystem scoring -> confidence fusion -> priority engine ->
  explainability engine, wired end to end and runnable against the
  simulator.
- ESP32 firmware emitting the Doc 02 `SensorPacket` schema over BLE.

Explicitly deferred (see `docs/13_Development_Architecture.md` and
`docs/16_User_Interface_and_Embedded_Display_Specification.md` — these
describe production/ML/UI phases this pass does not attempt):

- **Doc 13 (Model Training & Validation)** — the subsystem risk engines are
  deterministic rule/deviation-based scorers, not trained ML models. There
  is no labeled clinical dataset to train against yet; CLAUDE.md prohibits
  inventing one. Doc 08 explicitly allows this ("Clinical Rules excel at
  recognizing known physiological danger" — ML is additive, not required).
- **Doc 15 (Production Operations)** — no FastAPI service, Redis Streams,
  TimescaleDB, or Kubernetes deployment. The backend runs as a local Python
  process against SQLite, consistent with an MVP that has one Hub and no
  hospital network to integrate with yet.
- **Doc 16 (Embedded Touchscreen UI)** — the full multi-role (nurse/
  physician/admin/biomedical-tech) React-style embedded interface with
  Alert Center, Device Management, and Administration is not built. The
  Streamlit dashboard in `backend/dashboard/` covers the Doc 16 §7-13 home
  dashboard concepts (priority queue, patient cards, confidence, live
  refresh) as an interim substitute.

---

# License

Private — Proprietary. Copyright (c) SENTRA AI.
