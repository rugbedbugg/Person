"""Minecraft's coarse context and homeostatic goals, and the core goal stack they feed.

Each is computed from a DecisionState (ADR 0026); `snapshot_decision` builds
one from a single observation, beliefs revised from its reports alone.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition import GoalStack
from person_minecraft.context import DecisionContext
from person_minecraft.context import decision_context as context_of
from person_minecraft.goals import SurvivalGoalProvider
from person_minecraft.offline import facts_from_observation, snapshot_decision

REPOSITORY = Path(__file__).resolve().parents[3]


def decision_context(observation: dict[str, Any]) -> DecisionContext:
    return context_of(snapshot_decision(observation))


def context_id(observation: dict[str, Any]) -> str:
    return decision_context(observation).identifier()


def symbolic_state(observation: dict[str, Any]) -> dict[str, float]:
    return facts_from_observation(observation)


class Provider(SurvivalGoalProvider):
    """Proposes from an observation, through the decision state it makes."""

    def propose(self, observation: Any, state: dict[str, float], tick: int) -> Any:  # type: ignore[override]
        return super().propose(snapshot_decision(observation), state, tick)


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
    nudged["payload"]["vitals"]["health"] += 0.4
    nudged["payload"]["environment"]["timeOfDay"] += 200
    nudged["payload"]["environment"]["lightLevel"] = max(
        0, nudged["payload"]["environment"]["lightLevel"] - 1
    )
    nudged["payload"]["inventory"]["items"].append({"name": "dirt", "count": 3})
    assert context_id(nudged) == context_id(observation)


def test_meaningful_differences_change_the_context(observation: dict[str, Any]) -> None:
    hurt = deepcopy(observation)
    hurt["payload"]["vitals"]["health"] = 4
    assert context_id(hurt) != context_id(observation)

    threatened = deepcopy(observation)
    threatened["payload"]["nearby"]["hostiles"] = [
        {
            "name": "zombie",
            "distance": 3.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "reach",
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    assert decision_context(threatened).threat == "immediate"
    assert context_id(threatened) != context_id(observation)


def test_the_context_space_stays_small() -> None:
    from person_minecraft.context import (
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
    provider = Provider()
    fed = deepcopy(observation)
    fed["payload"]["vitals"]["food"] = 17
    hungry = deepcopy(observation)
    hungry["payload"]["vitals"]["food"] = 3

    def priority_of(document: dict[str, Any]) -> float:
        goals = provider.propose(document, symbolic_state(document), 100)
        food = next(goal for goal in goals if goal.goal_type == "SECURE_FOOD")
        return food.priority

    assert priority_of(hungry) > priority_of(fed)


def test_a_threat_produces_the_highest_priority_goal(observation: dict[str, Any]) -> None:
    threatened = deepcopy(observation)
    threatened["payload"]["nearby"]["hostiles"] = [
        {
            "name": "zombie",
            "distance": 3.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "reach",
            "named": False,
            "tamed": False,
            "protectedTarget": True,
        }
    ]
    goals = Provider().propose(threatened, symbolic_state(threatened), 10)
    assert goals[0].goal_type == "SURVIVE_IMMEDIATE"
    assert goals[0].source == "emergency"


def test_goals_suspend_and_resume_around_an_emergency(observation: dict[str, Any]) -> None:
    provider = Provider()
    stack = GoalStack()

    calm = deepcopy(observation)
    calm["payload"]["vitals"]["food"] = 19
    state = symbolic_state(calm)
    active = stack.update(provider.propose(calm, state, 0), state, 0)
    assert active is not None
    building = active.goal_id
    assert active.goal_type in {"SECURE_SHELTER", "ESTABLISH_TOOLS", "ESTABLISH_STORAGE"}

    threatened = deepcopy(calm)
    threatened["payload"]["nearby"]["hostiles"] = [
        {
            "name": "zombie",
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
    provider = Provider()
    stack = GoalStack()
    hungry = deepcopy(observation)
    hungry["payload"]["vitals"]["food"] = 5
    state = symbolic_state(hungry)
    stack.update(provider.propose(hungry, state, 0), state, 0)
    assert "goal_secure_food" in stack.entries

    fed = deepcopy(hungry)
    fed["payload"]["vitals"]["food"] = 20
    fed_state = symbolic_state(fed)
    stack.update(provider.propose(fed, fed_state, 30), fed_state, 30)
    assert stack.entries["goal_secure_food"].status == "COMPLETE"
    assert stack.active is None or stack.active.goal_id != "goal_secure_food"


def test_a_blocked_goal_stops_being_selected(observation: dict[str, Any]) -> None:
    provider = Provider()
    stack = GoalStack()
    state = symbolic_state(observation)
    active = stack.update(provider.propose(observation, state, 0), state, 0)
    assert active is not None
    stack.block(active.goal_id, "no_feasible_plan", 1)
    assert stack.entries[active.goal_id].status == "BLOCKED"
    following = stack.update(provider.propose(observation, state, 2), state, 2)
    assert following is None or following.goal_id != active.goal_id


def test_blocking_a_goal_that_is_already_blocked_is_not_a_new_event(
    observation: dict[str, Any],
) -> None:
    # A goal stays blocked until something reopens it. Blocking it again
    # changes nothing, so it must not be recorded, or appraised, as a fresh
    # thwarting: one blockage would otherwise count once per observation.
    provider = Provider()
    stack = GoalStack()
    state = symbolic_state(observation)
    active = stack.update(provider.propose(observation, state, 0), state, 0)
    assert active is not None
    for tick in (1, 2, 3):
        stack.block(active.goal_id, "no_feasible_plan", tick)
    blocked = [event for event in stack.history if event[2] == "blocked"]
    assert blocked == [(1, active.goal_id, "blocked")]
    assert stack.entries[active.goal_id].status == "BLOCKED"

    stack.reopen(active.goal_id, 4)
    stack.block(active.goal_id, "no_feasible_plan", 5)
    assert [e for e in stack.history if e[2] == "blocked"][-1] == (5, active.goal_id, "blocked")


def test_every_context_identifier_fits_the_protocol() -> None:
    # The runtime receives the context id in every PolicyDecision; one the
    # protocol refuses means the decision is never sent.
    import re

    from person_minecraft.context import (
        DAY_PHASES,
        FOOD_BANDS,
        FOOD_STATES,
        HEALTH_BANDS,
        HOME_STATES,
        THREAT_LEVELS,
        TOOL_TIERS,
        DecisionContext,
    )

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3] / "packages/protocol/schemas/common.schema.json"
        ).read_text(encoding="utf-8")
    )
    pattern = re.compile(schema["$defs"]["contextId"]["pattern"])
    longest = DecisionContext(
        *(
            max(values, key=len)
            for values in (
                HEALTH_BANDS,
                FOOD_BANDS,
                DAY_PHASES,
                THREAT_LEVELS,
                HOME_STATES,
                TOOL_TIERS,
                FOOD_STATES,
            )
        )
    )
    assert pattern.fullmatch(longest.identifier()), longest.identifier()


def test_a_goal_proposed_already_satisfied_is_never_queued_or_completed(
    observation: dict[str, Any],
) -> None:
    # Food 16 and 17 are below full, so SECURE_FOOD is proposed, and at or
    # above its completion level of 16. It used to be queued and completed
    # again at every observation: a phantom success, appraised each time.
    provider = Provider()
    stack = GoalStack()
    for tick, food in enumerate([17, 16, 17, 16]):
        nearly = deepcopy(observation)
        nearly["payload"]["vitals"]["food"] = food
        state = symbolic_state(nearly)
        proposals = provider.propose(nearly, state, tick)
        assert any(goal.goal_type == "SECURE_FOOD" for goal in proposals)
        stack.update(proposals, state, tick)
    assert [event for event in stack.history if event[1] == "goal_secure_food"] == []

    hungry = deepcopy(observation)
    hungry["payload"]["vitals"]["food"] = 12
    state = symbolic_state(hungry)
    stack.update(provider.propose(hungry, state, 10), state, 10)
    assert stack.entries["goal_secure_food"].status in {"QUEUED", "ACTIVE"}


@pytest.mark.parametrize("goal_type", ["SECURE_SHELTER", "ESTABLISH_TOOLS", "PROJECT_ANYTHING"])
def test_no_goal_type_is_queued_when_proposed_already_satisfied(goal_type: str) -> None:
    from person_cognition import Goal
    from person_skills import Condition

    def proposal(tick: int) -> Goal:
        return Goal(
            goal_id=f"goal_{goal_type.lower()}",
            goal_type=goal_type,
            priority=500.0,
            source="test",
            created_at_tick=tick,
            status="QUEUED",
            completion_condition=(Condition("some_fact", ">=", 3),),
            reason_codes=("test",),
        )

    stack = GoalStack()
    met = {"some_fact": 3.0}
    for tick in range(4):
        assert stack.update([proposal(tick)], met, tick) is None
    assert stack.entries == {} and stack.history == []

    unmet = {"some_fact": 1.0}
    chosen = stack.update([proposal(9)], unmet, 9)
    assert chosen is not None and chosen.goal_type == goal_type
