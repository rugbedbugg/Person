"""How much Person leans on deliberation (ADR 0020 instrumentation).

The long-term question is whether familiar situations need fewer general
deliberations over time. That is only testable if the rate is measured from
the start, per experienced hour and by what triggered it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

#: Experienced ticks in one experienced hour: twenty a second.
EXPERIENCED_HOUR_TICKS = 72_000


def deliberation_rate(events: Iterable[Any], experienced_ticks: int) -> dict[str, Any]:
    """Deliberations per experienced hour, overall and by reason."""
    reasons = Counter(
        str(event.payload["reason"]) for event in events if event.type == "deliberation_requested"
    )
    hours = experienced_ticks / EXPERIENCED_HOUR_TICKS
    total = sum(reasons.values())
    return {
        "deliberations": total,
        "experienced_hours": round(hours, 4),
        "per_experienced_hour": round(total / hours, 4) if hours > 0 else None,
        "by_reason": dict(sorted(reasons.items())),
    }


def habit_metrics(events: Iterable[Any]) -> dict[str, Any]:
    """What active habits did (ADR 0022): formation, use, outcomes, failures.

    `deliberations_avoided` is the habit invocations, each a problem answered
    without a model; it is a count, never a fabricated event. A falling model
    rate is learning only if `habit_failures`, demotions and breakdowns do
    not rise with it.
    """
    events = list(events)
    kinds = Counter(str(event.type) for event in events)
    outcomes = Counter(
        (str(event.payload.get("via", "deliberation")), str(event.payload["verdict"]))
        for event in events
        if event.type == "habit_evidence"
    )
    breakdowns = sum(
        1
        for event in events
        if event.type == "deliberation_requested"
        and event.payload.get("reason") == "habit_breakdown"
    )
    return {
        "candidates": kinds["habit_candidate_formed"],
        "promotions": kinds["habit_promoted"],
        "conflicts": kinds["habit_conflict"],
        "invocations": kinds["habit_invoked"],
        "deliberations_avoided": kinds["habit_invoked"],
        "not_applicable": kinds["habit_not_applicable"],
        "demotions": kinds["habit_demoted"],
        "breakdowns": breakdowns,
        "deliberated_successes": outcomes[("deliberation", "success")],
        "deliberated_failures": outcomes[("deliberation", "failure")],
        "habit_successes": outcomes[("habit", "success")],
        "habit_failures": outcomes[("habit", "failure")],
    }
