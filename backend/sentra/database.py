"""SQLite persistence for patient identity/calibration and dashboard
snapshots. Doc 15 §5 calls for externalized configuration and Doc 13-15's
production stack (TimescaleDB, Redis) is explicitly deferred — see
README.md "What's Implemented vs. Deferred"."""
from __future__ import annotations

import json
import os
import sqlite3
import threading

from .models import DashboardObject

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sentra.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            name TEXT,
            age_band TEXT,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );

        CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            ts REAL,
            state TEXT,
            priority REAL,
            confidence REAL,
            trend TEXT,
            explanation_json TEXT,
            alerts_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_patient_ts ON dashboard_snapshots(patient_id, ts);
        """
    )
    conn.commit()


def set_patient_calibration(patient_id: str, name: str | None, age_band: str | None) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO patients (patient_id, name, age_band)
           VALUES (?, ?, ?)
           ON CONFLICT(patient_id) DO UPDATE SET name = excluded.name, age_band = excluded.age_band""",
        (patient_id, name or patient_id, age_band),
    )
    conn.commit()


def get_patient(patient_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    return dict(row) if row else None


def record_snapshot(dashboard_object: DashboardObject) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO patients (patient_id, name)
           VALUES (?, ?) ON CONFLICT(patient_id) DO NOTHING""",
        (dashboard_object.patient_id, dashboard_object.patient_id),
    )
    conn.execute(
        """INSERT INTO dashboard_snapshots
           (patient_id, ts, state, priority, confidence, trend, explanation_json, alerts_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            dashboard_object.patient_id,
            dashboard_object.timestamp.timestamp(),
            dashboard_object.patient_state.value,
            dashboard_object.priority,
            dashboard_object.confidence,
            dashboard_object.trend,
            dashboard_object.explanation.model_dump_json() if dashboard_object.explanation else None,
            json.dumps(dashboard_object.alerts),
        ),
    )
    conn.commit()


def get_latest_snapshots() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.* FROM dashboard_snapshots s
           INNER JOIN (
               SELECT patient_id, MAX(ts) AS max_ts FROM dashboard_snapshots GROUP BY patient_id
           ) latest ON s.patient_id = latest.patient_id AND s.ts = latest.max_ts"""
    ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["explanation"] = json.loads(d["explanation_json"]) if d["explanation_json"] else None
        d["alerts"] = json.loads(d["alerts_json"]) if d["alerts_json"] else []
        results.append(d)
    return results


def get_priority_history(patient_id: str, limit: int = 60) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT ts, priority, state FROM dashboard_snapshots
           WHERE patient_id = ? ORDER BY ts DESC LIMIT ?""",
        (patient_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]
