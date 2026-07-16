"""Doc 03 §11 packet validation. No downstream module sees an invalid packet."""
from __future__ import annotations

from ..models import SensorPacket

_seen_packet_ids: set[str] = set()

MAX_SEEN_IDS = 50_000  # bounded so long-running processes don't leak memory


def validate_packet(packet: SensorPacket) -> tuple[bool, list[str]]:
    """Returns (is_valid, errors). Errors are human-readable per Doc 03 §11."""
    errors: list[str] = []

    if not packet.patient_id:
        errors.append("missing patient_id")
    if not packet.device_id:
        errors.append("missing device_id")
    if packet.sampling_rate <= 0:
        errors.append("invalid sampling_rate")
    if not packet.values:
        errors.append("empty values[]")
    if packet.battery_level is not None and not (0 <= packet.battery_level <= 100):
        errors.append("battery_level out of range")

    if packet.packet_id in _seen_packet_ids:
        errors.append("duplicate packet_id")
    else:
        if len(_seen_packet_ids) >= MAX_SEEN_IDS:
            _seen_packet_ids.clear()
        _seen_packet_ids.add(packet.packet_id)

    return (len(errors) == 0, errors)
