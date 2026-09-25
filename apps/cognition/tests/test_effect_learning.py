"""Learned reliability of skill effects: uncertain, revisable, and bounded.

The rules defended here are ADR 0011's. Only a genuine attempt, judged on a
fact Person can evaluate from its own experience, teaches anything; refusals,
takeovers, preemptions and missing prerequisites are inconclusive. A belief
keeps its evidence and its strength apart from its estimate, never reaches
certainty from one outcome, and can be reversed. The learning mode decides
where evidence goes: nowhere, a shadow table the planner never sees, or the
active table, which then adds a small, separately recorded term to routine
scores. Routine statistics, memory salience and affect are untouched.

Cognition-level evidence. The TypeScript suite covers hidden world state and
a world shifted by 1000 blocks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from person_cognition.affect import AffectRecord
from person_cognition.effect_learning import (
    EVALUABLE_FACTS,
    RELIABILITY_LIMIT,
    EffectBelief,
    EffectBeliefs,
    classify,
    reliability_term,
)
from person_cognition.memory import MemoryStore, RecallRules
from person_cognition.prediction import PendingPrediction
from person_persistence import EvidenceJournal, new_event
from person_policy import EvidencePolicyProvider, RoutineCandidate, RoutineStatistics
from person_skills import skill_registry
from test_loop import Harness, envelope
from test_spatial import STILL, at

REPOSITORY = Path(__file__).resolve().parents[3]
WOOD = ({"fact": "wood", "op": "+=", "value": 8},)


def trial(
    *,
    status: str = "SUCCESS",
    requested_status: str | None = None,
    executed: str = "gather_wood",
    emergency: bool = False,
    reasons: tuple[str, ...] = (),
    effects: tuple[dict[str, Any], ...] = WOOD,
    before: float = 0.0,
    after: float | None = 8.0,
    fact: str = "wood",
) -> list[Any]:
    return classify(
        requested="gather_wood",
        executed=executed,
        status=status,
        requested_status=requested_status or status,
        emergency=emergency,
        reason_codes=reasons,
        expected_effects=effects,
        state_before={fact: before},
        state_after=None if after is None else {fact: after},
    )


def evidence(verdict: str, admitted: str = "active", skill: str = "gather_wood") -> Any:
    return new_event(
        person_id="ada",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep",
        decision_id=None,
        tick=1,
        policy_revision=0,
        training_context="fixture",
        event_type="effect_evidence",
        payload={
            "skill": skill,
            "fact": "wood",
            "verdict": verdict,
            "reason": "test",
            "admitted_to": admitted,
            "prediction_event_id": None,
        },
        previous_event_id=None,
    )


def belief_after(*verdicts: str) -> EffectBelief:
    beliefs = EffectBeliefs()
    for verdict in verdicts:
        beliefs.apply(evidence(verdict))
    found = beliefs.belief("active", "fixture", "gather_wood", "wood")
    assert found is not None
    return found


# ------------------------------------------------------------ classification


def test_a_genuine_attempt_whose_effect_is_felt_supports_it() -> None:
    assert [(t.verdict, t.reason) for t in trial()] == [("supports", "effect_observed")]
    assert [t.verdict for t in trial(after=0.0)] == ["contradicts"]
    assert [t.verdict for t in trial(after=2.0)] == ["partial"]


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"status": "INVALIDATED", "reasons": ("protected_area",)}, "not_attempted_invalidated"),
        ({"emergency": True, "executed": "flee"}, "overridden_by_runtime"),
        ({"status": "SUCCESS", "requested_status": "PREEMPTED"}, "not_attempted_success"),
        (
            {"status": "FAILED", "reasons": ("missing_materials",)},
            "not_attempted_missing_materials",
        ),
        (
            {"status": "UNREACHABLE", "reasons": ("unreachable_resource",)},
            "not_attempted_unreachable",
        ),
        ({"status": "INTERRUPTED"}, "not_attempted_interrupted"),
        ({"after": None}, "no_observation_after"),
    ],
)
def test_what_was_not_a_genuine_attempt_or_could_not_be_judged_teaches_nothing(
    kwargs: dict[str, Any], reason: str
) -> None:
    trials = trial(**kwargs)
    assert trials and all(t.verdict == "inconclusive" for t in trials)
    assert trials[0].reason == reason


def test_an_attempt_that_really_failed_is_evidence() -> None:
    # The furnace ran and produced nothing: that is about what the action does.
    trials = trial(status="FAILED", reasons=("no_fuel",), after=0.0)
    assert [t.verdict for t in trials] == ["contradicts"]


@pytest.mark.parametrize(
    "fact", ["at_home", "sheltered", "stored_surplus", "owned_storage_available"]
)
def test_beliefs_ledger_facts_and_unobservables_are_not_evaluable(fact: str) -> None:
    effect = ({"fact": fact, "op": "=", "value": 1},)
    trials = trial(effects=effect, fact=fact, before=0.0, after=1.0)
    assert [(t.verdict, t.reason) for t in trials] == [("inconclusive", "not_evaluable_by_person")]
    assert fact not in EVALUABLE_FACTS


def test_trials_and_beliefs_are_keyed_by_skill_and_fact_only() -> None:
    # C4: whatever tree the motor chose, nothing here can name it.
    assert set(trial()[0].to_json()) == {"skill", "fact", "verdict", "reason"}
    assert set(belief_after("supports").to_json()) == {
        "skill",
        "fact",
        "supporting",
        "contradicting",
        "provenance",
    }


# ---------------------------------------------------------------- belief


def test_repeated_success_raises_and_repeated_failure_lowers_reliability() -> None:
    assert (belief_after(*["supports"] * 8).estimate or 0) > 0.8
    assert (belief_after(*["contradicts"] * 8).estimate or 1) < 0.2


def test_one_outcome_is_not_certainty() -> None:
    once = belief_after("contradicts")
    assert once.estimate is not None and 0 < once.estimate < 0.5
    assert once.strength < 0.25
    assert 0.5 < (belief_after("supports").estimate or 0) < 1


def test_later_contradicting_evidence_reverses_an_earlier_trend() -> None:
    reversed_ = belief_after(*["supports"] * 5, *["contradicts"] * 10)
    assert (reversed_.estimate or 1) < 0.5


def test_no_experience_is_not_the_same_as_balanced_experience() -> None:
    unknown = EffectBelief("gather_wood", "wood")
    balanced = belief_after(*["supports"] * 10, *["contradicts"] * 10)
    assert unknown.estimate is None and unknown.strength == 0
    assert balanced.estimate == pytest.approx(0.5)
    assert balanced.strength > 0.8


def test_every_belief_can_say_why_it_is_held() -> None:
    held = belief_after("supports", "contradicts", "supports")
    assert len(held.provenance) == 3 and held.supporting == 2 and held.contradicting == 1


# ----------------------------------------------------------- learning modes


def settle(
    harness: Harness,
    verdict: str,
    skill: str = "gather_wood",
    effects: tuple[dict[str, Any], ...] = WOOD,
) -> None:
    """One settled prediction through the loop's own learning path."""
    pending = PendingPrediction(
        decision_id="33333333-3333-4333-8333-333333333333",
        context_id="c",
        routine_id="r",
        goal_id="g",
        requested_skill=skill,
        state_before={str(effect["fact"]): 0.0 for effect in effects},
        tick=1,
        executed_skill=skill,
        expected_effects=effects,
        status="SUCCESS",
        requested_status="SUCCESS",
        settled=True,
    )
    gained = 8.0 if verdict == "supports" else 0.0
    after = {str(effect["fact"]): gained for effect in effects}
    harness.loop._learn_effects(pending, after, None, 10)


