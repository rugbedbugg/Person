"""Derive the symbolic planning state from a semantic Observation.

The planner reasons over a flat table of named numbers, not over the
observation itself. Keeping the derivation in one readable function is what
makes a plan inspectable: every precondition in every SkillSpec names a fact
that appears here.

Some of those facts are evidence: only current perception can establish them,
and no skill claims to produce them. A count of zero for one of them means
"not seen", and nothing more. `evidence_percepts` names the percepts behind
each, including the ones in the corner of the eye, which are leads rather than
identifications and never count towards the fact itself.
"""

from __future__ import annotations

from typing import Any

PLANT_FOOD = {"apple", "sweet_berries", "carrot"}


def _count(items: list[dict[str, Any]], predicate: Any) -> int:
    return sum(item["count"] for item in items if predicate(item["name"]))


def evidence_percepts(observation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Every percept that bears on each evidence fact, central or peripheral.

    Relevance is decided here, above the firewall, from what the observation
    says: the body never marks anything as interesting.
    """
    nearby = observation["nearby"]
    permissions = observation["permissions"]

    def resources(kind: str) -> list[dict[str, Any]]:
        return [
            resource
            for resource in nearby["resources"]
            if resource["kind"] == kind and resource["harvestPermitted"]
        ]

    return {
        "reachable_wood": resources("wood"),
        "reachable_stone": resources("stone"),
        "reachable_coal": resources("coal"),
        "reachable_plant_food": resources("plant_food"),
        "reachable_animal": [
            animal for animal in nearby["passiveAnimals"] if not animal["protectedTarget"]
        ],
        "permitted_container_nearby": [
            container
            for container in nearby["containers"]
            if container["provenance"] == "existing" and permissions["withdrawExisting"]
        ],
    }


def recognised(percepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only what Person is looking at is identified well enough to act on."""
    return [percept for percept in percepts if percept["detail"] == "central"]


def symbolic_state(observation: dict[str, Any]) -> dict[str, float]:
    inventory = observation["inventory"]
    items = inventory["items"]
    categories = inventory["categories"]
    nearby = observation["nearby"]
    home = observation["home"]
    permissions = observation["permissions"]
    affordances = observation["affordances"]
    vitals = observation["vitals"]

    hostiles = nearby["hostiles"]
    hazards = nearby["hazards"]
    immediate_threat = any(entity["distance"] <= 7 for entity in hostiles)
    close_hazard = any(hazard["distance"] <= 2 for hazard in hazards)

    shelter_state = home["shelterState"]
    home_distance = home["homeDistance"]
    at_home = home_distance is not None and home_distance <= 2

    evidence = {
        fact: float(len(recognised(percepts)))
        for fact, percepts in evidence_percepts(observation).items()
    }

    tool_tier = 0
    for item in items:
        if item["name"].endswith("_pickaxe"):
            prefix = item["name"].removesuffix("_pickaxe")
            tool_tier = max(
                tool_tier, {"wooden": 1, "stone": 2, "iron": 3, "diamond": 4}.get(prefix, 0)
            )

    owned_furnace = any(
        station["kind"] == "furnace" and station["provenance"] == "owned"
        for station in nearby["workstations"]
    )
    owned_table = any(
        station["kind"] == "crafting_table" and station["provenance"] == "owned"
        for station in nearby["workstations"]
    )

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
        "tool_tier": tool_tier,
        "food_level": vitals["food"],
        "health_level": vitals["health"],
        "inventory_space": inventory["freeSlots"],
        "safe": 0.0 if (immediate_threat or close_hazard) else 1.0,
        "sheltered": 1.0 if (shelter_state == "complete" and at_home) else 0.0,
        "shelter_complete": 1.0 if shelter_state == "complete" else 0.0,
        "shelter_known": 1.0 if shelter_state in {"complete", "partial", "breached"} else 0.0,
        "home_known": 1.0 if home["activeHome"] is not None else 0.0,
        "at_home": 1.0 if at_home else 0.0,
        "furnace_placed": 1.0 if owned_furnace else 0.0,
        "owned_storage_available": 1.0 if home["ownedStorage"] else 0.0,
        # Evidence: recognised percepts only. Hostiles and hazards above count
        # in the periphery too, because noticing a threat needs no
        # identification, while acting on a target does.
        **evidence,
        "diggable_ground": 1.0 if affordances["diggableGround"] else 0.0,
        "harvesting_permitted": 1.0 if permissions["harvest"] else 0.0,
        "building_permitted": 1.0 if permissions["build"] else 0.0,
        "hunting_permitted": 1.0 if permissions["huntPassive"] else 0.0,
        "rested": 0.0,
        "stored_surplus": 0.0,
        "withdrawn": 0.0,
        "looted": 0.0,
    }
