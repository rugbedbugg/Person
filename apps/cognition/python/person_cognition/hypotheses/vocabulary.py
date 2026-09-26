"""What a hypothesis may speak of: a closed vocabulary Person legitimately has.

A condition is something Person perceived when it decided to act, or a place
in its own map. Nothing else can appear in a hypothesis, because nothing else
is Person's: not a coordinate, not an entity handle, not the state of a block
it never saw.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from person_skills import SkillRegistry

from ..effect_learning import EVALUABLE_FACTS

#: Values from the observation schema: what Person can perceive.
WEATHER: tuple[str, ...] = ("clear", "rain", "thunder")
DAY_PHASES: tuple[str, ...] = ("dawn", "day", "dusk", "night")
#: The condition variables, in the order a proposer considers them.
VARIABLES: tuple[str, ...] = ("weather", "day_phase", "place")
#: How sure Person must be of where it is for "here" to count as a condition.
#: Below it, a place is not known, and a trial cannot say which arm it was in.
PLACE_CONFIDENCE = 0.5


@dataclass(frozen=True, slots=True)
class Perceived:
    """The conditions Person perceived at one moment: the only facts it can vary."""

    weather: str
    day_phase: str
    #: The place Person believed it was at, if it was sure enough.
    place: str | None

    def value(self, variable: str) -> str | None:
        return {"weather": self.weather, "day_phase": self.day_phase, "place": self.place}.get(
            variable
        )

    def to_json(self) -> dict[str, str | None]:
        return {"weather": self.weather, "day_phase": self.day_phase, "place": self.place}

    @classmethod
    def from_json(cls, body: Mapping[str, Any]) -> Perceived:
        place = body.get("place")
        return cls(
            weather=str(body["weather"]),
            day_phase=str(body["day_phase"]),
            place=None if place is None else str(place),
        )


def perceived(observation: Mapping[str, Any], here: Any | None) -> Perceived:
    """Conditions now: the weather and day phase seen, and the place believed."""
    environment = observation["environment"]
    place = None
    if here is not None and here.confidence >= PLACE_CONFIDENCE:
        place = str(here.place_id)
    return Perceived(
        weather=str(environment["weather"]),
        day_phase=str(environment["dayPhase"]),
        place=place,
    )


def vocabulary(places: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Every value each condition variable may take, now."""
    return {
        "weather": WEATHER,
        "day_phase": DAY_PHASES,
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
                effect.fact for effect in spec.expected_effects if effect.fact in EVALUABLE_FACTS
            )
        )
        if facts:
            effects[skill] = facts
    return effects
