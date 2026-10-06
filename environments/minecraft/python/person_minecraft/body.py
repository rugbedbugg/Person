"""The Minecraft body as interoception reads it (ADR 0014, 0025, 0026).

The body view of Person's SelfState. Health, food and breath in bubbles are
what a player is shown; threat is the one intensity all perceived danger adds
up to, so no hostile needs an identity (C4).
"""

from __future__ import annotations

from person_cognition.interoception import BodyReading

from .perception import MinecraftPercepts


def threat_intensity(percepts: MinecraftPercepts) -> float:
    """One number for all the danger Person perceives: how close the nearest is."""
    nearby = percepts.nearby
    level = 0.0
    for hostile in nearby["hostiles"]:
        level = max(level, 1.0 - float(hostile["distance"]) / 16.0)
    for hazard in nearby["hazards"]:
        level = max(level, 1.0 - float(hazard["distance"]) / 4.0)
    return round(max(0.0, level), 4)


def body_reading(percepts: MinecraftPercepts) -> BodyReading:
    vitals = percepts.vitals
    return BodyReading(
        health=float(vitals["health"]),
        food=float(vitals["food"]),
        breath=int(vitals["breath"]),
        threat=threat_intensity(percepts),
    )
