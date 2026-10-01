"""Habit learning, C4: shadow evidence only (ADR 0022). Scripted only."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from person_cognition.deliberation.habits import (
    PROMOTION_STREAK,
    STABILIZATION_WINDOW,
    Episode,
    HabitBook,
    HabitTracker,
    context_signature,
    template_id,
)
from test_metareasoning import ANSWER, Step, emergency, event

OBSERVATION = {
    "vitals": {"health": 10.0, "food": 18.0, "breath": 10},
    "environment": {"dayPhase": "day", "weather": "clear"},
    "nearby": {
        "hostiles": [
            {"name": "zombie", "rangeBand": "near", "distance": 6.0},
            {"name": "skeleton", "rangeBand": "far", "distance": 20.0},
            {"name": "zombie", "rangeBand": "far", "distance": 22.0},
        ]
    },
    "inventory": {"categories": {"wood": 3, "food": 0, "tools": 1}},
}


# ---------------------------------------------------------------- identity


def test_the_signature_is_coarse_canonical_and_holds_nothing_privileged() -> None:
    signature = context_signature(
        observation=OBSERVATION,
        place={"place_id": "place_3", "confidence": 0.9},
        desired_facts=["wood", "at_home"],
        source_goal_type="ESTABLISH_TOOLS",
    )
    assert signature["schema"] == "context_signature_v1"
    assert signature["health"] == "low" and signature["food"] == "full"
    assert signature["place"] == {"ref": "place_3", "confidence": "high"}
    assert signature["threats"] == [
        {"kind": "skeleton", "count": "one", "nearest": "far"},
        {"kind": "zombie", "count": "few", "nearest": "near"},
    ]
    assert signature["inventory"] == {"wood": "some"}, "only categories the desired facts map to"
    text = str(signature)
    for privileged in ("distance", "6.0", "'x'", "position"):
        assert privileged not in text


def test_an_unsure_place_is_unknown() -> None:
    signature = context_signature(
        observation=OBSERVATION,
        place={"place_id": "place_3", "confidence": 0.3},
        desired_facts=[],
        source_goal_type=None,
    )
    assert signature["place"] == "unknown" and signature["source_goal_type"] == "none"


def test_a_templates_identity_is_its_meaning_not_its_history() -> None:
    signature = {"schema": "context_signature_v1", "health": "low"}
    base = {
        "trigger_kind": "emergency_recurrence",
        "semantic_key": "suffocation",
        "signature": signature,
        "goal_type": "RECOVER_HOME",
        "desired": [["at_home", "achieve"]],
    }
    same = template_id(**base)  # type: ignore[arg-type]
    assert same == template_id(**base)  # type: ignore[arg-type]
    assert same != template_id(**{**base, "goal_type": "SECURE_FOOD"})  # type: ignore[arg-type]
    assert same != template_id(**{**base, "signature": {**signature, "health": "healthy"}})  # type: ignore[arg-type]
    assert same != template_id(**{**base, "desired": [["at_home", "avoid"]]})  # type: ignore[arg-type]


# ----------------------------------------------------------------- episodes


class Journal:
    """Records events into the books as the loop's journal would."""

    def __init__(self) -> None:
        self.shadow = HabitBook("shadow")
        self.active = HabitBook("active")
        self.events: list[Any] = []

    def __call__(self, kind: str, payload: dict[str, Any]) -> None:
        recorded = event(kind, **payload)
        self.events.append(recorded)
        self.shadow.apply(recorded)
        self.active.apply(recorded)

    def kinds(self) -> list[str]:
        return [e.type for e in self.events]

    def verdicts(self) -> list[tuple[str, str]]:
        return [
            (e.payload["verdict"], e.payload["reason"])
            for e in self.events
            if e.type == "habit_evidence_shadow"
        ]


def episode(
    n: int, template: str = "hab_a", key: str = "emergency_recurrence:suffocation"
) -> Episode:
    return Episode(
        deliberation_id=f"dlb_{n}",
        template={
            "template_id": template,
            "trigger_kind": key.split(":")[0],
            "semantic_key": key.split(":")[1],
            "signature_sha": "sig",
            "goal_type": "RECOVER_HOME",
            "desired": [["at_home", "achieve"]],
        },
        semantic_key_full=key,
        life_epoch=0,
        world_epoch=0,
        session="s",
    )


def stable(
    tracker: HabitTracker, journal: Journal, n: int, at: int, template: str = "hab_a"
) -> None:
    tracker.open(episode(n, template))
    tracker.goal_ended(f"dlb_{n}", "satisfied", at, journal)
    tracker.step(
        now=at + STABILIZATION_WINDOW, life_epoch=0, world_epoch=0, session="s", record=journal
    )


