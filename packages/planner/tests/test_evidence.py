"""Evidence: what the planner may treat as seen, and what it still needs to see.

Two distinctions are defended here. A percept in the corner of the eye is a
lead, not an identification, so it cannot license acting on the thing. And a
plan that fails because something is not in view has failed for want of
evidence, which is a different fact from the thing not existing.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_planner import EVIDENCE_FACTS, evidence_needed, evidence_percepts, symbolic_state
from person_skills import Condition, skill_registry

REPOSITORY = Path(__file__).resolve().parents[3]

SHELTER = (Condition("shelter_complete", ">=", 1),)


@pytest.fixture
def observation() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    document["nearby"]["resources"] = []
    document["nearby"]["passiveAnimals"] = []
    return document


def percept(detail: str, bearing: str = "ahead", **fields: Any) -> dict[str, Any]:
    return {
        "distance": 6.0,
        "bearing": bearing,
        "elevation": "level",
        "rangeBand": "near",
        "detail": detail,
        **fields,
    }


def wood(detail: str, bearing: str = "ahead") -> dict[str, Any]:
    named = {"name": "oak_log"} if detail == "central" else {}
    return percept(detail, bearing, kind="wood", harvestPermitted=True, **named)


def animal(detail: str, bearing: str = "ahead") -> dict[str, Any]:
    named = {"name": "cow"} if detail == "central" else {}
    return percept(detail, bearing, named=False, tamed=False, protectedTarget=False, **named)


def test_a_recognised_tree_is_evidence_of_wood(observation: dict[str, Any]) -> None:
    observation["nearby"]["resources"] = [wood("central")]
    assert symbolic_state(observation)["reachable_wood"] == 1


def test_something_wood_coloured_in_the_periphery_is_not(observation: dict[str, Any]) -> None:
    observation["nearby"]["resources"] = [wood("peripheral", "left")]
    assert symbolic_state(observation)["reachable_wood"] == 0


def test_an_animal_shape_in_the_periphery_is_not_a_cow(observation: dict[str, Any]) -> None:
    observation["nearby"]["passiveAnimals"] = [animal("peripheral", "right")]
    assert symbolic_state(observation)["reachable_animal"] == 0

    observation["nearby"]["passiveAnimals"] = [animal("central")]
    assert symbolic_state(observation)["reachable_animal"] == 1


def test_movement_in_the_periphery_is_still_enough_to_be_wary(
    observation: dict[str, Any],
) -> None:
    # Recognition gates acting on a thing, not noticing a threat. Something
    # hostile at the edge of vision still makes Person unsafe.
    observation["nearby"]["hostiles"] = [
        percept("peripheral", "behind_left", named=False, tamed=False, protectedTarget=True)
        | {"distance": 5.0}
    ]
    assert symbolic_state(observation)["safe"] == 0


def test_peripheral_percepts_remain_available_as_leads(observation: dict[str, Any]) -> None:
    observation["nearby"]["resources"] = [wood("peripheral", "left")]
    observation["nearby"]["passiveAnimals"] = [animal("peripheral", "right")]

    leads = evidence_percepts(observation)
    assert [item["bearing"] for item in leads["reachable_wood"]] == ["left"]
    assert [item["bearing"] for item in leads["reachable_animal"]] == ["right"]


def test_a_plan_blocked_only_by_what_is_out_of_view_names_the_missing_evidence(
    observation: dict[str, Any],
) -> None:
    # Person holds three logs, so a visible tree would do, and so would
    # visible stone once those logs become a pickaxe. Either is worth seeing.
    state = symbolic_state(observation)
    assert evidence_needed(state, SHELTER) == ("reachable_stone", "reachable_wood")


def test_no_evidence_is_needed_when_a_plan_already_exists(observation: dict[str, Any]) -> None:
    observation["nearby"]["resources"] = [wood("central")]
    assert evidence_needed(symbolic_state(observation), SHELTER) == ()


def test_evidence_that_could_not_help_is_not_sought(observation: dict[str, Any]) -> None:
    # Seeing a tree Person may not cut would not make a shelter possible, so
    # it is not worth looking for.
    observation["permissions"]["harvest"] = False
    assert evidence_needed(symbolic_state(observation), SHELTER) == ()


def test_the_counterfactual_does_not_touch_the_real_state(observation: dict[str, Any]) -> None:
    state = symbolic_state(observation)
    before = deepcopy(state)
    evidence_needed(state, SHELTER)
    assert state == before
    assert state["reachable_wood"] == 0, "imagining a tree must not put one in the world"


def test_evidence_facts_are_established_only_by_perception() -> None:
    # If a skill claimed to produce one of these, the planner could plan its
    # way to seeing something, which is exactly the hallucination this
    # distinction exists to prevent.
    for spec in skill_registry():
        produced = {effect.fact for effect in spec.expected_effects}
        assert produced.isdisjoint(EVIDENCE_FACTS), f"{spec.id} claims to produce evidence"
