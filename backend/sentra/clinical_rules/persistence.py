"""Doc 08 §11 persistence engine: transient abnormalities SHALL NOT
immediately trigger severe rules. Tracks how long each (patient, rule)
condition has been continuously true."""
from __future__ import annotations

from datetime import datetime


class PersistenceTracker:
    def __init__(self):
        self._active_since: dict[tuple[str, str], datetime] = {}

    def update(self, patient_id: str, rule_id: str, condition_met: bool, ts: datetime) -> float:
        """Returns seconds the condition has been continuously true (0 if
        not currently met)."""
        key = (patient_id, rule_id)
        if condition_met:
            start = self._active_since.setdefault(key, ts)
            return (ts - start).total_seconds()
        self._active_since.pop(key, None)
        return 0.0

    def reset(self, patient_id: str, rule_id: str) -> None:
        self._active_since.pop((patient_id, rule_id), None)
