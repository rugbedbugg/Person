"""How far a belief is meant to hold (ADR 0026).

A belief about where Person's shelter is holds in one world. How reliably a
skill's effects follow holds for one embodiment of one environment. That
night follows day may hold across a whole environment. Very little Person
believes is environment-general, and nothing becomes so by accident.

    WORLD        one world of one environment
    EMBODIMENT   one embodiment of one environment, in any of its worlds
    ENVIRONMENT  every embodiment and world of one environment
    GENERAL      any environment

Revising a belief never changes its scope. Widening one is an explicit act,
`widen`, that names the evidence and the reason, and is refused when it would
skip a level or narrow instead. Nothing in the current implementation widens
any belief; the function exists so that the one road to cross-environment
knowledge is a visible, testable one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ScopeLevel(StrEnum):
    WORLD = "world"
    EMBODIMENT = "embodiment"
    ENVIRONMENT = "environment"
    GENERAL = "general"


#: How broad each level is. WORLD and EMBODIMENT are both narrower than
#: ENVIRONMENT, along different axes, and neither contains the other.
BREADTH: Mapping[ScopeLevel, int] = {
    ScopeLevel.WORLD: 0,
    ScopeLevel.EMBODIMENT: 0,
    ScopeLevel.ENVIRONMENT: 1,
    ScopeLevel.GENERAL: 2,
}


class ScopeError(ValueError):
    """A scope is malformed, or a change of scope is not allowed."""


@dataclass(frozen=True, slots=True)
class Situation:
    """Where Person is living now: the coordinates a scope is checked against."""

    environment_kind: str
    world_id: str
    embodiment_kind: str


@dataclass(frozen=True, slots=True)
class Scope:
    level: ScopeLevel
    environment_kind: str | None = None
    world_id: str | None = None
    embodiment_kind: str | None = None

    def __post_init__(self) -> None:
        level = ScopeLevel(self.level)
        needs = {
            ScopeLevel.WORLD: ("environment_kind", "world_id"),
            ScopeLevel.EMBODIMENT: ("environment_kind", "embodiment_kind"),
            ScopeLevel.ENVIRONMENT: ("environment_kind",),
            ScopeLevel.GENERAL: (),
        }[level]
        for name in ("environment_kind", "world_id", "embodiment_kind"):
            present = getattr(self, name) is not None
            if present != (name in needs):
                raise ScopeError(
                    f"a {level.value} scope {'needs' if not present else 'has no'} {name}"
                )

    @classmethod
    def world(cls, environment_kind: str, world_id: str) -> Scope:
        return cls(ScopeLevel.WORLD, environment_kind=environment_kind, world_id=world_id)

    @classmethod
    def embodiment(cls, environment_kind: str, embodiment_kind: str) -> Scope:
        return cls(
            ScopeLevel.EMBODIMENT,
            environment_kind=environment_kind,
            embodiment_kind=embodiment_kind,
        )

    @classmethod
    def environment(cls, environment_kind: str) -> Scope:
        return cls(ScopeLevel.ENVIRONMENT, environment_kind=environment_kind)

    @classmethod
    def general(cls) -> Scope:
        return cls(ScopeLevel.GENERAL)

    def applies_in(self, situation: Situation) -> bool:
        """Whether a belief of this scope is about the situation Person is in."""
        match self.level:
            case ScopeLevel.WORLD:
                return (
                    self.environment_kind == situation.environment_kind
                    and self.world_id == situation.world_id
                )
            case ScopeLevel.EMBODIMENT:
                return (
                    self.environment_kind == situation.environment_kind
                    and self.embodiment_kind == situation.embodiment_kind
                )
            case ScopeLevel.ENVIRONMENT:
                return self.environment_kind == situation.environment_kind
        return True

    def to_json(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "environment": self.environment_kind,
            "world": self.world_id,
            "embodiment": self.embodiment_kind,
        }

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Scope:
        return cls(
            ScopeLevel(str(body["level"])),
            environment_kind=body.get("environment"),
            world_id=body.get("world"),
            embodiment_kind=body.get("embodiment"),
        )


@dataclass(frozen=True, slots=True)
class Widening:
    """Why a belief is now held more broadly than where it was learned."""

    to: Scope
    reason: str
    evidence_refs: tuple[str, ...]


def check_widening(current: Scope, widening: Widening) -> Scope:
    """The scope a belief may be widened to, or `ScopeError`.

    One level at a time, only broader, only within the environment it was
    learned in unless the target is GENERAL, and never without evidence.
    """
    target = widening.to
    if not widening.reason or not widening.evidence_refs:
        raise ScopeError("widening a belief needs a reason and the evidence for it")
    if BREADTH[target.level] != BREADTH[current.level] + 1:
        raise ScopeError(f"cannot widen {current.level.value} to {target.level.value}")
    if (
        target.level is ScopeLevel.ENVIRONMENT
        and target.environment_kind != current.environment_kind
    ):
        raise ScopeError("a belief cannot move to another environment by widening")
    return target


def narrowest(scopes: Sequence[Scope]) -> Scope:
    """The narrowest of several scopes: what a conclusion drawn from all of them holds for."""
    if not scopes:
        raise ScopeError("no scope to narrow")
    return min(scopes, key=lambda scope: BREADTH[scope.level])
