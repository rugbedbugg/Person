"""Static class validity for benchmark worlds: construction checks, not measurements.

    uv run python scripts/benchmarks/validate_class.py <A|B|C> <observation.json> [--learning MODE]

Takes the observation a world gives Person before its first decision
(`initial-observation.ts`) and asks the frozen goal and project providers what
is legitimate there. It never runs the decision loop, never acts, never learns
and never looks at a trajectory, so it can check a held-out world without
consuming it. It prints a JSON record ending in PASS or FAIL, and exits 1 on
FAIL.

- A, wide margin: at the initial observation, the top legitimate goal leads the
  second by more than affect could ever lift the second over it.
- B, near tie: in one declared post-adoption witness state (the shelter
  complete, home known, daytime, calm; nothing else changed) the home
  project's storage milestone and the tools goal are both legitimate, 10 to 20
  apart, within affect's swing, and no third goal dominates both beyond it.
  It asserts the world contains that latent geometry, not that Person will
  reach it.
- C, exploration opportunity: at the initial observation, securing food is the
  top legitimate goal, at least two perceived food-acquisition opportunities
  of different kinds are present, and the learner is supervised.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from person_cognition.affect import Affect, bias_swings
from person_cognition.goals import Goal, SurvivalGoalProvider, homeostasis
from person_cognition.memory import encoding as remembering
from person_cognition.projects import PROJECT_PRIORITY, ProjectBook, ProjectManager
from person_cognition.spatial import Spatial, SpatialMap
from person_planner import symbolic_state

SEPARATION = (10.0, 20.0)
#: What the witness says about home. `home_place` is the loop's own label.
WITNESS_HOME, WITNESS_PLACE = "at_home", "home"
#: The perceived opportunity kinds, and how each one gets food.
OPPORTUNITIES = {
    "forage": "harvest plants: no combat, no stored stock",
    "hunt": "kill an animal: combat, then cooking",
    "stored": "take from storage: no acquisition risk, finite",
}


def character(goal: Goal) -> str:
    if goal.source == "emergency":
        return "fixed"
    return Affect.character(frozenset(condition.fact for condition in goal.completion_condition))


def describe(goal: Goal) -> dict[str, Any]:
    return {
        "goal_id": goal.goal_id,
        "goal_type": goal.goal_type,
        "character": character(goal),
        "base_priority": goal.priority,
    }


def initial(observation: dict[str, Any]) -> tuple[list[Goal], dict[str, float]]:
    """The candidates Person's first decision is made from, before any bias."""
    spatial = Spatial(SpatialMap())
    spatial.feel(observation["selfMotion"], frozenset(remembering.noticed(observation)))
    home, _ = spatial.home_relation()
    state = symbolic_state(observation, home=home)
    proposals = SurvivalGoalProvider().propose(observation, state, observation["tick"], home=home)
    return [goal for goal in proposals if not goal.satisfied_by(state)], state


def ranked(goals: list[Goal]) -> list[Goal]:
    return sorted(goals, key=lambda goal: (-goal.priority, goal.goal_type))


def check_a(observation: dict[str, Any]) -> dict[str, Any]:
    legitimate, _ = initial(observation)
    order = ranked(legitimate)
    swings = bias_swings()
    record: dict[str, Any] = {"candidates": [describe(goal) for goal in order]}
    if len(order) < 2:
        return {**record, "result": "FAIL", "why": "fewer than two legitimate goals"}
    top, second = order[0], order[1]
    margin = top.priority - second.priority
    swing = swings[character(second)][character(top)]
    passed = margin > swing
    return {
        **record,
        "margin": margin,
        "swing": swing,
        "result": "PASS" if passed else "FAIL",
        "why": None if passed else "affect could lift the second goal over the first",
    }


