"""Prediction error: what the skill contract promised against what happened.

Every SkillSpec declares its expected effects, and the planner reasons with
them as if they were true. This module measures how true they actually are.

It is instrumentation, not a learner. Nothing here feeds back into routine
selection in this milestone: the records exist so a later world model can be
built on measurements rather than on guesses, and so that a contract which is
quietly wrong shows up as data instead of as unexplained failures.

Both sides of the comparison are expressed in the symbolic planning state. That
keeps one taxonomy of what an item means, owned by the runtime that classifies
inventories, rather than a second copy of it here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["none", "minor", "major", "inverted", "unobserved"]

SEVERITY_ORDER: dict[str, int] = {
    "none": 0,
    "minor": 1,
    "major": 2,
    "inverted": 3,
    "unobserved": 1,
}

#: Facts worth reporting when they move without being predicted. Volatile facts
#: such as hunger or what happens to be in view change for reasons that have
#: nothing to do with the skill, and reporting those would bury the signal.
TRACKED_FACTS: frozenset[str] = frozenset(
    {
        "wood",
        "planks",
        "stone",
        "coal",
        "fuel",
        "raw_food",
        "cooked_food",
        "plant_food",
        "edible_food",
        "building_materials",
        "chest_item",
        "crafting_table",
        "wooden_pickaxe",
        "stone_pickaxe",
        "wooden_axe",
        "stone_axe",
        "tool_tier",
        "shelter_complete",
        "furnace_placed",
        "owned_storage_available",
        "at_home",
        "safe",
        "sheltered",
    }
)

#: A tolerance below which a numeric miss is not worth calling an error.
ABSOLUTE_TOLERANCE = 1.0
RELATIVE_TOLERANCE = 0.25


@dataclass(frozen=True, slots=True)
class FactError:
    fact: str
    before: float
    predicted: float
    observed: float
    error: float
    severity: Severity

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact": self.fact,
            "before": self.before,
            "predicted": self.predicted,
            "observed": self.observed,
            "error": round(self.error, 6),
            "severity": self.severity,
        }


@dataclass(slots=True)
class PendingPrediction:
    """A prediction awaiting the observation that will settle it."""

    decision_id: str
    context_id: str
    routine_id: str
    goal_id: str
    requested_skill: str
    state_before: dict[str, float]
    tick: int
    executed_skill: str | None = None
    expected_effects: tuple[dict[str, Any], ...] = ()
    status: str | None = None
    emergency: bool = False
    elapsed_ticks: int = 0
    health_cost: float = 0.0
    settled: bool = False
    evidence_refs: list[str] = field(default_factory=list)


def apply_effect(before: float, op: str, value: float) -> float:
    """The planner's own effect semantics, used to turn an effect into a number."""
    match op:
        case "+=":
            return before + value
        case "-=":
            return max(0.0, before - value)
        case "=":
            return value
        case "max":
            return max(before, value)
    raise ValueError(f"Unknown effect operator {op!r}")


def _severity(before: float, predicted: float, observed: float) -> Severity:
    error = observed - predicted
    if error == 0:
        return "none"
    predicted_change = predicted - before
    observed_change = observed - before
    if predicted_change != 0 and observed_change * predicted_change <= 0:
        # The fact moved the wrong way, or did not move at all when it was
        # supposed to. That is the interesting case for a world model.
        return "inverted"
    tolerance = max(ABSOLUTE_TOLERANCE, abs(predicted_change) * RELATIVE_TOLERANCE)
    return "minor" if abs(error) <= tolerance else "major"


def compare(
    expected_effects: Sequence[Mapping[str, Any]],
    state_before: Mapping[str, float],
    state_after: Mapping[str, float],
) -> tuple[list[FactError], list[dict[str, Any]], Severity]:
    """Compare declared effects with the observed symbolic change."""
    errors: list[FactError] = []
    predicted_facts: set[str] = set()
    for effect in expected_effects:
        fact = str(effect["fact"])
        predicted_facts.add(fact)
        before = float(state_before.get(fact, 0.0))
        predicted = apply_effect(before, str(effect["op"]), float(effect["value"]))
        observed = float(state_after.get(fact, 0.0))
        errors.append(
            FactError(
                fact=fact,
                before=before,
                predicted=predicted,
                observed=observed,
                error=observed - predicted,
                severity=_severity(before, predicted, observed),
            )
        )

    unexplained = [
        {
            "fact": fact,
            "before": float(state_before.get(fact, 0.0)),
            "observed": float(state_after.get(fact, 0.0)),
        }
        for fact in sorted(TRACKED_FACTS - predicted_facts)
        if float(state_after.get(fact, 0.0)) != float(state_before.get(fact, 0.0))
    ]

    worst: Severity = "none"
    for entry in errors:
        if SEVERITY_ORDER[entry.severity] > SEVERITY_ORDER[worst]:
            worst = entry.severity
    return errors, unexplained, worst


def build_payload(
    pending: PendingPrediction,
    state_after: Mapping[str, float] | None,
) -> dict[str, Any]:
    """The evidence payload for one settled prediction."""
    if state_after is None:
        return {
            "decision_id": pending.decision_id,
            "context_id": pending.context_id,
            "routine_id": pending.routine_id,
            "goal_id": pending.goal_id,
            "requested_skill": pending.requested_skill,
            "executed_skill": pending.executed_skill,
            "status": pending.status,
            "emergency": pending.emergency,
            "elapsed_ticks": pending.elapsed_ticks,
            "health_cost": pending.health_cost,
            "expected": [dict(effect) for effect in pending.expected_effects],
            "observed": [],
            "unexplained": [],
            "severity": "unobserved",
            "reason": "no observation followed the outcome",
            "evidence_refs": list(pending.evidence_refs),
        }

    errors, unexplained, worst = compare(
        pending.expected_effects, pending.state_before, state_after
    )
    return {
        "decision_id": pending.decision_id,
        "context_id": pending.context_id,
        "routine_id": pending.routine_id,
        "goal_id": pending.goal_id,
        "requested_skill": pending.requested_skill,
        "executed_skill": pending.executed_skill,
        "status": pending.status,
        "emergency": pending.emergency,
        "elapsed_ticks": pending.elapsed_ticks,
        "health_cost": pending.health_cost,
        "expected": [dict(effect) for effect in pending.expected_effects],
        "observed": [entry.as_dict() for entry in errors],
        "unexplained": unexplained,
        "severity": worst,
        "evidence_refs": list(pending.evidence_refs),
    }
