"""The Minecraft planning facts, derived from a DecisionState (ADR 0026).

The planner reasons over a flat table of named numbers, the facts every
SkillSpec precondition and effect names (`skills/facts.json`). This module is
the one place they are derived, and it derives each from the epistemic view
it belongs to:

    evidence facts     current perception, recognised percepts only
                       (`reachable_*`, `permitted_container_nearby`)
    threat (`safe`)    current perception, periphery included: noticing a
                       threat needs no identification
    holdings, vitals   the body channel of current perception
    shelter, home,     beliefs, revised from the runtime's reports of
    storage, stations  Person's own works (`beliefs.py`)
    at home            the self-state: Person's own spatial estimate (C8)
    permissions        the runtime's current report of what it permits

These are facts about now, so memory never sets one. A recalled episode about
coal does not make coal reachable: planning may consult
`DecisionState.recalled` (memory as the loop's bounded recall supplied it),
but a planning fact is never derived from it, and an architecture test holds
the facts identical with and without recalled memories.

Before ADR 0026 these facts came from `person_planner.symbolic_state`, which
read the raw observation for everything. The values are the same for every
observation that carries the reported channels, which every Minecraft
observation does; what changed is where each one is allowed to come from.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from person_epistemics import DecisionState, PerceptualState

from .perception import MinecraftPercepts

PLANT_FOOD = {"apple", "sweet_berries", "carrot"}

#: Facts only current perception establishes. No skill produces them, a test
#: asserts that, and a zero means "not seen" rather than "not there". The same
#: list is `factClasses.evidence` in `skills/vocabulary.json`.
EVIDENCE_FACTS: frozenset[str] = frozenset(
    {
        "reachable_wood",
        "reachable_stone",
        "reachable_coal",
        "reachable_plant_food",
        "reachable_animal",
        "permitted_container_nearby",
    }
)

Decision = DecisionState[MinecraftPercepts, Any]


def _count(items: Sequence[Mapping[str, Any]], predicate: Callable[[str], bool]) -> int:
    return sum(int(item["count"]) for item in items if predicate(str(item["name"])))


def evidence_percepts(percepts: MinecraftPercepts) -> dict[str, list[dict[str, Any]]]:
    """Every percept that bears on each evidence fact, central or peripheral.

    Relevance is decided here, above the firewall, from what Person perceives:
    the body never marks anything as interesting.
    """
    nearby = percepts.nearby
    permissions = percepts.permissions

    def resources(kind: str) -> list[dict[str, Any]]:
        return [
            dict(resource)
            for resource in nearby["resources"]
            if resource["kind"] == kind and resource["harvestPermitted"]
        ]

    return {
        "reachable_wood": resources("wood"),
        "reachable_stone": resources("stone"),
        "reachable_coal": resources("coal"),
        "reachable_plant_food": resources("plant_food"),
        # Whose an animal is shows only on one Person is looking at, so a shape
        # in the periphery stays a lead until it is recognised as someone's.
        "reachable_animal": [
            dict(animal)
            for animal in nearby["passiveAnimals"]
            if animal["detail"] == "peripheral" or not animal.get("protectedTarget", True)
        ],
        "permitted_container_nearby": [
            dict(container)
            for container in nearby["containers"]
            if container["provenance"] == "existing" and permissions["withdrawExisting"]
        ],
    }


def recognised(percepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only what Person is looking at is identified well enough to act on."""
    return [percept for percept in percepts if percept["detail"] == "central"]


def perceived_threat(percepts: MinecraftPercepts) -> bool:
    nearby = percepts.nearby
    return any(entity["distance"] <= 7 for entity in nearby["hostiles"]) or any(
        hazard["distance"] <= 2 for hazard in nearby["hazards"]
    )


def tool_tier(percepts: MinecraftPercepts) -> int:
    tier = 0
    for item in percepts.inventory["items"]:
        if item["name"].endswith("_pickaxe"):
            prefix = item["name"].removesuffix("_pickaxe")
            tier = max(tier, {"wooden": 1, "stone": 2, "iron": 3, "diamond": 4}.get(prefix, 0))
    return tier


def evidence_facts(state: PerceptualState[MinecraftPercepts]) -> dict[str, float]:
    """The evidence facts alone: what current perception puts within reach."""
    return {
        fact: float(len(recognised(percepts)))
        for fact, percepts in evidence_percepts(state.percepts).items()
    }


def planning_facts(decision: Decision) -> dict[str, float]:
    """The planner's facts for one decision."""
    percepts = decision.percepts.percepts
    beliefs = decision.beliefs
    inventory = percepts.inventory
    items = inventory["items"]
    categories = inventory["categories"]
    permissions = percepts.permissions
    affordances = percepts.affordances
    vitals = percepts.vitals

    shelter_state = beliefs.value("shelter_state", "unknown")
    at_home = decision.self_state.home_relation == "at_home"
    owned_table = bool(beliefs.value("owned_crafting_table", False))

    return {
        "wood": categories["wood"],
        "planks": _count(items, lambda n: n.endswith("_planks")),
        "stone": categories["stone"],
        "coal": categories["coal"],
        "fuel": categories["fuel"],
        "raw_food": categories["raw_food"],
        "cooked_food": categories["cooked_food"],
        "plant_food": _count(items, lambda n: n in PLANT_FOOD),
        "edible_food": categories["food"],
        "building_materials": categories["building_materials"],
        "chest_item": _count(items, lambda n: n == "chest"),
        "crafting_table": _count(items, lambda n: n == "crafting_table")
        + (1 if owned_table else 0),
        "wooden_pickaxe": _count(items, lambda n: n == "wooden_pickaxe"),
        "stone_pickaxe": _count(items, lambda n: n == "stone_pickaxe"),
        "wooden_axe": _count(items, lambda n: n == "wooden_axe"),
        "stone_axe": _count(items, lambda n: n == "stone_axe"),
        "tool_tier": tool_tier(percepts),
        "food_level": vitals["food"],
        "health_level": vitals["health"],
        "inventory_space": inventory["freeSlots"],
        "safe": 0.0 if perceived_threat(percepts) else 1.0,
        "sheltered": 1.0 if (shelter_state == "complete" and at_home) else 0.0,
        "shelter_complete": 1.0 if shelter_state == "complete" else 0.0,
        "shelter_known": 1.0 if shelter_state in {"complete", "partial", "breached"} else 0.0,
        "home_known": 1.0 if beliefs.value("home_known", False) else 0.0,
        "at_home": 1.0 if at_home else 0.0,
        "furnace_placed": 1.0 if beliefs.value("owned_furnace", False) else 0.0,
        "owned_storage_available": 1.0 if int(beliefs.value("owned_storage", 0) or 0) else 0.0,
        # Evidence: recognised percepts only. Hostiles and hazards above count
        # in the periphery too, because noticing a threat needs no
        # identification, while acting on a target does.
        **evidence_facts(decision.percepts),
        "diggable_ground": 1.0 if affordances["diggableGround"] else 0.0,
        "harvesting_permitted": 1.0 if permissions["harvest"] else 0.0,
        "building_permitted": 1.0 if permissions["build"] else 0.0,
        "hunting_permitted": 1.0 if permissions["huntPassive"] else 0.0,
        "rested": 0.0,
        "stored_surplus": 0.0,
        "withdrawn": 0.0,
        "looted": 0.0,
    }