def witness(observation: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The declared post-adoption state: only adoption's preconditions set."""
    changed = deepcopy(observation)
    set_: list[str] = []
    if changed["home"]["shelterState"] != "complete":
        changed["home"]["shelterState"] = "complete"
        set_.append("home.shelterState = complete")
    if changed["environment"]["dayPhase"] in {"dusk", "night"}:
        changed["environment"]["dayPhase"] = "day"
        set_.append("environment.dayPhase = day")
    state = symbolic_state(changed, home=WITNESS_HOME)
    calm = {drive.name: drive.urgency for drive in homeostasis(changed, state)}
    if any(calm.get(name, 0.0) > 0.3 for name in ("health", "food", "safety")):
        changed["vitals"]["health"] = 20
        changed["vitals"]["food"] = 20
        set_.append("vitals.health = 20, vitals.food = 20 (calm)")
    set_.append(f"home relation = {WITNESS_HOME}, home place known")
    return changed, set_


def check_b(observation: dict[str, Any]) -> dict[str, Any]:
    original = json.dumps(observation, sort_keys=True)
    changed, set_ = witness(observation)
    state = symbolic_state(changed, home=WITNESS_HOME)
    tick = changed["tick"]
    manager = ProjectManager(ProjectBook())
    adopted = manager.consider(
        state=state,
        drives=homeostasis(changed, state),
        home_place=WITNESS_PLACE,
        night=False,
        now=0,
    )
    record: dict[str, Any] = {"witness_sets": set_}
    if not adopted or adopted[0][1]["project"]["kind"] != "improve_home":
        return {**record, "result": "FAIL", "why": "the home project is not adopted"}
    manager.book.load_json({"projects": [adopted[0][1]["project"]]})
    project_goal = manager.goal(state, tick)
    proposals = SurvivalGoalProvider().propose(changed, state, tick, home=WITNESS_HOME)
    goals = [goal for goal in [*proposals, project_goal] if goal and not goal.satisfied_by(state)]
    record["candidates"] = [describe(goal) for goal in ranked(goals)]
    tools = next((goal for goal in goals if goal.goal_type == "ESTABLISH_TOOLS"), None)
    failures: list[str] = []
    if project_goal is None or "milestone_storage" not in project_goal.reason_codes:
        failures.append("the project's next milestone is not storage")
    if tools is None:
        failures.append("the tools goal is not legitimate")
    if failures:
        return {**record, "result": "FAIL", "why": "; ".join(failures)}
    assert project_goal is not None and tools is not None
    swings = bias_swings()
    pair = (character(project_goal), character(tools))
    separation = abs(project_goal.priority - tools.priority)
    swing = max(swings[pair[0]][pair[1]], swings[pair[1]][pair[0]])
    thirds = [goal for goal in goals if goal not in (project_goal, tools)]
    dominating = [
        goal.goal_id
        for goal in thirds
        if goal.priority - max(project_goal.priority, tools.priority)
        > max(swings[member][character(goal)] for member in pair)
    ]
    urgency = {drive.name: drive.urgency for drive in homeostasis(changed, state)}
    expected_tools = round(260 + 60 * urgency["tool_readiness"], 3)
    if not SEPARATION[0] <= separation <= SEPARATION[1]:
        failures.append(f"separation {separation} outside {list(SEPARATION)}")
    if separation > swing:
        failures.append(f"separation {separation} beyond affect's swing {swing}")
    if dominating:
        failures.append(f"dominated by {dominating}")
    if project_goal.priority != PROJECT_PRIORITY or tools.priority != expected_tools:
        failures.append("providers disagree with the frozen priority formulas")
    if json.dumps(observation, sort_keys=True) != original:
        failures.append("the witness changed its input")
    return {
        **record,
        "project_goal": describe(project_goal),
        "tools_goal": describe(tools),
        "separation": separation,
        "swing": swing,
        "third_goals": [describe(goal) for goal in thirds],
        "formula": {"project": PROJECT_PRIORITY, "tools": expected_tools},
        "result": "FAIL" if failures else "PASS",
        "why": "; ".join(failures) or None,
    }


def opportunities(observation: dict[str, Any]) -> list[str]:
    nearby, home = observation["nearby"], observation["home"]
    found = []
    if any(item.get("kind") == "plant_food" for item in nearby["resources"]):
        found.append("forage")
    if nearby["passiveAnimals"] and observation["permissions"].get("huntPassive"):
        found.append("hunt")
    if home.get("foodReserve", 0) > 0:
        found.append("stored")
    return found


def check_c(observation: dict[str, Any], learning: str | None) -> dict[str, Any]:
    legitimate, _ = initial(observation)
    order = ranked(legitimate)
    kinds = opportunities(observation)
    failures = []
    if not order or order[0].goal_type != "SECURE_FOOD":
        failures.append("securing food is not the top legitimate goal")
    if len(kinds) < 2:
        failures.append(f"only {kinds} food opportunity kinds perceived")
    if learning != "supervised":
        failures.append(f"learner is {learning}, not supervised")
    return {
        "candidates": [describe(goal) for goal in order],
        "opportunities": {kind: OPPORTUNITIES[kind] for kind in kinds},
        "learning": learning,
        "result": "FAIL" if failures else "PASS",
        "why": "; ".join(failures) or None,
    }


def validate(cls: str, observation: dict[str, Any], learning: str | None = None) -> dict[str, Any]:
    checks = {
        "A": lambda: check_a(observation),
        "B": lambda: check_b(observation),
        "C": lambda: check_c(observation, learning),
    }
    return {"class": cls, **checks[cls]()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cls", choices=["A", "B", "C"])
    parser.add_argument("observation", type=Path)
    parser.add_argument("--learning", default=None)
    arguments = parser.parse_args()
    observation = json.loads(arguments.observation.read_text(encoding="utf-8"))
    record = validate(arguments.cls, observation, arguments.learning)
    print(json.dumps(record, indent=2, sort_keys=True))
    sys.exit(0 if record["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