def test_a_satisfied_goal_succeeds_only_after_a_quiet_window() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(episode(1))
    tracker.goal_ended("dlb_1", "satisfied", 100, journal)
    tracker.step(
        now=100 + STABILIZATION_WINDOW - 1, life_epoch=0, world_epoch=0, session="s", record=journal
    )
    assert journal.verdicts() == []
    tracker.step(
        now=100 + STABILIZATION_WINDOW, life_epoch=0, world_epoch=0, session="s", record=journal
    )
    assert journal.verdicts() == [("success", "stable")]
    assert journal.kinds()[0] == "habit_candidate_shadow"


def test_one_new_raw_signal_inside_the_window_means_it_did_not_resolve() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(episode(1))
    tracker.raw_signal("emergency_recurrence:suffocation", 50, journal)
    assert journal.verdicts() == [], (
        "a recurrence while still pursuing the goal is not yet a verdict"
    )
    tracker.goal_ended("dlb_1", "satisfied", 100, journal)
    tracker.raw_signal("repeated_failure:SECURE_FOOD", 150, journal)
    assert journal.verdicts() == [], "a different problem says nothing"
    tracker.raw_signal("emergency_recurrence:suffocation", 200, journal)
    assert journal.verdicts() == [("failure", "recurred")]


@pytest.mark.parametrize(
    ("change", "verdict"),
    [
        ({"life_epoch": 1}, ("failure", "died")),
        ({"world_epoch": 1}, ("inconclusive", "world_or_session")),
        ({"session": "t"}, ("inconclusive", "world_or_session")),
    ],
)
def test_death_fails_while_world_loss_or_a_new_session_is_inconclusive(
    change: dict[str, Any], verdict: tuple[str, str]
) -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(episode(1))
    tracker.goal_ended("dlb_1", "satisfied", 100, journal)
    state = {"life_epoch": 0, "world_epoch": 0, "session": "s", **change}
    tracker.step(now=200, record=journal, **state)
    assert journal.verdicts() == [verdict]


@pytest.mark.parametrize(
    ("why", "verdict"),
    [
        ("failed", ("failure", "goal_failed")),
        ("expired", ("failure", "goal_expired")),
        ("session_ended", ("inconclusive", "goal_session_ended")),
    ],
)
def test_how_an_adopted_goal_ends(why: str, verdict: tuple[str, str]) -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(episode(1))
    tracker.goal_ended("dlb_1", why, 100, journal)
    assert journal.verdicts() == [verdict]


# ---------------------------------------------------------------- promotion


def test_three_consecutive_independent_successes_promote_in_the_shadow_only() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    for n in range(PROMOTION_STREAK - 1):
        stable(tracker, journal, n, n * 10_000)
    assert "habit_promotion_shadow" not in journal.kinds(), "two successes are not a habit"
    stable(tracker, journal, 9, 90_000)
    assert journal.kinds()[-1] == "habit_promotion_shadow"
    assert journal.shadow.templates["hab_a"].state == "promoted"
    assert journal.active.templates == {}, "the active book never sees shadow evidence"


def test_a_failure_resets_the_streak_but_keeps_the_history() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    stable(tracker, journal, 1, 0)
    stable(tracker, journal, 2, 10_000)
    tracker.open(episode(3))
    tracker.goal_ended("dlb_3", "failed", 20_000, journal)
    stable(tracker, journal, 4, 30_000)
    template = journal.shadow.templates["hab_a"]
    assert template.streak == 1 and template.successes == 3 and template.failures == 1
    assert "habit_promotion_shadow" not in journal.kinds()


def test_alternating_solutions_promote_nothing() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    stable(tracker, journal, 1, 0, "hab_a")
    stable(tracker, journal, 2, 10_000, "hab_b")
    stable(tracker, journal, 3, 20_000, "hab_a")
    assert "habit_promotion_shadow" not in journal.kinds()


def test_a_second_template_for_a_promoted_scope_is_a_conflict_not_a_replacement() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    for n in range(3):
        stable(tracker, journal, n, n * 10_000, "hab_a")
    for n in range(3, 6):
        stable(tracker, journal, n, n * 10_000, "hab_b")
    assert journal.kinds()[-1] == "habit_conflict_shadow"
    assert journal.shadow.templates["hab_b"].state == "candidate"
    assert journal.shadow.templates["hab_a"].state == "promoted"


# ---------------------------------------------------------- streams, restart


def test_each_book_reads_only_its_own_stream_and_rebuilds_identically() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    for n in range(3):
        stable(tracker, journal, n, n * 10_000)
    rebuilt = HabitBook("shadow")
    active = HabitBook("active")
    for recorded in journal.events:
        rebuilt.apply(recorded)
        active.apply(recorded)
    assert rebuilt.to_json() == journal.shadow.to_json()
    assert active.to_json() == {"templates": []}
    snapshot = HabitBook("shadow")
    snapshot.load_json(rebuilt.to_json())
    assert snapshot.to_json() == rebuilt.to_json()


# --------------------------------------------------------------- isolation


