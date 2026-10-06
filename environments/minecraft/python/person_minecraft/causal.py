"""What Person can vary in Minecraft when it tests a cause (ADR 0012, 0025).

The condition variables and their values are declared in the manifest
(`causal.variables`); this reads their current values from percepts.
"""

from __future__ import annotations

from .perception import MinecraftPercepts


def conditions(percepts: MinecraftPercepts) -> dict[str, str]:
    """The weather and day phase Person perceives now."""
    return {"weather": str(percepts.sky["weather"]), "day_phase": str(percepts.sky["dayPhase"])}
