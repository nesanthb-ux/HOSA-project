"""Doc 03 §12 connection monitoring, §15 sensor health score, §16 failure
recovery. Doc 03 §15 lists health-score factors (battery, packet loss,
latency, signal stability, connection quality) but does not specify exact
weights, unlike Docs 05/09/10/11 which do. The 0.4/0.3/0.3 split below is a
documented simplification (battery / packet loss / signal folded together),
not a fabricated clinical formula."""
from __future__ import annotations

from ..models import SensorPacket, SensorStatus

HEALTH_WARNING_THRESHOLD = 50.0  # Doc 03 §15


class DeviceManager:
    def __init__(self):
        self._status: dict[tuple[str, str], SensorStatus] = {}
        self._packet_counts: dict[tuple[str, str], int] = {}
        self._invalid_counts: dict[tuple[str, str], int] = {}

    def record_valid_packet(self, packet: SensorPacket) -> SensorStatus:
        key = (packet.device_id, packet.sensor_type.value)
        self._packet_counts[key] = self._packet_counts.get(key, 0) + 1
        return self._update_status(packet, connected=True)

    def record_invalid_packet(self, packet: SensorPacket) -> None:
        key = (packet.device_id, packet.sensor_type.value)
        self._invalid_counts[key] = self._invalid_counts.get(key, 0) + 1

    def mark_disconnected(self, device_id: str, sensor_type: str) -> None:
        key = (device_id, sensor_type)
        if key in self._status:
            self._status[key] = self._status[key].model_copy(update={"connected": False})

    def _update_status(self, packet: SensorPacket, connected: bool) -> SensorStatus:
        key = (packet.device_id, packet.sensor_type.value)
        packet_loss_fraction = self._packet_loss_fraction(key)
        health = self._health_score(packet.battery_level, packet_loss_fraction, packet.connection_strength)

        status = SensorStatus(
            device_id=packet.device_id,
            sensor_type=packet.sensor_type,
            connected=connected,
            battery=packet.battery_level,
            signal_strength=packet.connection_strength,
            firmware_version=packet.firmware_version,
            health_score=health,
        )
        self._status[key] = status
        return status

    def _packet_loss_fraction(self, key: tuple[str, str]) -> float:
        valid = self._packet_counts.get(key, 0)
        invalid = self._invalid_counts.get(key, 0)
        total = valid + invalid
        return (invalid / total) if total else 0.0

    @staticmethod
    def _health_score(battery: float | None, packet_loss_fraction: float,
                       rssi: float | None) -> float:
        battery_score = battery if battery is not None else 100.0
        loss_score = max(0.0, 100.0 - packet_loss_fraction * 100.0)
        signal_score = 100.0 if rssi is None else max(0.0, min(100.0, (rssi + 100.0) * 2.0))
        return round(0.4 * battery_score + 0.3 * loss_score + 0.3 * signal_score, 1)

    def status_for(self, device_id: str, sensor_type: str) -> SensorStatus | None:
        return self._status.get((device_id, sensor_type))

    def all_statuses(self) -> list[SensorStatus]:
        return list(self._status.values())

    def needs_maintenance(self) -> list[SensorStatus]:
        return [s for s in self._status.values() if s.health_score < HEALTH_WARNING_THRESHOLD]