def tables(harness: Harness) -> dict[str, int]:
    return {name: len(table) for name, table in harness.loop.effect_beliefs.tables.items()}


def test_off_learns_nothing_shadow_only_shadow_supervised_the_active_table(
    tmp_path: Path,
) -> None:
    for mode, expected in (
        ("off", {"active": 0, "shadow": 0}),
        ("shadow", {"active": 0, "shadow": 1}),
        ("supervised", {"active": 1, "shadow": 0}),
    ):
        harness = Harness(tmp_path / mode, learning_mode=mode)
        harness.hello()
        for _ in range(3):
            settle(harness, "supports")
        assert tables(harness) == expected, mode
        recorded = [
            dict(event.payload)
            for event in EvidenceJournal(tmp_path / mode / "journal").read()
            if event.type == "effect_evidence"
        ]
        assert len(recorded) == 3, "every trial is journalled, whatever the mode"


@pytest.fixture
def view() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPOSITORY / "fixtures/protocol-corpus/valid/observation.json").read_text(encoding="utf-8")
    )
    document["selfMotion"] = dict(STILL)
    return document


BERRIES = (
    {"fact": "plant_food", "op": "+=", "value": 6},
    {"fact": "edible_food", "op": "+=", "value": 6},
)


def hungry_by_berries(view: dict[str, Any]) -> dict[str, Any]:
    changed = at(view, 100)
    changed["nearby"]["resources"] = [
        {
            "kind": "plant_food",
            "name": "sweet_berry_bush",
            "distance": 4.0,
            "bearing": "ahead",
            "elevation": "level",
            "rangeBand": "reach",
            "detail": "central",
            "harvestPermitted": True,
        }
    ]
    return changed


