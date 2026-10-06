"""What Minecraft experience is worth remembering, and what it is about (ADR 0007, 0025).

The episode mechanism is Person's (`person_cognition.memory`). Which percepts
are worth an episode, and which memory subjects a Minecraft skill or planning
fact is about, are the Minecraft profile's. Everything here drafts from
current percepts or reported outcomes: it never reads a memory, and nothing it
drafts can be anything but lived (`Provenance` refuses other sources).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from person_cognition.memory.encoding import DETAIL_ITEMS
from person_cognition.memory.episodes import EpisodeDraft, Provenance
from person_cognition.memory.salience import base_salience
from person_skills import SkillRegistry

from .facts import EVIDENCE_FACTS
from .perception import MinecraftPercepts

#: Resource categories worth remembering having seen.
RESOURCE_SUBJECTS: Mapping[str, str] = {
    "wood": "wood",
    "stone": "stone",
    "coal": "coal",
    "plant_food": "plant_food",
}

#: Skills whose routine success is not an experience worth keeping. Their
#: failures, and anything the runtime did instead of them, still are.
UNREMARKABLE_SKILLS: frozenset[str] = frozenset({"look", "look_around", "wait_safely"})

#: What a skill category is about, for remembering having done it.
CATEGORY_SUBJECTS: Mapping[str, tuple[str, ...]] = {
    "food": ("food",),
    "shelter": ("shelter",),
    "crafting": ("crafting",),
    "storage": ("storage",),
    "emergency": ("danger",),
}

#: What each emergency the runtime handles is about, beyond the danger every
#: emergency is (the core subject `danger`). One entry per trigger in the
#: manifest's `emergency.triggers`, so a new trigger cannot go unclassified.
EMERGENCY_SUBJECTS: Mapping[str, tuple[str, ...]] = {
    "imminent_lethal_damage": (),
    "lava_exposure": (),
    "suffocation": (),
    "hostile_swarm": ("hostile",),
    "immediate_threat": ("hostile",),
    "critical_health": (),
    "critical_hunger": (),
    "dangerous_path": (),
    "protected_area_entry": (),
    "invalid_destructive_interaction": (),
    "forbidden_target": (),
    "unauthorized_deposit": (),
}


def emergency_subjects(trigger: str) -> tuple[str, ...]:
    """The subjects, beyond danger, of an emergency the runtime reported."""
    return EMERGENCY_SUBJECTS[trigger]


def noticed(percepts: MinecraftPercepts) -> dict[str, list[Mapping[str, Any]]]:
    """The subjects present in what Person perceives, and the percepts behind each.

    Resources, animals, players and containers count only when recognised. A
    threat counts at the edge of vision too, as it does for the planner.
    """
    nearby: Mapping[str, Any] = percepts.nearby
    found: dict[str, list[Mapping[str, Any]]] = {}

    def add(subject: str, percept: Mapping[str, Any]) -> None:
        found.setdefault(subject, []).append(percept)

    for resource in nearby["resources"]:
        subject = RESOURCE_SUBJECTS.get(resource["kind"])
        if subject is not None and resource["detail"] == "central":
            add(subject, resource)
    for key, subject in (
        ("passiveAnimals", "animal"),
        ("players", "player"),
        ("containers", "container"),
    ):
        for percept in nearby[key]:
            if percept["detail"] == "central":
                add(subject, percept)
    for hostile in nearby["hostiles"]:
        add("hostile", hostile)
    for hazard in nearby["hazards"]:
        add("hazard", hazard)
    return found


def _name(percept: Mapping[str, Any]) -> str | None:
    if percept["detail"] != "central":
        return None
    name = percept.get("name", percept.get("kind"))
    return str(name) if name is not None else None


def perceived(
    state: MinecraftPercepts, subject: str, percepts: list[Mapping[str, Any]]
) -> EpisodeDraft:
    """Having seen something of one kind: what it was, how many, how near."""
    nearest = min(percepts, key=lambda percept: float(percept["distance"]))
    names = sorted({name for name in map(_name, percepts) if name is not None})
    details = {
        "what": names[:DETAIL_ITEMS],
        "count": len(percepts),
        "recognised": bool(names),
        "nearest_range": str(nearest["rangeBand"]),
        "day_phase": str(state.sky["dayPhase"]),
    }
    subjects = (subject, "danger") if subject in {"hostile", "hazard"} else (subject,)
    return EpisodeDraft(
        kind="perceived",
        subjects=subjects,
        details=details,
        provenance=Provenance("perceived", message_id=state.message_id),
        salience=base_salience("perceived", subjects, details),
    )


def skill_subjects(skill_id: str, registry: SkillRegistry) -> tuple[str, ...]:
    """What doing a skill is about: the evidence it needs, and its category."""
    if skill_id not in registry.ids:
        return ("self",)
    spec = registry.get(skill_id)
    subjects: set[str] = set(CATEGORY_SUBJECTS.get(spec.category, ()))
    for condition in spec.preconditions:
        if condition.fact in EVIDENCE_FACTS:
            subjects.add(evidence_subject(condition.fact))
    return tuple(sorted(subjects)) or ("self",)


def evidence_subject(fact: str) -> str:
    if fact == "permitted_container_nearby":
        return "container"
    return fact.removeprefix("reachable_")


def evidence_subjects(facts: Iterable[str]) -> frozenset[str]:
    """The memory subjects that evidence facts are about."""
    return frozenset(evidence_subject(fact) for fact in facts)
