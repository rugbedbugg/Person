"""Turning what cognition was given into episodes, through a whitelist.

Every function here reads a message cognition actually received, or a decision
cognition actually made, and copies named fields out of it. None of them
copies a message wholesale, so a field added to a message later does not leak
into memory by accident. None of them sees a `WorldSnapshot`, the placement
ledger, or a skill's choice of target, because cognition never does.

An action is remembered by the skill that executed and by what Person felt
happen. It is never remembered as done to a particular thing: until skills
act on perceived referents (C4), nothing says which thing that was.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from person_planner import EVIDENCE_FACTS
from person_skills import SkillRegistry

from .episodes import EpisodeDraft, Provenance
from .salience import base_salience

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

#: How many names, effects or inventory changes one episode keeps.
DETAIL_ITEMS = 4


def noticed(observation: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    """The subjects present in an observation, and the percepts behind each.

    Resources, animals, players and containers count only when recognised. A
    threat counts at the edge of vision too, as it does for the planner.
    """
    nearby = observation["nearby"]
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
    observation: Mapping[str, Any], subject: str, percepts: list[Mapping[str, Any]]
) -> EpisodeDraft:
    """Having seen something of one kind: what it was, how many, how near."""
    nearest = min(percepts, key=lambda percept: float(percept["distance"]))
    names = sorted({name for name in map(_name, percepts) if name is not None})
    details = {
        "what": names[:DETAIL_ITEMS],
        "count": len(percepts),
        "recognised": bool(names),
        "nearest_range": str(nearest["rangeBand"]),
        "day_phase": str(observation["environment"]["dayPhase"]),
    }
    subjects = (subject, "danger") if subject in {"hostile", "hazard"} else (subject,)
    return EpisodeDraft(
        kind="perceived",
        subjects=subjects,
        details=details,
        provenance=Provenance("perceived", message_id=str(observation["messageId"])),
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
            subjects.add(_evidence_subject(condition.fact))
    return tuple(sorted(subjects)) or ("self",)


def _evidence_subject(fact: str) -> str:
    if fact == "permitted_container_nearby":
        return "container"
    return fact.removeprefix("reachable_")


def acted(
    outcome: Mapping[str, Any], registry: SkillRegistry, evidence_event_id: str | None
) -> EpisodeDraft | None:
    """What Person did, as the runtime reported it and as Person felt it."""
    executed = str(outcome["executedSkill"])
    status = str(outcome["status"])
    emergency = bool(outcome["emergency"])
    if executed in UNREMARKABLE_SKILLS and status == "SUCCESS" and not emergency:
        return None
    details: dict[str, Any] = {
        "skill": executed,
        "status": status,
        "emergency": emergency,
        "effects": sorted(str(effect) for effect in outcome["effects"])[:DETAIL_ITEMS],
        "inventory": [
            f"{change['name']}:{int(change['delta']):+d}"
            for change in outcome["inventoryDelta"][:DETAIL_ITEMS]
        ],
        "health_cost": float(outcome["healthCost"]),
    }
    if outcome["requestedSkill"] != executed:
        # What Person meant to do, when the runtime did something else.
        details["requested"] = str(outcome["requestedSkill"])
    subjects = skill_subjects(executed, registry)
    return EpisodeDraft(
        kind="acted",
        subjects=subjects,
        details=details,
        provenance=Provenance(
            "action_outcome",
            message_id=str(outcome["messageId"]),
            decision_id=str(outcome["decisionId"]),
            evidence_event_id=evidence_event_id,
        ),
        salience=base_salience("acted", subjects, details),
    )


def endangered(message: Mapping[str, Any], evidence_event_id: str | None) -> EpisodeDraft:
    """The runtime took over to keep Person alive."""
    trigger = str(message["trigger"])
    details = {"trigger": trigger, "response": str(message["action"])}
    subjects = ("danger", "hostile") if "hostile" in trigger or "threat" in trigger else ("danger",)
    return EpisodeDraft(
        kind="endangered",
        subjects=subjects,
        details=details,
        provenance=Provenance(
            "action_outcome",
            message_id=str(message["messageId"]),
            decision_id=message.get("decisionId"),
            evidence_event_id=evidence_event_id,
        ),
        salience=base_salience("endangered", subjects, details),
    )


def hurt(before: float, observation: Mapping[str, Any]) -> EpisodeDraft | None:
    """Losing health, felt between one observation and the next."""
    after = float(observation["vitals"]["health"])
    lost = round(before - after, 2)
    if lost < 1.0:
        return None
    details = {"health_lost": lost, "health_after": after}
    subjects = ("self", "danger")
    return EpisodeDraft(
        kind="hurt",
        subjects=subjects,
        details=details,
        provenance=Provenance("proprioceptive", message_id=str(observation["messageId"])),
        salience=base_salience("hurt", subjects, details),
    )


def searched(
    sought: tuple[str, ...], conclusion: str, looks: int, decision_id: str | None
) -> EpisodeDraft:
    """A bounded search Person made, and what it concluded, in its own words."""
    subjects = tuple(sorted({_evidence_subject(fact) for fact in sought}))
    details = {"sought": list(subjects), "conclusion": conclusion, "looks": looks}
    return EpisodeDraft(
        kind="searched",
        subjects=subjects,
        details=details,
        provenance=Provenance("own_decision", decision_id=decision_id),
        salience=base_salience("searched", subjects, details),
    )


def evidence_subjects(facts: tuple[str, ...]) -> frozenset[str]:
    """The memory subjects that evidence facts are about."""
    return frozenset(_evidence_subject(fact) for fact in facts)
