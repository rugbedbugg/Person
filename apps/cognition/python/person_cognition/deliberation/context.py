"""The bounded deliberation context (ADR 0020, C1).

Everything a deliberative model may know, and nothing more, built only from
projections cognition already has, each within its own firewall: the
self-knowledge and operational projections (ADR 0017), the Person-facing
observation (ADR 0002), what is in working memory now (ADR 0007; building a
context recalls nothing), beliefs with their uncertainty (ADR 0011, 0012),
goals and projects, recent outcomes and prediction errors, and Person's
capabilities. Raw affect is deliberately absent until C6. Every collection is
capped, and every item carries a reference a proposal can cite as a premise.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

CONTEXT_SCHEMA = "person-deliberation-context-v2"

#: Why deliberation may be requested. C3 decides when; C1 only records why.
REASONS: tuple[str, ...] = (
    "no_viable_plan",
    "repeated_prediction_error",
    "repeated_failure",
    "emergency_recurrence",
    "novel_context",
    "belief_conflict",
    "high_uncertainty",
    "project_reconsideration",
    "unexpected_outcome",
    "reflection",
    # ADR 0022, C5: a habit Person relied on failed, so think again.
    "habit_breakdown",
)

#: Hard caps on every collection. Implementation parameters.
CAPS: Mapping[str, int] = {
    "request_refs": 8,
    "situation": 24,
    "in_view_per_kind": 4,
    "holdings": 12,
    "memories": 3,
    "beliefs": 12,
    "hypotheses": 6,
    "goals": 5,
    "projects": 4,
    "recent": 8,
    "capabilities": 32,
    "list_items": 4,
}


def capped(items: Iterable[Any], cap: int) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if len(out) >= cap:
            break
        out.append(item)
    return out


@dataclass(frozen=True, slots=True)
class Retrieval:
    """What one act of deliberation recalled for itself: the cue Person
    derived from the problem, and the memories it made available."""

    cue_subjects: tuple[str, ...]
    cue_kinds: tuple[str, ...]
    memory_ids: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "cue_subjects": list(self.cue_subjects),
            "cue_kinds": list(self.cue_kinds),
            "result_refs": list(self.memory_ids),
            "result_count": len(self.memory_ids),
        }


@dataclass(frozen=True, slots=True)
class DeliberationContext:
    """One context, as the model will see it, with its citable references."""

    document: dict[str, Any]
    #: Reference -> (section, item), for the grounding gate.
    refs: Mapping[str, tuple[str, dict[str, Any]]]
    #: The request-local recall this context carries, if a request made one.
    retrieval: Retrieval | None = None

    def reason(self) -> str:
        return str(self.document["request"]["reason"])


@dataclass(frozen=True, slots=True)
class Capability:
    skill: str
    summary: str
    effects: tuple[str, ...]


def build_context(
    *,
    reason: str,
    request_refs: Sequence[str] = (),
    self_knowledge: Mapping[str, Any] | None,
    world_available: bool | None,
    situation: Sequence[Mapping[str, Any]],
    place: Mapping[str, Any] | None,
    working_memory: Sequence[Mapping[str, Any]],
    beliefs: Sequence[Mapping[str, Any]],
    hypotheses: Sequence[Mapping[str, Any]],
    goals: Sequence[Mapping[str, Any]],
    projects: Sequence[Mapping[str, Any]],
    recent: Sequence[Mapping[str, Any]],
    capabilities: Sequence[Capability],
    vocabulary: Mapping[str, Sequence[str]],
    home_relation: str = "unknown",
    place_labels: Mapping[str, str] | None = None,
) -> DeliberationContext:
    """The bounded context a model may see.

    `home_relation` is Person's own belief about where home is (C8), never
    the runtime's anchor; `place_labels` holds Person's own labels for the
    places this context already cites, and nothing else (v2, ADR 0024)."""
    labels = dict(place_labels or {})

    def place_ref(place_id: Any) -> dict[str, Any] | None:
        if place_id is None:
            return None
        return {"id": str(place_id), "label": labels.get(str(place_id))}

    if reason not in REASONS:
        raise ValueError(f"unknown deliberation reason {reason!r}")
    refs: dict[str, tuple[str, dict[str, Any]]] = {}

    def cite(prefix: str, section: str, items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for number, item in enumerate(items, start=1):
            entry = {"ref": f"{prefix}{number}", **dict(item)}
            refs[entry["ref"]] = (section, entry)
            out.append(entry)
        return out

    # What Person perceives now, as the environment summarises it: bounded,
    # banded, and already capped per kind (Minecraft's:
    # `person_minecraft.situation.situation_facts`). The core adds what it owns.
    situation = [dict(fact) for fact in situation]
    if place is not None:
        situation.append(
            {
                "fact": "place",
                "value": str(place["place_id"]),
                "label": labels.get(str(place["place_id"])),
                "certain": float(place["confidence"]) >= 0.5,
            }
        )
    situation.append({"fact": "home_relation", "value": home_relation})
    if world_available is not None:
        situation.append({"fact": "world_available", "value": bool(world_available)})

    memories = [
        {
            "kind": str(item["kind"]),
            "subjects": capped(item.get("subjects", ()), CAPS["list_items"]),
            "details": dict(item.get("details") or {}),
            "place": place_ref(item.get("place")),
            "source": item.get("source", "perceived"),
        }
        for item in list(working_memory)[-CAPS["memories"] :]
    ]
    document: dict[str, Any] = {
        "schema": CONTEXT_SCHEMA,
        "request": {
            "reason": reason,
            "refs": capped(request_refs, CAPS["request_refs"]),
        },
        "self": dict(self_knowledge) if self_knowledge is not None else None,
        "situation": cite("s", "situation", capped(situation, CAPS["situation"])),
        "memories": cite("m", "memories", memories),
        "beliefs": cite("b", "beliefs", capped(beliefs, CAPS["beliefs"])),
        "hypotheses": cite("h", "hypotheses", capped(hypotheses, CAPS["hypotheses"])),
        "goals": cite("g", "goals", capped(goals, CAPS["goals"])),
        "projects": cite("p", "projects", capped(projects, CAPS["projects"])),
        "recent": cite("r", "recent", list(recent)[-CAPS["recent"] :]),
        "capabilities": cite(
            "c",
            "capabilities",
            (
                {
                    "skill": capability.skill,
                    "summary": capability.summary[:160],
                    "effects": list(capability.effects),
                }
                for capability in capped(capabilities, CAPS["capabilities"])
            ),
        ),
        "vocabulary": {name: list(values) for name, values in sorted(vocabulary.items())},
    }
    return DeliberationContext(document=document, refs=refs)
