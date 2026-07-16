"""Doc 03 §10 buffer management: one circular buffer per (patient, sensor)."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta

from ..models import SensorPacket

DEFAULT_BUFFER_SECONDS = 60.0


class RingBuffer:
    """Stores incoming packets per (patient_id, sensor_type) until enough
    data exists to build a window, then evicts anything older than
    DEFAULT_BUFFER_SECONDS relative to the newest packet."""

    def __init__(self, buffer_seconds: float = DEFAULT_BUFFER_SECONDS):
        self.buffer_seconds = buffer_seconds
        self._buffers: dict[tuple[str, str], deque[SensorPacket]] = defaultdict(deque)

    def add(self, packet: SensorPacket) -> None:
        key = (packet.patient_id, packet.sensor_type.value)
        buf = self._buffers[key]
        buf.append(packet)
        self._evict_old(buf)

    def _evict_old(self, buf: deque[SensorPacket]) -> None:
        if not buf:
            return
        newest = buf[-1].timestamp
        cutoff = newest - timedelta(seconds=self.buffer_seconds)
        while buf and buf[0].timestamp < cutoff:
            buf.popleft()

    def packets_in_range(self, patient_id: str, sensor_type: str, start, end) -> list[SensorPacket]:
        key = (patient_id, sensor_type)
        return [p for p in self._buffers.get(key, ()) if start <= p.timestamp <= end]

    def latest(self, patient_id: str, sensor_type: str) -> SensorPacket | None:
        buf = self._buffers.get((patient_id, sensor_type))
        return buf[-1] if buf else None

    def patient_ids(self) -> set[str]:
        return {pid for (pid, _sensor) in self._buffers.keys()}