def test_shadow_learning_changes_no_decision(tmp_path: Path, view: dict[str, Any]) -> None:
    # Heavy shadow evidence against the very skill the plan needs. Were the
    # shadow table visible to the planner, it would show in the scores.
    runs = {}
    for mode in ("off", "shadow"):
        harness = Harness(tmp_path / mode, learning_mode=mode)
        harness.hello()
        for _ in range(12):
            settle(harness, "contradicts", "gather_plant_food", BERRIES)
        _, _, invocation = harness.observe(hungry_by_berries(view))
        runs[mode] = (invocation["skillId"], invocation["parameters"], invocation["routineId"])
        selected = [
            dict(event.payload)
            for event in EvidenceJournal(tmp_path / mode / "journal").read()
            if event.type == "routine_selected"
        ]
        steps = {step for record in selected for step in record["steps"]}
        assert any("gather_plant_food" in step for step in steps), steps
        for record in selected:
            assert all(candidate["learned_effect"] == 0 for candidate in record["candidates"])
    assert runs["off"] == runs["shadow"]
    assert harness.loop.effect_beliefs.tables["shadow"], "the shadow learner did learn"


def test_active_beliefs_survive_restart_without_filling_the_mind(tmp_path: Path) -> None:
    first = Harness(tmp_path, learning_mode="supervised")
    first.hello()
    for _ in range(4):
        settle(first, "supports")
    before = first.loop.effect_beliefs.belief("active", "fixture", "gather_wood", "wood")

    second = Harness(tmp_path, learning_mode="supervised")
    second.hello()
    after = second.loop.effect_beliefs.belief("active", "fixture", "gather_wood", "wood")
    assert after == before and after is not None
    assert len(second.loop.memory.working) == 0
    assert len(second.loop.memory_store) == len(first.loop.memory_store), "no episodes added"


# ----------------------------------------------------------------- policy


def option(name: str, steps: tuple[str, ...], applicable: bool = True) -> RoutineCandidate:
    return RoutineCandidate(
        routine_id=f"r_{name}",
        name=name,
        steps=steps,
        step_labels=steps,
        risk=0.2,
        cost=3.0,
        ticks=2400,
        applicable=applicable,
    )


def supervised_provider() -> EvidencePolicyProvider:
    statistics = RoutineStatistics()
    for routine in ("r_plants", "r_hunt"):
        for _ in range(6):
            statistics.apply(
                new_event(
                    person_id="ada",
                    world_id="w",
                    session_id="00000000-0000-4000-8000-000000000001",
                    episode_id="ep",
                    decision_id=None,
                    tick=1,
                    policy_revision=0,
                    training_context="fixture",
                    event_type="routine_outcome",
                    payload={"routine_id": routine, "context_id": "c", "status": "SUCCESS"},
                    previous_event_id=None,
                )
            )
    return EvidencePolicyProvider(
        statistics, training_context="fixture", learning_mode="supervised", minimum_support=3
    )


