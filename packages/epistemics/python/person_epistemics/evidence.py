"""Epistemic evidence: the narrow thing that may move a belief (ADR 0027).

A canonical event is a record that something happened: an episode started, a
memory was recalled, an affect changed, a deliberation was requested. Almost
none of those is evidence for any belief. Evidence is an admitted item that
bears on one belief, with a provenance class, a scope, the time it was
obtained in Person's experienced time, and references to the records it rests
on.

    canonical event  --(explicit admission, or nothing)-->  EpistemicEvidence

`admit` is the only constructor the rest of cognition uses, and it refuses:

- anything whose class can never be evidence (`MEMORY_RECALL`, `REPLAY`,
  `COUNTERFACTUAL`, `MODEL_ROLLOUT`, `INFERENCE`, `INITIAL_KNOWLEDGE`);
- anything reported by someone else, until a testimony channel with its own
  weighing exists (ADR 0004);
- anything from an experience stream that is not lived, so replayed material
  never becomes evidence about the world Person is living in;
- anything without a reference to what it rests on.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .experience import ExperienceKey
from .provenance import NEVER_EVIDENCE, REPORTED, WORLD_EVIDENCE, Source
from .scope import Scope

BeliefValue = float | int | str | bool | None


class EvidenceRefused(ValueError):
    """An item cannot be admitted as evidence, and why."""


@dataclass(frozen=True, slots=True)
class EpistemicEvidence:
    """One admitted item bearing on one belief."""

    bears_on: str
    value: BeliefValue
    source: Source
    scope: Scope
    #: Person's experienced time when it was obtained.
    observed_at: int
    confidence: float
    #: The canonical events, or the protocol messages, it rests on.
    refs: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "bears_on": self.bears_on,
            "value": self.value,
            "source": self.source.value,
            "scope": self.scope.to_json(),
            "observed_at": self.observed_at,
            "confidence": self.confidence,
            "refs": list(self.refs),
        }


def admit(
    *,
    bears_on: str,
    value: BeliefValue,
    source: Source,
    scope: Scope,
    observed_at: int,
    confidence: float,
    refs: tuple[str, ...],
    experience: ExperienceKey,
) -> EpistemicEvidence:
    """Admit one item as evidence about the world, or raise `EvidenceRefused`."""
    source = Source(source)
    if source in NEVER_EVIDENCE:
        raise EvidenceRefused(f"{source.value} is never evidence about the world")
    if source in REPORTED:
        raise EvidenceRefused(f"{source.value} has no admission channel yet")
    if source not in WORLD_EVIDENCE:  # pragma: no cover - the classes partition Source
        raise EvidenceRefused(f"{source.value} is not world evidence")
    if not experience.lived:
        raise EvidenceRefused("replayed experience is never new evidence about the world")
    if not refs:
        raise EvidenceRefused("evidence must reference what it rests on")
    if not 0.0 <= confidence <= 1.0:
        raise EvidenceRefused("confidence must lie in [0, 1]")
    return EpistemicEvidence(
        bears_on=bears_on,
        value=value,
        source=source,
        scope=scope,
        observed_at=observed_at,
        confidence=confidence,
        refs=tuple(refs),
    )


@dataclass(frozen=True, slots=True)
class EventAdmission:
    """How a canonical event type relates to evidence: what it may bear on, and as what.

    A table of these, kept by whoever reduces the event, is the explicit
    relationship ADR 0027 requires. An event type with no entry is history and
    nothing more.
    """

    event_type: str
    source: Source
    bears_on: str


def admissions(table: Mapping[str, EventAdmission]) -> Mapping[str, EventAdmission]:
    """Check a reducer's admission table: every entry must be admissible in principle."""
    for event_type, entry in table.items():
        if entry.event_type != event_type:
            raise EvidenceRefused(f"admission for {event_type} names {entry.event_type}")
        if entry.source not in WORLD_EVIDENCE:
            raise EvidenceRefused(f"{event_type} cannot be admitted as {entry.source.value}")
    return table
