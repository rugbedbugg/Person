"""How much an experience matters, by a fixed and inspectable table.

Salience decides how slowly a memory becomes inaccessible. The foundation
model is deliberately plain: a base value per kind of episode, a bonus for a
few subjects, adjustments for failure and gain, and a bonus the first time
Person encodes anything about a subject. It is not affect and not personality;
those are later phases and will not be smuggled in here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

BASE: Mapping[str, float] = {
    "perceived": 0.2,
    "acted": 0.2,
    "searched": 0.3,
    "hurt": 0.5,
    "endangered": 0.8,
}

#: Threats and scarce things are worth remembering for longer.
SUBJECT_BONUS: Mapping[str, float] = {
    "hostile": 0.3,
    "hazard": 0.2,
    "danger": 0.1,
    "coal": 0.1,
    "container": 0.1,
}

#: The first episode about a subject.
NOVELTY_BONUS = 0.2


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def base_salience(kind: str, subjects: Iterable[str], details: Mapping[str, Any]) -> float:
    """Salience from what the episode is, before familiarity."""
    value = BASE[kind] + max((SUBJECT_BONUS.get(subject, 0.0) for subject in subjects), default=0)
    if kind == "acted":
        status = details.get("status")
        if status == "DEATH":
            return 1.0
        if status != "SUCCESS":
            value += 0.2
        if any(int(change.split(":")[-1]) > 0 for change in details.get("inventory", [])):
            value += 0.1
        if details.get("emergency"):
            value += 0.2
    elif kind == "hurt":
        value += 0.05 * float(details.get("health_lost", 0.0))
    elif kind == "searched" and details.get("conclusion") != "found":
        value += 0.1
    return _clamp(value)


def with_novelty(salience: float, novel: bool) -> float:
    return _clamp(salience + (NOVELTY_BONUS if novel else 0.0))
