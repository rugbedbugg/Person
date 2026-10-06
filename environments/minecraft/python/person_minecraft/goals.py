"""Minecraft survival: homeostatic drives and the goals they raise (ADR 0025).

Moved from `person_cognition.goals`, which keeps the environment-neutral
mechanism (Goal, Drive, the goal stack). What a body needs in Minecraft, and
which goals those needs raise, belong to the Minecraft profile. Needs produce
urgency rather than commands.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from person_cognition.affect import GoalCharacter
from person_cognition.goals import CORE_GOAL_TYPES, Drive, Goal
from person_epistemics import DecisionState
from person_skills import Condition

from .perception import MinecraftPercepts

#: Minecraft's goal types, and the core's own, in the order they are listed
#: to a deliberation (ADR 0020).
GOAL_TYPES: tuple[str, ...] = (
    "SURVIVE_IMMEDIATE",
    "SECURE_FOOD",
    "SECURE_SHELTER",
    "ESTABLISH_TOOLS",
    "ESTABLISH_STORAGE",
    "RECOVER_HOME",
    "MAINTAIN_RESERVES",
    *CORE_GOAL_TYPES,
)

Decision = DecisionState[MinecraftPercepts, Any]


#: Whether a drive is pressing (`person_cognition.goals.Drive`): health, food
#: and safety are; while one is urgent Person takes up no project and no
#: investigation. The rest are needs it can meet at leisure.
PRESSING = True
NOT_PRESSING = False

#: Facts whose pursuit keeps Person close and protected, as opposed to going
#: out and getting things: a goal that would make one of them true is
#: `protective` for affect (`person_cognition.affect.GoalCharacter`).
PROTECTIVE_FACTS: frozenset[str] = frozenset(
    {
        "shelter_complete",
        "sheltered",
        "at_home",
        "owned_storage_available",
        "stored_surplus",
        "safe",
    }
)


def goal_character(completion_facts: frozenset[str]) -> GoalCharacter:
    """What a goal with this completion condition is like, for affect."""
    return "protective" if completion_facts & PROTECTIVE_FACTS else "outgoing"


def homeostasis(decision: Decision, state: dict[str, float]) -> list[Drive]:
    """Survival needs, expressed as urgency rather than as actions."""
    percepts = decision.percepts.percepts
    vitals = percepts.vitals
    reserve = int(decision.beliefs.value("food_reserve", 0) or 0)
    drives: list[Drive] = []

    drives.append(
        Drive("health", max(0.0, (20.0 - vitals["health"]) / 20.0), "health_below_full", PRESSING)
    )
    drives.append(
        Drive("food", max(0.0, (20.0 - vitals["food"]) / 20.0), "food_below_full", PRESSING)
    )

    threat = 0.0
    for hostile in percepts.nearby["hostiles"]:
        threat = max(threat, max(0.0, 1.0 - hostile["distance"] / 16.0))
    for hazard in percepts.nearby["hazards"]:
        threat = max(threat, max(0.0, 1.0 - hazard["distance"] / 4.0))
    drives.append(Drive("safety", threat, "threat_proximity", PRESSING))

    night = percepts.night
    shelter_gap = 0.0 if state.get("shelter_complete", 0) >= 1 else (1.0 if night else 0.5)
    drives.append(Drive("shelter", shelter_gap, "shelter_incomplete", NOT_PRESSING))

    tool_gap = max(0.0, (2.0 - state.get("tool_tier", 0)) / 2.0)
    drives.append(Drive("tool_readiness", tool_gap, "tool_tier_below_stone", NOT_PRESSING))

    drives.append(
        Drive("fuel", 0.0 if state.get("fuel", 0) >= 4 else 0.5, "fuel_reserve_low", NOT_PRESSING)
    )
    drives.append(
        Drive(
            "food_reserve",
            0.0 if reserve >= 4 else 0.6,
            "stored_food_reserve_low",
            NOT_PRESSING,
        )
    )
    capacity = percepts.inventory["freeSlots"]
    drives.append(
        Drive(
            "inventory_capacity",
            0.0 if capacity > 4 else 0.7,
            "inventory_nearly_full",
            NOT_PRESSING,
        )
    )
    return drives


def _condition(fact: str, value: float) -> Condition:
    return Condition(fact, ">=", value)


class SurvivalGoalProvider:
    """Deterministic survival goals, ordered by homeostatic urgency."""

    name = "survival"

    def propose(self, decision: Decision, state: dict[str, float], tick: int) -> list[Goal]:
        percepts = decision.percepts.percepts
        home_relation = decision.self_state.home_relation
        reserve = int(decision.beliefs.value("food_reserve", 0) or 0)
        drives = {drive.name: drive for drive in homeostasis(decision, state)}
        night = percepts.night
        proposals: list[Goal] = []

        def add(
            goal_type: str,
            priority: float,
            conditions: Sequence[Condition],
            reasons: Sequence[str],
            source: str = "homeostasis",
        ) -> None:
            proposals.append(
                Goal(
                    goal_id=f"goal_{goal_type.lower()}",
                    goal_type=goal_type,
                    priority=round(min(1000.0, max(0.0, priority)), 3),
                    source=source,
                    created_at_tick=tick,
                    status="QUEUED",
                    completion_condition=tuple(conditions),
                    reason_codes=tuple(reasons),
                )
            )

        safety = drives["safety"].urgency
        health = drives["health"].urgency
        if safety > 0.4 or percepts.vitals["health"] < 7:
            add(
                "SURVIVE_IMMEDIATE",
                900 + 100 * safety,
                [_condition("safe", 1)],
                ["threat_present" if safety > 0.4 else "health_critical"],
                source="emergency",
            )

        food_urgency = drives["food"].urgency
        if percepts.vitals["food"] < 18:
            add(
                "SECURE_FOOD",
                400 + 400 * food_urgency + 100 * health,
                [_condition("food_level", 16)],
                ["food_band_below_full"],
            )

        if state.get("shelter_complete", 0) < 1:
            add(
                "SECURE_SHELTER",
                350 + (300 if night else 0) + 100 * drives["shelter"].urgency,
                [_condition("shelter_complete", 1)],
                ["night_approaching" if night else "shelter_incomplete"],
            )

        if state.get("tool_tier", 0) < 2:
            add(
                "ESTABLISH_TOOLS",
                260 + 60 * drives["tool_readiness"].urgency,
                [_condition("tool_tier", 2)],
                ["tool_tier_below_stone"],
            )

        # Storage serves basic reserves and inventory capacity, which are needs
        # (`PERSON_SPEC` section 17). The `improve_home` project also has it as
        # a milestone, at higher priority, when Person commits to its home.
        if state.get("owned_storage_available", 0) < 1:
            add(
                "ESTABLISH_STORAGE",
                220,
                [_condition("owned_storage_available", 1)],
                ["no_owned_storage"],
            )

        # Person's own belief that it is far from a home it remembers, never
        # a distance the runtime measured (C8).
        if home_relation == "far" and night:
            add(
                "RECOVER_HOME",
                600,
                [_condition("at_home", 1)],
                ["far_from_home_at_night"],
            )

        if reserve < 4 and state.get("owned_storage_available", 0) >= 1:
            add(
                "MAINTAIN_RESERVES",
                180,
                [_condition("stored_surplus", 1)],
                ["stored_food_reserve_low"],
            )

        proposals.sort(key=lambda goal: (-goal.priority, goal.goal_type))
        return proposals


def idle_goal(tick: int) -> Goal:
    """What Person does when nothing is urgent: rest, safely."""
    return Goal(
        goal_id="goal_maintain_reserves",
        goal_type="MAINTAIN_RESERVES",
        priority=10.0,
        source="maintenance",
        created_at_tick=tick,
        status="QUEUED",
        completion_condition=(Condition("rested", ">=", 1),),
        reason_codes=("nothing_urgent",),
    )
