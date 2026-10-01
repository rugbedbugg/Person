"""Active habits, C5: invocation, demotion and breakdown (ADR 0022).

Through the arbiter, with scripted models: a promoted habit answers its own
problem without a model call, a contradicted or failed habit is demoted at
once, and its problem goes back to System 2.
"""

from __future__ import annotations

from typing import Any

from person_cognition.deliberation.habits import (
    PROMOTION_STREAK,
    STABILIZATION_WINDOW,
    HabitBook,
    HabitTracker,
    context_signature,
    signature_sha,
    template_id,
)
from person_cognition.deliberation.metareasoning import (
    COOLDOWNS,
    PER_HOUR_ORDINARY,
    RECOVERY_BAND,
    Trigger,
)
from test_metareasoning import ANSWER, Step, emergency, event

BASIS: dict[str, Any] = {"observation": None, "place": None, "source_goal_type": None}
DESIRED = [["at_home", "achieve"]]


def promoted_template(
    book: HabitBook,
    *,
    desired: list[list[str]] = DESIRED,
    goal_type: str = "RECOVER_HOME",
) -> str:
    """Journal a habit's formation into the active book, as three lived
    deliberated successes would have."""
    signature = context_signature(**BASIS, desired_facts=[f for f, _ in desired])
    tid = template_id(
        trigger_kind="emergency_recurrence",
        semantic_key="suffocation",
        signature=signature,
        goal_type=goal_type,
        desired=desired,
    )
    body = {
        "template_id": tid,
        "trigger_kind": "emergency_recurrence",
        "semantic_key": "suffocation",
        "signature_sha": signature_sha(signature),
        "goal_type": goal_type,
        "desired": desired,
    }
    book.apply(event("habit_candidate_formed", template=body, experienced_tick=0))
    for n in range(PROMOTION_STREAK):
        book.apply(
            event(
                "habit_evidence",
                template_id=tid,
                deliberation_id=f"dlb_{n}",
                verdict="success",
                reason="stable",
                experienced_tick=n,
            )
        )
    book.apply(event("habit_promoted", template_id=tid, founding=[], experienced_tick=3))
    return tid


class Active(Step):
    """A Step whose arbiter runs habits `active`, books fed by its records."""

    def __init__(self, answers: list[Any], *, basis: dict[str, Any] | None = None) -> None:
        super().__init__("active", answers)
        self.book = HabitBook("active")
        self.shadow = HabitBook("shadow")
        self.arbiter.habits_mode = "active"
        self.arbiter.active_book = self.book
        self.arbiter.tracker = HabitTracker(self.book)
        self.arbiter.tracker.on_breakdown = self.arbiter.habit_broke
        self.arbiter.basis_for = lambda trigger: dict(basis or BASIS)
        self.arbiter.new_invocation_id = lambda: "hinv_1"

    def record(self, kind: str, payload: dict[str, Any]) -> None:
        super().record(kind, payload)
        self.book.apply(event(kind, **payload))
        self.shadow.apply(event(kind, **payload))


def test_a_promoted_habit_answers_its_problem_without_a_model() -> None:
    step = Active([ANSWER])
    tid = promoted_template(step.book)
    emergency(step)
    step(10)
    assert step.kinds() == ["habit_invoked"], "no request, no answer, no model call"
    invoked = step.records[0][1]
    assert invoked["template_id"] == tid and invoked["priority"] == RECOVERY_BAND
    goal = step.arbiter.adopted_goal(10)
    assert goal.source == "habit" and goal.planning_profile == "recovery"
    assert step.model._answers == [ANSWER], "the model was never asked"  # type: ignore[attr-defined]


def test_a_habit_runs_whatever_the_providers_budgets_say() -> None:
    step = Active([])
    promoted_template(step.book)
    for n in range(4):  # spend the whole hour's budget on other problems
        step.record(
            "deliberation_requested",
            {
                "deliberation_id": f"dlb_{n}",
                "trigger_key_full": f"repeated_failure:G{n}",
                "trigger_kind": "repeated_failure",
                "session_id": "s",
                "experienced_tick": 1,
            },
        )
    emergency(step)
    step(10)
    assert step.kinds()[-1] == "habit_invoked"


def test_another_context_is_not_applicable_and_costs_nothing() -> None:
    step = Active([ANSWER], basis={**BASIS, "source_goal_type": "SECURE_FOOD"})
    tid = promoted_template(step.book)
    emergency(step)
    step(10)
    assert step.kinds() == ["habit_not_applicable", "deliberation_requested"]
    assert step.records[0][1]["template_ids"] == [tid]
    assert step.book.templates[tid].state == "promoted", "no penalty"


