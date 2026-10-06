"""Interoception: the body as affect feels it (ADR 0014).

What reaches affect from the body is what the observation reports and a
player is shown: health, food, and breath in bubbles. From it come two kinds
of thing, kept apart:

    phasic   a bounded event or transition: harm taken, hunger or breath
             crossing into a worse band or recovering, a threat appearing or
             coming closer. Appraised once, when it happens.

    tonic    an ongoing condition: being hungry, badly hurt, short of breath,
             in perceived danger. A pressure held until the next observation,
             integrated by affect in experienced time.

Threat is aggregated to one intensity, so no hostile needs an identity (C4):
an exposure begins when some threat is perceived, escalates when it comes
closer than this exposure has yet been, and ends when none is perceived.

Nothing here reads a coordinate, an entity or anything the body does not
report, and nothing here touches `control`: the body is not evidence that
Person's own actions worked. Bands and magnitudes are implementation
parameters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .affect import Appraisal

#: Food below this is hunger; at or below STARVING it is starvation.
HUNGER_FROM = 18.0
STARVING = 6.0
#: Health below this is being badly hurt.
HURT_BELOW = 12.0
#: Breath, in bubbles: full, and the bands below it.
BREATH_FULL = 10
BREATH_SHORT = 7
BREATH_CRITICAL = 3
#: How much closer a threat must come, in intensity, to escalate.
ESCALATION_STEP = 0.25


@dataclass(frozen=True, slots=True)
class BodyReading:
    """What the body reports this observation, as interoception reads it.

    The environment profile produces it from its percepts (Minecraft's:
    `person_minecraft.body.body_reading`), and it is the body view of the
    SelfState (ADR 0026). Its scales are Minecraft's today: 20 health and food
    points and 10 bubbles of breath; see `docs/CURRENT_STATE.md`.
    """

    health: float
    food: float
    breath: int
    #: The strongest perceived threat, 0 (none) to 1 (upon Person).
    threat: float


def pressures(reading: BodyReading) -> dict[str, float]:
    """The ongoing conditions a reading implies, each from 0 to 1."""
    return {
        "hunger": _clamp((HUNGER_FROM - reading.food) / HUNGER_FROM),
        "vulnerability": _clamp((HURT_BELOW - reading.health) / HURT_BELOW),
        "breathlessness": _clamp((BREATH_FULL - reading.breath) / BREATH_FULL),
        "threat": reading.threat,
    }


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def hunger_band(food: float) -> int:
    return 0 if food >= HUNGER_FROM else 2 if food <= STARVING else 1


def breath_band(breath: int) -> int:
    return 0 if breath > BREATH_SHORT else 2 if breath <= BREATH_CRITICAL else 1


@dataclass(frozen=True, slots=True)
class Sensed:
    pressures: dict[str, float]
    events: list[Appraisal] = field(default_factory=list)


class Interoception:
    """Turns successive body readings into pressures and bodily events."""

    def __init__(self) -> None:
        self.previous: BodyReading | None = None
        #: The closest the current exposure has come, or None when no threat
        #: is perceived.
        self.exposure: float | None = None

    def lose_continuity(self) -> None:
        """The world went away (I2): no transition is felt across the absence,
        and a threat seen afterwards is a new exposure."""
        self.previous = None
        self.exposure = None

    def sense(self, reading: BodyReading) -> Sensed:
        events: list[Appraisal] = []
        previous = self.previous
        if previous is not None:
            events.extend(self._transitions(previous, reading))
        events.extend(self._threat(reading.threat))
        self.previous = reading
        return Sensed(pressures(reading), events)

    def _transitions(self, before: BodyReading, now: BodyReading) -> list[Appraisal]:
        events: list[Appraisal] = []
        lost = before.health - now.health
        if lost >= 1.0:
            # "I was hurt": once, for this loss. "I am still badly hurt" is
            # the vulnerability pressure, not another event.
            lost = round(lost, 2)
            events.append(
                Appraisal(
                    "harm", {"health_lost": lost}, {"unease": 0.08 * lost, "valence": -0.05 * lost}
                )
            )
        was, is_ = hunger_band(before.food), hunger_band(now.food)
        if is_ > was:
            events.append(
                Appraisal("hunger_starving", {"food": now.food}, {"valence": -0.08, "unease": 0.05})
                if is_ == 2
                else Appraisal("hunger_onset", {"food": now.food}, {"valence": -0.03})
            )
        elif is_ == 0 and was > 0:
            events.append(Appraisal("hunger_relieved", {"food": now.food}, {"valence": 0.05}))
        was, is_ = breath_band(before.breath), breath_band(now.breath)
        if is_ > was:
            events.append(
                Appraisal(
                    "breath_critical", {"breath": now.breath}, {"unease": 0.2, "valence": -0.05}
                )
                if is_ == 2
                else Appraisal("breath_short", {"breath": now.breath}, {"unease": 0.1})
            )
        elif is_ == 0 and was > 0:
            events.append(Appraisal("breath_recovered", {"breath": now.breath}, {"valence": 0.03}))
        return events

    def _threat(self, level: float) -> list[Appraisal]:
        if level <= 0.0:
            self.exposure = None
            return []
        if self.exposure is None:
            self.exposure = level
            return [Appraisal("threat_onset", {"threat": level}, {"unease": round(0.3 * level, 4)})]
        if level >= self.exposure + ESCALATION_STEP:
            rise = round(level - self.exposure, 4)
            self.exposure = level
            return [
                Appraisal(
                    "threat_escalation",
                    {"threat": level, "rise": rise},
                    {"unease": round(0.3 * rise, 4)},
                )
            ]
        return []


# ------------------------------------------------------ one event, once


def combined(
    base: Appraisal | None, consequences: Sequence[tuple[dict[str, Any], Appraisal]]
) -> Appraisal:
    """One appraisal for one causal event and everything it brought about.

    The event's own appraisal, plus the strongest good consequence and the
    strongest bad one. Never the sum over consequences: one act that happens
    to satisfy three goals is still one act (ADR 0014, decision 8).
    """
    deltas: dict[str, float] = dict(base.deltas) if base else {}
    components: dict[str, float] = dict(base.components) if base else {}
    appraisals = [appraisal for _, appraisal in consequences]
    good = [a for a in appraisals if a.deltas.get("valence", 0.0) > 0]
    bad = [a for a in appraisals if a.deltas.get("valence", 0.0) < 0]
    chosen = []
    if good:
        chosen.append(max(good, key=lambda a: a.deltas.get("valence", 0.0)))
    if bad:
        chosen.append(min(bad, key=lambda a: a.deltas.get("valence", 0.0)))
    for appraisal in chosen:
        for dimension, change in appraisal.deltas.items():
            deltas[dimension] = round(deltas.get(dimension, 0.0) + change, 4)
        for name, value in appraisal.components.items():
            components[name] = value
    components["consequences"] = float(len(consequences))
    trigger = base.trigger if base else "consequences"
    return Appraisal(trigger, components, deltas)
