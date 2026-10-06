"""Which Minecraft percepts bear on persistent beliefs, and as what (ADR 0026).

Only the runtime's reports of Person's own works become beliefs here: whether
it has a home, the state of its shelter, its storage, its furnace and its
crafting table, and the food it has stored. They are about this world only,
so each is scoped to it, and each rests on the observation that reported it.

What Person sees in passing (a tree, a cow, coal) does not become a belief
here at all: it is current perception, used while it is perceived, and it is
remembered as an episode. Remembering coal is not believing coal is there.
"""

from __future__ import annotations

from person_epistemics import EpistemicEvidence, PerceptualState, Scope, Source, admit

from .perception import MinecraftPercepts

#: The fact beliefs Minecraft revises from runtime reports.
BELIEF_KEYS: tuple[str, ...] = (
    "home_known",
    "shelter_state",
    "owned_storage",
    "owned_furnace",
    "owned_crafting_table",
    "food_reserve",
)


def belief_evidence(
    state: PerceptualState[MinecraftPercepts], now: int
) -> tuple[EpistemicEvidence, ...]:
    percepts = state.percepts
    home = percepts.home
    stations = percepts.nearby["workstations"]

    def owned(kind: str) -> bool:
        return any(
            station["kind"] == kind and station["provenance"] == "owned" for station in stations
        )

    values: dict[str, bool | int | str] = {
        "home_known": home["activeHome"] is not None,
        "shelter_state": str(home["shelterState"]),
        "owned_storage": len(home["ownedStorage"]),
        "owned_furnace": owned("furnace"),
        "owned_crafting_table": owned("crafting_table"),
        "food_reserve": int(home["foodReserve"]),
    }
    scope = Scope.world(state.experience.environment_kind, state.world_id)
    return tuple(
        admit(
            bears_on=key,
            value=values[key],
            source=Source.RUNTIME_REPORT,
            scope=scope,
            observed_at=now,
            confidence=1.0,
            refs=(state.message_id,),
            experience=state.experience,
        )
        for key in BELIEF_KEYS
    )
