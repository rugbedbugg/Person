# Manual Minecraft validation

Nothing in the automated suite proves that Person works against a real
Minecraft server. The fixture world exercises the same skill code, but it is a
simulation with rules written in `fixtures/src/`, not Minecraft. This document
is the ladder that closes that gap, and `IMPLEMENTATION_REPORT.md` records which
rungs have actually been climbed.

## Before you start

Use a disposable world. Person places blocks, digs, crafts, and kills animals.
It never issues commands, never teleports, never grants items, never resets a
save, and never touches a container it did not place, but it does change the
world it is in.

Requirements:

- Minecraft Java Edition 1.16.1, single player, opened to LAN.
- Normal or Peaceful difficulty, natural daylight cycle, cheats off.
- A dedicated offline bot identity, not your own account.
- `authorization` in the configuration set to true on every field, which is an
  assertion by you that this world is yours and that the resource areas are
  unowned.

Copy `examples/minecraft-lan.toml`, set `server.port` to the port Minecraft
shows when you open to LAN, set `world.home` to a flat spot with a solid three
by three floor, and set `world.exploration` to a box you are happy for Person
to work inside.

```
uv run person-cognition --config my-world.toml    # never run directly; the runtime spawns it
node apps/cli/src/bin/person.ts validate my-world.toml
node apps/cli/src/bin/person.ts run --config my-world.toml
```

## The ladder

### 1. Peaceful world, connection and observation

Set `difficulty` to Peaceful. Start a run with `runtime.maxDecisions = 1`.

Check: Person connects, spawns inside the exploration bounds, and the episode
report contains one decision with a semantic context, a goal and a routine.
Nothing should be broken or placed yet beyond the first skill.

### 2. Each skill individually

Give Person a starting inventory by hand where a skill needs one, and use a
one-decision run for each. Work through the library in this order, since later
ones depend on earlier ones:

```
gather_wood        gather_plant_food     hunt_safe_passive_animals
craft_basic_tools  mine_stone            mine_coal
craft_stone_tools  craft_furnace         cook_food             eat_to_target
build_basic_shelter  repair_shelter
craft_chest        place_owned_chest     deposit_owned_storage
withdraw_owned_storage  loot_permitted_container
return_home        wait_safely           flee                  dig_in
```

For each: read the `SkillOutcome` in the episode report, and compare
`inventoryDelta`, `completionEvidence` and `elapsedTicks` against what you can
see in the world. This is the step the fixture cannot do for you, because it is
where Mineflayer, the server and real terrain disagree with a simulation.

Watch specifically for:

- placement refusals, where the server rejects a block the client thought it
  placed;
- pathfinder giving up on terrain the fixture would have walked;
- furnace timing, which the adapter waits on with a generous margin;
- drops that land somewhere the collector does not reach.

### 3. Evidence before and after

After each skill, run `person inspect evidence --config my-world.toml`. The
counts should move by exactly one attempt for the skill that ran, and the
executed skill should be the one you watched.

### 4. A complete survival routine

Peaceful world, a full run. Person should reach food, shelter, tools, a
furnace, cooked food and owned storage without intervention.

### 5. Normal difficulty

Switch to Normal. Watch the safety kernel: hostiles should produce
`EmergencyEvent` records, the requested skill should be marked `PREEMPTED`, and
`flee` or `dig_in` should be what the outcome credits.

### 6. No cheats, no intervention

Confirm that nothing in the run required an operator to place, give or teleport.

### 7. Multiple Minecraft days

A long run across several day and night cycles, with a process restart in the
middle. Person should shelter at night, resume its goals in the morning, and
its evidence should be one unbroken chain across the restart.

## What is still unverified until you do this

- Mineflayer connection, authentication and spawn validation against a server.
- Pathfinder behaviour on real terrain, including the guard rejecting steps into
  protected areas during live replanning.
- Server-side placement, crafting, smelting and container transfers.
- Real mob behaviour, damage, and whether the flee clearances are large enough.
- Whether the tick budgets in the skill specs are realistic at real tick rates.
- Death and respawn handling in a live world.
