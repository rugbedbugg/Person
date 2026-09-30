"""The static class validators, checked on the known worlds before any new one.

Every development and old held-out world of classes A to C must pass its
class, and each targeted mutation must fail it. The validators only read the
observation a world gives before the first decision; nothing here runs Person.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
WORLDS = REPOSITORY / "fixtures/worlds/benchmarks"
PLANS = REPOSITORY / "experiments/benchmarks"
CLASSES = {"a-wide-margin": "A", "b-near-tie": "B", "c-exploration": "C"}

spec = importlib.util.spec_from_file_location(
    "validate_class", REPOSITORY / "scripts/benchmarks/validate_class.py"
)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def observe(world: dict[str, Any] | Path, tmp_path: Path) -> dict[str, Any]:
    if isinstance(world, dict):
        path = tmp_path / "world.json"
        path.write_text(json.dumps(world), encoding="utf-8")
    else:
        path = world
    out = subprocess.run(
        ["node", "scripts/benchmarks/initial-observation.ts", str(path)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def world(split: str, name: str) -> dict[str, Any]:
    return json.loads((WORLDS / split / f"{name}.json").read_text(encoding="utf-8"))


def learning(split: str, name: str) -> str:
    plan = json.loads((PLANS / split / f"{name}.json").read_text(encoding="utf-8"))
    return str(plan["learningMode"])


@pytest.mark.parametrize("split", ["development", "heldout"])
@pytest.mark.parametrize("name", sorted(CLASSES))
def test_every_known_world_is_an_instance_of_its_class(
    split: str, name: str, tmp_path: Path
) -> None:
    file = WORLDS / split / f"{name}.json"
    before = hashlib.sha256(file.read_bytes()).hexdigest()
    record = validator.validate(CLASSES[name], observe(file, tmp_path), learning(split, name))
    assert record["result"] == "PASS", record
    assert hashlib.sha256(file.read_bytes()).hexdigest() == before, "the world was changed"


def failing(cls: str, observation: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    record = validator.validate(cls, observation, mode)
    assert record["result"] == "FAIL", record
    return record


def test_a_fails_when_affect_could_reorder_its_top_two_goals(tmp_path: Path) -> None:
    # Hungry at night: the food goal and the shelter goal come within reach.
    mutated = world("development", "a-wide-margin")
    mutated["timeOfDay"] = 13000
    mutated["vitals"]["food"] = 2
    record = failing("A", observe(mutated, tmp_path))
    assert record["margin"] <= record["swing"]


def test_b_fails_when_tool_readiness_removes_the_tools_goal(tmp_path: Path) -> None:
    mutated = world("heldout", "b-near-tie")
    mutated["inventory"] = [{"name": "stone_pickaxe", "count": 1}, {"name": "oak_log", "count": 40}]
    assert "tools goal" in failing("B", observe(mutated, tmp_path))["why"]


def test_b_fails_when_storage_is_not_the_projects_next_milestone(tmp_path: Path) -> None:
    observation = observe(world("development", "b-near-tie"), tmp_path)
    observation["home"]["ownedStorage"] = [{"storageId": "storage_a", "contents": []}]
    failing("B", observation)


def test_b_fails_when_a_hostile_keeps_person_from_calm(tmp_path: Path) -> None:
    # A hostile in view: Person is not calm, so the home project is never
    # adopted in the witness, and the near tie cannot arise.
    mutated = world("development", "b-near-tie")
    mutated["entities"] = [{"name": "zombie", "position": {"x": 0, "y": 64, "z": -5}}]
    assert "not adopted" in failing("B", observe(mutated, tmp_path))["why"]


def test_b_fails_when_a_third_goal_dominates_the_tie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Under the witness's calm, daytime conditions no provider goal outranks
    # the pair, so the rule is exercised with one injected goal above both.
    observation = observe(world("development", "b-near-tie"), tmp_path)
    propose = validator.SurvivalGoalProvider.propose

    def with_a_rival(self: Any, *args: Any, **kwargs: Any) -> list[Any]:
        goals = propose(self, *args, **kwargs)
        rival = next(goal for goal in goals if goal.goal_type == "ESTABLISH_TOOLS")
        return [
            *goals,
            replace(rival, goal_id="goal_rival", goal_type="RIVAL", priority=400.0),
        ]

    monkeypatch.setattr(validator.SurvivalGoalProvider, "propose", with_a_rival)
    assert "dominated" in failing("B", observation)["why"]


def test_b_fails_outside_its_separation_band(tmp_path: Path) -> None:
    observation = observe(world("development", "b-near-tie"), tmp_path)
    # Development B sits exactly on the band's lower edge (300 against 290).
    assert validator.validate("B", deepcopy(observation))["separation"] == 10.0
    validator.SEPARATION = (11.0, 20.0)
    try:
        assert "outside" in failing("B", observation)["why"]
    finally:
        validator.SEPARATION = (10.0, 20.0)


def test_c_fails_with_a_single_kind_of_food(tmp_path: Path) -> None:
    mutated = world("development", "c-exploration")
    mutated["entities"] = []
    assert "opportunity" in failing("C", observe(mutated, tmp_path), "supervised")["why"]


def test_c_fails_when_food_is_not_the_top_goal(tmp_path: Path) -> None:
    mutated = world("development", "c-exploration")
    mutated["vitals"]["food"] = 20
    assert "top" in failing("C", observe(mutated, tmp_path), "supervised")["why"]


def test_c_fails_without_the_supervised_learner(tmp_path: Path) -> None:
    observation = observe(world("development", "c-exploration"), tmp_path)
    assert "supervised" in failing("C", observation, "off")["why"]


@pytest.mark.parametrize(
    ("cls", "name"),
    [("A", "a2-wide-margin"), ("B", "b2-near-tie"), ("C", "c2-exploration")],
)
def test_the_frozen_v2_worlds_are_instances_of_their_classes(
    cls: str, name: str, tmp_path: Path
) -> None:
    # Static, like the check that admitted them; never a run.
    plan = json.loads(
        (REPOSITORY / f"experiments/r2/heldout/{name}.json").read_text(encoding="utf-8")
    )
    observation = observe(WORLDS / "heldout-v2" / f"{name}.json", tmp_path)
    record = validator.validate(cls, observation, plan["learningMode"])
    assert record["result"] == "PASS", record
    recorded = json.loads(
        (REPOSITORY / f"experiments/benchmarks/heldout-v2/validation/{cls}2.json").read_text(
            encoding="utf-8"
        )
    )
    assert recorded["result"] == "PASS"
