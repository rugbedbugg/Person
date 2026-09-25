"""Affect: appraised from experience, decaying, and only ever a bounded bias.

The rules defended here are ADR 0010's. Affect rises from what Person
perceives and feels, settles toward baseline as experienced time passes, and
persists across a restart. It adjusts the priority of goals that already
exist, by a bounded and recorded amount, and Person's willingness to explore
routines the runtime would accept. It never creates a goal, never runs a
skill, never changes what the runtime permits, and never touches memory
salience.

Cognition-level evidence with hand-built messages. The TypeScript suite covers
the same hidden threat behind a wall, and a world shifted by 1000 blocks.
"""

from __future__ import annotations

import dataclasses
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from person_cognition.affect import (
    BIAS_LIMIT,
    HALF_LIVES,
    Affect,
    AffectRecord,
    AffectState,
    Temperament,
    appraise_harm,
    appraise_outcome,
    appraise_threat,
    decay,
)
from person_cognition.memory import RecallRules
from person_cognition.memory import salience as memory_salience
from person_persistence import EvidenceJournal, new_event
from person_policy import EvidencePolicyProvider, RoutineCandidate, RoutineStatistics
from test_cognitive_home import outcome
from test_loop import Harness, envelope
from test_spatial import STILL, at

REPOSITORY = Path(__file__).resolve().parents[3]
COGNITION = REPOSITORY / "apps/cognition/python/person_cognition"


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


def zombie(distance: float) -> dict[str, Any]:
    return {
        "name": "zombie",
        "distance": distance,
        "bearing": "ahead",
        "elevation": "level",
        "rangeBand": "near",
        "detail": "central",
        "named": False,
        "tamed": False,
        "protectedTarget": True,
    }


def appraisals(evidence: Path) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in EvidenceJournal(evidence / "journal").read()
        if event.type == "affect_appraised"
    ]


def skill_outcome(skill: str, status: str, *, emergency: bool = False) -> dict[str, Any]:
    return {
        "executedSkill": skill,
        "requestedSkill": skill,
        "status": status,
        "emergency": emergency,
    }


# --------------------------------------------------------------- appraisal


