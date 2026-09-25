"""Immutable evidence records.

Evidence is the substrate everything else is rebuilt from. Scores change when
the scoring algorithm changes; the facts must not. Each record therefore keeps
what happened, in what context, under which policy revision, with a link to the
record before it.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

EVIDENCE_SCHEMA_VERSION = "person-evidence-v7"

#: Versions this reader understands. A journal written before prediction-error
#: instrumentation existed is still valid history and is read unchanged; only
#: new records carry the current version. This is the compatibility rule
#: `migrations/README.md` describes: read both, convert neither.
SUPPORTED_EVIDENCE_SCHEMAS: tuple[str, ...] = (
    "person-evidence-v1",
    "person-evidence-v2",
    "person-evidence-v3",
    "person-evidence-v4",
    "person-evidence-v5",
    "person-evidence-v6",
    "person-evidence-v7",
)

EVENT_TYPES: tuple[str, ...] = (
    "episode_started",
    "episode_ended",
    "goal_selected",
    "routine_selected",
    "routine_outcome",
    "skill_started",
    "skill_completed",
    "skill_failed",
    "skill_interrupted",
    "emergency_override",
    "death",
    #: Instrumentation only. Never scored, never fed back into policy.
    "prediction_error",
    #: Instrumentation only: why Person looked, and what the looking concluded.
    #: Engineering truth for the operator, never scored, never recalled.
    "information_search",
    #: An episode entered Person's memory. The memory store is rebuilt from
    #: these and from nothing else (ADR 0007). Never scored.
    "memory_encoded",
    #: A cue Person recalled with, and which memories came back.
    #: Instrumentation only: recalling changes nothing in the store.
    "memory_recalled",
    #: Person formed a cognitive place, in its own frame (ADR 0008). The
    #: spatial model is rebuilt from these and `place_visited` alone.
    "place_formed",
    #: Person believed it was back at a place it had formed.
    "place_visited",
    #: Person took up a project: a persistent commitment of its own.
    #: The project book is rebuilt from these and `project_changed` alone.
    "project_started",
    #: A project progressed, was interrupted, resumed, completed or abandoned.
    "project_changed",
    #: One appraisal and the affect change it made: trigger, components,
    #: state before, delta, state after (ADR 0010). The affect record is
    #: rebuilt from these alone. Never scored.
    "affect_appraised",
)

#: Event types introduced after the first evidence schema version.
V2_EVENT_TYPES: frozenset[str] = frozenset({"prediction_error"})
#: Event types introduced with the third.
V3_EVENT_TYPES: frozenset[str] = frozenset({"information_search"})
#: Event types introduced with the fourth.
V4_EVENT_TYPES: frozenset[str] = frozenset({"memory_encoded", "memory_recalled"})
#: Event types introduced with the fifth.
V5_EVENT_TYPES: frozenset[str] = frozenset({"place_formed", "place_visited"})
#: Event types introduced with the sixth.
V6_EVENT_TYPES: frozenset[str] = frozenset({"project_started", "project_changed"})
#: Event types introduced with the seventh.
V7_EVENT_TYPES: frozenset[str] = frozenset({"affect_appraised"})

#: The first schema each later event type may appear under. A record cannot
#: claim a schema older than its own type, so history cannot be backdated.
INTRODUCED_IN: dict[str, str] = {
    **dict.fromkeys(V2_EVENT_TYPES, "person-evidence-v2"),
    **dict.fromkeys(V3_EVENT_TYPES, "person-evidence-v3"),
    **dict.fromkeys(V4_EVENT_TYPES, "person-evidence-v4"),
    **dict.fromkeys(V5_EVENT_TYPES, "person-evidence-v5"),
    **dict.fromkeys(V6_EVENT_TYPES, "person-evidence-v6"),
    **dict.fromkeys(V7_EVENT_TYPES, "person-evidence-v7"),
}

REQUIRED_FIELDS: tuple[str, ...] = (
    "event_id",
    "previous_event_id",
    "person_id",
    "world_id",
    "session_id",
    "episode_id",
    "decision_id",
    "tick",
    "timestamp",
    "schema_version",
    "policy_revision",
    "training_context",
    "type",
    "payload",
)


class EvidenceError(ValueError):
    """A record is not a well-formed evidence event."""


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    event_id: str
    previous_event_id: str | None
    person_id: str
    world_id: str
    session_id: str
    episode_id: str
    decision_id: str | None
    tick: int
    timestamp: str
    schema_version: str
    policy_revision: int
    training_context: str
    type: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "previous_event_id": self.previous_event_id,
            "person_id": self.person_id,
            "world_id": self.world_id,
            "session_id": self.session_id,
            "episode_id": self.episode_id,
            "decision_id": self.decision_id,
            "tick": self.tick,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "policy_revision": self.policy_revision,
            "training_context": self.training_context,
            "type": self.type,
            "payload": dict(self.payload),
        }

    @staticmethod
    def from_json(document: Any) -> EvidenceEvent:
        if not isinstance(document, dict):
            raise EvidenceError("Evidence record is not a JSON object")
        missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in document]
        if missing:
            raise EvidenceError(f"Evidence record is missing {', '.join(missing)}")
        schema = document["schema_version"]
        if schema not in SUPPORTED_EVIDENCE_SCHEMAS:
            raise EvidenceError(
                f"Unsupported evidence schema {schema!r}; "
                f"this runtime reads {', '.join(SUPPORTED_EVIDENCE_SCHEMAS)}"
            )
        if document["type"] not in EVENT_TYPES:
            raise EvidenceError(f"Unknown evidence event type {document['type']!r}")
        introduced = INTRODUCED_IN.get(document["type"])
        if introduced is not None and SUPPORTED_EVIDENCE_SCHEMAS.index(
            schema
        ) < SUPPORTED_EVIDENCE_SCHEMAS.index(introduced):
            raise EvidenceError(f"Event type {document['type']!r} cannot claim schema {schema!r}")
        if not isinstance(document["payload"], dict):
            raise EvidenceError("Evidence payload must be an object")
        if not isinstance(document["tick"], int) or document["tick"] < 0:
            raise EvidenceError("Evidence tick must be a non-negative integer")
        try:
            uuid.UUID(document["event_id"])
        except (ValueError, AttributeError, TypeError) as error:
            raise EvidenceError("Evidence event_id must be a UUID") from error
        return EvidenceEvent(**{name: document[name] for name in REQUIRED_FIELDS})


def new_event(
    *,
    person_id: str,
    world_id: str,
    session_id: str,
    episode_id: str,
    decision_id: str | None,
    tick: int,
    policy_revision: int,
    training_context: str,
    event_type: str,
    payload: Mapping[str, Any],
    previous_event_id: str | None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> EvidenceEvent:
    if event_type not in EVENT_TYPES:
        raise EvidenceError(f"Unknown evidence event type {event_type!r}")
    return EvidenceEvent(
        event_id=event_id or str(uuid.uuid4()),
        previous_event_id=previous_event_id,
        person_id=person_id,
        world_id=world_id,
        session_id=session_id,
        episode_id=episode_id,
        decision_id=decision_id,
        tick=tick,
        timestamp=timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        schema_version=EVIDENCE_SCHEMA_VERSION,
        policy_revision=policy_revision,
        training_context=training_context,
        type=event_type,
        payload=dict(payload),
    )
