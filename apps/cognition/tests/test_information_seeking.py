"""Information seeking: "I do not see it" is not "it is not there".

When a goal cannot be planned only because what it needs is out of view, the
planner spends a bounded amount of effort looking for it, one deliberate glance
at a time, through the ordinary skill path. Each glance produces an ordinary
observation, and the planner decides again from that. A search that runs out
concludes that nothing was found in that search, and nothing stronger.

Everything here drives the real cognition loop in process with hand-built
observations. It is cognition-level evidence only: it says nothing about what a
Minecraft body would have shown Person.
"""

from __future__ import annotations

import dataclasses
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.search import LOOK_BUDGET, SEARCH_ROUTINE_ID, InformationSearch
from person_persistence import EvidenceJournal
from test_loop import Harness

REPOSITORY = Path(__file__).resolve().parents[3]
GAZE_WORDS = {"forward", "left", "right", "up", "down"}


@pytest.fixture
def empty_view() -> dict[str, Any]:
    """Well fed, healthy, no shelter, and nothing useful in sight."""
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    document["nearby"]["resources"] = []
    document["nearby"]["passiveAnimals"] = []
    return document


def tree(detail: str, bearing: str = "ahead") -> dict[str, Any]:
    return {
        "kind": "wood",
        **({"name": "oak_log"} if detail == "central" else {}),
        "distance": 7.0,
        "bearing": bearing,
        "elevation": "level",
        "rangeBand": "near",
        "detail": detail,
        "harvestPermitted": True,
    }


def with_tree(observation: dict[str, Any], detail: str, bearing: str = "ahead") -> dict[str, Any]:
    changed = deepcopy(observation)
    changed["nearby"]["resources"] = [tree(detail, bearing)]
    return changed


def searches(evidence: Path) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(evidence / "journal").read()
        if event.type == "information_search"
    ]


def shelter(goal: dict[str, Any]) -> dict[str, Any]:
    return next(entry for entry in goal["stack"] if entry["goalType"] == "SECURE_SHELTER")