def test_a_goal_already_satisfied_while_the_problem_recurs_demotes_and_breaks_down() -> None:
    step = Active([ANSWER])
    tid = promoted_template(step.book)
    step.state["at_home"] = 1.0
    emergency(step)
    step(10)
    assert step.kinds() == ["habit_demoted", "deliberation_requested"], "System 2 at once"
    assert step.records[0][1]["reason"] == "satisfied_at_invocation"
    assert step.book.templates[tid].state == "demoted"
    requested = step.records[-1]
    assert requested[0] == "deliberation_requested"
    assert requested[1]["trigger_key_full"] == f"habit_breakdown:{tid}"
    assert requested[1]["budget_kind"] == "emergency_recurrence"


def test_an_infeasible_habit_is_demoted_and_never_invoked() -> None:
    step = Active([ANSWER])
    promoted_template(step.book)
    step.state["home_known"] = 0.0  # return_home has no plan
    emergency(step)
    step(10)
    assert step.kinds() == ["habit_demoted", "deliberation_requested"]
    assert step.records[0][1]["reason"] == "infeasible_at_invocation"
    assert "habit_invoked" not in step.kinds()


def invoked_and_satisfied(step: Active) -> None:
    emergency(step)
    step(10)
    step.state["at_home"] = 1.0
    step(20)
    assert [k for k in step.kinds() if k.startswith("habit_")][-1] == "habit_goal_ended"


def test_a_habits_own_success_never_counts_toward_promotion() -> None:
    step = Active([])
    tid = promoted_template(step.book)
    invoked_and_satisfied(step)
    step(20 + STABILIZATION_WINDOW)
    evidence = step.records[-1][1]
    assert evidence["via"] == "habit" and evidence["verdict"] == "success"
    template = step.book.templates[tid]
    assert template.habit_successes == 1
    assert template.successes == PROMOTION_STREAK and template.streak == PROMOTION_STREAK
    assert template.invocations == 1


def test_a_definite_failure_demotes_at_once_and_bypasses_the_original_cooldown() -> None:
    step = Active([ANSWER])
    tid = promoted_template(step.book)
    # The original problem was deliberated a moment ago: its key is cooling down.
    step.record(
        "deliberation_adopted",
        {
            "deliberation_id": "dlb_old",
            "trigger_key_full": "emergency_recurrence:suffocation",
            "experienced_tick": 5,
        },
    )
    invoked_and_satisfied(step)
    step.arbiter.raw_signal("emergency_recurrence:suffocation", 30, step.record)
    kinds = [k for k in step.kinds() if k.startswith("habit_")]
    assert kinds[-2:] == ["habit_evidence", "habit_demoted"]
    assert step.book.templates[tid].state == "demoted"
    assert step.book.templates[tid].streak == 0
    step(40)
    assert step.kinds()[-1] == "deliberation_requested", "System 2 again, at once"
    assert COOLDOWNS[0] > 40 - 5


def test_a_breakdown_obeys_the_budgets_and_its_own_cooldown() -> None:
    step = Active([None, None])
    tid = promoted_template(step.book)
    step.arbiter.habit_broke(step.book.templates[tid], "recurred", 10)
    for n in range(PER_HOUR_ORDINARY + 1):
        step.record(
            "deliberation_requested",
            {
                "deliberation_id": f"dlb_{n}",
                "trigger_key_full": f"repeated_failure:G{n}",
                "trigger_kind": "repeated_failure",
                "session_id": "s",
                "experienced_tick": 1,
            },
        )
    step(20)
    # An emergency-descended breakdown may use the reserved slot only while
    # the hour has it; here the hour is spent in full.
    assert step.records[-1][0] == "deliberation_suppressed"
    assert step.records[-1][1]["reason"] == "hourly_budget"


def test_after_demotion_only_fresh_deliberated_successes_promote_again() -> None:
    book = HabitBook("active")
    tracker = HabitTracker(book)

    def record(kind: str, payload: dict[str, Any]) -> None:
        book.apply(event(kind, **payload))

    tid = promoted_template(book)
    tracker.demote(book.templates[tid], "recurred", 0, record)
    body = book.templates[tid].body()
    from person_cognition.deliberation.habits import Episode

    def episode(n: int, via: str) -> Episode:
        return Episode(
            deliberation_id=f"x{n}",
            template=body,
            semantic_key_full="emergency_recurrence:suffocation",
            life_epoch=0,
            world_epoch=0,
            session="s",
            via=via,
        )

    at = 100
    for n in range(PROMOTION_STREAK - 1):
        tracker.open(episode(n, "deliberation"))
        tracker.goal_ended(f"x{n}", "satisfied", at, record)
        at += STABILIZATION_WINDOW
        tracker.step(now=at, life_epoch=0, world_epoch=0, session="s", record=record)
    assert book.templates[tid].state == "demoted"
    tracker.open(episode(9, "deliberation"))
    tracker.goal_ended("x9", "satisfied", at, record)
    tracker.step(
        now=at + STABILIZATION_WINDOW, life_epoch=0, world_epoch=0, session="s", record=record
    )
    assert book.templates[tid].state == "promoted"


