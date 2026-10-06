"""Persistent, scoped fact beliefs (ADR 0026).

A belief is what Person currently takes to be true, which is not what it
currently perceives and not what it remembers. It carries:

    key              what it is about, in the environment's fact vocabulary
    value            what Person takes to be the case
    confidence       how strongly, in [0, 1]
    basis            the provenance class of the evidence it last rested on
    evidence_refs    the records that evidence rests on
    updated_at       Person's experienced time when the value was last revised
    last_observed_at when evidence last confirmed it, even unchanged
    scope            how far it holds (`person_epistemics.scope`)

The representation is deliberately conservative: no distributions, no
graphical model. A belief changes only through `BeliefState.revise`, which
takes admitted `EpistemicEvidence` and nothing else, so a memory, a
prediction or a counterfactual has no way in. Revising never changes a
belief's scope.

The store is rebuilt from `belief_revised` events alone. A revision is
journalled only when a value, basis or scope changes; a confirmation of an
unchanged belief refreshes `last_observed_at` in an ephemeral overlay
(`Freshness`) that is never persisted, so a restart restores the time of the
last revision, which is older and therefore conservative.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from .evidence import BeliefValue, EpistemicEvidence
from .provenance import WORLD_EVIDENCE, Source
from .scope import BREADTH, Scope, Situation

#: The canonical event type the belief store is rebuilt from.
BELIEF_EVENT = "belief_revised"


class EventLike(Protocol):
    @property
    def type(self) -> str: ...

    @property
    def payload(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class FactBelief:
    key: str
    value: BeliefValue
    confidence: float
    basis: Source
    evidence_refs: tuple[str, ...]
    updated_at: int
    last_observed_at: int | None
    scope: Scope

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "basis": self.basis.value,
            "evidence_refs": list(self.evidence_refs),
            "updated_at": self.updated_at,
            "last_observed_at": self.last_observed_at,
            "scope": self.scope.to_json(),
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> FactBelief:
        observed = body.get("last_observed_at")
        return cls(
            key=str(body["key"]),
            value=body["value"],
            confidence=float(body["confidence"]),
            basis=Source(str(body["basis"])),
            evidence_refs=tuple(str(ref) for ref in body["evidence_refs"]),
            updated_at=int(body["updated_at"]),
            last_observed_at=None if observed is None else int(observed),
            scope=Scope.from_json(body["scope"]),
        )

    def age(self, now: int) -> int | None:
        """Experienced ticks since evidence last bore on it."""
        return None if self.last_observed_at is None else max(0, now - self.last_observed_at)


@dataclass(frozen=True, slots=True)
class BeliefRevision:
    """One change to one belief, as it is journalled."""

    belief: FactBelief
    previous: BeliefValue

    def payload(self) -> dict[str, Any]:
        return {**self.belief.to_json(), "previous": self.previous}


@dataclass(frozen=True, slots=True)
class _Revised:
    payload: Mapping[str, Any]
    type: str = BELIEF_EVENT


def _identity(key: str, scope: Scope) -> tuple[str, str, str | None, str | None, str | None]:
    return (key, scope.level.value, scope.environment_kind, scope.world_id, scope.embodiment_kind)


@dataclass
class Freshness:
    """When each unchanged belief was last confirmed. Ephemeral by design."""

    confirmed: dict[tuple[str, str, str | None, str | None, str | None], int] = field(
        default_factory=dict
    )

    def confirm(self, key: str, scope: Scope, now: int) -> None:
        self.confirmed[_identity(key, scope)] = now

    def last(self, key: str, scope: Scope) -> int | None:
        return self.confirmed.get(_identity(key, scope))


class BeliefView(Mapping[str, FactBelief]):
    """The beliefs that hold in one situation: read-only, keyed by fact."""

    def __init__(self, beliefs: Mapping[str, FactBelief], version: int) -> None:
        self._beliefs = dict(beliefs)
        #: How many revisions the store had applied when this view was taken.
        self.version = version

    def __getitem__(self, key: str) -> FactBelief:
        return self._beliefs[key]

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._beliefs))

    def __len__(self) -> int:
        return len(self._beliefs)

    def value(self, key: str, default: BeliefValue = None) -> BeliefValue:
        belief = self._beliefs.get(key)
        return default if belief is None else belief.value


class BeliefState:
    """Every fact belief Person holds, in every scope, rebuilt from its revisions."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._beliefs: dict[tuple[str, str, str | None, str | None, str | None], FactBelief] = {}
        self.version = 0
        #: Revisions the store refused to apply, because their basis is not
        #: world evidence. Nonzero means something wrote what it must not.
        self.refused = 0

    # ------------------------------------------------------------- reducer

    def apply(self, event: EventLike) -> None:
        if event.type != BELIEF_EVENT:
            return
        belief = FactBelief.from_json(event.payload)
        if belief.basis not in WORLD_EVIDENCE:
            self.refused += 1
            return
        self._beliefs[_identity(belief.key, belief.scope)] = belief
        self.version += 1

    def admit_revision(self, revision: BeliefRevision) -> None:
        """Apply a revision that had no journal to go through (no continuity root)."""
        self.apply(_Revised(revision.payload()))

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "refused": self.refused,
            "beliefs": [belief.to_json() for belief in self._beliefs.values()],
        }

    def load_json(self, body: Mapping[str, Any]) -> None:
        self.reset()
        for record in body["beliefs"]:
            belief = FactBelief.from_json(record)
            self._beliefs[_identity(belief.key, belief.scope)] = belief
        self.version = int(body["version"])
        self.refused = int(body.get("refused", 0))

    # --------------------------------------------------------------- reading

    def beliefs(self) -> tuple[FactBelief, ...]:
        return tuple(self._beliefs.values())

    def get(self, key: str, situation: Situation) -> FactBelief | None:
        """The narrowest belief about `key` that holds in the situation."""
        candidates = [
            belief
            for belief in self._beliefs.values()
            if belief.key == key and belief.scope.applies_in(situation)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda belief: BREADTH[belief.scope.level])

    def view(self, situation: Situation, freshness: Freshness | None = None) -> BeliefView:
        keys = {belief.key for belief in self._beliefs.values()}
        held: dict[str, FactBelief] = {}
        for key in keys:
            belief = self.get(key, situation)
            if belief is None:
                continue
            confirmed = freshness.last(key, belief.scope) if freshness else None
            if confirmed is not None and (
                belief.last_observed_at is None or confirmed > belief.last_observed_at
            ):
                belief = replace(belief, last_observed_at=confirmed)
            held[key] = belief
        return BeliefView(held, self.version)

    # -------------------------------------------------------------- revising

    def revise(
        self,
        evidence: Sequence[EpistemicEvidence],
        freshness: Freshness | None = None,
    ) -> list[BeliefRevision]:
        """The revisions this evidence calls for. Pure: nothing is applied.

        The caller journals each revision, and the journal applies it, so the
        store is only ever what its records say.
        """
        revisions: list[BeliefRevision] = []
        for item in evidence:
            if not isinstance(item, EpistemicEvidence):
                raise TypeError("beliefs are revised by admitted evidence only")
            current = self._beliefs.get(_identity(item.bears_on, item.scope))
            if (
                current is not None
                and current.value == item.value
                and current.basis == item.source
                and current.confidence == item.confidence
            ):
                if freshness is not None:
                    freshness.confirm(item.bears_on, item.scope, item.observed_at)
                continue
            revisions.append(
                BeliefRevision(
                    belief=FactBelief(
                        key=item.bears_on,
                        value=item.value,
                        confidence=item.confidence,
                        basis=item.source,
                        evidence_refs=item.refs,
                        updated_at=item.observed_at,
                        last_observed_at=item.observed_at,
                        # Evidence about this world revises a belief about
                        # this world: the scope travels with the evidence and
                        # is never widened here.
                        scope=item.scope,
                    ),
                    previous=None if current is None else current.value,
                )
            )
        return revisions
