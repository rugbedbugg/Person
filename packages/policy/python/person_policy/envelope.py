"""The safe exploration envelope.

Exploration of an uncertain routine is only allowed when Person can afford to
be wrong. Outside the envelope the exploration bonus is exactly zero and the
best-supported safe behaviour wins.

This mirrors, on the cognition side, the safety hierarchy the runtime enforces.
It is not a substitute for it: the runtime stays authoritative either way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EnvelopeThresholds:
    health: float = 16.0
    food: float = 14.0
    max_home_distance: float = 96.0
    min_light: int = 7


@dataclass(frozen=True, slots=True)
class EnvelopeVerdict:
    open: bool
    reasons: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.open


def safe_envelope(
    observation: dict[str, Any], thresholds: EnvelopeThresholds | None = None
) -> EnvelopeVerdict:
    limits = thresholds or EnvelopeThresholds()
    vitals = observation["vitals"]
    nearby = observation["nearby"]
    home = observation["home"]
    environment = observation["environment"]
    reasons: list[str] = []

    if not vitals["alive"]:
        reasons.append("not_alive")
    if vitals["health"] < limits.health:
        reasons.append("health_below_envelope")
    if vitals["food"] < limits.food:
        reasons.append("food_below_envelope")
    if any(entity["distance"] <= 16 for entity in nearby["hostiles"]):
        reasons.append("hostile_nearby")
    if any(hazard["distance"] <= 3 for hazard in nearby["hazards"]):
        reasons.append("hazard_nearby")

    distance = home["homeDistance"]
    if distance is not None and distance > limits.max_home_distance:
        reasons.append("too_far_from_home")
    if not observation["navigation"]["returnPathKnown"]:
        reasons.append("return_path_unknown")

    sheltered = home["shelterState"] == "complete" and (distance is not None and distance <= 2)
    dark = environment["dayPhase"] == "night" or environment["lightLevel"] < limits.min_light
    if dark and not sheltered:
        reasons.append("darkness_without_shelter")

    return EnvelopeVerdict(open=not reasons, reasons=tuple(reasons))