def test_a_perceived_threat_raises_unease(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    threatened = at(view, 100)
    threatened["nearby"]["hostiles"] = [zombie(6.0)]
    harness.observe(threatened)

    record = appraisals(tmp_path)[-1]
    assert record["trigger"] == "perceived_threat"
    assert record["after"]["unease"] > record["before"]["unease"] == 0.0
    assert harness.loop.affect.state.unease > 0


def test_no_threat_in_view_means_no_threat_appraisal(view: dict[str, Any]) -> None:
    # An unperceived threat is not in the observation at all, so there is
    # nothing to appraise. The end-to-end wall test is in TypeScript.
    assert appraise_threat(view) is None


def test_harm_felt_through_the_body_is_appraised(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    harness.observe(at(view, 100))
    hurt = at(view, 120)
    hurt["vitals"]["health"] = 14.0
    harness.observe(hurt)
    record = appraisals(tmp_path)[-1]
    assert record["trigger"] == "harm"
    assert record["components"] == {"health_lost": 6.0}
    assert record["after"]["valence"] < 0 and record["after"]["unease"] > 0


def test_success_and_repeated_failure_are_appraised_differently() -> None:
    succeeding = Affect(AffectRecord())
    failing = Affect(AffectRecord())
    for tick in range(5):
        appraisal = appraise_outcome(skill_outcome("gather_wood", "SUCCESS"))
        assert appraisal is not None
        succeeding.feel(appraisal, tick)
        appraisal = appraise_outcome(skill_outcome("gather_wood", "FAILED"))
        assert appraisal is not None
        failing.feel(appraisal, tick)
    assert succeeding.state.valence > 0 > failing.state.valence
    assert succeeding.state.control > 0 > failing.state.control
    assert appraise_outcome(skill_outcome("look", "SUCCESS")) is None, "a glance is nothing"


def test_every_change_is_recorded_with_its_cause(tmp_path: Path, view: dict[str, Any]) -> None:
    harness = Harness(tmp_path)
    harness.hello()
    threatened = at(view, 100)
    threatened["nearby"]["hostiles"] = [zombie(4.0)]
    harness.observe(threatened)
    for record in appraisals(tmp_path):
        assert set(record) == {
            "trigger",
            "components",
            "before",
            "delta",
            "after",
            "experienced_tick",
        }
        for dimension, change in record["delta"].items():
            assert record["after"][dimension] == pytest.approx(
                record["before"][dimension] + change, abs=1e-3
            )


# ------------------------------------------------------- decay and restart


def test_affect_decays_toward_baseline_in_experienced_time() -> None:
    affect = Affect(AffectRecord())
    harm = appraise_harm(8.0)
    assert harm is not None
    affect.feel(harm, 0)
    raised = affect.state
    affect.advance(int(HALF_LIVES["unease"]))
    assert affect.state.unease == pytest.approx(raised.unease / 2, abs=1e-3)
    affect.advance(int(HALF_LIVES["unease"]) * 20)
    assert affect.state.unease < 0.01 and abs(affect.state.valence) < abs(raised.valence)
    assert decay(raised, Temperament(), 0) == raised, "no time, no change"


def test_one_failure_does_not_change_person_for_good() -> None:
    affect = Affect(AffectRecord())
    failure = appraise_outcome(skill_outcome("mine_stone", "FAILED"))
    assert failure is not None
    affect.feel(failure, 0)
    affect.advance(200_000)
    assert affect.state == AffectState()


def test_a_restart_resumes_affect_rather_than_resetting_it(
    tmp_path: Path, view: dict[str, Any]
) -> None:
    first = Harness(tmp_path)
    first.hello()
    threatened = at(view, 100)
    threatened["nearby"]["hostiles"] = [zombie(3.0)]
    first.observe(threatened)
    felt = first.loop.affect.state
    first.loop.handle(
        {
            **envelope("EpisodeEvent", 120),
            "episodeId": "ep_1",
            "phase": "ended",
            "reasonCodes": ["test"],
            "rngSeed": 7,
            "trainingContext": "fixture",
        }
    )
    second = Harness(tmp_path)
    second.hello()
    assert second.loop.affect.state == felt, "no downtime decay: Person was not there"
    assert felt.unease > 0


# -------------------------------------------------------------------- bias


def test_the_bias_is_bounded_and_never_touches_urgent_goals() -> None:
    extreme = [
        AffectState(valence=-1, unease=1, control=-1),
        AffectState(valence=1, unease=0, control=1),
    ]
    for state in extreme:
        affect = Affect(AffectRecord())
        affect.state = state
        for facts in (frozenset({"owned_storage_available"}), frozenset({"tool_tier"})):
            assert abs(affect.bias(facts, "homeostasis")) <= BIAS_LIMIT
        assert affect.bias(frozenset({"safe"}), "emergency") == 0.0


def ranked(harness: Harness, view: dict[str, Any], state: AffectState | None) -> str:
    if state is not None:
        harness.loop.affect.state = state
    goal, _, _ = harness.observe(at(view, 200))
    return str(goal["goal"]["goalType"])


@pytest.fixture
def two_goals(view: dict[str, Any]) -> dict[str, Any]:
    """A home, no storage, a wooden pickaxe: tools (290) and the project (300)."""
    close = deepcopy(view)
    close["home"]["shelterState"] = "complete"
    close["inventory"]["items"].append({"name": "wooden_pickaxe", "count": 1})
    return close


def with_home(tmp_path: Path, view: dict[str, Any]) -> Harness:
    harness = Harness(tmp_path)
    harness.hello()
    _, policy, invocation = harness.observe(at(view, 100))
    harness.loop.handle(outcome(invocation, policy, "build_basic_shelter"))
    return harness


def experienced(appraisal_outcomes: list[dict[str, Any]], harm: float) -> AffectState:
    """The state a history of legitimate experiences leaves behind."""
    affect = Affect(AffectRecord())
    for index, message in enumerate(appraisal_outcomes):
        appraisal = appraise_outcome(message)
        if appraisal is not None:
            affect.feel(appraisal, index)
    hurt = appraise_harm(harm)
    if hurt is not None:
        affect.feel(hurt, len(appraisal_outcomes))
    return affect.state


def test_different_experience_makes_a_different_near_choice_through_the_generic_bias(
    tmp_path: Path, two_goals: dict[str, Any]
) -> None:
    confident = experienced([skill_outcome("gather_wood", "SUCCESS")] * 10, harm=0)
    shaken = experienced([skill_outcome("gather_wood", "FAILED")] * 4, harm=6)

    neutral = ranked(with_home(tmp_path / "neutral", two_goals), two_goals, AffectState())
    bold = ranked(with_home(tmp_path / "bold", two_goals), two_goals, confident)
    wary = ranked(with_home(tmp_path / "wary", two_goals), two_goals, shaken)

    assert neutral == "ESTABLISH_STORAGE", "base order: the project's storage milestone"
    assert bold == "ESTABLISH_TOOLS", "a run of success makes going out more attractive"
    assert wary == "ESTABLISH_STORAGE"


def test_affect_cannot_create_a_goal_or_outrank_an_urgent_one(
    tmp_path: Path, two_goals: dict[str, Any]
) -> None:
    harness = with_home(tmp_path, two_goals)
    hungry = deepcopy(two_goals)
    hungry["vitals"]["food"] = 6.0
    harness.loop.affect.state = AffectState(valence=-1, unease=1, control=-1)
    goal, _, _ = harness.observe(at(hungry, 200))
    assert goal["goal"]["goalType"] == "SECURE_FOOD", "hunger still comes first"
    before = {entry["goalType"] for entry in goal["stack"]}
    harness.loop.affect.state = AffectState(valence=1, unease=0, control=1)
    goal, _, _ = harness.observe(at(hungry, 220))
    assert {entry["goalType"] for entry in goal["stack"]} == before, "no new goals"


# --------------------------------------------------------------- exploration


def test_unease_narrows_exploration_and_calm_restores_it() -> None:
    calm = Affect(AffectRecord())
    uneasy = Affect(AffectRecord())
    uneasy.state = AffectState(unease=0.8, control=-0.4)
    assert uneasy.tolerance() < calm.tolerance() == 1.0
    uneasy.advance(int(HALF_LIVES["control"]) * 20)
    assert uneasy.tolerance() == pytest.approx(1.0, abs=0.01)


def known_success(routine_id: str) -> Any:
    return new_event(
        person_id="ada",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep",
        decision_id=None,
        tick=1,
        policy_revision=0,
        training_context="fixture",
        event_type="routine_outcome",
        payload={"routine_id": routine_id, "context_id": "c", "status": "SUCCESS"},
        previous_event_id=None,
    )


def option(name: str) -> RoutineCandidate:
    steps = ("gather_plant_food", "eat_to_target")
    return RoutineCandidate(
        routine_id=f"r_{name}",
        name=name,
        steps=steps,
        step_labels=steps,
        risk=0.2,
        cost=3.0,
        ticks=2400,
    )


def test_calm_explores_and_unease_prefers_the_familiar_inside_the_same_permissions(
    view: dict[str, Any],
) -> None:
    # Case A and case B: the same candidates, the same observation, so the
    # same runtime permissions. Only Person's willingness differs.
    statistics = RoutineStatistics()
    for _ in range(6):
        statistics.apply(known_success("r_known"))
    provider = EvidencePolicyProvider(
        statistics,
        training_context="fixture",
        learning_mode="supervised",
        minimum_support=3,
        exploration_bonus=0.9,
    )
    options = [option("known"), option("untried")]
    calm = Affect(AffectRecord())
    uneasy = Affect(AffectRecord())
    uneasy.state = AffectState(unease=1.0, control=-1.0)

    bold = provider.propose(view, None, options, "c", tolerance=calm.tolerance())
    wary = provider.propose(view, None, options, "c", tolerance=uneasy.tolerance())
    assert bold.routine_id == "r_untried", bold.reason_codes
    assert wary.routine_id == "r_known", wary.reason_codes
    assert "safe_envelope_open" in bold.reason_codes and "safe_envelope_open" in wary.reason_codes


# ---------------------------------------------------------------- boundaries


def test_affect_code_reads_nothing_privileged_and_runs_no_skill() -> None:
    source = (COGNITION / "affect.py").read_text(encoding="utf-8")
    for forbidden in (
        "WorldSnapshot",
        "yaw",
        "pitch",
        "position",
        "homeDistance",
        "EvidenceJournal",
        "SkillInvocation",
        "skill_id",
        "_emit",
        "invoke",
    ):
        assert forbidden not in source, forbidden
    # Nothing outside affect.py reads the state to decide anything: only the
    # bias and the tolerance leave it.
    for path in COGNITION.rglob("*.py"):
        if path.name == "affect.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "affect.state." not in text, f"{path.name} reads affect state directly"


def test_memory_salience_and_recall_are_untouched_by_affect() -> None:
    assert RecallRules() == RecallRules(
        base_half_life=24_000.0, salience_stretch=9.0, threshold=0.05, limit=3
    )
    for path in (COGNITION / "memory").rglob("*.py"):
        assert "affect" not in path.read_text(encoding="utf-8").lower().replace("not affect", ""), (
            f"{path.name} mentions affect"
        )
    assert "affect" not in dir(memory_salience)


def test_the_protocol_has_no_way_to_carry_affect_to_the_runtime() -> None:
    for schema in (REPOSITORY / "packages/protocol/schemas").glob("*.json"):
        body = schema.read_text(encoding="utf-8").lower()
        for word in ("affect", "valence", "unease", "tolerance"):
            assert word not in body, f"{schema.name} mentions {word}"


def test_affect_is_not_belief(view: dict[str, Any]) -> None:
    from person_planner import symbolic_state

    assert "unease" not in symbolic_state(view)
    assert dataclasses.fields(AffectState)
