"""Projects: commitments Person takes up, sets aside for urgent needs, and resumes.

The flagship case, end to end through the real cognition loop: Person has a
home, is calm, and takes up improving it. Hunger becomes more urgent; the
project is interrupted, not erased; Person eats; the hunger passes; the
project resumes. After a restart the project is still there and is checked
before it is pursued. A project whose milestone keeps being blocked is
abandoned, and one the world has already satisfied is closed rather than
resumed blindly.

Cognition-level evidence with hand-built messages.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.affect import BIAS_LIMIT
from person_cognition.projects import (
    BLOCKS_TO_ABANDON,
    PROJECT_PRIORITY,
    ProjectBook,
    ProjectManager,
)
from person_persistence import EvidenceJournal
from test_cognitive_home import outcome
from test_loop import Harness, envelope
from test_spatial import STILL, at

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def view() -> dict[str, Any]:
    """Healthy, fed, equipped, daytime, a complete shelter, no storage yet."""
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    document["home"]["shelterState"] = "complete"
    # Equipped too: without a stone pickaxe, tools are a more urgent need.
    document["inventory"]["items"].append({"name": "stone_pickaxe", "count": 1})
    document["selfMotion"] = dict(STILL)
    return document


def records(evidence: Path, kind: str) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(evidence / "journal").read()
        if event.type == kind
    ]


def changes(evidence: Path, project_id: str | None = None) -> list[str]:
    return [record["change"] for record in history(evidence, project_id)]


def history(evidence: Path, project_id: str | None = None) -> list[dict[str, Any]]:
    """What happened to one project, or to all of them."""
    return [
        record
        for record in records(evidence, "project_changed")
        if project_id is None or record["project"]["project_id"] == project_id
    ]


def first_project(evidence: Path) -> str:
    return str(records(evidence, "project_started")[0]["project"]["project_id"])


def with_home(tmp_path: Path, view: dict[str, Any]) -> Harness:
    """A Person that built its shelter here, so it has a home place."""
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, invocation = harness.observe(at(view, 100))
    harness.loop.handle(outcome(invocation, policy, "build_basic_shelter"))
    return harness


def step(harness: Harness, observation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    goal, policy, invocation = harness.observe(observation)
    harness.complete(invocation, policy)
    return goal, invocation


def hungry(view: dict[str, Any], tick: int) -> dict[str, Any]:
    changed = at(view, tick)
    changed["vitals"]["food"] = 6.0
    return changed


def finish(harness: Harness, tick: int) -> None:
    harness.loop.handle(
        {
            **envelope("EpisodeEvent", tick),
            "episodeId": "ep_1",
            "phase": "ended",
            "reasonCodes": ["test"],
            "rngSeed": 7,
            "trainingContext": "fixture",
        }
    )


# ----------------------------------------------------------------- choosing


def test_a_calm_person_with_a_home_takes_up_improving_it(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, view)
    goal, _ = step(harness, at(view, 120))

    started = records(tmp_path, "project_started")
    assert len(started) == 1
    project = started[0]["project"]
    assert project["kind"] == "improve_home"
    assert project["anchor"] == harness.loop.spatial.home_place()
    assert "home_attachment" in project["reasons"]

    active = goal["goal"]
    assert active["goalId"] == f"goal_{project['project_id']}"
    assert active["goalType"] == "ESTABLISH_STORAGE", "the shelter milestone is already met"
    assert active["source"] == "self_generated"
    # The project's own priority, plus at most the bounded affect term, with
    # both parts journalled separately (ADR 0010).
    assert abs(active["priority"] - PROJECT_PRIORITY) <= BIAS_LIMIT
    selected = [
        record
        for record in records(tmp_path, "goal_selected")
        if record["goal_id"] == active["goalId"]
    ][-1]
    assert selected["base_priority"] == PROJECT_PRIORITY
    assert selected["priority"] == round(PROJECT_PRIORITY + selected["affect_bias"], 3)


@pytest.mark.parametrize("pressure", ["hungry", "threatened", "night", "homeless"])
def test_no_project_is_taken_up_under_pressure_or_without_a_home(
    tmp_path: Path, view: dict[str, Any], pressure: str
) -> None:
    harness = Harness(tmp_path) if pressure == "homeless" else with_home(tmp_path, view)
    if pressure == "homeless":
        harness.hello()
    observation = at(view, 120)
    if pressure == "hungry":
        observation["vitals"]["food"] = 6.0
    elif pressure == "threatened":
        observation["nearby"]["hostiles"] = [
            {
                "name": "zombie",
                "distance": 6.0,
                "bearing": "ahead",
                "elevation": "level",
                "rangeBand": "near",
                "detail": "central",
                "named": False,
                "tamed": False,
                "protectedTarget": True,
            }
        ]
    elif pressure == "night":
        observation["environment"]["dayPhase"] = "night"
    harness.observe(observation)
    assert records(tmp_path, "project_started") == []


# ---------------------------------------------------- interrupt and resume


def test_hunger_interrupts_a_project_which_resumes_when_the_hunger_passes(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, view)
    goal, _ = step(harness, at(view, 120))
    project_goal = goal["goal"]["goalId"]
    assert project_goal.startswith("goal_project_")

    goal, _ = step(harness, hungry(view, 140))
    assert goal["goal"]["goalType"] == "SECURE_FOOD", "the urgent need wins"
    stack = {entry["goalId"]: entry for entry in goal["stack"]}
    assert stack[project_goal]["status"] == "SUSPENDED", "interrupted, not erased"

    goal, _ = step(harness, at(view, 160))
    assert goal["goal"]["goalId"] == project_goal, "back to the project"

    assert changes(tmp_path)[-2:] == ["interrupted", "resumed"]
    project = records(tmp_path, "project_changed")[-1]["project"]
    assert project["status"] == "ACTIVE"
    assert [item["by"] for item in project["interruptions"]] == ["secure_food"]


# ---------------------------------------------------------------- restart


def test_an_unfinished_project_survives_restart_and_is_checked_first(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = with_home(tmp_path, view)
    step(first, at(view, 120))
    finish(first, 200)
    project_id = records(tmp_path, "project_started")[0]["project"]["project_id"]
    recalls_before = len(records(tmp_path, "memory_recalled"))

    second = Harness(tmp_path)
    second.hello()
    assert [project.project_id for project in second.loop.project_book.projects()] == [project_id]
    goal, _ = step(second, at(view, 5, {**STILL, "continuity": "start"}))

    assert "resumed" in changes(tmp_path)
    assert records(tmp_path, "project_changed")[-1]["project"]["note"] in {
        "resumed_after_restart",
        None,
    }
    assert goal["goal"]["goalId"] == f"goal_{project_id}"
    recalls = records(tmp_path, "memory_recalled")[recalls_before:]
    assert recalls and recalls[0]["cue"]["purpose"] == "goal"
    assert all(len(recall["recalled"]) <= 3 for recall in recalls), "bounded recall only"


def test_a_project_the_world_already_satisfied_is_closed_not_resumed(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = with_home(tmp_path, view)
    step(first, at(view, 120))
    finish(first, 200)

    second = Harness(tmp_path)
    second.hello()
    done = at(view, 5, {**STILL, "continuity": "start"})
    done["home"]["ownedStorage"] = [{"storageId": "storage_a", "contents": []}]
    goal, _ = step(second, done)

    project_id = first_project(tmp_path)
    last = history(tmp_path, project_id)[-1]["project"]
    assert last["status"] == "COMPLETE"
    assert last["note"] == "already_done"
    assert goal["goal"]["goalId"] != f"goal_{project_id}"


def test_a_project_blocked_again_and_again_is_abandoned(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, view)
    _, invocation = step(harness, at(view, 120))
    project_goal = invocation["goalId"]
    tick = 140
    for _ in range(BLOCKS_TO_ABANDON + 1):
        harness.loop.goals.block(project_goal, "no_feasible_plan", tick)
        step(harness, at(view, tick))
        tick += 20

    project_id = first_project(tmp_path)
    assert "abandoned" in changes(tmp_path, project_id)
    abandoned = history(tmp_path, project_id)[-1]["project"]
    assert abandoned["status"] == "ABANDONED"
    assert abandoned["note"] == "blocked_storage"
    # And the same kind is not taken up again at once; another may be.
    step(harness, at(view, tick))
    kinds = [record["project"]["kind"] for record in records(tmp_path, "project_started")]
    assert kinds.count("improve_home") == 1


# ------------------------------------------------------------ boundaries


def test_project_state_holds_no_coordinate_heading_or_runtime_target(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, view)
    step(harness, at(view, 120))
    step(harness, hungry(view, 140))
    body = json.dumps(harness.loop.project_book.to_json())
    for forbidden in ('"x"', '"y"', '"z"', "yaw", "pitch", "position", "homeDistance"):
        assert forbidden not in body


def test_the_same_evidence_gives_the_same_project_decisions(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    def life(directory: Path) -> list[str]:
        harness = with_home(directory, view)
        for observation in (at(view, 120), hungry(view, 140)):
            step(harness, deepcopy(observation))
        step(harness, at(view, 160))
        return [
            json.dumps({key: value for key, value in record.items()}, sort_keys=True)
            for record in records(directory, "project_changed")
        ]

    assert life(tmp_path / "a") == life(tmp_path / "b")


def test_the_manager_has_no_way_to_read_the_journal() -> None:
    source = (REPOSITORY / "apps/cognition/python/person_cognition/projects.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("EvidenceJournal", "EvidenceStore", "read_text", "memory_store"):
        assert forbidden not in source
    assert re.search(r"(?<![\w.])open\(", source) is None, "no file access"
    assert ProjectManager(ProjectBook()).current() is None
