"""What an episode is, and the closed vocabularies that describe one.

An episode is a small, immutable record of something Person experienced. It
says what kind of experience it was, what it was about, when in Person's own
experienced time it happened, how salient it was, a handful of whitelisted
details, and where it came from. It never holds a coordinate, an entity
handle, or the thing an action was done to (ADR 0007).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from person_epistemics import LIVED, Source
from person_protocol import discovered

#: The kinds of episode the foundation encodes.
KINDS: frozenset[str] = frozenset({"perceived", "acted", "endangered", "hurt", "searched", "died"})

#: Subjects every environment has: Person itself, and danger to it.
CORE_SUBJECTS: frozenset[str] = frozenset({"danger", "self"})

#: What an episode can be about. Closed, so a cue cannot smuggle in a query:
#: the core subjects, and those each installed environment declares in its
#: manifest (`memory.subjects`, ADR 0025). Data, not code: the memory package
#: imports no environment.
SUBJECTS: frozenset[str] = CORE_SUBJECTS.union(
    *(manifest.document.get("memory", {}).get("subjects", ()) for manifest in discovered().values())
)

#: Where a memory came from, and the provenance class each source is
#: (ADR 0027). Every one of them is lived: an episode is something Person
#: lived through, once, and nothing else.
SOURCE_CLASSES: Mapping[str, Source] = {
    "perceived": Source.REAL_OBSERVATION,
    "proprioceptive": Source.REAL_OBSERVATION,
    "action_outcome": Source.INTERVENTION_OUTCOME,
    "own_decision": Source.INTERVENTION_OUTCOME,
}
SOURCES: frozenset[str] = frozenset(SOURCE_CLASSES)
assert all(source in LIVED for source in SOURCE_CLASSES.values())

#: Sources reserved for later phases (`PERSON_SPEC` section 22.2). Named so the
#: distinctions exist before anything produces them; nothing encodes them yet.
#: None of them is lived, so none can ever become an episode: told, read or
#: inferred material would enter memory, when it does, as a different kind of
#: record. Recall, replay, counterfactuals and model rollouts are not here at
#: all: they are never sources of an episode.
FUTURE_SOURCES: frozenset[str] = frozenset({"inferred", "taught", "operator", "external"})


class MemoryRecordError(ValueError):
    """A memory record, or a request for one, is malformed."""


@dataclass(frozen=True, slots=True)
class Provenance:
    """Why Person has this memory."""

    source: str
    #: The protocol message the experience arrived in, when there was one.
    message_id: str | None = None
    #: The decision it belonged to, when it was one of Person's own.
    decision_id: str | None = None
    #: The evidence event recording the same happening, when there is one.
    evidence_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise MemoryRecordError(f"unknown memory source {self.source!r}")

    @property
    def source_class(self) -> Source:
        return SOURCE_CLASSES[self.source]

    def to_json(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "message_id": self.message_id,
            "decision_id": self.decision_id,
            "evidence_event_id": self.evidence_event_id,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Provenance:
        return cls(
            source=str(body["source"]),
            message_id=body.get("message_id"),
            decision_id=body.get("decision_id"),
            evidence_event_id=body.get("evidence_event_id"),
        )


@dataclass(frozen=True, slots=True)
class EpisodeDraft:
    """An experience about to be encoded: everything but its salience and time."""

    kind: str
    subjects: tuple[str, ...]
    details: Mapping[str, Any]
    provenance: Provenance
    #: Salience before familiarity is taken into account.
    salience: float

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise MemoryRecordError(f"unknown episode kind {self.kind!r}")
        if not self.subjects:
            raise MemoryRecordError("an episode must be about something")
        unknown = set(self.subjects) - SUBJECTS
        if unknown:
            raise MemoryRecordError(f"unknown memory subjects {sorted(unknown)}")


@dataclass(frozen=True, slots=True)
class Episode:
    """One remembered experience. Immutable: memories are never refreshed."""

    memory_id: str
    kind: str
    subjects: tuple[str, ...]
    #: Person's experienced time at encoding. Recency is measured in this.
    experienced_tick: int
    #: The world tick at encoding, kept for provenance only.
    world_tick: int
    episode_id: str
    #: The experience stream it was lived in (`ExperienceKey.key`): a fixture
    #: memory and a Mineflayer one never mix, nor a lived one and a replay.
    experience: str
    salience: float
    details: Mapping[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance("perceived"))
    #: The cognitive place Person believed it was at, and how strongly
    #: (ADR 0008). Person's own belief, never a runtime location.
    place_id: str | None = None
    place_confidence: float = 0.0

    def detail(self, key: str) -> Any:
        return self.details.get(key)

    def to_json(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "subjects": list(self.subjects),
            "experienced_tick": self.experienced_tick,
            "world_tick": self.world_tick,
            "episode_id": self.episode_id,
            "experience": self.experience,
            "salience": self.salience,
            "details": dict(self.details),
            "provenance": self.provenance.to_json(),
            "place_id": self.place_id,
            "place_confidence": self.place_confidence,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Episode:
        return cls(
            memory_id=str(body["memory_id"]),
            kind=str(body["kind"]),
            subjects=tuple(str(subject) for subject in body["subjects"]),
            experienced_tick=int(body["experienced_tick"]),
            world_tick=int(body["world_tick"]),
            episode_id=str(body["episode_id"]),
            experience=str(body["experience"]),
            salience=float(body["salience"]),
            details=dict(body["details"]),
            provenance=Provenance.from_json(body["provenance"]),
            place_id=body.get("place_id"),
            place_confidence=float(body.get("place_confidence", 0.0)),
        )
