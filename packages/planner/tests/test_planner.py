"""The planner derives strategies from skill contracts, not from hard-coded recipes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from person_planner import plan_for, relevant_skills, simulate, symbolic_state
from person_skills import Condition, skill_registry

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def state() -> dict[str, float]:
    observation = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    derived = symbolic_state(observation)
    derived.update({"reachable_stone": 4.0, "reachable_plant_food": 3.0, "reachable_coal": 2.0})
    return derived


def labels(plan) -> list[str]:
    return [step.label() for step in plan.steps]


GOALS = {
    "food": [Condition("food_level", ">=", 16)],
    "shelter": [Condition("shelter_complete", ">=", 1)],
    "tools": [Condition("tool_tier", ">=", 2)],
    "cooking": [Condition("cooked_food", ">=", 2)],
    "storage": [Condition("owned_storage_available", ">=", 1)],
    "reserves": [Condition("stored_surplus", ">=", 1)],
}


@pytest.mark.parametrize("name", sorted(GOALS))
def test_every_survival_goal_has_a_feasible_plan(state: dict[str, float], name: str) -> None:
    plans = plan_for(state, GOALS[name], limit=4)
    assert plans, f"no plan found for {name}"
    registry = skill_registry()
    for plan in plans:
        current = dict(state)
        for step in plan.steps:
            spec = registry.get(step.skill_id)
            assert spec.applicable(current), f"{step.skill_id} precondition failed in {name}"
            current = simulate(current, [step])
        assert all(condition.holds(current) for condition in GOALS[name])


def test_cooking_plan_derives_the_whole_dependency_chain(state: dict[str, float]) -> None:
    plans = plan_for(state, GOALS["cooking"], limit=3)
    assert plans
    skills = set(plans[0].skill_ids)
    # Nothing here is a hard-coded cooking recipe: each step is present because
    # some other step declared it as a precondition.
    assert "cook_food" in skills
    assert "craft_furnace" in skills
    assert "mine_stone" in skills
    assert "craft_basic_tools" in skills
    assert {"hunt_safe_passive_animals"} & skills


def test_alternative_strategies_are_offered_for_shelter(state: dict[str, float]) -> None:
    plans = plan_for(state, GOALS["shelter"], limit=4)
    assert len(plans) >= 2, "learning needs more than one way to reach a goal"
    first, second = plans[0], plans[1]
    assert first.skill_ids != second.skill_ids
    assert first.cost <= second.cost


def test_plans_are_minimal(state: dict[str, float]) -> None:
    registry = skill_registry()
    for goal in GOALS.values():
        for plan in plan_for(state, goal, limit=4):
            for index in range(len(plan.steps)):
                reduced = plan.steps[:index] + plan.steps[index + 1 :]
                current = dict(state)
                feasible = True
                for step in reduced:
                    spec = registry.get(step.skill_id)
                    if not spec.applicable(current):
                        feasible = False
                        break
                    current = simulate(current, [step])
                assert not (feasible and all(condition.holds(current) for condition in goal)), (
                    f"{[s.label() for s in plan.steps]} contains a step that does nothing"
                )


def test_planning_is_deterministic(state: dict[str, float]) -> None:
    for goal in GOALS.values():
        runs = [[labels(plan) for plan in plan_for(state, goal, limit=4)] for _ in range(3)]
        assert runs[0] == runs[1] == runs[2]


def test_an_already_satisfied_goal_needs_no_plan(state: dict[str, float]) -> None:
    plans = plan_for(state, [Condition("home_known", ">=", 1)], limit=3)
    assert plans and plans[0].steps == ()


def test_impossible_goals_produce_no_plan(state: dict[str, float]) -> None:
    barren = dict(state)
    for fact in (
        "reachable_wood",
        "reachable_stone",
        "reachable_coal",
        "reachable_plant_food",
        "reachable_animal",
        "wood",
        "building_materials",
    ):
        barren[fact] = 0.0
    assert plan_for(barren, GOALS["shelter"], limit=3) == []


def test_relevance_closure_keeps_unrelated_skills_out(state: dict[str, float]) -> None:
    registry = skill_registry()
    specs = [registry.get(skill_id) for skill_id in registry.ids]
    relevant = {spec.id for spec in relevant_skills(GOALS["cooking"], specs)}
    assert "cook_food" in relevant
    assert "loot_permitted_container" not in relevant
    assert "dig_in" not in relevant


def test_emergency_reflexes_are_not_planned(state: dict[str, float]) -> None:
    for goal in GOALS.values():
        for plan in plan_for(state, goal, limit=4):
            assert "flee" not in plan.skill_ids
            assert "dig_in" not in plan.skill_ids
            assert "wait_safely" not in plan.skill_ids
