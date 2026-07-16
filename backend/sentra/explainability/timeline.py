"""Doc 12 §18 timeline reconstruction, from the Priority Engine's state history."""
from __future__ import annotations

from ..models import StateHistory, TimelineEvent


def build_timeline(history: list[StateHistory]) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            timestamp=h.transition_time,
            description=f"Priority changed {h.previous_state.value} -> {h.current_state.value} ({h.transition_reason})",
        )
        for h in history
    ]
