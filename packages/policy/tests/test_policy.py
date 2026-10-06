"""Evidence-guided selection, attribution, and the safe exploration envelope."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from person_epistemics import ExperienceKey
from person_persistence import new_event
from person_policy import (
    DeterministicPolicyProvider,
    EnvelopeVerdict,
    EvidencePolicyProvider,
    NoCandidatesError,
    OutcomeCounts,
    RoutineCandidate,
    RoutineStatistics,
)

REPOSITORY = Path(__file__).resolve().parents[3]

#: The policy is environment-neutral: an experience stream of no particular
#: environment, and the envelope verdicts an environment would hand it.
FIXTURE = ExperienceKey("test_env", "test_body")
LIVE = ExperienceKey("test_env", "real_body", "hard")
OPEN = EnvelopeVerdict(open=True, reasons=())


def candidate(
    name: str, risk: float = 0.2, cost: float = 3.0, ticks: int = 2400
) -> RoutineCandidate:
    return RoutineCandidate(
        routine_id=f"r_{name}",
        name=name,
        steps=("gather_plant_food", "eat_to_target"),
        step_labels=("gather_plant_food", "eat_to_target"),
        risk=risk,
        cost=cost,
        ticks=ticks,
    )


def outcome_event(
    routine_id: str, status: str, *, health_cost: float = 0.0, context: str = "c"
) -> Any:
    return new_event(
        person_id="ada",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep",
        decision_id=None,
        tick=1,
        policy_revision=0,
        experience=FIXTURE,
        event_type="routine_outcome",
        payload={
            "routine_id": routine_id,
            "context_id": context,
            "status": status,
            "health_cost": health_cost,
            "elapsed_ticks": 100,
        },
        previous_event_id=None,
    )


def skill_event(requested: str, executed: str, status: str) -> Any:
    return new_event(
        person_id="ada",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep",
        decision_id=None,
        tick=1,
        policy_revision=0,
        experience=FIXTURE,
        event_type="skill_completed" if status == "SUCCESS" else "skill_interrupted",
        payload={
            "requested_skill": requested,
            "executed_skill": executed,
            "status": status,
            "context_id": "c",
            "health_cost": 0,
            "elapsed_ticks": 10,
        },
        previous_event_id=None,
    )


def test_uncertainty_is_reflected_in_the_estimate() -> None:
    thin = OutcomeCounts(attempts=1, successes=1)
    thick = OutcomeCounts(attempts=100, successes=100)
    assert thin.posterior_mean < thick.posterior_mean
    assert thin.posterior_lower() < thick.posterior_lower()
    assert thin.posterior_lower() < 0.6


def test_learning_credits_the_executed_skill_not_the_requested_one() -> None:
    statistics = RoutineStatistics()
    statistics.apply(skill_event("gather_wood", "flee", "SUCCESS"))

    flee = statistics.skill(FIXTURE.key, "c", "flee")
    gather = statistics.skill(FIXTURE.key, "c", "gather_wood")
    assert flee.attempts == 1
    assert flee.successes == 1
    assert gather.attempts == 0, "the requested skill never ran and must not be credited"
    assert gather.successes == 0
    assert gather.preemptions == 1


def test_statistics_never_merge_across_experience_streams() -> None:
    statistics = RoutineStatistics()
    fixture_event = outcome_event("r_a", "SUCCESS")
    live = new_event(
        person_id="ada",
        world_id="w",
        session_id="00000000-0000-4000-8000-000000000001",
        episode_id="ep",
        decision_id=None,
        tick=1,
        policy_revision=0,
        experience=LIVE,
        event_type="routine_outcome",
        payload={"routine_id": "r_a", "context_id": "c", "status": "FAILED"},
        previous_event_id=None,
    )
    statistics.apply(fixture_event)
    statistics.apply(live)
    assert statistics.routine(FIXTURE.key, "c", "r_a").successes == 1
    assert statistics.routine(LIVE.key, "c", "r_a").failures == 1
    assert statistics.routine(FIXTURE.key, "c", "r_a").failures == 0


def test_statistics_round_trip_through_a_snapshot() -> None:
    statistics = RoutineStatistics()
    statistics.apply(outcome_event("r_a", "SUCCESS"))
    statistics.apply(skill_event("gather_wood", "flee", "SUCCESS"))
    body = statistics.to_json()
    restored = RoutineStatistics()
    restored.load_json(body)
    assert restored.routine(FIXTURE.key, "c", "r_a").successes == 1
    assert restored.skill(FIXTURE.key, "c", "flee").attempts == 1


def test_the_deterministic_provider_prefers_the_safest_plan() -> None:
    provider = DeterministicPolicyProvider()
    choice = provider.propose(
        OPEN,
        None,
        [candidate("risky", risk=0.9, cost=1.0), candidate("safe", risk=0.1, cost=5.0)],
        "c",
    )
    assert choice.routine_name == "safe"
    assert choice.learned_or_fallback == "fallback"
    with pytest.raises(NoCandidatesError):
        provider.propose(OPEN, None, [], "c")


def test_learning_off_always_returns_the_fallback() -> None:
    statistics = RoutineStatistics()
    for _ in range(10):
        statistics.apply(outcome_event("r_risky", "SUCCESS"))
    provider = EvidencePolicyProvider(statistics, experience=FIXTURE.key, learning_mode="off")
    choice = provider.propose(
        OPEN, None, [candidate("risky", risk=0.9), candidate("safe", risk=0.1)], "c"
    )
    assert choice.learned_or_fallback == "fallback"
    assert "learning_off" in choice.reason_codes


def test_shadow_mode_records_the_learner_but_runs_the_fallback() -> None:
    statistics = RoutineStatistics()
    for _ in range(6):
        statistics.apply(outcome_event("r_risky", "SUCCESS"))
    provider = EvidencePolicyProvider(
        statistics, experience=FIXTURE.key, learning_mode="shadow", minimum_support=3
    )
    choice = provider.propose(
        OPEN, None, [candidate("risky", risk=0.3), candidate("safe", risk=0.1)], "c"
    )
    assert choice.learned_or_fallback == "fallback"
    assert choice.routine_name == "safe"
    assert choice.shadow_routine_id == "r_risky"


def test_supported_routines_are_reused_in_supervised_mode() -> None:
    statistics = RoutineStatistics()
    for _ in range(6):
        statistics.apply(outcome_event("r_proven", "SUCCESS"))
    for _ in range(6):
        statistics.apply(outcome_event("r_unproven", "FAILED"))
    provider = EvidencePolicyProvider(
        statistics, experience=FIXTURE.key, learning_mode="supervised", minimum_support=3
    )
    choice = provider.propose(
        OPEN,
        None,
        [candidate("proven", risk=0.3), candidate("unproven", risk=0.1)],
        "c",
    )
    assert choice.routine_id == "r_proven"
    assert choice.learned_or_fallback == "learned"
    assert choice.confidence > 0.5


def test_a_costly_routine_loses_to_a_safer_one_with_the_same_record() -> None:
    statistics = RoutineStatistics()
    for _ in range(6):
        statistics.apply(outcome_event("r_bloody", "SUCCESS", health_cost=12.0))
        statistics.apply(outcome_event("r_gentle", "SUCCESS", health_cost=0.0))
    provider = EvidencePolicyProvider(
        statistics, experience=FIXTURE.key, learning_mode="supervised", minimum_support=3
    )
    choice = provider.propose(OPEN, None, [candidate("bloody"), candidate("gentle")], "c")
    assert choice.routine_id == "r_gentle"


def test_exploration_is_suppressed_outside_the_safe_envelope() -> None:
    statistics = RoutineStatistics()
    for _ in range(6):
        statistics.apply(outcome_event("r_known", "SUCCESS"))
    provider = EvidencePolicyProvider(
        statistics,
        experience=FIXTURE.key,
        learning_mode="supervised",
        minimum_support=3,
        exploration_bonus=0.9,
    )
    options = [candidate("known", risk=0.2), candidate("untried", risk=0.2)]
    options[1] = RoutineCandidate(
        routine_id="r_untried",
        name="untried",
        steps=options[1].steps,
        step_labels=options[1].step_labels,
        risk=0.2,
        cost=3.0,
        ticks=2400,
    )

    safe = provider.propose(OPEN, None, options, "c")
    assert safe.routine_id == "r_untried", "a large bonus should tempt exploration when it is safe"

    verdict = EnvelopeVerdict(open=False, reasons=("hostile_nearby",))
    cautious = provider.propose(verdict, None, options, "c")
    assert cautious.routine_id == "r_known"
