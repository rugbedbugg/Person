"""Metareasoning rules, unit by unit (ADR 0021). Scripted models only."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from person_cognition.deliberation import ScriptedModel, build_context
from person_cognition.deliberation.arbiter import Arbiter, immediate_runner, thread_runner
from person_cognition.deliberation.context import Capability
from person_cognition.deliberation.deliberator import Deliberator
from person_cognition.deliberation.metareasoning import (
    COOLDOWNS,
    EXPERIENCED_HOUR,
    PER_HOUR,
    PER_SESSION,
    RECOVERY_BAND,
    RECURRENCE_WINDOW,
    STALE_AFTER,
    ArbitrationRecord,
    Detectors,
    Trigger,
    admit_goal,
    band,
    prediction_key,
)
from person_persistence import new_event
from person_skills import skill_registry

GOAL_TYPES = ("RECOVER_HOME", "SECURE_FOOD", "INVESTIGATE", "SURVIVE_IMMEDIATE")


def event(kind: str, **payload: Any) -> Any:
    return new_event(
        person_id="test-person-000",
        world_id="w",
        session_id="s",
        episode_id="e",
        decision_id=None,
        tick=0,
        policy_revision=0,
        training_context="fixture",
        event_type=kind,
        payload=payload,
        previous_event_id=None,
    )


# --------------------------------------------------------------- detectors


def test_an_emergency_recurs_only_three_times_within_the_window() -> None:
    detectors = Detectors()
    assert detectors.emergency("suffocation", 0) is None
    assert detectors.emergency("suffocation", 100) is None
    fired = detectors.emergency("suffocation", 200)
    assert fired is not None and fired.kind == "emergency_recurrence" and fired.key == "suffocation"
    spread = Detectors()
    for at in (0, RECURRENCE_WINDOW, 2 * RECURRENCE_WINDOW):
        assert spread.emergency("suffocation", at + 1) is None, "too far apart to be one problem"


def test_failures_plans_and_prediction_errors_need_three() -> None:
    detectors = Detectors()
    assert detectors.goal_failed("SECURE_FOOD", "g", 2, 500.0) is None
    assert detectors.goal_failed("SECURE_FOOD", "g", 3, 500.0).source_priority == 500.0
    assert detectors.planned("SECURE_FOOD", "g", False, 500.0) is None
    assert detectors.planned("SECURE_FOOD", "g", True, 500.0) is None, "a plan resets the count"
    for _ in range(2):
        assert detectors.planned("SECURE_FOOD", "g", False, 500.0) is None
    assert detectors.planned("SECURE_FOOD", "g", False, 500.0) is not None
    for at in (0, 10):
        assert detectors.prediction("gather_wood", ["wood"], "major", at, "g", 1.0) is None
    assert detectors.prediction("gather_wood", ["wood"], "minor", 20, "g", 1.0) is None
    assert detectors.prediction("gather_wood", ["wood"], "inverted", 30, "g", 1.0) is not None


def test_one_failed_invocation_is_one_signal_keyed_by_its_failing_facts() -> None:
    detectors = Detectors()
    facts = ["wood", "fuel", "building_materials", "wood"]
    for at in (0, 10):
        assert detectors.prediction("gather_wood", facts, "major", at, "g", 1.0) is None, (
            "three failing facts in one invocation are one signal, not three"
        )
    assert detectors.prediction("gather_wood", ["fuel"], "major", 20, "g", 1.0) is None, (
        "a different set of failing facts is a different problem"
    )
    fired = detectors.prediction("gather_wood", list(reversed(facts)), "major", 30, "g", 1.0)
    assert fired is not None
    assert (
        fired.key
        == "gather_wood:building_materials+fuel+wood"
        == prediction_key("gather_wood", facts)
    )


def test_a_stuck_project_is_one_problem_not_one_per_decision() -> None:
    detectors = Detectors()
    assert detectors.project("improve_home", "p1", 1, 1) is not None
    assert detectors.project("improve_home", "p1", 1, 1) is None
    assert detectors.project("improve_home", "p2", 0, 1) is None


# ------------------------------------------------------------- suppression


def requested(
    key: str, at: int, session: str = "s", deliberation_id: str = "d", kind: str = "x"
) -> Any:
    return event(
        "deliberation_requested",
        deliberation_id=deliberation_id,
        trigger_key_full=key,
        trigger_kind=kind,
        experienced_tick=at,
        session_id=session,
    )


def resolved(key: str, at: int, reason: str, deliberation_id: str = "d") -> Any:
    return event(
        "deliberation_discarded",
        deliberation_id=deliberation_id,
        trigger_key_full=key,
        experienced_tick=at,
        reason=reason,
    )


def test_a_key_cools_down_from_its_resolution_and_backs_off_on_unavailability() -> None:
    record = ArbitrationRecord()
    key = "emergency_recurrence:suffocation"
    record.apply(requested(key, 0))
    record.apply(resolved(key, 100, "rejected"))
    assert record.suppression(key, 100 + COOLDOWNS[0] - 1, "s") == "cooldown"
    assert record.suppression(key, 100 + COOLDOWNS[0], "s") is None
    record = ArbitrationRecord()
    seen = []
    for n in range(6):
        record.apply(requested(key, n, deliberation_id=f"d{n}"))
        record.apply(resolved(key, 0, "unavailable", deliberation_id=f"d{n}"))
        seen.append(COOLDOWNS[record.backoff[key]])
    assert seen == [12_000, 24_000, 48_000, 72_000, 72_000, 72_000]
    record.apply(requested(key, 1, deliberation_id="ok"))
    record.apply(resolved(key, 1, "rejected", deliberation_id="ok"))
    assert key not in record.backoff, "an answer resets the backoff"


def test_budgets_per_experienced_hour_and_per_session() -> None:
    record = ArbitrationRecord()
    for n in range(PER_HOUR):
        record.apply(requested(f"k{n}", n * 10, deliberation_id=f"d{n}"))
        record.apply(resolved(f"k{n}", n * 10, "rejected", deliberation_id=f"d{n}"))
    assert record.suppression("other", 100, "s") == "hourly_budget"
    assert record.suppression("other", EXPERIENCED_HOUR + 100, "s") is None
    record = ArbitrationRecord()
    for n in range(PER_SESSION):
        record.apply(requested(f"k{n}", n * EXPERIENCED_HOUR, deliberation_id=f"d{n}"))
        record.apply(resolved(f"k{n}", n * EXPERIENCED_HOUR, "rejected", deliberation_id=f"d{n}"))
    assert record.suppression("other", PER_SESSION * EXPERIENCED_HOUR, "s") == "session_budget"
    assert record.suppression("other", PER_SESSION * EXPERIENCED_HOUR, "s2") is None


def test_cooldowns_and_budgets_are_rebuilt_and_a_crashed_request_never_blocks() -> None:
    key = "repeated_failure:SECURE_FOOD"
    events = [requested(key, 0, deliberation_id="a"), resolved(key, 50, "unavailable", "a")]
    events.append(requested("other", 60, session="old", deliberation_id="crashed"))
    rebuilt = ArbitrationRecord()
    for item in events:
        rebuilt.apply(item)
    again = ArbitrationRecord()
    again.load_json(json.loads(json.dumps(rebuilt.to_json())))
    for record in (rebuilt, again):
        assert record.suppression(key, 50 + COOLDOWNS[1] - 1, "new") == "cooldown"
        assert record.suppression("third", 70, "new") is None, "unmatched evidence, not a block"


# ------------------------------------------------------------ bands, admission


def test_the_priority_is_the_triggers_never_the_models() -> None:
    assert band(Trigger("emergency_recurrence", "suffocation", {})) == (
        RECOVERY_BAND,
        "recovery_band",
    )
    assert band(Trigger("repeated_failure", "g", {}, source_priority=180.0)) == (
        180.0,
        "inherited_capped",
    )
    assert band(Trigger("no_viable_plan", "g", {}, source_priority=990.0))[0] == RECOVERY_BAND
    assert band(Trigger("project_reconsideration", "p", {}))[0] == 300.0


def proposal(**strategy: Any) -> dict[str, Any]:
    base = {
        "id": "s1",
        "goal_type": "RECOVER_HOME",
        "desired": [{"fact": "at_home", "direction": "achieve"}],
        "premises": ["m1"],
    }
    return {"preferred": "s1", "strategies": [{**base, **strategy}]}


@pytest.mark.parametrize(
    ("body", "why"),
    [
        ({"preferred": "s9", "strategies": []}, "no_preferred_strategy"),
        (proposal(goal_type="CONQUER"), "unknown_goal"),
        (proposal(goal_type="INVESTIGATE"), "unknown_goal"),
        (proposal(desired=[]), "no_desired_state"),
        (
            proposal(desired=[{"fact": "creeper_gone", "direction": "achieve"}]),
            "unrepresentable_goal",
        ),
        (proposal(premises=["s1"]), "does_not_cite_trigger"),
    ],
)
def test_the_goal_admission_gate(body: dict[str, Any], why: str) -> None:
    admitted, reason = admit_goal(
        body, goal_types=GOAL_TYPES, state={"at_home": 0.0}, trigger_refs=frozenset({"m1"})
    )
    assert admitted is None and reason == why


def test_an_admissible_goal_becomes_a_completion_condition() -> None:
    admitted, reason = admit_goal(
        proposal(), goal_types=GOAL_TYPES, state={"at_home": 0.0}, trigger_refs=frozenset({"m1"})
    )
    assert reason is None
    assert admitted == {"goal_type": "RECOVER_HOME", "conditions": [("at_home", ">=", 1.0)]}


# ------------------------------------------------------------ the arbiter


@dataclass
class Goals:
    entries: dict[str, Any] = field(default_factory=dict)


@dataclass
class Projects:
    def projects(self) -> tuple[()]:
        return ()


def context(trigger: Trigger) -> tuple[Any, frozenset[str]]:
    built = build_context(
        reason=trigger.kind,
        self_knowledge=None,
        world_available=True,
        observation=None,
        place=None,
        working_memory=[{"kind": "endangered", "details": {"trigger": "suffocation"}}],
        beliefs=[],
        hypotheses=[],
        goals=[],
        projects=[],
        recent=[],
        capabilities=[Capability("return_home", "Go home.", ("at_home",))],
        vocabulary={
            "goal_types": GOAL_TYPES,
            "project_kinds": (),
            "facts": ("at_home", "rested"),
            "directions": ("achieve",),
        },
    )
    return built, frozenset({"m1"})


ANSWER = {
    "assessment": {"summary": "Air keeps running out.", "premises": ["m1"]},
    "strategies": [
        {
            "id": "s1",
            "goal_type": "RECOVER_HOME",
            "project_kind": None,
            "desired": [{"fact": "at_home", "direction": "achieve"}],
            "expected": [{"fact": "at_home", "direction": "achieve", "support": ["c1"]}],
            "capability_refs": ["c1"],
            "premises": ["m1"],
        }
    ],
    "preferred": "s1",
}


class Step:
    """Drives an arbiter one decision at a time, recording what it records."""

    def __init__(self, mode: str, answers: list[Any], runner: Any = immediate_runner) -> None:
        self.arbiter = Arbiter(record=ArbitrationRecord(), runner=runner)
        self.mode = mode
        self.model = ScriptedModel(answers)
        self.records: list[tuple[str, dict[str, Any]]] = []
        self.state = {"at_home": 0.0, "home_known": 1.0}
        self.goals = Goals()

    def record(self, kind: str, payload: dict[str, Any]) -> None:
        self.records.append((kind, payload))
        self.arbiter.record.apply(event(kind, **payload))

    def __call__(self, now: int, *, life: int = 0, session: str = "s") -> None:
        self.arbiter.step(
            mode=self.mode,
            deliberator=Deliberator(mode=self.mode, model=self.model, record=self.record),
            record=self.record,
            state=self.state,
            now=now,
            session=session,
            life_epoch=life,
            alive=True,
            world_available=True,
            goals=self.goals,
            projects=Projects(),
            registry=skill_registry(),
            goal_types=GOAL_TYPES,
            context_for=context,
            decision=now,
            failures=lambda goal_id: 0,
        )

    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.records]


REST = {
    **ANSWER,
    "strategies": [
        {
            **ANSWER["strategies"][0],
            "desired": [{"fact": "rested", "direction": "achieve"}],
            "expected": [],
            "capability_refs": [],
        }
    ],
}


def test_a_goal_of_action_facts_is_satisfied_by_its_routine_and_handed_back() -> None:
    step = Step("active", [REST])
    step.state.update(safe=1.0, rested=0.0)
    emergency(step)
    step(10)
    step(20)
    assert step.kinds()[-1] == "deliberation_adopted"
    adopted = step.arbiter.adopted
    assert adopted is not None
    step(30)
    assert step.arbiter.adopted is adopted, "an action fact is never observed in state"
    rested = frozenset({"rested"})
    step.arbiter.routine_finished("some_other_goal", "SUCCESS", rested, 31)
    step.arbiter.routine_finished(adopted.goal_id, "FAILED", rested, 32)
    step.arbiter.routine_finished(adopted.goal_id, "SUCCESS", frozenset({"looked"}), 33)
    step(40)
    assert step.arbiter.adopted is adopted, (
        "only its own routine succeeding, and declaring the fact, satisfies it"
    )
    step.arbiter.routine_finished(adopted.goal_id, "SUCCESS", rested, 41)
    step(50)
    assert step.arbiter.adopted is None
    assert step.records[-1][1]["why"] == "satisfied"
    assert step.arbiter.ended == [(adopted, "satisfied")], (
        "the loop closes it in its goal stack, or nobody would"
    )


def emergency(step: Step) -> None:
    step.arbiter.raise_trigger(Trigger("emergency_recurrence", "suffocation", {"recurrences": 3}))


def test_an_emergency_is_never_interrupted_to_think() -> None:
    step = Step("active", [ANSWER])
    emergency(step)
    step.arbiter.emergency_now = True
    step(10)
    assert step.kinds() == [], "deferred while the emergency is being handled"
    step(20)
    assert step.kinds() == ["deliberation_requested"]


def test_an_answer_is_used_at_a_later_decision_and_adopted_at_the_recovery_band() -> None:
    step = Step("active", [ANSWER])
    emergency(step)
    step(10)
    assert step.arbiter.adopted is None, "System 1 answered this decision"
    step(20)
    assert step.kinds()[-1] == "deliberation_adopted"
    adopted = step.records[-1][1]
    assert adopted["priority"] == RECOVERY_BAND and adopted["priority_source"] == "recovery_band"
    goal = step.arbiter.adopted_goal(20)
    assert goal.source == "deliberation" and goal.priority == RECOVERY_BAND


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda s, now: s(now, life=1), "died"),
        (lambda s, now: s(now, session="other"), "stale"),
        (lambda s, now: s(now + STALE_AFTER + 1), "stale"),
    ],
)
def test_a_stale_answer_is_discarded(change: Any, reason: str) -> None:
    step = Step("active", [ANSWER])
    emergency(step)
    step(10)
    change(step, 20)
    assert step.kinds()[-1] == "deliberation_discarded"
    assert step.records[-1][1]["reason"] == reason


def test_a_lost_world_since_the_request_discards_the_answer() -> None:
    step = Step("active", [ANSWER])
    emergency(step)
    step(10)
    step.arbiter.world_epoch += 1
    step(20)
    assert step.records[-1][1]["reason"] == "world_lost"


def test_an_answer_already_satisfied_is_superseded() -> None:
    step = Step("active", [ANSWER])
    emergency(step)
    step(10)
    step.state["at_home"] = 1.0
    step(20)
    assert step.records[-1][1]["reason"] == "superseded"


def test_record_only_never_adopts_only_shadows() -> None:
    step = Step("record_only", [ANSWER])
    emergency(step)
    step(10)
    step(20)
    assert "deliberation_adopted" not in step.kinds()
    kind, payload = step.records[-1]
    assert kind == "deliberation_shadow_disposition" and payload["disposition"] == "would_adopt"
    assert step.arbiter.adopted is None and step.arbiter.adopted_goal(20) is None


def test_an_adopted_goal_expires_and_ends_with_its_reason() -> None:
    step = Step("active", [ANSWER])
    emergency(step)
    step(10)
    step(20)
    step(20 + 2_400 + 1)
    kind, payload = step.records[-1]
    assert kind == "deliberation_goal_ended" and payload["why"] == "expired"
    assert step.arbiter.adopted is None


def test_the_provider_call_runs_off_the_main_thread_and_touches_nothing_there() -> None:
    called_on: list[str] = []

    class Slow:
        provider = "slow"
        model = "slow-v0"

        def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> Any:
            called_on.append(threading.current_thread().name)
            return ScriptedModel([ANSWER]).deliberate(instruction, context, timeout_s=timeout_s)

    step = Step("active", [], runner=thread_runner)
    step.model = Slow()  # type: ignore[assignment]
    emergency(step)
    step(10)
    assert step.kinds() == ["deliberation_requested"], "only the request, on the main thread"
    step.arbiter.in_flight.handle._finished.wait(5)  # type: ignore[union-attr]
    step(20)
    assert called_on and called_on[0] != threading.main_thread().name
    assert step.kinds()[-2:] == ["deliberation_completed", "deliberation_adopted"]


def test_one_hourly_slot_stays_free_for_a_recurring_emergency() -> None:
    record = ArbitrationRecord()
    for n in range(3):
        record.apply(requested(f"k{n}", n, deliberation_id=f"d{n}", kind="repeated_failure"))
        record.apply(resolved(f"k{n}", n, "rejected", deliberation_id=f"d{n}"))
    assert record.suppression("k9", 10, "s", "no_viable_plan") == "hourly_budget_reserved"
    assert record.suppression("e", 10, "s", "emergency_recurrence") is None
    record.apply(requested("e", 10, deliberation_id="de", kind="emergency_recurrence"))
    record.apply(resolved("e", 10, "rejected", deliberation_id="de"))
    assert record.suppression("e2", 20, "s", "emergency_recurrence") == "hourly_budget"


def test_a_detector_that_fires_needs_three_new_signals_to_fire_again() -> None:
    detectors = Detectors()
    for at in (0, 10, 20):
        fired = detectors.emergency("suffocation", at)
    assert fired is not None
    assert detectors.emergency("suffocation", 30) is None, "no storm of repeated firings"
    assert detectors.emergency("suffocation", 40) is None
    assert detectors.emergency("suffocation", 50) is not None


# ----------------------------------------------- source retry (C4.1)


def adopted_for(trigger_kind: str = "repeated_failure", **changes: Any) -> Any:
    from person_cognition.deliberation.arbiter import Adopted

    fields: dict[str, Any] = {
        "deliberation_id": "dlb_1",
        "goal_id": "goal_deliberation_dlb_1",
        "goal_type": "MAINTAIN_RESERVES",
        "conditions": (("rested", ">=", 1.0),),
        "priority": 300.0,
        "adopted_at": 10,
        "trigger_kind": trigger_kind,
        "source_goal_id": "goal_establish_tools",
        "source_goal_type": "ESTABLISH_TOOLS",
        "source_created_at": 0,
        "source_block_reason": "repeated_routine_failure",
    }
    fields.update(changes)
    return Adopted(**fields)


def source(**changes: Any) -> Goals:
    goal = SimpleNamespace(
        created_at_tick=0, status="BLOCKED", suspension_reason="repeated_routine_failure"
    )
    for key, value in changes.items():
        setattr(goal, key, value)
    return Goals(entries={"goal_establish_tools": goal})


def test_a_satisfied_remedy_may_lift_only_the_block_it_was_for() -> None:
    retry = Arbiter.source_retry
    assert retry(adopted_for(), source()) == "repeated_routine_failure"
    assert (
        retry(
            adopted_for("no_viable_plan", source_block_reason="no_feasible_plan"),
            source(suspension_reason="no_feasible_plan"),
        )
        == "no_feasible_plan"
    )
    for refused in (
        retry(adopted_for("emergency_recurrence"), source()),
        retry(adopted_for("repeated_prediction_error"), source()),
        retry(adopted_for(source_block_reason=None), source()),
        retry(adopted_for(), Goals()),
        retry(adopted_for(), source(status="QUEUED", suspension_reason=None)),
        retry(adopted_for(), source(suspension_reason="no_candidate_routine")),
        retry(adopted_for(), source(created_at_tick=500)),
    ):
        assert refused is None
