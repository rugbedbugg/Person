# Skills

A skill is the smallest cognitive action available to planning. It is not a
movement primitive: cognition can ask for `gather_wood(target_amount=16)`, and
cannot ask to walk forward, turn, or break a block at a coordinate.

Each skill exists in two halves that are checked against each other:

- a **SkillSpec**, canonical JSON in `packages/skills/specs/`, read by the
  planner and enforced by the runtime;
- an **implementation**, TypeScript in
  `apps/node-runtime/src/skills/impl/`, written against the embodiment port.

An architecture test asserts the two sets are identical, so a spec without an
implementation, or an implementation without a spec, fails the build.

## The contract

```json
{
  "id": "gather_wood",
  "version": 1,
  "category": "resources",
  "parameters": {
    "target_amount": {
      "type": "integer",
      "minimum": 1,
      "maximum": 64,
      "default": 8
    }
  },
  "preconditions": [{ "fact": "reachable_wood", "op": ">=", "value": 1 }],
  "expectedEffects": [
    { "fact": "wood", "op": "+=", "value": 8, "scalesWith": "target_amount" }
  ],
  "possibleFailures": ["unreachable_resource", "inventory_full", "timed_out"],
  "requiredPermissions": ["harvest_resource"],
  "costLimits": { "maxTicks": 2400, "maxDistance": 64, "minHealth": 6 },
  "interruptionPolicy": "preemptible",
  "completionEvidence": ["inventory_delta", "harvested_blocks"],
  "risk": 0.2,
  "emergency": false
}
```

`preconditions` and `expectedEffects` name facts from
`packages/skills/specs/facts.json`. Those facts are the planner's whole
vocabulary, and the registry refuses a spec that invents one.

## The library

| Category   | Skills                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------- |
| Emergency  | `flee`, `dig_in`, `wait_safely`, `return_home`                                                     |
| Food       | `gather_plant_food`, `hunt_safe_passive_animals`, `cook_food`, `eat_to_target`                     |
| Resources  | `gather_wood`, `mine_stone`, `mine_coal`                                                           |
| Crafting   | `craft_basic_tools`, `craft_stone_tools`, `craft_furnace`, `craft_chest`                           |
| Shelter    | `build_basic_shelter`, `repair_shelter`                                                            |
| Storage    | `place_owned_chest`, `deposit_owned_storage`, `withdraw_owned_storage`, `loot_permitted_container` |
| Perception | `look_around`, `look`                                                                              |

## One implementation, two bodies

Skills are written against the `Embodiment` port, not against Mineflayer. Two
implementations exist: `MineflayerEmbodiment` drives a real 1.16.1 client, and
`FixtureWorld` is a deterministic simulation. A fixture test therefore exercises
the same skill code that runs against Minecraft, rather than a parallel
imitation of it.

The fixture is not a Minecraft replica and does not pretend to be. It models
blocks, inventory, containers, crafting, smelting, hunger, damage, hostile
pursuit, day phase and scripted events, with every rule visible in
`fixtures/src/`. What it cannot tell you is whether a real server accepts a
placement, whether pathfinder finds a route around real terrain, or how a mob
actually behaves. Those belong to `docs/LAN_TESTING.md`.

## Terminal states

Every execution ends in exactly one of `SUCCESS`, `FAILED`, `INTERRUPTED`,
`PREEMPTED`, `TIMED_OUT`, `INVALIDATED`, `UNREACHABLE`, `DEATH`,
`DISCONNECTED`.

The runner, not the individual skill, enforces the bounds. Every
`context.checkpoint()` re-reads the world and re-checks the tick budget, the
health floor, whether Person is still alive and connected, and whether the
safety kernel wants control. A skill author cannot forget the bounds, because
they are not the skill author's job.

## Hunting

`hunt_safe_passive_animals` targets unnamed, untamed passive animals only, for
food. Players, villagers, named animals and tamed animals are refused by the
permission gate, which is consulted when a target is chosen and again when it
is attacked. The embodiment guard refuses a forbidden target even if a skill
asks. Combat with players is out of scope and has no configuration path.

## Storage

`deposit_owned_storage` requires a provenance record showing Person placed the
container itself. Containers Person did not place have no record, so there is
no code path that authorises a deposit into one. `loot_permitted_container`
withdraws from a pre-existing container when configuration allows it, and has
no deposit path at all.
