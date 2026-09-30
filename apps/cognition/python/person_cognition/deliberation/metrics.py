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
