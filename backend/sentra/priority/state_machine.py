"""Doc 11 §19-21: continuous patient state, at most one priority level of
movement per processing window (either direction), unless a Critical
Override bypasses that limit. This single rule mechanically implements
both §19's escalation cap and §21's "priority SHALL NOT immediately return
to Normal after one healthy measurement" de-escalation requirement — a
patient recovering from CRITICAL still has to pass through HIGH_PRIORITY,
CONCERN, and WATCH one window at a time."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ..models import PatientState, StateHistory, state_rank

_STATE_ORDER = [
    PatientState.NORMAL, PatientState.WATCH, PatientState.CONCERN,
    PatientState.HIGH_PRIORITY, PatientState.CRITICAL,
]


class PriorityStateMachine:
    def __init__(self):
        self._state: dict[str, PatientState] = {}
        self._history: dict[str, list[StateHistory]] = defaultdict(list)

    def current_state(self, patient_id: str) -> PatientState:
        return self._state.get(patient_id, PatientState.NORMAL)

    def transition(self, patient_id: str, target_state: PatientState, ts: datetime,
                    reason: str, critical_override: bool = False) -> PatientState:
        current = self.current_state(patient_id)

        if critical_override:
            new_state = target_state
        else:
            cur_rank = state_rank(current)
            tgt_rank = state_rank(target_state)
            if tgt_rank > cur_rank:
                new_rank = min(tgt_rank, cur_rank + 1)
            elif tgt_rank < cur_rank:
                new_rank = max(tgt_rank, cur_rank - 1)
            else:
                new_rank = cur_rank
            new_state = _STATE_ORDER[new_rank]

        if new_state != current:
            self._history[patient_id].append(StateHistory(
                previous_state=current, current_state=new_state,
                transition_time=ts, transition_reason=reason,
            ))
        self._state[patient_id] = new_state
        return new_state

    def history_for(self, patient_id: str) -> list[StateHistory]:
        return list(self._history.get(patient_id, []))
