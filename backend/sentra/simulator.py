"""Stands in for real ESP32 Patient Nodes + BLE until hardware exists.
Emits SensorPacket objects matching the same schema
firmware/patient_node/patient_node.ino sends over BLE, so this module can
be swapped for a real hub/ble_manager.py without touching the rest of the
pipeline. Ported from the project's earlier hub/simulator.py; see that
file's history for the original single-sensor-type version.
"""
from __future__ import annotations

import random
from datetime import datetime

from .models import SensorPacket, SensorType


class NodeSimulator:
    SCENARIOS = ("stable", "deteriorating", "intermittent", "fall_event")

    def __init__(self, patient_id: str, device_id: str, scenario: str = "stable",
                 true_hr: float = 75, true_temp: float = 36.8):
        self.patient_id = patient_id
        self.device_id = device_id
        self.scenario = scenario
        self.true_hr = true_hr
        self.true_temp = true_temp
        self.motion = 1.0
        self.battery = 100.0
        self.tick_count = 0
        self.connected = True
        self._disconnect_until = 0

    def tick(self, ts: datetime) -> list[SensorPacket]:
        """Returns the packets this node would send this second (empty
        list while "disconnected"), mirroring the firmware's on-node
        disconnect buffering — the Hub simply never receives them live."""
        self.tick_count += 1
        self.battery = max(0.0, self.battery - 0.002)

        # Events wait past the ~30 min baseline learning window (Doc 07 §7)
        # so the fingerprint has already locked onto a normal baseline
        # before the anomaly happens, instead of the anomaly getting
        # absorbed as "normal" — same timing lesson as the earlier
        # hub/simulator.py.
        if self.scenario == "deteriorating" and self.tick_count > 200:
            self.true_hr += 0.15
            self.true_temp += 0.003
            self.motion = max(0.1, self.motion - 0.01)

        if self.scenario == "fall_event":
            if self.tick_count == 220:
                self.motion = 9.0
            elif self.tick_count == 225:
                self.motion = 1.0

        if self.scenario == "intermittent":
            if self.connected and random.random() < 0.02:
                self.connected = False
                self._disconnect_until = self.tick_count + random.randint(5, 15)
            elif not self.connected and self.tick_count >= self._disconnect_until:
                self.connected = True

        if not self.connected:
            return []

        hr = max(30.0, random.gauss(self.true_hr, 2.0))
        spo2 = max(70.0, min(100.0, random.gauss(97.0, 1.0)))
        temp = random.gauss(self.true_temp, 0.05)
        motion = max(0.0, random.gauss(self.motion, 0.3))
        battery_pct = self.battery
        rssi = random.gauss(-60, 8)

        common = dict(patient_id=self.patient_id, device_id=self.device_id, timestamp=ts,
                      battery_level=battery_pct, connection_strength=rssi, firmware_version="sim-1.0")
        return [
            SensorPacket(sensor_type=SensorType.PPG, sampling_rate=1, values=[hr, spo2], **common),
            SensorPacket(sensor_type=SensorType.IMU, sampling_rate=1, values=[motion], **common),
            SensorPacket(sensor_type=SensorType.TEMPERATURE, sampling_rate=1, values=[temp], **common),
        ]
