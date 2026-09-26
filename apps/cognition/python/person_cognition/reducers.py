"""Everything cognition rebuilds from the journal after a restart.

Seven reducers read the same journal for different things: the routine
statistics read outcomes, the memory store reads encoded episodes, the
spatial map reads the places Person formed and revisited, the project book
reads the projects Person took up, the affect record reads appraisals, the
effect beliefs read classified prediction evidence, and the hypothesis book
reads causal trials, hypotheses, their evidence and investigations. None sees
the other's state, and each ignores the events it has no case for.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from person_persistence import EvidenceEvent
from person_policy import RoutineStatistics

from .affect import AffectRecord
from .effect_learning import EffectBeliefs
from .hypotheses import HypothesisBook
from .memory import MemoryStore
from .projects import ProjectBook
from .spatial import SpatialMap


class CognitiveReducers:
    def __init__(
        self,
        statistics: RoutineStatistics,
        memory: MemoryStore,
        spatial: SpatialMap,
        projects: ProjectBook,
        affect: AffectRecord,
        effects: EffectBeliefs,
        hypotheses: HypothesisBook,
    ) -> None:
        self.statistics = statistics
        self.memory = memory
        self.spatial = spatial
        self.projects = projects
        self.affect = affect
        self.effects = effects
        self.hypotheses = hypotheses

    def reset(self) -> None:
        self.statistics.reset()
        self.memory.reset()
        self.spatial.reset()
        self.projects.reset()
        self.affect.reset()
        self.effects.reset()
        self.hypotheses.reset()

    def apply(self, event: EvidenceEvent) -> None:
        self.statistics.apply(event)
        self.memory.apply(event)
        self.spatial.apply(event)
        self.projects.apply(event)
        self.affect.apply(event)
        self.effects.apply(event)
        self.hypotheses.apply(event)

    def to_json(self) -> dict[str, Any]:
        return {
            "statistics": self.statistics.to_json(),
            "memory": self.memory.to_json(),
            "spatial": self.spatial.to_json(),
            "projects": self.projects.to_json(),
            "affect": self.affect.to_json(),
            "effects": self.effects.to_json(),
            "hypotheses": self.hypotheses.to_json(),
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        # A snapshot written before a reducer existed lacks its key. The store
        # treats the KeyError as a rejected body and rebuilds from the journal.
        self.statistics.load_json(body["statistics"])
        self.memory.load_json(body["memory"])
        self.spatial.load_json(body["spatial"])
        self.projects.load_json(body["projects"])
        self.affect.load_json(body["affect"])
        self.effects.load_json(body["effects"])
        self.hypotheses.load_json(body["hypotheses"])