def test_the_mode_switch_leaves_active_habits_and_behaviour_identical() -> None:
    """G2: the same lived active evidence, after `off` or after `record_only`,
    rebuilds the same active habits and the same next decision."""
    lived = Active([])
    promoted_template(lived.book)
    active_events = [event(kind, **payload) for kind, payload in lived.records]
    formation = HabitBook("active")
    promoted_template(formation)
    shadow_history = [
        event(
            "habit_candidate_shadow",
            template={**next(iter(formation.templates.values())).body()},
            experienced_tick=0,
        ),
        event(
            "habit_promotion_shadow", template_id="hab_shadow_only", founding=[], experienced_tick=1
        ),
    ]

    def run(history: list[Any]) -> tuple[dict[str, Any], list[str]]:
        step = Active([ANSWER])
        promoted_template(step.book)
        for recorded in history:
            step.book.apply(recorded)
        emergency(step)
        step(10)
        return step.book.to_json(), step.kinds()

    after_off = run(active_events)
    after_shadow = run(shadow_history + active_events)
    assert after_off == after_shadow


def test_habit_active_requires_active_deliberation() -> None:
    import pytest
    from person_config import ConfigError, validate_config_document
    from test_deliberation import _example_document

    base = _example_document()
    base["deliberation"] = {"mode": "active", "habits": "active"}
    validate_config_document(base)
    for mode in ("record_only", "off"):
        base["deliberation"] = {"mode": mode, "habits": "active"}
        with pytest.raises(ConfigError):
            validate_config_document(base)
    base["deliberation"] = {"habits": "active"}
    with pytest.raises(ConfigError):
        validate_config_document(base)


def test_a_habit_derived_remedy_keeps_the_recovery_planning_profile() -> None:
    """The provenance bug the relay anticipated: recovery planning must not
    depend on a deliberation having happened. A habit whose response is rest
    is feasible only through the recovery profile, and keeps it."""
    from person_planner import plan_for
    from person_skills import Condition, skill_registry

    step = Active([])
    tid = promoted_template(
        step.book, desired=[["rested", "achieve"]], goal_type="MAINTAIN_RESERVES"
    )
    step.state.update(safe=1.0, rested=0.0)
    rest = [Condition("rested", ">=", 1)]
    assert not [p for p in plan_for(step.state, rest, registry=skill_registry()) if p.steps], (
        "ordinary planning still has no way to rest"
    )
    emergency(step)
    step(10)
    assert step.kinds() == ["habit_invoked"] and step.records[0][1]["template_id"] == tid
    goal = step.arbiter.adopted_goal(10)
    assert goal.source == "habit" and goal.planning_profile == "recovery"


def test_one_remedy_at_a_time_and_a_live_one_is_never_replaced() -> None:
    step = Active([ANSWER, ANSWER])
    promoted_template(step.book)
    emergency(step)
    step.arbiter.raise_trigger(Trigger("repeated_failure", "SECURE_FOOD", {}))
    step(10)
    assert step.kinds() == ["habit_invoked", "deliberation_suppressed"]
    assert step.records[-1][1]["reason"] == "remedy_in_progress"


def test_a_habit_has_first_refusal_whatever_order_problems_arrive_in() -> None:
    step = Active([ANSWER])
    promoted_template(step.book)
    step.arbiter.raise_trigger(Trigger("repeated_failure", "SECURE_FOOD", {}))
    emergency(step)  # pending after another problem
    step(10)
    assert step.kinds()[0] == "habit_invoked"
    assert "deliberation_requested" not in step.kinds()


def test_an_answer_arriving_while_a_remedy_is_live_is_discarded() -> None:
    from person_cognition.deliberation.arbiter import Handle

    step = Active([ANSWER])
    held: list[tuple[Handle, Any]] = []

    def deferred(call: Any) -> Handle:
        handle = Handle()
        held.append((handle, call))
        return handle

    step.arbiter.runner = deferred
    step.arbiter.raise_trigger(Trigger("repeated_failure", "SECURE_FOOD", {}))
    step(10)
    assert step.kinds() == ["deliberation_requested"]
    promoted_template(step.book)
    emergency(step)
    step(20)
    assert step.kinds()[-1] == "habit_invoked", "the habit does not wait for a model"
    handle, call = held[0]
    handle.set(call())
    step(30)
    discarded = [p for k, p in step.records if k == "deliberation_discarded"]
    assert discarded and discarded[0]["reason"] == "superseded"
    assert step.arbiter.adopted is not None and step.arbiter.adopted.via == "habit"


def test_habit_metrics_count_use_and_failure_together() -> None:
    from person_cognition.deliberation.metrics import habit_metrics

    step = Active([ANSWER])
    tid = promoted_template(step.book)
    invoked_and_satisfied(step)
    step.arbiter.raw_signal("emergency_recurrence:suffocation", 30, step.record)
    step(40)
    metrics = habit_metrics(event(kind, **payload) for kind, payload in step.records)
    assert metrics["invocations"] == metrics["deliberations_avoided"] == 1
    assert metrics["habit_failures"] == 1 and metrics["demotions"] == 1
    assert metrics["breakdowns"] == 1
    assert step.book.templates[tid].demotions == 1
