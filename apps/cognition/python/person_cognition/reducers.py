"""Everything cognition rebuilds from the journal after a restart.

Two reducers read the same journal for different things: the routine
statistics read outcomes, and the memory store reads encoded episodes. Neither
sees the other's state, and each ignores the events it has no case for.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from person_persistence import EvidenceEvent
from person_policy import RoutineStatistics

from .memory import MemoryStore


class CognitiveReducers:
    def __init__(self, statistics: RoutineStatistics, memory: MemoryStore) -> None:
        self.statistics = statistics
        self.memory = memory

    def reset(self) -> None:
        self.statistics.reset()
        self.memory.reset()

    def apply(self, event: EvidenceEvent) -> None:
        self.statistics.apply(event)
        self.memory.apply(event)

    def to_json(self) -> dict[str, Any]:
        return {"statistics": self.statistics.to_json(), "memory": self.memory.to_json()}

    def load_json(self, body: Mapping[str, Any]) -> None:
        # A snapshot written before memory existed has neither key. The store
        # treats the KeyError as a rejected body and rebuilds from the journal.
        self.statistics.load_json(body["statistics"])
        self.memory.load_json(body["memory"])
