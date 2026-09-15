"""Coarse context, homeostatic goals, and the interruption/resumption stack."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition import GoalStack, SurvivalGoalProvider, decision_context
from person_cognition.context import context_id
from person_planner import symbolic_state

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def observation() -> dict[str, Any]:
    return json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )


def test_context_serialisation_is_stable_and_greppable(observation: dict[str, Any]) -> None:
    identifier = context_id(observation)
    assert identifier == context_id(deepcopy(observation))
    assert len(identifier) <= 64
    assert identifier.startswith("h_")
    assert ".f_" in identifier and ".t_" in identifier


def test_equivalent_situations_share_a_context(observation: dict[str, Any]) -> None:
    nudged = deepcopy(observation)
    nudged["vitals"]["health"] += 0.4
    nudged["environment"]["position"]["x"] += 3
    nudged["environment"]["timeOfDay"] += 200
    nudged["inventory"]["items"].append({"name": "dirt", "count": 3})
    assert context_id(nudged) == context_id(observation)


def test_meaningful_differences_change_the_context(observation: dict[str, Any]) -> None:
    hurt = deepcopy(observation)
    hurt["vitals"]["health"] = 4
    assert context_id(hurt) != context_id(observation)

    threatened = deepcopy(observation)
    threatened["nearby"]["hostiles"] = [
        {
            "entityId": 1,
            "name": "zombie",
            "position": {"x": 1, "y": 64, "z": 1},
            "distance": 3.0,
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    assert decision_context(threatened).threat == "immediate"
    assert context_id(threatened) != context_id(observation)


def test_the_context_space_stays_small() -> None:
    from person_cognition.context import (
        DAY_PHASES,
        FOOD_BANDS,
        FOOD_STATES,
        HEALTH_BANDS,
        HOME_STATES,
        THREAT_LEVELS,
        TOOL_TIERS,
    )

    total = 1
    for dimension in (
        HEALTH_BANDS,
        FOOD_BANDS,
        DAY_PHASES,
        THREAT_LEVELS,
        HOME_STATES,
        TOOL_TIERS,
        FOOD_STATES,
    ):
        total *= len(dimension)
    assert total <= 12000, "the decision context must not explode"


def test_hunger_raises_the_priority_of_securing_food(observation: dict[str, Any]) -> None:
    provider = SurvivalGoalProvider()
    fed = deepcopy(observation)
    fed["vitals"]["food"] = 17
    hungry = deepcopy(observation)
    hungry["vitals"]["food"] = 3

    def priority_of(document: dict[str, Any]) -> float:
        goals = provider.propose(document, symbolic_state(document), 100)
        food = next(goal for goal in goals if goal.goal_type == "SECURE_FOOD")
        return food.priority

    assert priority_of(hungry) > priority_of(fed)


def test_a_threat_produces_the_highest_priority_goal(observation: dict[str, Any]) -> None:
    threatened = deepcopy(observation)
    threatened["nearby"]["hostiles"] = [
        {
            "entityId": 1,
            "name": "zombie",
            "position": {"x": 1, "y": 64, "z": 1},
            "distance": 3.0,
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    goals = SurvivalGoalProvider().propose(threatened, symbolic_state(threatened), 10)
    assert goals[0].goal_type == "SURVIVE_IMMEDIATE"
    assert goals[0].source == "emergency"


def test_goals_suspend_and_resume_around_an_emergency(observation: dict[str, Any]) -> None:
    provider = SurvivalGoalProvider()
    stack = GoalStack()

    calm = deepcopy(observation)
    calm["vitals"]["food"] = 19
    state = symbolic_state(calm)
    active = stack.update(provider.propose(calm, state, 0), state, 0)
    assert active is not None
    building = active.goal_id
    assert active.goal_type in {"SECURE_SHELTER", "ESTABLISH_TOOLS", "ESTABLISH_STORAGE"}

    threatened = deepcopy(calm)
    threatened["nearby"]["hostiles"] = [
        {
            "entityId": 1,
            "name": "zombie",
            "position": {"x": 1, "y": 64, "z": 1},
            "distance": 2.0,
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    danger_state = symbolic_state(threatened)
    emergency = stack.update(provider.propose(threatened, danger_state, 10), danger_state, 10)
    assert emergency is not None
    assert emergency.goal_type == "SURVIVE_IMMEDIATE"
    suspended = {goal.goal_id for goal in stack.suspended()}
    assert building in suspended
    assert stack.entries[building].suspension_reason == "preempted_by_survive_immediate"

    resumed = stack.update(provider.propose(calm, state, 20), state, 20)
    assert resumed is not None
    assert resumed.goal_id == building
    assert resumed.status == "ACTIVE"
    assert stack.resume_counts().get(building, 0) >= 1


def test_a_satisfied_goal_completes_and_leaves_the_stack(observation: dict[str, Any]) -> None:
    provider = SurvivalGoalProvider()
    stack = GoalStack()
    hungry = deepcopy(observation)
    hungry["vitals"]["food"] = 5
    state = symbolic_state(hungry)
    stack.update(provider.propose(hungry, state, 0), state, 0)
    assert "goal_secure_food" in stack.entries

    fed = deepcopy(hungry)
    fed["vitals"]["food"] = 20
    fed_state = symbolic_state(fed)
    stack.update(provider.propose(fed, fed_state, 30), fed_state, 30)
    assert stack.entries["goal_secure_food"].status == "COMPLETE"
    assert stack.active is None or stack.active.goal_id != "goal_secure_food"


def test_a_blocked_goal_stops_being_selected(observation: dict[str, Any]) -> None:
    provider = SurvivalGoalProvider()
    stack = GoalStack()
    state = symbolic_state(observation)
    active = stack.update(provider.propose(observation, state, 0), state, 0)
    assert active is not None
    stack.block(active.goal_id, "no_feasible_plan", 1)
    assert stack.entries[active.goal_id].status == "BLOCKED"
    following = stack.update(provider.propose(observation, state, 2), state, 2)
    assert following is None or following.goal_id != active.goal_id
