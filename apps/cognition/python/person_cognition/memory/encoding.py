"""Turning what cognition was given into episodes, through a whitelist.

Environment-neutral: which percepts are worth remembering, and what a skill
is about, are the environment profile's (`person_minecraft.memory`); this
module drafts the episodes every environment shares.

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

from .episodes import EpisodeDraft, Provenance
from .salience import base_salience

#: Skills whose routine success is not an experience worth keeping. Their
#: failures, and anything the runtime did instead of them, still are. Which
#: skills those are is the environment's to say; the loop passes them in.

#: How many names, effects or inventory changes one episode keeps.
DETAIL_ITEMS = 4


def acted(
    outcome: Mapping[str, Any],
    subjects: tuple[str, ...],
    evidence_event_id: str | None,
    *,
    unremarkable: frozenset[str] = frozenset(),
) -> EpisodeDraft | None:
    """What Person did, as the runtime reported it and as Person felt it.

    `subjects` is what doing the executed skill is about, in the environment's
    vocabulary; `unremarkable` the skills whose plain success is not worth an
    episode.
    """
    executed = str(outcome["executedSkill"])
    status = str(outcome["status"])
    emergency = bool(outcome["emergency"])
    if executed in unremarkable and status == "SUCCESS" and not emergency:
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


def endangered(
    message: Mapping[str, Any], evidence_event_id: str | None, about: tuple[str, ...]
) -> EpisodeDraft:
    """The runtime took over to keep Person alive.

    Every emergency is about `danger`. What else it is about (a hostile, in
    Minecraft) is the environment's to say: `about`, from
    `CognitiveEnvironment.emergency_subjects`.
    """
    trigger = str(message["trigger"])
    details = {"trigger": trigger, "response": str(message["action"])}
    subjects = ("danger", *about)
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


def hurt(before: float, after: float, message_id: str) -> EpisodeDraft | None:
    """Losing health, felt between one observation and the next."""
    lost = round(before - after, 2)
    if lost < 1.0:
        return None
    details = {"health_lost": lost, "health_after": after}
    subjects = ("self", "danger")
    return EpisodeDraft(
        kind="hurt",
        subjects=subjects,
        details=details,
        provenance=Provenance("proprioceptive", message_id=message_id),
        salience=base_salience("hurt", subjects, details),
    )


def died(
    *,
    health: float | None,
    food: float | None,
    threat_in_view: bool,
    goal_type: str | None,
    project_kind: str | None,
    message_id: str | None,
) -> EpisodeDraft:
    """Person's own death, from what it knew (ADR 0017, I3).

    Only the body it last felt, whether a threat was in view, and what it was
    doing. Never a cause, a place in the world, or the items it lost: the
    runtime knows those, Person does not. How it felt is journalled with the
    death as engineering evidence, and kept out of memory (ADR 0010).
    """
    details: dict[str, Any] = {
        "outcome": "died",
        "health_before": health,
        "food_before": food,
        "threat_in_view": threat_in_view,
        "goal": goal_type,
        "project": project_kind,
    }
    subjects = ("self", "danger")
    return EpisodeDraft(
        kind="died",
        subjects=subjects,
        details=details,
        provenance=Provenance("proprioceptive", message_id=message_id),
        salience=base_salience("died", subjects, details),
    )


def searched(
    subjects: tuple[str, ...], conclusion: str, looks: int, decision_id: str | None
) -> EpisodeDraft:
    """A bounded search Person made, and what it concluded, in its own words.

    `subjects` is what was sought, in the environment's memory vocabulary.
    """
    subjects = tuple(sorted(set(subjects)))
    details = {"sought": list(subjects), "conclusion": conclusion, "looks": looks}
    return EpisodeDraft(
        kind="searched",
        subjects=subjects,
        details=details,
        provenance=Provenance("own_decision", decision_id=decision_id),
        salience=base_salience("searched", subjects, details),
    )
