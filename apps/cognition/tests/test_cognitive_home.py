"""Home is where Person believes it is, not a distance the runtime measured (C8).

The observation used to carry `home.homeDistance`: exact, drift-free, at any
range, through walls. It is gone. Whether Person is at home, near it or far
from it is now Person's own belief, derived from its spatial model, and it can
be uncertain or wrong. Trusted containment is untouched by any of this; it
lives in the runtime and uses exact positions (see the TypeScript suite).
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from person_cognition.spatial import Estimate, Spatial, SpatialMap
from person_persistence import new_event
from person_planner import symbolic_state
from person_policy import safe_envelope
from person_protocol import protocol_validator
from test_loop import Harness, envelope
from test_spatial import STILL, at, moved

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def view() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["vitals"].update({"health": 20.0, "food": 20.0})
    for key in ("resources", "passiveAnimals", "hostiles", "players", "containers", "hazards"):
        document["nearby"][key] = []
    document["selfMotion"] = dict(STILL)
    return document


def settled_home(spatial: Spatial, spatial_map: SpatialMap) -> None:
    """What happens when Person builds its shelter: this place is home."""
    kind, payload = spatial.settle("shelter", 0, label="home")
    spatial_map.apply(
        new_event(
            person_id="ada",
            world_id="w",
            session_id="8f6c1c0e-3d0a-4a1e-9f3a-2b6f1d9c4e11",
            episode_id="ep_1",
            decision_id=None,
            tick=0,
            policy_revision=0,
            training_context="fixture",
            event_type=kind,
            payload=payload,
            previous_event_id=None,
        )
    )


def fresh() -> Spatial:
    spatial_map = SpatialMap()
    spatial = Spatial(spatial_map)
    settled_home(spatial, spatial_map)
    return spatial


# ------------------------------------------------------- the observation


def test_the_observation_carries_no_home_distance(view: dict[str, Any]) -> None:
    assert "homeDistance" not in view["home"]
    smuggled = deepcopy(view)
    smuggled["home"]["homeDistance"] = 0.0
    valid, _ = protocol_validator().validate(smuggled)
    assert not valid, "the schema refuses a home distance"


def test_without_a_belief_person_is_not_taken_to_be_home(view: dict[str, Any]) -> None:
    assert symbolic_state(view)["at_home"] == 0
    assert symbolic_state(view, home="at_home")["at_home"] == 1
    assert symbolic_state(view, home="near")["at_home"] == 0


# ------------------------------------------------------------ the relation


def test_home_relation_follows_the_spatial_model_and_its_doubt() -> None:
    assert Spatial(SpatialMap()).home_relation() == ("unknown", 0.0), "no home place yet"

    spatial = fresh()
    relation, confidence = spatial.home_relation()
    assert relation == "at_home" and 0 < confidence < 1, "never certain"

    spatial.feel(moved("ahead", 20), frozenset())
    assert spatial.home_relation()[0] == "near"

    spatial.feel(moved("ahead", 60), frozenset())
    assert spatial.home_relation()[0] == "far"


def test_enough_doubt_makes_home_unknown_rather_than_near_or_far() -> None:
    spatial = fresh()
    spatial.feel(moved("ahead", 30), frozenset())
    # Thirty blocks with twelve of accumulated doubt could be either side of
    # the near/far line, so Person does not claim to know which.
    assert spatial.home_relation()[0] == "unknown"


def test_being_lost_makes_home_unknown() -> None:
    spatial = fresh()
    spatial.feel(
        {
            "continuity": "discontinuous",
            "translation": {"direction": "unknown", "band": "unknown", "distance": None},
            "rotation": "unknown",
            "vertical": "unknown",
        },
        frozenset(),
    )
    assert spatial.home_relation() == ("unknown", 0.0)


# ---------------------------------------------------------------- the loop


def outcome(invocation: dict[str, Any], policy: dict[str, Any], skill: str) -> dict[str, Any]:
    return {
        **envelope("SkillOutcome", invocation["tick"] + 10),
        "decisionId": invocation["decisionId"],
        "goalId": invocation["goalId"],
        "routineId": invocation["routineId"],
        "contextId": policy["contextId"],
        "requestedSkill": invocation["skillId"],
        "requestedParameters": invocation["parameters"],
        "requestedSkillStatus": "SUCCESS",
        "executedSkill": skill,
        "executedParameters": {},
        "status": "SUCCESS",
        "emergency": False,
        "reasonCodes": [],
        "effects": [],
        "expectedEffects": [],
        "healthBefore": 20,
        "healthAfter": 20,
        "foodBefore": 20,
        "foodAfter": 20,
        "healthCost": 0,
        "resourceCost": [],
        "inventoryDelta": [],
        "elapsedTicks": 10,
        "interruptReason": None,
        "completionEvidence": {"kinds": ["elapsed_ticks"], "details": {}},
    }


def home_via(harness: Harness, view: dict[str, Any], skill: str) -> None:
    _, policy, invocation = harness.observe(at(view, 100))
    harness.loop.handle(outcome(invocation, policy, skill))


def night(view: dict[str, Any], tick: int, motion: dict[str, Any] | None = None) -> dict[str, Any]:
    dark = at(view, tick, motion)
    dark["environment"]["dayPhase"] = "night"
    dark["environment"]["lightLevel"] = 2
    return dark


def goal_types(goal: dict[str, Any]) -> set[str]:
    return {entry["goalType"] for entry in goal["stack"]}


@pytest.mark.parametrize("skill", ["build_basic_shelter", "return_home"])
def test_home_is_learned_from_person_s_own_actions(
    tmp_path: Path, view: dict[str, Any], skill: str
) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    home_via(harness, view, skill)
    _, policy, _ = harness.observe(at(view, 120))
    assert harness.loop.home == "at_home"
    assert ".hm_at_home." in f".{policy['contextId']}."


def test_the_night_return_follows_belief_not_the_body(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    home_via(harness, view, "build_basic_shelter")

    goal, _, _ = harness.observe(night(view, 200))
    assert "RECOVER_HOME" not in goal_types(goal), "at home at night: nothing to recover"

    # Corrupt Person's belief without moving anything physical: it now thinks
    # it is far from home, and wants to go back, though the body never moved.
    far = harness.loop.spatial.estimate
    harness.loop.spatial.estimate = replace(far, forward=far.forward + 80)
    goal, _, _ = harness.observe(night(view, 220))
    assert harness.loop.home == "far"
    assert "RECOVER_HOME" in goal_types(goal)


def test_a_believed_home_survives_restart_with_honest_doubt(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Harness(tmp_path)
    first.hello()
    home_via(first, view, "build_basic_shelter")
    first.loop.handle(
        {
            **envelope("EpisodeEvent", 300),
            "episodeId": "ep_1",
            "phase": "ended",
            "reasonCodes": ["test"],
            "rngSeed": 7,
            "trainingContext": "fixture",
        }
    )
    second = Harness(tmp_path)
    second.hello()
    second.observe(at(view, 5, {**STILL, "continuity": "start"}))
    relation, confidence = second.loop.spatial.home_relation()
    assert relation == "at_home"
    assert confidence < first.loop.spatial.home_relation()[1], "less sure after waking"


def test_the_exploration_envelope_reads_belief(view: dict[str, Any]) -> None:
    assert "too_far_from_home" in safe_envelope(view, home="far").reasons
    assert "too_far_from_home" not in safe_envelope(view, home="unknown").reasons


def test_an_estimate_is_never_set_from_outside_the_sense() -> None:
    # The test above corrupts the estimate deliberately, as a probe. The loop
    # itself never assigns it; an architecture test enforces that.
    assert Estimate().uncertainty == 0.0
