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
node apps/cli/src/bin/person.ts validate my-world.toml
bash scripts/lan-check.sh my-world.toml
node apps/cli/src/bin/person.ts observe --config my-world.toml --out first-contact.json
node apps/cli/src/bin/person.ts run --config my-world.toml
```

`person-cognition` is never run by hand; the runtime spawns it.

## The ladder

### 1. Peaceful world, connection and one observation

Set `difficulty` to Peaceful and `runtime.trainingContext` to
`minecraft_peaceful`. Then:

```
node apps/cli/src/bin/person.ts observe --config my-world.toml --out first-contact.json
```

`observe` connects, waits for the world to actually be usable, takes one
observation, validates it against the protocol schema and disconnects. It runs
no skill, so it is the smallest thing that can go wrong.

Check in order:

- the command exits zero and says the observation is valid;
- connection is refused with a clear reason if the world is in creative, in the
  wrong dimension, at the wrong difficulty, or has a frozen daylight cycle;
- position, dimension, day phase, light level and biome match what you see;
- `nearby` counts resources, animals and containers you can also see;
- nothing in the printed summary looks like a placeholder.

Then compare it against a fixture capture, which flags fields that are valid
and empty:

```
node apps/cli/src/bin/person.ts observe --config examples/fixture.toml --out fixture.json
node apps/cli/src/bin/person.ts compare fixture.json first-contact.json
```

Structural findings matter: a field present in one and missing from the other
means the real body cannot populate something cognition expects. Value
differences between two different worlds are ordinary. Anything marked
`suspicious` is a field that may never have been written.

Only once this is clean, start a run with `runtime.maxDecisions = 1` and check
that the episode report contains one decision with a semantic context, a goal
and a routine.

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

### 3. Evidence, timing and prediction error after each skill

After each skill:

```
node apps/cli/src/bin/person.ts inspect evidence --config my-world.toml
node apps/cli/src/bin/person.ts inspect predictions --config my-world.toml
```

The evidence counts should move by exactly one attempt for the skill that ran,
and the executed skill should be the one you watched.

The episode report now carries a `tickBudgets` section: runs, mean and maximum
elapsed ticks, the split between navigation and interaction, and how close the
run came to its budget. **This is the first time those numbers mean anything**,
because fixture ticks are invented. Record them.

A budget is only revised when the measurement shows the budget is the reason.
Work through the alternatives first: an unrealistic budget, bad navigation, bad
target selection, server latency, or completion evidence that is wrong. Node
still clamps limits downward and never upward.

Prediction error will be noisy at first and that is the point. A skill that
succeeds can still have been wrong about what it would achieve, and a skill
that fails can have been right. Look for `inverted` records on skills that
succeeded: those are contracts that are lying.

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
