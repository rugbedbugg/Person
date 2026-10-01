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

CONTEXT_SCHEMA = "person-deliberation-context-v1"

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
    "inventory": 12,
    "memories": 3,
    "beliefs": 12,
    "hypotheses": 6,
    "goals": 5,
    "projects": 4,
    "recent": 8,
    "capabilities": 32,
    "list_items": 4,
}

NEARBY_KINDS: tuple[str, ...] = (
    "hostiles",
    "passiveAnimals",
    "players",
    "resources",
    "hazards",
    "containers",
    "workstations",
)


def _band(value: float, bands: Sequence[tuple[float, str]], top: str) -> str:
    for limit, name in bands:
        if value <= limit:
            return name
    return top


def health_band(health: float) -> str:
    return _band(health, ((6, "critical"), (12, "low")), "healthy")


def food_band(food: float) -> str:
    return _band(food, ((6, "critical"), (12, "low"), (17, "sufficient")), "full")


def breath_band(breath: float) -> str:
    return _band(breath, ((3, "critical"), (7, "short")), "normal")


def _capped(items: Iterable[Any], cap: int) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if len(out) >= cap:
            break
        out.append(item)
    return out


@dataclass(frozen=True, slots=True)
class DeliberationContext:
    """One context, as the model will see it, with its citable references."""

    document: dict[str, Any]
    #: Reference -> (section, item), for the grounding gate.
    refs: Mapping[str, tuple[str, dict[str, Any]]]

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
    observation: Mapping[str, Any] | None,
    place: Mapping[str, Any] | None,
    working_memory: Sequence[Mapping[str, Any]],
    beliefs: Sequence[Mapping[str, Any]],
    hypotheses: Sequence[Mapping[str, Any]],
    goals: Sequence[Mapping[str, Any]],
    projects: Sequence[Mapping[str, Any]],
    recent: Sequence[Mapping[str, Any]],
    capabilities: Sequence[Capability],
    vocabulary: Mapping[str, Sequence[str]],
) -> DeliberationContext:
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

    situation: list[dict[str, Any]] = []
    if observation is not None:
        vitals = observation["vitals"]
        environment = observation["environment"]
        situation.append({"fact": "health", "value": health_band(float(vitals["health"]))})
        situation.append({"fact": "food", "value": food_band(float(vitals["food"]))})
        situation.append({"fact": "breath", "value": breath_band(float(vitals["breath"]))})
        situation.append({"fact": "day_phase", "value": str(environment["dayPhase"])})
        situation.append({"fact": "weather", "value": str(environment["weather"])})
        for kind in NEARBY_KINDS:
            seen = observation.get("nearby", {}).get(kind, [])
            names: dict[str, dict[str, Any]] = {}
            for thing in seen:
                name = str(thing.get("name") or thing.get("kind"))
                entry = names.setdefault(name, {"count": 0, "nearest": thing.get("rangeBand")})
                entry["count"] += 1
            for name, entry in _capped(sorted(names.items()), CAPS["in_view_per_kind"]):
                situation.append(
                    {
                        "fact": f"in_view.{kind}",
                        "value": name,
                        "count": entry["count"],
                        "nearest": entry["nearest"],
                    }
                )
        categories = observation.get("inventory", {}).get("categories", {})
        held = [(name, count) for name, count in sorted(categories.items()) if count]
        for name, count in _capped(held, CAPS["inventory"]):
            situation.append({"fact": f"holding.{name}", "value": int(count)})
    if place is not None:
        situation.append(
            {
                "fact": "place",
                "value": str(place["place_id"]),
                "certain": float(place["confidence"]) >= 0.5,
            }
        )
    if world_available is not None:
        situation.append({"fact": "world_available", "value": bool(world_available)})

    memories = [
        {
            "kind": str(item["kind"]),
            "subjects": _capped(item.get("subjects", ()), CAPS["list_items"]),
            "details": dict(item.get("details") or {}),
            "place": item.get("place"),
            "source": item.get("source", "perceived"),
        }
        for item in list(working_memory)[-CAPS["memories"] :]
    ]
    document: dict[str, Any] = {
        "schema": CONTEXT_SCHEMA,
        "request": {
            "reason": reason,
            "refs": _capped(request_refs, CAPS["request_refs"]),
        },
        "self": dict(self_knowledge) if self_knowledge is not None else None,
        "situation": cite("s", "situation", _capped(situation, CAPS["situation"])),
        "memories": cite("m", "memories", memories),
        "beliefs": cite("b", "beliefs", _capped(beliefs, CAPS["beliefs"])),
        "hypotheses": cite("h", "hypotheses", _capped(hypotheses, CAPS["hypotheses"])),
        "goals": cite("g", "goals", _capped(goals, CAPS["goals"])),
        "projects": cite("p", "projects", _capped(projects, CAPS["projects"])),
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
                for capability in _capped(capabilities, CAPS["capabilities"])
            ),
        ),
        "vocabulary": {name: list(values) for name, values in sorted(vocabulary.items())},
    }
    return DeliberationContext(document=document, refs=refs)
