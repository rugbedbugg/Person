"""What a Minecraft situation looks like to deliberation (ADR 0020, 0022, 0025).

Two coarse, Person-visible summaries of current perception, both moved from
the core deliberation package because every field in them is Minecraft's:

    situation_facts     the `situation` section of a deliberation context
    context_signature   `context_signature_v1`, the context a habit is keyed by

Both read percepts only, never a memory or a belief, and both band or count
everything, so no distance or coordinate reaches a model or a habit. Their
output is byte-for-byte what the core produced before the move: habits are
persisted by the hash of their signature.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from person_cognition.deliberation.context import CAPS, capped

from .perception import MinecraftPercepts

CONTEXT_SIGNATURE_SCHEMA = "context_signature_v1"

NEARBY_KINDS: tuple[str, ...] = (
    "hostiles",
    "passiveAnimals",
    "players",
    "resources",
    "hazards",
    "containers",
    "workstations",
)


def _band(value: float, bands: Sequence[tuple[float, str]], top: str) -> str:
    for limit, name in bands:
        if value <= limit:
            return name
    return top


def health_band(health: float) -> str:
    return _band(health, ((6, "critical"), (12, "low")), "healthy")


def food_band(food: float) -> str:
    return _band(food, ((6, "critical"), (12, "low"), (17, "sufficient")), "full")


def breath_band(breath: float) -> str:
    return _band(breath, ((3, "critical"), (7, "short")), "normal")


def _sections(observation: MinecraftPercepts | Mapping[str, Any] | None) -> Mapping[str, Any]:
    """The four percept sections a summary reads, from percepts or a test's mapping."""
    if observation is None:
        return {}
    if isinstance(observation, MinecraftPercepts):
        return {
            "vitals": observation.vitals,
            "environment": observation.sky,
            "nearby": observation.nearby,
            "inventory": observation.inventory,
        }
    return observation


def situation_facts(percepts: MinecraftPercepts | None) -> list[dict[str, Any]]:
    """The facts of the situation a deliberation is shown, before the core's own."""
    if percepts is None:
        return []
    situation: list[dict[str, Any]] = []
    vitals = percepts.vitals
    sky = percepts.sky
    situation.append({"fact": "health", "value": health_band(float(vitals["health"]))})
    situation.append({"fact": "food", "value": food_band(float(vitals["food"]))})
    situation.append({"fact": "breath", "value": breath_band(float(vitals["breath"]))})
    situation.append({"fact": "day_phase", "value": str(sky["dayPhase"])})
    situation.append({"fact": "weather", "value": str(sky["weather"])})
    nearby: Mapping[str, Any] = percepts.nearby
    for kind in NEARBY_KINDS:
        seen = nearby.get(kind, [])
        names: dict[str, dict[str, Any]] = {}
        for thing in seen:
            name = str(thing.get("name") or thing.get("kind"))
            entry = names.setdefault(name, {"count": 0, "nearest": thing.get("rangeBand")})
            entry["count"] += 1
        for name, entry in capped(sorted(names.items()), CAPS["in_view_per_kind"]):
            situation.append(
                {
                    "fact": f"in_view.{kind}",
                    "value": name,
                    "count": entry["count"],
                    "nearest": entry["nearest"],
                }
            )
    categories = percepts.inventory.get("categories", {})
    held = [(name, count) for name, count in sorted(categories.items()) if count]
    for name, count in capped(held, CAPS["holdings"]):
        situation.append({"fact": f"holding.{name}", "value": int(count)})
    return situation


#: Inventory categories a response's desired facts make relevant. A fact
#: with no declared mapping adds no inventory to the signature.
INVENTORY_FOR_FACT: Mapping[str, tuple[str, ...]] = {
    "wood": ("wood",),
    "planks": ("wood",),
    "stone": ("stone",),
    "coal": ("coal", "fuel"),
    "fuel": ("fuel",),
    "raw_food": ("raw_food",),
    "cooked_food": ("cooked_food", "raw_food", "fuel"),
    "plant_food": ("food",),
    "edible_food": ("food",),
    "food_level": ("food",),
    "building_materials": ("building_materials",),
    "shelter_complete": ("building_materials",),
    "wooden_pickaxe": ("tools",),
    "stone_pickaxe": ("tools",),
    "wooden_axe": ("tools",),
    "stone_axe": ("tools",),
    "tool_tier": ("tools",),
}


def _count_band(count: int) -> str:
    return "one" if count <= 1 else "few" if count <= 3 else "many"


def _confidence_band(confidence: float) -> str:
    return "high" if confidence >= 0.8 else "medium"


def context_signature(
    *,
    observation: MinecraftPercepts | Mapping[str, Any] | None,
    place: Mapping[str, Any] | None,
    desired_facts: Sequence[str],
    source_goal_type: str | None,
) -> dict[str, Any]:
    """`context_signature_v1`: coarse, Person-visible, deterministic."""
    observation = _sections(observation)
    vitals = (observation or {}).get("vitals", {})
    environment = (observation or {}).get("environment", {})
    nearby = (observation or {}).get("nearby", {})
    threats: dict[str, dict[str, Any]] = {}
    for hostile in nearby.get("hostiles", []):
        kind = str(hostile.get("name") or hostile.get("kind"))
        entry = threats.setdefault(kind, {"count": 0, "nearest": hostile.get("rangeBand")})
        entry["count"] += 1
    categories = (observation or {}).get("inventory", {}).get("categories", {})
    relevant = sorted({c for fact in desired_facts for c in INVENTORY_FOR_FACT.get(fact, ())})
    recognised = place is not None and float(place.get("confidence", 0.0)) >= 0.5
    return {
        "schema": CONTEXT_SIGNATURE_SCHEMA,
        "health": health_band(float(vitals.get("health", 20.0))),
        "food": food_band(float(vitals.get("food", 20.0))),
        "breath": breath_band(float(vitals.get("breath", 10.0))),
        "day_phase": str(environment.get("dayPhase", "unknown")),
        "weather": str(environment.get("weather", "unknown")),
        "place": (
            {
                "ref": str(place["place_id"]),
                "confidence": _confidence_band(float(place["confidence"])),
            }
            if recognised and place is not None
            else "unknown"
        ),
        "threats": [
            {"kind": kind, "count": _count_band(entry["count"]), "nearest": entry["nearest"]}
            for kind, entry in sorted(threats.items())
        ],
        "inventory": {
            category: "some" if categories.get(category) else "0" for category in relevant
        },
        "source_goal_type": source_goal_type or "none",
    }