def test_shadow_habit_learning_changes_nothing_the_arbiter_does() -> None:
    def run(track: bool) -> list[tuple[str, dict[str, Any]]]:
        step = Step("active", [ANSWER])
        if track:
            book = HabitBook("shadow")
            step.arbiter.tracker = HabitTracker(book)
            step.arbiter.basis_for = lambda trigger: {
                "observation": None,
                "place": None,
                "source_goal_type": None,
            }
            journalled = step.record

            def record(kind: str, payload: dict[str, Any]) -> None:
                journalled(kind, payload)
                book.apply(event(kind, **payload))  # as the loop's reducers do

            step.record = record  # type: ignore[method-assign]
        emergency(step)
        step(10)
        step(20)
        step.state["at_home"] = 1.0
        step(30)
        step(30 + STABILIZATION_WINDOW)
        return step.records

    def scrub(records: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
        random = {"deliberation_id", "goal_id", "latency_ms"}
        return [
            (kind, {key: value for key, value in payload.items() if key not in random})
            for kind, payload in records
            if not kind.startswith("habit_")
        ]

    plain = run(track=False)
    tracked = run(track=True)
    assert scrub(tracked) == scrub(plain), "the same requests, answers, adoptions and endings"
    assert [k for k, _ in tracked if k.startswith("habit_")] == [
        "habit_candidate_shadow",
        "habit_evidence_shadow",
    ]


# ------------------------------------------------- positive resolution (C4.1)


def failure_episode(n: int) -> Episode:
    base = episode(n, key="repeated_failure:ESTABLISH_TOOLS")
    base.source_goal_id = "goal_establish_tools"
    return base


def test_silence_after_a_blocked_goal_is_not_resolution() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(failure_episode(1))
    tracker.source_progress("goal_establish_tools", 50)  # before the remedy: not evidence
    tracker.goal_ended("dlb_1", "satisfied", 100, journal)
    tracker.source_progress("goal_other", 150)
    tracker.step(
        now=100 + STABILIZATION_WINDOW, life_epoch=0, world_epoch=0, session="s", record=journal
    )
    assert journal.verdicts() == [("inconclusive", "no_retry")]
    assert journal.shadow.templates["hab_a"].streak == 0


def test_a_retried_source_that_succeeds_and_stays_quiet_is_a_success() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(failure_episode(1))
    tracker.goal_ended("dlb_1", "satisfied", 100, journal)
    tracker.source_progress("goal_establish_tools", 200)
    tracker.step(
        now=100 + STABILIZATION_WINDOW, life_epoch=0, world_epoch=0, session="s", record=journal
    )
    assert journal.verdicts() == [("success", "stable")]


def test_a_retry_that_fails_again_is_the_recurrence() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    tracker.open(failure_episode(1))
    tracker.goal_ended("dlb_1", "satisfied", 100, journal)
    tracker.raw_signal("repeated_failure:ESTABLISH_TOOLS", 200, journal)
    assert journal.verdicts() == [("failure", "recurred")]


def test_other_trigger_classes_need_no_retry() -> None:
    journal = Journal()
    tracker = HabitTracker(journal.shadow)
    stable(tracker, journal, 1, 0)
    assert journal.verdicts() == [("success", "stable")]


@pytest.mark.parametrize(("retried", "verdict"), [(False, "no_retry"), (True, "stable")])
def test_through_the_arbiter_a_remedy_without_a_retry_is_never_a_success(
    retried: bool, verdict: str
) -> None:
    from person_cognition.deliberation.metareasoning import Trigger

    step = Step("active", [ANSWER])
    book = HabitBook("shadow")
    step.arbiter.tracker = HabitTracker(book)
    step.arbiter.basis_for = lambda trigger: {
        "observation": None,
        "place": None,
        "source_goal_type": None,
    }
    journalled = step.record

    def record(kind: str, payload: dict[str, Any]) -> None:
        journalled(kind, payload)
        book.apply(event(kind, **payload))

    step.record = record  # type: ignore[method-assign]
    step.goals.entries["goal_tools"] = SimpleNamespace(
        goal_id="goal_tools",
        goal_type="ESTABLISH_TOOLS",
        status="BLOCKED",
        suspension_reason="repeated_routine_failure",
        created_at_tick=0,
        priority=300.0,
    )
    step.arbiter.raise_trigger(
        Trigger("repeated_failure", "ESTABLISH_TOOLS", {}, source_goal_id="goal_tools")
    )
    step(10)
    step(20)
    step.state["at_home"] = 1.0
    step(30)
    if retried:
        step.arbiter.routine_finished("goal_tools", "SUCCESS", frozenset(), 40)
    step(30 + STABILIZATION_WINDOW)
    assert [
        (payload["verdict"], payload["reason"])
        for kind, payload in step.records
        if kind == "habit_evidence_shadow"
    ] == [("success" if retried else "inconclusive", verdict)]
    assert "habit_promotion_shadow" not in [kind for kind, _ in step.records]
