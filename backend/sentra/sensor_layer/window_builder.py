"""Doc 03 §8 window construction: 30s windows, 50% overlap, one per patient."""
from __future__ import annotations

from datetime import datetime, timedelta

from .. import config
from ..models import SensorType, SignalWindow
from .ring_buffer import RingBuffer


class WindowBuilder:
    def __init__(self, ring_buffer: RingBuffer, window_size: float | None = None,
                 overlap: float | None = None):
        window_cfg = config.get_weights()["window"]
        self.window_size = window_size or window_cfg["size_seconds"]
        self.overlap = overlap if overlap is not None else window_cfg["overlap_fraction"]
        self.step = self.window_size * (1 - self.overlap)
        self.ring_buffer = ring_buffer
        self._next_start: dict[str, datetime] = {}

    def maybe_build_window(self, patient_id: str, now: datetime) -> SignalWindow | None:
        """Returns a SignalWindow once window_size seconds have accumulated
        since the last emitted window's start (advancing by `step` each
        time), else None. Call this once per patient per processing tick."""
        next_start = self._next_start.setdefault(patient_id, now)
        window_end = next_start + timedelta(seconds=self.window_size)
        if now < window_end:
            return None

        ppg_pkts = self.ring_buffer.packets_in_range(patient_id, SensorType.PPG.value, next_start, window_end)
        imu_pkts = self.ring_buffer.packets_in_range(patient_id, SensorType.IMU.value, next_start, window_end)
        temp_pkts = self.ring_buffer.packets_in_range(patient_id, SensorType.TEMPERATURE.value, next_start, window_end)

        self._next_start[patient_id] = next_start + timedelta(seconds=self.step)

        if not (ppg_pkts or imu_pkts or temp_pkts):
            return None

        def column(pkts, index):
            """PPG packets carry values=[hr, spo2] (firmware convention,
            see docs/HARDWARE_SCOPE.md §4); other sensor types carry a
            single scalar at index 0."""
            out: list[float] = []
            for p in pkts:
                if index < len(p.values):
                    out.append(p.values[index])
            return out

        return SignalWindow(
            patient_id=patient_id,
            start_time=next_start,
            end_time=window_end,
            duration_seconds=self.window_size,
            ppg=column(ppg_pkts, 0),
            ppg_spo2=column(ppg_pkts, 1),
            imu=column(imu_pkts, 0),
            temperature=column(temp_pkts, 0),
        )
