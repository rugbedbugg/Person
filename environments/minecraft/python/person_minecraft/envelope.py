"""The safe exploration envelope, in Minecraft (moved from person_policy, ADR 0025).

The policy package decides how exploration is weighted; whether Person can
afford to be wrong right now depends on what a Minecraft body needs, so the
envelope is the Minecraft profile's.

Exploration of an uncertain routine is only allowed when Person can afford to
be wrong. Outside the envelope the exploration bonus is exactly zero and the
best-supported safe behaviour wins.

This mirrors, on the cognition side, the safety hierarchy the runtime enforces.
It is not a substitute for it: the runtime stays authoritative either way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from person_epistemics import DecisionState
from person_policy import EnvelopeVerdict

from .perception import MinecraftPercepts


@dataclass(frozen=True, slots=True)
class EnvelopeThresholds:
    health: float = 16.0
    food: float = 14.0
    min_light: int = 7


def safe_envelope(
    decision: DecisionState[MinecraftPercepts, Any],
    thresholds: EnvelopeThresholds | None = None,
) -> EnvelopeVerdict:
    """Whether Person can afford to explore, from what it perceives and believes.

    Home is its own spatial belief (C8); its shelter's state its belief from
    the runtime's report; the return path the runtime's current report.
    """
    limits = thresholds or EnvelopeThresholds()
    percepts = decision.percepts.percepts
    vitals = percepts.vitals
    nearby = percepts.nearby
    environment = percepts.sky
    home = decision.self_state.home_relation
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

    if home == "far":
        reasons.append("too_far_from_home")
    if not percepts.navigation["returnPathKnown"]:
        reasons.append("return_path_unknown")

    sheltered = decision.beliefs.value("shelter_state") == "complete" and home == "at_home"
    dark = environment["dayPhase"] == "night" or environment["lightLevel"] < limits.min_light
    if dark and not sheltered:
        reasons.append("darkness_without_shelter")

    return EnvelopeVerdict(open=not reasons, reasons=tuple(reasons))