def beliefs_where(unreliable: str, reliable: str) -> EffectBeliefs:
    beliefs = EffectBeliefs()
    registry = skill_registry()
    for skill, verdict in ((unreliable, "contradicts"), (reliable, "supports")):
        for effect in registry.get(skill).expected_effects:
            for _ in range(10):
                event = evidence(verdict, skill=skill)
                event = new_event(
                    **{
                        key: getattr(event, key)
                        for key in (
                            "person_id",
                            "world_id",
                            "session_id",
                            "episode_id",
                            "decision_id",
                            "tick",
                            "policy_revision",
                            "training_context",
                        )
                    },
                    event_type="effect_evidence",
                    payload={**event.payload, "fact": effect.fact},
                    previous_event_id=None,
                )
                beliefs.apply(event)
    return beliefs


def test_supported_reliability_can_change_a_close_choice_and_only_a_close_one(
    view: dict[str, Any],
) -> None:
    provider = supervised_provider()
    plants = option("plants", ("gather_plant_food",))
    hunt = option("hunt", ("hunt_safe_passive_animals",))
    registry = skill_registry()

    neutral = provider.propose(view, None, [plants, hunt], "c")
    for unreliable, reliable in (
        ("gather_plant_food", "hunt_safe_passive_animals"),
        ("hunt_safe_passive_animals", "gather_plant_food"),
    ):
        term = reliability_term(beliefs_where(unreliable, reliable), registry, "fixture")
        chosen = provider.propose(view, None, [plants, hunt], "c", reliability=term)
        winner = {"gather_plant_food": "r_plants", "hunt_safe_passive_animals": "r_hunt"}
        assert chosen.routine_id == winner[reliable], (neutral.routine_id, chosen.reason_codes)
        learned = {
            scored.candidate.routine_id: scored.learned_effect for scored in chosen.candidates
        }
        assert all(abs(value) <= RELIABILITY_LIMIT for value in learned.values())
        assert learned[winner[reliable]] > 0 > learned[winner[unreliable]]

    # And no reliability can make an option the runtime would refuse win.
    term = reliability_term(
        beliefs_where("gather_plant_food", "hunt_safe_passive_animals"), registry, "fixture"
    )
    refused = option("hunt", ("hunt_safe_passive_animals",), applicable=False)
    chosen = provider.propose(view, None, [plants, refused], "c", reliability=term)
    assert chosen.routine_id == "r_plants"


# ----------------------------------------------------------- separations


def test_routine_statistics_memory_and_affect_ignore_effect_evidence() -> None:
    statistics = RoutineStatistics()
    memory = MemoryStore()
    affect = AffectRecord()
    before = (json.dumps(statistics.to_json(), sort_keys=True), affect.to_json())
    for verdict in ("supports", "contradicts", "partial"):
        event = evidence(verdict)
        statistics.apply(event)
        memory.apply(event)
        affect.apply(event)
    assert json.dumps({**statistics.to_json(), "events_applied": 0}, sort_keys=True) == json.dumps(
        {**json.loads(before[0]), "events_applied": 0}, sort_keys=True
    )
    assert statistics.routines == {} and statistics.skills == {}
    assert len(memory) == 0 and affect.to_json() == before[1]
    assert RecallRules() == RecallRules(
        base_half_life=24_000.0, salience_stretch=9.0, threshold=0.05, limit=3
    )


def test_the_learner_reads_nothing_privileged_and_touches_nothing_else() -> None:
    source = (REPOSITORY / "apps/cognition/python/person_cognition/effect_learning.py").read_text(
        encoding="utf-8"
    )
    # Everything outside docstrings: the prose may name what is excluded.
    code = "\n".join(source.split('"""')[2::2])
    for forbidden in (
        "WorldSnapshot",
        "yaw",
        "position",
        "homeDistance",
        "completionEvidence",
        "EvidenceJournal",
        "read_text",
        "affect",
        "salience",
        "RoutineStatistics",
    ):
        assert forbidden not in code, forbidden
    assert envelope("Observation", 1)["type"] == "Observation"