def exhaust(harness: Harness, view: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Keeps showing Person the same empty view until it stops looking.

    Every invocation gets its outcome, as the runtime always sends one.
    """
    looks: list[str] = []
    for _ in range(LOOK_BUDGET + 4):
        goal, policy, invocation = harness.observe(view)
        harness.complete(invocation, policy)
        if invocation["skillId"] != "look":
            return looks, goal
        looks.append(invocation["parameters"]["direction"])
    raise AssertionError(f"the search never ended: {looks}")


def test_something_out_of_view_is_looked_for_rather_than_given_up_on(
    tmp_path: Path, empty_view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()

    goal, policy, invocation = harness.observe(empty_view)

    assert goal["goal"]["goalType"] == "SECURE_SHELTER"
    assert goal["goal"]["status"] == "ACTIVE", "the goal is still wanted, not blocked"
    assert invocation["skillId"] == "look"
    assert list(invocation["parameters"]) == ["direction"]
    assert invocation["parameters"]["direction"] in GAZE_WORDS
    assert "seeking_evidence" in policy["reasonCodes"]
    assert policy["routineId"] == SEARCH_ROUTINE_ID

    [started] = searches(tmp_path)
    assert started["phase"] == "started"
    assert started["goal_id"] == "goal_secure_shelter"
    assert started["purpose"] == ["reachable_stone", "reachable_wood"]


def test_a_glimpse_in_the_periphery_is_turned_towards(
    tmp_path: Path, empty_view: dict[str, Any]
) -> None:
    for bearing, expected in (("left", "left"), ("behind_right", "right")):
        harness = Harness(tmp_path / bearing)
        harness.hello()
        _, _, invocation = harness.observe(with_tree(empty_view, "peripheral", bearing))
        # Something wood-like at the edge of vision is a reason to look, and
        # not a reason to start chopping.
        assert invocation["skillId"] == "look"
        assert invocation["parameters"]["direction"] == expected


def test_the_search_stops_as_soon_as_the_evidence_is_there(
    tmp_path: Path, empty_view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, look = harness.observe(empty_view)
    harness.complete(look, policy)

    # The glance was an ordinary skill; what it revealed arrives as an ordinary
    # observation, and the planner simply plans again.
    _, policy, act = harness.observe(with_tree(empty_view, "central"))

    assert act["skillId"] == "gather_wood"
    assert policy["routineId"] != SEARCH_ROUTINE_ID
    phases = [record["phase"] for record in searches(tmp_path)]
    assert phases == ["started", "satisfied"]
    assert searches(tmp_path)[-1]["looks"] == [look["parameters"]["direction"]]


def test_a_search_for_something_never_seen_is_finite(
    tmp_path: Path, empty_view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()

    looks, goal = exhaust(harness, empty_view)

    assert 1 <= len(looks) <= LOOK_BUDGET
    assert set(looks) <= GAZE_WORDS
    blocked = shelter(goal)
    assert blocked["status"] == "BLOCKED"
    assert blocked["suspensionReason"] == "not_found_in_bounded_search"
    concluded = searches(tmp_path)[-1]
    assert concluded["phase"] == "exhausted"
    assert concluded["conclusion"] == "not_found_in_bounded_search"
    assert concluded["looks"] == looks


def test_running_out_of_looks_is_not_knowing_it_is_absent(
    tmp_path: Path, empty_view: dict[str, Any]
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    exhaust(harness, empty_view)

    # Nothing Person said, and nothing it recorded, claims absence.
    said = json.dumps(harness.sent) + json.dumps(searches(tmp_path))
    for claim in ("absent", "none_exist", "no_wood", "not_exist", "nonexist"):
        assert claim not in said.lower(), claim

    # And it did not act as though it knew: the moment a tree is actually
    # seen, the goal is live again.
    goal, _, invocation = harness.observe(with_tree(empty_view, "central"))
    assert shelter(goal)["status"] == "ACTIVE"
    assert invocation["skillId"] == "gather_wood"


def test_a_more_urgent_goal_abandons_the_search(tmp_path: Path, empty_view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, look = harness.observe(empty_view)
    harness.complete(look, policy)

    hungry = deepcopy(empty_view)
    hungry["vitals"]["food"] = 4.0
    hungry["inventory"]["items"].append({"name": "sweet_berries", "count": 6})
    hungry["inventory"]["categories"]["food"] = 6
    goal, _, _ = harness.observe(hungry)

    assert goal["goal"]["goalType"] == "SECURE_FOOD"
    abandoned = [record for record in searches(tmp_path) if record["phase"] == "abandoned"]
    assert [record["goal_id"] for record in abandoned] == ["goal_secure_shelter"]


def test_the_search_state_has_no_room_for_geometry() -> None:
    # The only state that coordinates several glances is what Person decided
    # and why. There is no field in which an angle, a position or a body
    # handle could be kept, so none can leak into a later decision.
    fields = {field.name for field in dataclasses.fields(InformationSearch)}
    # `recalled` holds memory identifiers and `recalls_unfound` a flag: what
    # Person remembered, never where anything is.
    assert fields == {
        "goal_id",
        "purpose",
        "budget",
        "looks",
        "pitch_steps",
        "recalled",
        "recalls_unfound",
    }
    for forbidden in ("yaw", "pitch_deg", "position", "coord", "heading", "entity", "x", "z"):
        assert forbidden not in fields


def test_same_evidence_same_search(tmp_path: Path, empty_view: dict[str, Any]) -> None:
    # Cognition's choices are a function of what it perceived. Two runs shown
    # the same observations look in the same directions.
    runs: list[list[str]] = []
    for name in ("first", "second"):
        harness = Harness(tmp_path / name)
        harness.hello()
        looks, _ = exhaust(harness, empty_view)
        runs.append(looks)
    assert runs[0] == runs[1]
