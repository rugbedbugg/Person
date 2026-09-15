"""Coarse decision context.

Learning must not be conditioned on the full observation: nearly every
observation is unique, so nearly every experience would be its own special
case. The context is deliberately small and its serialisation is deterministic,
so two situations that call for the same decision land in the same bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HEALTH_BANDS = ("critical", "low", "healthy")
FOOD_BANDS = ("starving", "low", "sufficient", "full")
DAY_PHASES = ("dawn", "day", "dusk", "night")
THREAT_LEVELS = ("none", "nearby", "immediate")
HOME_STATES = ("at_home", "near", "far", "unknown")
TOOL_TIERS = ("none", "wood", "stone", "iron", "diamond")
FOOD_STATES = ("none", "raw", "cooked", "stored")

IMMEDIATE_THREAT_DISTANCE = 7.0
NEARBY_THREAT_DISTANCE = 16.0
NEAR_HOME_DISTANCE = 2.0
FAR_HOME_DISTANCE = 32.0

PLANT_FOOD = {"apple", "sweet_berries", "carrot"}


@dataclass(frozen=True, slots=True)
class DecisionContext:
    health_band: str
    food_band: str
    day_phase: str
    threat: str
    home_state: str
    tool_tier: str
    food_state: str

    def identifier(self) -> str:
        """Stable, short, greppable. Equal situations produce equal strings."""
        return ".".join(
            (
                f"h_{self.health_band}",
                f"f_{self.food_band}",
                f"d_{self.day_phase}",
                f"t_{self.threat}",
                f"hm_{self.home_state}",
                f"tt_{self.tool_tier}",
                f"fs_{self.food_state}",
            )
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "health_band": self.health_band,
            "food_band": self.food_band,
            "day_phase": self.day_phase,
            "threat": self.threat,
            "home_state": self.home_state,
            "tool_tier": self.tool_tier,
            "food_state": self.food_state,
        }


def _health_band(health: float) -> str:
    if health < 7:
        return "critical"
    if health < 13:
        return "low"
    return "healthy"


def _food_band(food: float) -> str:
    if food < 7:
        return "starving"
    if food < 13:
        return "low"
    if food < 18:
        return "sufficient"
    return "full"


def _threat(observation: dict[str, Any]) -> str:
    hostiles = observation["nearby"]["hostiles"]
    if any(entity["distance"] <= IMMEDIATE_THREAT_DISTANCE for entity in hostiles):
        return "immediate"
    if any(entity["distance"] <= NEARBY_THREAT_DISTANCE for entity in hostiles):
        return "nearby"
    hazards = observation["nearby"]["hazards"]
    if any(hazard["distance"] <= 1.5 for hazard in hazards):
        return "immediate"
    return "none"


def _home_state(observation: dict[str, Any]) -> str:
    home = observation["home"]
    if home["activeHome"] is None or home["homeDistance"] is None:
        return "unknown"
    distance = home["homeDistance"]
    if distance <= NEAR_HOME_DISTANCE:
        return "at_home"
    if distance <= FAR_HOME_DISTANCE:
        return "near"
    return "far"


def _tool_tier(observation: dict[str, Any]) -> str:
    tier = 0
    for item in observation["inventory"]["items"]:
        if not item["name"].endswith("_pickaxe"):
            continue
        prefix = item["name"].removesuffix("_pickaxe")
        tier = max(tier, {"wooden": 1, "stone": 2, "iron": 3, "diamond": 4}.get(prefix, 0))
    return TOOL_TIERS[tier]


def _food_state(observation: dict[str, Any]) -> str:
    """What kind of food security Person currently has.

    ``stored`` means there is a reserve in owned storage, ``cooked`` that
    something ready to eat is carried, ``raw`` that food is carried but needs
    processing first.
    """
    home = observation["home"]
    if home["foodReserve"] > 0:
        return "stored"
    categories = observation["inventory"]["categories"]
    plant = sum(
        item["count"] for item in observation["inventory"]["items"] if item["name"] in PLANT_FOOD
    )
    if categories["cooked_food"] > 0 or plant > 0:
        return "cooked"
    if categories["raw_food"] > 0:
        return "raw"
    return "none"


def decision_context(observation: dict[str, Any]) -> DecisionContext:
    return DecisionContext(
        health_band=_health_band(observation["vitals"]["health"]),
        food_band=_food_band(observation["vitals"]["food"]),
        day_phase=observation["environment"]["dayPhase"],
        threat=_threat(observation),
        home_state=_home_state(observation),
        tool_tier=_tool_tier(observation),
        food_state=_food_state(observation),
    )


def context_id(observation: dict[str, Any]) -> str:
    return decision_context(observation).identifier()
