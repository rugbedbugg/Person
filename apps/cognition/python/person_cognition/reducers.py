"""Everything cognition rebuilds from the journal after a restart.

Three reducers read the same journal for different things: the routine
statistics read outcomes, the memory store reads encoded episodes, and the
spatial map reads the places Person formed and revisited. None
sees the other's state, and each ignores the events it has no case for.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from person_persistence import EvidenceEvent
from person_policy import RoutineStatistics

from .memory import MemoryStore
from .spatial import SpatialMap


class CognitiveReducers:
    def __init__(
        self, statistics: RoutineStatistics, memory: MemoryStore, spatial: SpatialMap
    ) -> None:
        self.statistics = statistics
        self.memory = memory
        self.spatial = spatial

    def reset(self) -> None:
        self.statistics.reset()
        self.memory.reset()
        self.spatial.reset()

    def apply(self, event: EvidenceEvent) -> None:
        self.statistics.apply(event)
        self.memory.apply(event)
        self.spatial.apply(event)

    def to_json(self) -> dict[str, Any]:
        return {
            "statistics": self.statistics.to_json(),
            "memory": self.memory.to_json(),
            "spatial": self.spatial.to_json(),
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        # A snapshot written before a reducer existed lacks its key. The store
        # treats the KeyError as a rejected body and rebuilds from the journal.
        self.statistics.load_json(body["statistics"])
        self.memory.load_json(body["memory"])
        self.spatial.load_json(body["spatial"])
