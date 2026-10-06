"""Minecraft percepts: the observation payload, typed, as perception (ADR 0025, 0026).

This is where a Minecraft `Observation` crosses the epistemic boundary. The
payload has already passed through the runtime's perception firewall (ADR
0002): it carries no coordinate, no entity handle and nothing the body could
not sense. `perceive` turns it into a `PerceptualState` whose percepts are
this module's `MinecraftPercepts`, and nothing downstream reads the raw
message again.

The payload mixes three channels, and they are kept apart here because they
are different kinds of information:

    sensed     vision and the sky: `nearby` (except workstations) and
               `environment`. Current, bounded, and possibly wrong.
    body       proprioception and interoception: `vitals` and `inventory`.
               What Person feels of itself; it feeds the SelfState.
    reported   the trusted runtime's records of Person's own works and
               standing: workstations and `home` (the placement ledger),
               `permissions`, `affordances`, `navigation`. Not senses; they
               reach beliefs as `Source.RUNTIME_REPORT`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict, cast

from person_epistemics import ExperienceKey, PerceptualState, Source

Bearing = Literal[
    "ahead", "ahead_left", "ahead_right", "left", "right", "behind_left", "behind_right", "behind"
]
Detail = Literal["central", "peripheral"]


class RelativePercept(TypedDict):
    bearing: Bearing
    elevation: Literal["above", "level", "below"]
    rangeBand: Literal["reach", "near", "mid", "far"]
    distance: float
    detail: Detail


class EntityPercept(RelativePercept):
    name: NotRequired[str]
    named: NotRequired[bool]
    tamed: NotRequired[bool]
    protectedTarget: NotRequired[bool]
    username: NotRequired[str]


class ResourcePercept(RelativePercept):
    kind: Literal["wood", "stone", "coal", "plant_food", "dirt", "other"]
    name: NotRequired[str]
    harvestPermitted: bool


class ContainerPercept(RelativePercept):
    kind: str
    provenance: Literal["owned", "existing"]
    storageId: str | None


class WorkstationRecord(RelativePercept):
    kind: str
    provenance: Literal["owned", "existing"]
    source: Literal["placement_ledger"]


class HazardPercept(RelativePercept):
    kind: str


class ItemStack(TypedDict):
    name: str
    count: int


class Vitals(TypedDict):
    health: float
    food: float
    breath: int
    armor: float
    statusEffects: list[dict[str, Any]]
    alive: bool


class Sky(TypedDict):
    dimension: str
    dayPhase: Literal["dawn", "day", "dusk", "night"]
    timeOfDay: int
    weather: Literal["clear", "rain", "thunder"]
    lightLevel: int
    biome: str


class Inventory(TypedDict):
    items: list[ItemStack]
    categories: dict[str, int]
    freeSlots: int


class Nearby(TypedDict):
    resources: list[ResourcePercept]
    hostiles: list[EntityPercept]
    passiveAnimals: list[EntityPercept]
    players: list[EntityPercept]
    containers: list[ContainerPercept]
    workstations: list[WorkstationRecord]
    hazards: list[HazardPercept]


class OwnedStorage(TypedDict):
    storageId: str
    contents: list[ItemStack]


class Home(TypedDict):
    activeHome: dict[str, str] | None
    shelterState: Literal["none", "partial", "complete", "breached", "unknown"]
    ownedStorage: list[OwnedStorage]
    bedKnown: bool
    foodReserve: int
    fuelReserve: int


class Navigation(TypedDict):
    routeStatus: str
    pathRisk: str
    stuckState: str
    returnPathKnown: bool


@dataclass(frozen=True, slots=True)
class MinecraftPercepts:
    """One Minecraft observation's payload, typed and divided by channel."""

    message_id: str
    # sensed
    nearby: Nearby
    sky: Sky
    # body
    vitals: Vitals
    inventory: Inventory
    # reported by the trusted runtime
    home: Home
    permissions: dict[str, bool]
    affordances: dict[str, bool]
    navigation: Navigation

    @property
    def night(self) -> bool:
        return self.sky["dayPhase"] in {"dusk", "night"}


def perceive(observation: Mapping[str, Any]) -> PerceptualState[MinecraftPercepts]:
    """The epistemic boundary for one Minecraft observation.

    Reads the validated message once. What comes out is current perception
    and nothing else: no belief, no memory, no world truth.
    """
    payload = cast(Mapping[str, Any], observation["payload"])
    percepts = MinecraftPercepts(
        message_id=str(observation["messageId"]),
        nearby=cast(Nearby, payload["nearby"]),
        sky=cast(Sky, payload["environment"]),
        vitals=cast(Vitals, payload["vitals"]),
        inventory=cast(Inventory, payload["inventory"]),
        home=cast(Home, payload["home"]),
        permissions=cast(dict[str, bool], payload["permissions"]),
        affordances=cast(dict[str, bool], payload["affordances"]),
        navigation=cast(Navigation, payload["navigation"]),
    )
    return PerceptualState(
        message_id=str(observation["messageId"]),
        tick=int(observation["tick"]),
        world_id=str(observation["worldId"]),
        experience=ExperienceKey.from_message(observation["experience"]),
        self_motion=observation["selfMotion"],
        previous_outcome=observation["previousOutcome"],
        percepts=percepts,
        source=Source.REAL_OBSERVATION,
    )
