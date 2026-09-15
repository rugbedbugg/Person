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

EVIDENCE_SCHEMA_VERSION = "person-evidence-v1"

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
)

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
        if document["schema_version"] != EVIDENCE_SCHEMA_VERSION:
            raise EvidenceError(
                f"Unsupported evidence schema {document['schema_version']!r}; "
                f"this runtime reads {EVIDENCE_SCHEMA_VERSION}"
            )
        if document["type"] not in EVENT_TYPES:
            raise EvidenceError(f"Unknown evidence event type {document['type']!r}")
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
