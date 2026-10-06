"""What a hypothesis may speak of: a closed vocabulary Person legitimately has.

The causal machinery is Person's; the condition variables it may vary come
from the environment profile, which knows what can be perceived there.

A condition is something Person perceived when it decided to act, or a place
in its own map. Nothing else can appear in a hypothesis, because nothing else
is Person's: not a coordinate, not an entity handle, not the state of a block
it never saw.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from person_protocol import discovered
from person_skills import SkillRegistry

#: The condition variables an environment lets Person vary, and their values:
#: what it can perceive of its situation (its manifest's `causal.variables`,
#: ADR 0025). Data, not code; this package imports no environment.
ENVIRONMENT_VARIABLES: dict[str, tuple[str, ...]] = {
    name: tuple(values)
    for manifest in discovered().values()
    for name, values in manifest.document.get("causal", {}).get("variables", {}).items()
}
#: The condition variables, in the order a proposer considers them: the
#: environment's, then the place in Person's own map, which every
#: environment has.
VARIABLES: tuple[str, ...] = (*ENVIRONMENT_VARIABLES, "place")
#: How sure Person must be of where it is for "here" to count as a condition.
#: Below it, a place is not known, and a trial cannot say which arm it was in.
PLACE_CONFIDENCE = 0.5


@dataclass(frozen=True, slots=True)
class Perceived:
    """The conditions Person perceived at one moment: the only facts it can vary."""

    #: The environment's condition variables and their perceived values.
    conditions: tuple[tuple[str, str], ...]
    #: The place Person believed it was at, if it was sure enough.
    place: str | None

    def value(self, variable: str) -> str | None:
        if variable == "place":
            return self.place
        return dict(self.conditions).get(variable)

    def to_json(self) -> dict[str, str | None]:
        return {**dict(self.conditions), "place": self.place}

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Perceived:
        place = body.get("place")
        return cls(
            conditions=tuple(
                (name, str(body[name])) for name in ENVIRONMENT_VARIABLES if name in body
            ),
            place=None if place is None else str(place),
        )


def perceived(conditions: Mapping[str, str], here: Any | None) -> Perceived:
    """Conditions now: what the environment says was perceived, and the place believed."""
    place = None
    if here is not None and here.confidence >= PLACE_CONFIDENCE:
        place = str(here.place_id)
    return Perceived(
        conditions=tuple(
            (name, str(conditions[name])) for name in ENVIRONMENT_VARIABLES if name in conditions
        ),
        place=place,
    )


def vocabulary(places: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Every value each condition variable may take, now."""
    return {
        **ENVIRONMENT_VARIABLES,
        # Only places Person has formed. A place it has never been cannot be
        # named, whatever a proposer imagines.
        "place": tuple(sorted(places)),
    }


def evaluable_effects(
    registry: SkillRegistry, offered: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    """Per offered, non-emergency skill: the declared effects Person can judge.

    A hypothesis about any other outcome could never be contradicted by
    anything Person observes, so it is not a hypothesis Person can hold.
    """
    effects: dict[str, tuple[str, ...]] = {}
    for skill in sorted(set(offered)):
        if skill not in registry.ids:
            continue
        spec = registry.get(skill)
        if spec.emergency:
            continue
        facts = tuple(
            dict.fromkeys(
                effect.fact
                for effect in spec.expected_effects
                if effect.fact in registry.vocabulary.evaluable_facts
            )
        )
        if facts:
            effects[skill] = facts
    return effects
