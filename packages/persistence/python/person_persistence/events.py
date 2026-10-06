"""Immutable canonical events: Person's append-only longitudinal history.

A canonical event is a record that something happened: an episode began, a
skill ran, a memory was encoded or recalled, an affect changed, a deliberation
was requested, the body died. It is the substrate everything else is rebuilt
from. Scores change when the scoring algorithm changes; the history must not.
Each record therefore keeps what happened, in which experience stream, under
which policy revision, with a link to the record before it.

A canonical event is **not** epistemic evidence (ADR 0027). Most events are
history and nothing more; the few that bear on a belief do so through an
explicit admission (`person_epistemics.evidence`), never by being recorded.
The journal used to be called the evidence journal, and its records still
carry `person-evidence-v1` to `-v19` as their schema names; those records are
read as they are and never rewritten. New records are `person-event-v20`.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from person_epistemics import ExperienceKey

from .legacy import legacy_experience

#: The schema new records are written under. v20 renamed the family from
#: "evidence" to "event" and replaced `training_context` with `experience`.
EVENT_SCHEMA_VERSION = "person-event-v20"

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
    "person-evidence-v8",
    "person-evidence-v9",
    "person-evidence-v10",
    "person-evidence-v11",
    "person-evidence-v12",
    "person-evidence-v13",
    "person-evidence-v14",
    "person-evidence-v15",
    "person-evidence-v16",
    "person-evidence-v17",
    "person-evidence-v18",
    "person-evidence-v19",
    "person-event-v20",
)
#: Records written before v20 carry `training_context`; from v20, `experience`.
LEGACY_SCHEMAS: frozenset[str] = frozenset(SUPPORTED_EVIDENCE_SCHEMAS[:19])

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
    #: One declared effect of one settled prediction, classified: supports,
    #: partial, contradicts or inconclusive, with the reason, and what the
    #: learning mode then admitted it to (ADR 0011). The effect-belief tables
    #: are rebuilt from these alone.
    "effect_evidence",
    #: One conclusive trial of a skill's declared effect with the conditions
    #: Person perceived when it decided (ADR 0012): its own record of what
    #: happened when, which hypothesis generation reasons over.
    "causal_trial",
    #: A proposal passed the grounding gate and became a hypothesis, with no
    #: evidence yet: its provenance, premises and the table it went to.
    "hypothesis_proposed",
    #: A proposal was quarantined, with the reasons. Never a hypothesis.
    "hypothesis_rejected",
    #: One trial counted for or against one hypothesis: its arm, whether it
    #: was interventional or observational, and its verdict.
    "hypothesis_evidence",
    #: An investigation started, ran a trial, was interrupted, resumed,
    #: concluded or retired. Investigations are rebuilt from these alone.
    "investigation_changed",
    #: One tonic update of affect (ADR 0014): the bodily and threat pressures
    #: in force, the offset they set, the experienced time covered, and the
    #: state before and after. With `affect_appraised`, the affect record is
    #: rebuilt from these alone. Never scored.
    "affect_tonic",
    #: The first event of a continuity root: who this Person is, and when it
    #: began (ADR 0017). Written once, never changed; nothing precedes it.
    "person_founded",
    #: A cognition process began living this Person's life, and what it
    #: learned about the gap since the last recorded event (ADR 0017).
    "session_started",
    #: A cognition process ended cleanly. A crash writes nothing.
    "session_ended",
    #: The world became available to the body, or stopped being available
    #: (ADR 0017, I2): an operational state, never a verdict on the run, and
    #: written only when the state actually changes.
    "world_availability_changed",
    #: The trusted runtime observed the body die (ADR 0017, I3). `terminal`
    #: is authoritative: a terminal death is, by itself, the end of that
    #: Person, whether or not a `person_terminated` record follows it.
    "person_died",
    #: The same Person's body was brought back after a death.
    "person_respawned",
    #: Readability only: the Person a terminal death ended. Termination is
    #: reconstructed from the death record, never from this alone.
    "person_terminated",
    # ADR 0020, C1: a deliberation was requested, answered (and gated), or
    # could not be answered. Engineering evidence; nothing is rebuilt from it.
    "deliberation_requested",
    "deliberation_completed",
    "deliberation_unavailable",
    # ADR 0021, C3: why a trigger did not become a request, and how each
    # request ended: adopted as one temporary goal, discarded, or (record-only)
    # what would have happened; and how an adopted goal ended.
    "deliberation_suppressed",
    "deliberation_adopted",
    "deliberation_discarded",
    "deliberation_shadow_disposition",
    "deliberation_goal_ended",
    # ADR 0021/0022 amendment (C4.1): the one retry a satisfied remedy grants
    # the goal whose blocking raised its trigger.
    "deliberation_source_retry",
    # ADR 0022: habits. Record-only's shadow stream, which nothing that acts
    # ever reads, and the active stream C5 invokes habits from.
    "habit_candidate_shadow",
    "habit_evidence_shadow",
    "habit_promotion_shadow",
    "habit_conflict_shadow",
    "habit_candidate_formed",
    "habit_evidence",
    "habit_promoted",
    "habit_conflict",
    "habit_invoked",
    "habit_not_applicable",
    "habit_demoted",
    # ADR 0022, C5: how a habit's goal ended, and the one retry a satisfied
    # habit remedy grants its source goal.
    "habit_goal_ended",
    "habit_source_retry",
    # ADR 0023, C6: the facts at the affective arbitration point.
    "affective_arbitration_shadow",
    #: ADR 0026: one fact belief revised by admitted evidence, with its
    #: value, confidence, basis, evidence references and scope. The belief
    #: store is rebuilt from these alone.
    "belief_revised",
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
#: Event types introduced with the eighth.
V8_EVENT_TYPES: frozenset[str] = frozenset({"effect_evidence"})
#: Event types introduced with the ninth.
V9_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "causal_trial",
        "hypothesis_proposed",
        "hypothesis_rejected",
        "hypothesis_evidence",
        "investigation_changed",
    }
)

#: Event types introduced with the tenth.
V10_EVENT_TYPES: frozenset[str] = frozenset({"affect_tonic"})
#: Event types introduced with the eleventh.
V11_EVENT_TYPES: frozenset[str] = frozenset({"person_founded", "session_started", "session_ended"})
#: Event types introduced with the twelfth.
V12_EVENT_TYPES: frozenset[str] = frozenset({"world_availability_changed"})
#: Event types introduced with the thirteenth.
V13_EVENT_TYPES: frozenset[str] = frozenset(
    {"person_died", "person_respawned", "person_terminated"}
)
#: Event types introduced with the fourteenth: deliberation (ADR 0020).
V14_EVENT_TYPES: frozenset[str] = frozenset(
    {"deliberation_requested", "deliberation_completed", "deliberation_unavailable"}
)

#: Event types introduced with the fifteenth: metareasoning (ADR 0021).
V15_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "deliberation_suppressed",
        "deliberation_adopted",
        "deliberation_discarded",
        "deliberation_shadow_disposition",
        "deliberation_goal_ended",
    }
)

#: Event types introduced with the sixteenth: habits (ADR 0022).
V16_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "habit_candidate_shadow",
        "habit_evidence_shadow",
        "habit_promotion_shadow",
        "habit_conflict_shadow",
        "habit_candidate_formed",
        "habit_evidence",
        "habit_promoted",
        "habit_conflict",
        "habit_invoked",
        "habit_not_applicable",
        "habit_demoted",
    }
)

#: Event types introduced with the seventeenth: the source retry (C4.1).
V17_EVENT_TYPES: frozenset[str] = frozenset({"deliberation_source_retry"})

#: Event types introduced with the eighteenth: active habits (C5).
V18_EVENT_TYPES: frozenset[str] = frozenset({"habit_goal_ended", "habit_source_retry"})

#: Event types introduced with the nineteenth: affective metareasoning (C6).
V19_EVENT_TYPES: frozenset[str] = frozenset({"affective_arbitration_shadow"})

#: Event types introduced with the twentieth: fact beliefs (ADR 0026).
V20_EVENT_TYPES: frozenset[str] = frozenset({"belief_revised"})

#: The first schema each later event type may appear under. A record cannot
#: claim a schema older than its own type, so history cannot be backdated.
INTRODUCED_IN: dict[str, str] = {
    **dict.fromkeys(V2_EVENT_TYPES, "person-evidence-v2"),
    **dict.fromkeys(V3_EVENT_TYPES, "person-evidence-v3"),
    **dict.fromkeys(V4_EVENT_TYPES, "person-evidence-v4"),
    **dict.fromkeys(V5_EVENT_TYPES, "person-evidence-v5"),
    **dict.fromkeys(V6_EVENT_TYPES, "person-evidence-v6"),
    **dict.fromkeys(V7_EVENT_TYPES, "person-evidence-v7"),
    **dict.fromkeys(V8_EVENT_TYPES, "person-evidence-v8"),
    **dict.fromkeys(V9_EVENT_TYPES, "person-evidence-v9"),
    **dict.fromkeys(V10_EVENT_TYPES, "person-evidence-v10"),
    **dict.fromkeys(V11_EVENT_TYPES, "person-evidence-v11"),
    **dict.fromkeys(V12_EVENT_TYPES, "person-evidence-v12"),
    **dict.fromkeys(V13_EVENT_TYPES, "person-evidence-v13"),
    **dict.fromkeys(V14_EVENT_TYPES, "person-evidence-v14"),
    **dict.fromkeys(V15_EVENT_TYPES, "person-evidence-v15"),
    **dict.fromkeys(V16_EVENT_TYPES, "person-evidence-v16"),
    **dict.fromkeys(V17_EVENT_TYPES, "person-evidence-v17"),
    **dict.fromkeys(V18_EVENT_TYPES, "person-evidence-v18"),
    **dict.fromkeys(V19_EVENT_TYPES, "person-evidence-v19"),
    **dict.fromkeys(V20_EVENT_TYPES, "person-event-v20"),
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
    "type",
    "payload",
)
#: The field that says which experience stream a record belongs to.
LEGACY_CONTEXT_FIELD = "training_context"
EXPERIENCE_FIELD = "experience"


class EventRecordError(ValueError):
    """A record is not a well-formed canonical event."""


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
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
    experience: ExperienceKey
    type: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    #: For a record read from a pre-v20 schema: the conflated value it was
    #: written with, kept so the record re-serialises exactly as it was.
    legacy_training_context: str | None = None

    @property
    def context_key(self) -> str:
        """The experience stream's partition key (`ExperienceKey.key`)."""
        return self.experience.key

    def to_json(self) -> dict[str, Any]:
        if self.schema_version in LEGACY_SCHEMAS:
            # A legacy record is re-serialised exactly as it was read.
            return self._fields(LEGACY_CONTEXT_FIELD, self.legacy_training_context)
        return self._fields(EXPERIENCE_FIELD, self.experience.to_json())

    def _fields(self, name: str, value: Any) -> dict[str, Any]:
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
            name: value,
            "type": self.type,
            "payload": dict(self.payload),
        }

    @staticmethod
    def from_json(document: Any) -> CanonicalEvent:
        if not isinstance(document, dict):
            raise EventRecordError("Event record is not a JSON object")
        missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in document]
        if missing:
            raise EventRecordError(f"Event record is missing {', '.join(missing)}")
        schema = document["schema_version"]
        if schema not in SUPPORTED_EVIDENCE_SCHEMAS:
            raise EventRecordError(
                f"Unsupported evidence schema {schema!r}; "
                f"this runtime reads {', '.join(SUPPORTED_EVIDENCE_SCHEMAS)}"
            )
        if document["type"] not in EVENT_TYPES:
            raise EventRecordError(f"Unknown event type {document['type']!r}")
        introduced = INTRODUCED_IN.get(document["type"])
        if introduced is not None and SUPPORTED_EVIDENCE_SCHEMAS.index(
            schema
        ) < SUPPORTED_EVIDENCE_SCHEMAS.index(introduced):
            raise EventRecordError(
                f"Event type {document['type']!r} cannot claim schema {schema!r}"
            )
        if not isinstance(document["payload"], dict):
            raise EventRecordError("Event payload must be an object")
        if not isinstance(document["tick"], int) or document["tick"] < 0:
            raise EventRecordError("Event tick must be a non-negative integer")
        try:
            uuid.UUID(document["event_id"])
        except (ValueError, AttributeError, TypeError) as error:
            raise EventRecordError("Event event_id must be a UUID") from error
        fields = {name: document[name] for name in REQUIRED_FIELDS}
        if schema in LEGACY_SCHEMAS:
            # Read compatibility (ADR 0025): the conflated training context is
            # mapped to the stream it always meant; the record is not changed.
            if LEGACY_CONTEXT_FIELD not in document:
                raise EventRecordError(f"Event record is missing {LEGACY_CONTEXT_FIELD}")
            legacy = str(document[LEGACY_CONTEXT_FIELD])
            try:
                experience = legacy_experience(legacy)
            except KeyError as error:
                raise EventRecordError(f"Unknown legacy training context {legacy!r}") from error
            return CanonicalEvent(experience=experience, legacy_training_context=legacy, **fields)
        else:
            if not isinstance(document.get(EXPERIENCE_FIELD), dict):
                raise EventRecordError(f"Event record is missing {EXPERIENCE_FIELD}")
            try:
                experience = ExperienceKey.from_json(document[EXPERIENCE_FIELD])
            except (KeyError, ValueError) as error:
                raise EventRecordError(f"Event experience is malformed: {error}") from error
        return CanonicalEvent(experience=experience, **fields)


def new_event(
    *,
    person_id: str,
    world_id: str,
    session_id: str,
    episode_id: str,
    decision_id: str | None,
    tick: int,
    policy_revision: int,
    experience: ExperienceKey,
    event_type: str,
    payload: Mapping[str, Any],
    previous_event_id: str | None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> CanonicalEvent:
    if event_type not in EVENT_TYPES:
        raise EventRecordError(f"Unknown event type {event_type!r}")
    return CanonicalEvent(
        event_id=event_id or str(uuid.uuid4()),
        previous_event_id=previous_event_id,
        person_id=person_id,
        world_id=world_id,
        session_id=session_id,
        episode_id=episode_id,
        decision_id=decision_id,
        tick=tick,
        timestamp=timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        schema_version=EVENT_SCHEMA_VERSION,
        policy_revision=policy_revision,
        experience=experience,
        type=event_type,
        payload=dict(payload),
    )


# Compatibility names. The journal was called the evidence journal before ADR
# 0027 separated history from evidence; these keep old scripts importable.
EvidenceEvent = CanonicalEvent
EvidenceError = EventRecordError
EVIDENCE_SCHEMA_VERSION = EVENT_SCHEMA_VERSION
