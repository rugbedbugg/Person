# Reality validation

Milestone 1. Date: 2026-09-15.

## The headline, stated plainly

**No Minecraft server was reachable from the environment this work was done
in.** There is no Java process on the machine, nothing listening on the
configured LAN port, and no way to open a world from here. Every claim below
that involves a live server is therefore marked "not run", and none of them
should be read as validated.

What was done instead is the part of reality validation that does not need a
server: the Mineflayer adapter was audited line by line against the installed
`mineflayer` 4.39.0, `mineflayer-pathfinder` 2.4.5 and `minecraft-data` 1.16.1
sources, and the defects that audit found were fixed and covered by tests that
run the adapter against a double built on Minecraft's own data tables.

That audit found a defect that would have crashed Person on its first contact
with any real server, and five more that would have produced wrong behaviour.
None of them were visible to the fixture tests, which is exactly the gap this
milestone exists to close. The remaining gap, the one only a server can close,
is listed at the end and is still open.

> **Update, later the same day.** A LAN world was opened and Person connected
> to it. This headline is kept exactly as it was written, because it is the
> honest record of what Milestone 1 could and could not claim. What happened on
> first contact is recorded in [First contact](#first-contact) at the end.

## Environment

|                                       |                                                  |
| ------------------------------------- | ------------------------------------------------ |
| Minecraft server                      | none available; **no live validation performed** |
| Target version                        | Java Edition 1.16.1                              |
| Node                                  | 22.23.2 (pinned), 24.20.0 (host default)         |
| Python                                | 3.12.14                                          |
| mineflayer                            | 4.39.0                                           |
| mineflayer-pathfinder                 | 2.4.5                                            |
| minecraft-data                        | 3.116.0, 1.16.1 tables                           |
| prismarine-block / prismarine-windows | 1.23.0 / 2.10.0                                  |
| Difficulty, LAN configuration         | not applicable; see `docs/LAN_TESTING.md`        |
| Mods or plugins                       | none                                             |

## How the adapter was checked without a server

Three independent methods, none of which is a substitute for running the thing:

1. **Source audit.** Every Mineflayer call the adapter makes was checked against
   the installed library source: the field it reads, the shape it gets back, and
   the failure it can throw. Findings below cite the file that settled them.
2. **Authoritative data.** Recipes, entity categories, block bounding boxes and
   item ids come from the real `minecraft-data` 1.16.1 tables rather than from
   the adapter's assumptions. The nine recipes Person uses were verified against
   those tables, including which of them require a crafting table.
3. **A conformance double.** `tests/support/mineflayer-double.ts` presents the
   API shapes the audit established, backed by real `minecraft-data` and
   `prismarine-recipe`. Twenty-seven tests run the adapter against it. Where the
   double and the real client differ, the double is wrong and the tests are
   worth less; that risk is stated in the blockers.

To check the tests were worth anything, the original metadata defect was
reintroduced deliberately: five tests failed. They were then restored.

## Observation validation

`person observe --config <file>` connects, normalises one observation,
validates it against the protocol schema and stops. It is the smallest thing
that can be done against a live server. `person compare <reference> <actual>`
diffs a capture against a reference and flags fields that look like defaults
nothing ever wrote.

Running the pair against the fixture found three fields that were structurally
valid and semantically empty:

| Field                    | Was                    | Now                                                                                 |
| ------------------------ | ---------------------- | ----------------------------------------------------------------------------------- |
| `vitals.armor`           | hard-coded `0`         | summed from the equipped armour slots, using 1.16.1 armour values                   |
| `environment.biome`      | hard-coded `"unknown"` | read from the block Person is standing on                                           |
| `environment.lightLevel` | guessed from the clock | read from block light, falling back to the clock only when the server has sent none |

`dimension` was hard-coded to `"overworld"` and is now read from
`bot.game.dimension`, with the `minecraft:` prefix stripped as mineflayer
already does.

Every other observation field was traced to a real source. The comparison tool
retains its list of suspicious defaults, so the same check can be run against a
real capture the moment one exists.

## Findings

Six defects, none of which the fixture tests could have revealed. Each is
described with the evidence that settled it.

### 1. Entity metadata is an object, not an array (fatal)

`lib/plugins/entities.js:936` parses metadata with
`entityMetadata[key] = value`, producing a sparse object keyed by metadata
index. The adapter called `.some()` on it. Against any real server the first
entity carrying metadata would have thrown `TypeError: metadata.some is not a
function` inside the observation builder, taking the observation, the decision
and the episode with it.

Fixed by reading index 2, which carries the optional custom name in 1.16.1,
and handling the string, chat-component and absent cases.

### 2. Named animals were never detected (safety)

The same code scanned for any string anywhere in metadata, which is not where a
custom name lives and would not have matched one. The permission gate refuses
named animals, so the gate was correct and the input to it was not: a named cow
was a legal hunting target.

Fixed with the same change. A custom-name value of an unrecognised shape is now
treated as named, because the cost of being wrong in that direction is a missed
meal and the cost of the other is killing something that belonged to somebody.

### 3. Hostile classification missed mobs the registry files as unknown

The adapter used a hand-written set. Checked against `minecraft-data` 1.16.1,
the registry has a "Hostile mobs" category of thirty-two entries, and files
`hoglin`, `zoglin`, `piglin`, `zombified_piglin`, `bee` and `fox` under
"UNKNOWN". Hoglins and zoglins attack on sight and were not in the adapter's
set, so the safety kernel would not have fled from them.

Fixed by taking hostility from the registry category plus an explicit list of
hostile-on-sight mobs the registry does not categorise. The huntable set stays a
short explicit allowlist that no data source can widen.

### 4. Neutral mobs were invisible to the safety kernel

Wolves, polar bears, bees and iron golems are "Passive mobs" by category and
perfectly capable of killing an unarmoured player once provoked. Treating them
as hostile on sight would leave Person fleeing from a llama indefinitely;
ignoring them leaves it standing still while a wolf pack kills it.

Fixed by adding a `neutral` classification and a `recentlyDamaged` signal
derived from the health event. A neutral mob becomes a threat only once Person
has actually taken damage, which is the honest signal the world provides.

### 5. The first withdrawal from any container always failed

`containerAt` returns a cached view that starts empty. The withdrawal skills
read it to decide what to take, concluded "nothing", and threw
`empty_container` from a chest that was full. Against a real server the
contents only exist once the window is open.

Fixed by adding `inspectContainer` to the embodiment port, implemented by both
bodies, and using it in `withdraw_owned_storage` and
`loot_permitted_container`. Mineflayer's plain `Error("Unable to withdraw, Bot
inventory is full.")` is now mapped to an `inventory_full` reason instead of
arriving as `unexpected_error`.

### 6. Crafting could fail on its own bookkeeping

The adapter looked the recipe up in Person's static table keyed by the wood
species it currently held the most of. When the planner had chosen oak planks
and the inventory had since tilted towards birch, the lookup missed and the
craft failed with "No Person recipe".

Fixed by asking the server which recipes are possible, which is also the
authority on whether a table is required: `recipesFor(id, null, n, null)` returns
only table-free recipes that current inventory can actually make. The static
table remains for the planner and the fixture, and was verified against the real
1.16.1 tables for all nine recipes, table requirements included.

### Smaller corrections found in the same pass

- `freeSlots` was `36 - stacks`, which over-reports capacity as soon as any
  stack is partially filled. Now `bot.inventory.emptySlotCount()`.
- A craft that produced nothing, and a smelt that produced nothing, both
  returned success. Both now fail explicitly.
- Smelting waited for the whole batch before taking any output, throwing away
  food that was already cooked if it timed out. It now collects output as it
  appears.
- Connection assumed that a spawn packet meant a usable world. It now waits
  explicitly for the entity, a valid position, loaded chunks under and around
  Person, the world clock, the inventory, vitals and the dimension, with a
  thirty-second bound and no reconnect loop.
- Game mode, dimension, difficulty and the daylight cycle are now validated at
  connect. Surviving in creative is not surviving, and a frozen clock makes the
  day phase the goal provider reasons about meaningless.
- `dig_in` could be chosen on flat open ground where no refuge can be dug. The
  snapshot now reports whether there is diggable ground, and the kernel chooses
  fleeing over digging when there is not.

## Skill matrix

Status vocabulary, used strictly:

- **Fixture**: exercised end to end in the deterministic fixture world.
- **Adapter**: the Mineflayer code path this skill depends on is exercised
  against the conformance double, which uses real Minecraft data tables.
- **Live**: run against a Minecraft server. **Nothing is marked live.**

| Skill                       | Fixture | Adapter                                   | Bugs found                                                               | Fix                                                         | Remaining caveat                                                            |
| --------------------------- | ------- | ----------------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------- | --------------------------------------------------------------------------- |
| `flee`                      | pass    | partial: `moveTo` guard, `attack`         | neutral mobs invisible; threat set inconsistent between kernel and skill | shared `kernel.threats()`; `neutral` plus `recentlyDamaged` | clearance targets tuned against a fixture whose mobs move deterministically |
| `dig_in`                    | pass    | `dig`, `place`                            | chosen where no refuge can be dug                                        | snapshot reports diggable ground; kernel prefers fleeing    | never tested against real terrain or suffocation risk                       |
| `wait_safely`               | pass    | `waitTicks`                               | none                                                                     | none                                                        | interruption proven in fixture only                                         |
| `return_home`               | pass    | `moveTo` guard, `dig`, `place`            | none new                                                                 | none                                                        | pathfinder behaviour on real terrain unknown                                |
| `gather_plant_food`         | pass    | `findBlocks`, `moveTo`, `dig`             | none new                                                                 | none                                                        | drop collection unverified against a real server                            |
| `hunt_safe_passive_animals` | pass    | entity classification, `attack`           | named animals undetected; metadata crash                                 | see findings 1, 2, 3, 4                                     | real mob flight and drop scatter unverified                                 |
| `cook_food`                 | pass    | `smelt`                                   | partial output discarded; empty smelt returned success                   | collect as ready; fail when nothing cooked                  | real furnace timing unverified                                              |
| `eat_to_target`             | pass    | `consume`                                 | contract claimed one item consumed                                       | corrected to three, with a documented residual error        | see prediction error below                                                  |
| `gather_wood`               | pass    | `findBlocks`, `moveTo`, `dig`, tool equip | none new                                                                 | none                                                        | tool durability unmodelled                                                  |
| `mine_stone`                | pass    | same as above                             | none new                                                                 | none                                                        | needs exposed stone; no dig-down skill                                      |
| `mine_coal`                 | pass    | same as above                             | none new                                                                 | none                                                        | same                                                                        |
| `craft_basic_tools`         | pass    | `craft`, `place`                          | wood-species recipe lookup; silent empty craft                           | server-authoritative recipes; explicit failure              | table placement site unverified on real terrain                             |
| `craft_stone_tools`         | pass    | `craft`                                   | same                                                                     | same                                                        | same                                                                        |
| `craft_furnace`             | pass    | `craft`, `place`                          | same                                                                     | same                                                        | same                                                                        |
| `craft_chest`               | pass    | `craft`                                   | same                                                                     | same                                                        | same                                                                        |
| `build_basic_shelter`       | pass    | `place`, `blockAt`                        | none new                                                                 | none                                                        | placement refusals and irregular terrain unverified                         |
| `repair_shelter`            | pass    | `place`, `blockAt`                        | none new                                                                 | none                                                        | same                                                                        |
| `place_owned_chest`         | pass    | `place`, provenance                       | none new                                                                 | none                                                        | real container entity behaviour unverified                                  |
| `deposit_owned_storage`     | pass    | `deposit` refusal                         | full-container mid-transfer lost progress                                | partial progress kept, errors mapped                        | slot handling against a real window unverified                              |
| `withdraw_owned_storage`    | pass    | `inspectContainer`, `withdraw`            | first withdrawal always failed                                           | `inspectContainer`                                          | same                                                                        |
| `loot_permitted_container`  | pass    | `inspectContainer`, `withdraw`            | same                                                                     | same                                                        | takes up to `amount` of every type it finds                                 |

Every row's Live column is "not run".

## Safety validation

Proven in the fixture and against the double:

| Rule                                                                             | Where                                                                                                                                                                           |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Protected-area harvest denial                                                    | `tests/safety/permissions.test.ts`                                                                                                                                              |
| Protected-area build denial, at the interaction                                  | same                                                                                                                                                                            |
| Protected-area movement denial                                                   | `tests/safety/protected-routes.test.ts`                                                                                                                                         |
| A legal start and a legal destination with an illegal straight line between them | same: a detour is found, and every step of it is legal                                                                                                                          |
| No legal detour means refusal, with Person not moved part of the way             | same                                                                                                                                                                            |
| Replanning cannot cross a protected area                                         | same: the guard is installed as pathfinder's step-exclusion function, which the search consults on every node of every re-plan; the test calls it directly and asserts the cost |
| Breaking and placing along a route refused outright                              | same                                                                                                                                                                            |
| Existing-container deposit denial                                                | permissions, storage and conformance suites, plus the configuration schema                                                                                                      |
| Owned-container deposit and withdrawal                                           | storage and conformance suites                                                                                                                                                  |
| Villager, named-animal and tamed-animal protection                               | permissions and conformance suites                                                                                                                                              |
| Player combat denial                                                             | permissions suite, plus a schema constant with one legal value                                                                                                                  |
| Hostile emergency preemption, with attribution to what ran                       | `tests/safety/attribution.test.ts`                                                                                                                                              |
| Refuge chosen only where a refuge can exist                                      | `tests/safety/kernel.test.ts`                                                                                                                                                   |

**None of this has been proven against a Minecraft server.** The mechanisms are
the same ones a server would exercise, and the pathfinder exclusion test checks
the actual integration point rather than a reimplementation of it, but the
server has not had a chance to disagree.

## Tick budget findings

Timing is now measured by wrapping the embodiment port, so every skill is
instrumented without any skill having to remember to be. Each outcome carries
navigation, interaction and waiting ticks, the budget it was given, and the
pressure it put on that budget; the episode report aggregates per skill.

From a twelve-decision fixture episode:

| Skill                 | Budget | Mean | Max | Pressure | Navigation | Interaction |
| --------------------- | ------ | ---- | --- | -------- | ---------- | ----------- |
| `eat_to_target`       | 400    | 192  | 192 | 0.48     | 0          | 192         |
| `flee`                | 600    | 138  | 212 | 0.35     | 138        | 0           |
| `gather_wood`         | 2400   | 452  | 452 | 0.19     | 68         | 384         |
| `craft_stone_tools`   | 1200   | 204  | 204 | 0.17     | 180        | 24          |
| `mine_stone`          | 3000   | 404  | 404 | 0.13     | 20         | 384         |
| `build_basic_shelter` | 3600   | 198  | 198 | 0.06     | 48         | 150         |
| `craft_basic_tools`   | 1200   | 14   | 14  | 0.01     | 0          | 14          |

**No budget was changed on the strength of these numbers, and none should be.**
The fixture's tick costs are invented: four ticks a step, twelve a dig. What
transfers is the instrument, not the measurements. When a real world is
available, the same table will say something meaningful, and the decision rule
is already written down: a budget is only revised when the measurement shows
the budget is the reason, rather than navigation, target selection, latency or
completion evidence being wrong.

## Prediction error findings

Prediction error compares each skill contract's declared effects against the
symbolic state the next observation reports. It is recorded as append-only
evidence under a compatibly widened schema, summarised in both reports, and
readable with `person inspect predictions`. It changes no policy: the statistics
reducer has no case for it, and a test replays a journal with and without the
records and asserts the statistics are identical.

It paid for itself immediately. From an eleven-prediction fixture episode:

```
recorded=11 none=9 major=1 inverted=1

major eat_to_target:
  food_level  predicted 18  observed 19
  edible_food predicted  5  observed  0

inverted craft_basic_tools:
  planks         predicted 8  observed 0
  wooden_pickaxe predicted 1  observed 0
  tool_tier      predicted 1  observed 0
```

Two different things, correctly distinguished:

- The `craft_basic_tools` record is a **failed skill**, preempted by a hostile
  and then failing outright. The contract was right and the world did not
  cooperate. Prediction error is not the same as skill failure, and the record
  reflects a real failure rather than a modelling defect.
- The `eat_to_target` record is a **wrong contract**. Eating to a target
  consumes several items, not one, and the spec said one. Corrected to three,
  with `food_level` now scaling with the requested target. The residual error
  remains and is a known limitation: the number of items eaten depends on the
  deficit and the food's value, which the effect language cannot express, so the
  contract carries a central estimate and the instrument keeps reporting the
  gap. Tuning the number until the error disappeared would be fitting one
  food type and lying about the rest.

## Planner audit

Representative outputs were inspected for the six goals the milestone names.
One real defect and two acceptable oddities.

**Defect, fixed.** Plan cost ignored parameter magnitude, so every
parameterisation of a plan tied. The planner offered four copies of one strategy
differing only in how absurd the number was, the deterministic policy picked
arbitrarily among them, and the evidence for one strategy was split across four
routine identities. Cooking two items began by hunting twelve animals.

Cost now scales with the magnitude of a scaling parameter. Cooking now hunts
three animals and mines eight stone, and a genuinely different second strategy
appears: mine coal for fuel instead of gathering wood. Six regression tests
cover it.

**Acceptable.** Building a shelter is offered as a way to satisfy "be at home",
because building one truthfully ends with Person at home. It is an absurd way to
get home and is ranked last by cost. Removing the effect to tidy the candidate
list would make the contract lie, so it stays and the ordering handles it.

**Checked and sound.** No plan repeats a step without reason; plans use
materials Person already holds rather than gathering more; an unreachable goal
produces no plan rather than a fantasy one.

## Deterministic survival

Not attempted against Minecraft.

In the fixture, with learning off, Person secures food, builds a shelter,
crafts wooden then stone tools, places owned storage, deposits and withdraws,
cooks, and survives an injected hostile with the emergency correctly attributed
to `flee`. That was true before this milestone and remains true; it says
nothing about Minecraft.

## Shadow and supervised learning

Not attempted. Stage F requires deterministic survival to be credible in a real
world first, and it has not been run in one. Shadow-mode behaviour remains
covered by unit tests: the learner proposes, the record is kept, the fallback
executes.

## Remaining blockers

Every one of these needs a person to open a world. They are listed in the order
`docs/LAN_TESTING.md` walks them.

1. **No server.** Connection, authentication, spawn validation, the readiness
   checks and clean shutdown are untested against a real client.
2. **The conformance double is a model of the API, not the API.** It was built
   from the library source and real data tables, so it is a good model, and it
   is still a model. Anywhere it is wrong, the tests that depend on it are
   worth less than they look.
3. **Pathfinder on real terrain.** Route quality, path resets, and how often
   the exclusion function turns a reachable destination into an unreachable one
   are unknown. This is the single most likely source of skill failures.
4. **Server-side placement.** The adapter retries and then fails explicitly, but
   the timing was never exercised against a server that can refuse.
5. **Furnace timing and container windows.** Both are written against the
   documented API with generous margins and have never seen real latency.
6. **Real mob behaviour.** Whether the flee clearances and the neutral-mob
   damage window are adequate is unknown.
7. **Tick budgets.** Meaningless until measured in a world where a tick is a
   tick.
8. **Death and respawn.** Death ends the episode; the recovery path does not
   exist and has not been designed.

## Pre-LAN readiness patch

Added after the audit above, before the first live run.

**The LAN port is runtime information.** Minecraft assigns a new one every time
a world is opened, so `--port` and `--host` override the configuration file for
one invocation on every connecting command, and are never written back. A
changed port never means editing a file.

**Connection failures are classified.** A refused connection used to sit until
the spawn timeout and then report that Person "did not spawn". It now races the
spawn against the error, kick and close events and names what happened:
`connection_refused`, `host_unresolved`, `host_unreachable`,
`connection_timed_out`, `connection_reset`, `connection_closed`,
`protocol_mismatch`, `identity_conflict`, `authentication_refused`,
`login_refused`, `server_kicked`, `spawn_timeout`, `chunk_data_unavailable`,
`world_not_ready`, plus the world-rule refusals already in place. Each carries
an operator hint.

**`person observe` is proven to only look.** A test wraps the body, records
every call and asserts none of the twelve physical operations is among them,
that position, inventory, health and world tick are unchanged, that no journal,
snapshot or episode report is written, and that the command disconnects before
returning even if the disconnect hangs.

**`person status` reports what Person is doing, from outside.** The runtime
writes a status file atomically; the command reads it. Nothing connects, and an
architecture test asserts nothing on the decision path or in cognition can read
it back.

**Operator intervention is declared, not detected.** `--operator-intervention`
writes a marker into the episode events and the status file, so a debug session
cannot later be mistaken for a counted acceptance run.

None of this is live validation. It is the instrumentation the first live run
will be judged with.

## What a reader should take from this

The body is meaningfully better than it was: a defect that would have crashed
on first contact is gone, two safety-relevant classification errors are fixed,
and three silent-success paths now fail honestly. The instruments the next
milestone needs, observation capture, comparison, prediction error and timing,
exist and are already finding things.

Person has still never been in Minecraft.

**That changed on 2026-09-15, a few hours after the above was written.** The
next section records it.

## First contact

The first live connection to Minecraft Java 1.16.1 over LAN. Person joined a
disposable Peaceful world as `PersonAda`, non-OP, using `person observe` with
the LAN port supplied by `--port`.

### What worked, first time

- The connection was established and the identity check passed.
- Person spawned inside the configured exploration bounds.
- Readiness held: chunks, clock, inventory, vitals and dimension all arrived
  before anything was read.
- One Observation was captured and it was **valid against the protocol schema**
  with no diagnostics.
- The configured home was reported correctly, at distance zero.
- The world rules check accepted the world: survival, Peaceful, daylight cycle
  running, Overworld.
- Person disconnected cleanly and the command exited.

The capture is kept as `first-contact.json`. `person observe` joining for a few
seconds and leaving is the designed behaviour and has not been changed.

### What the first real observation exposed

Four defects, none of which any fixture test could have found, because in each
case the fixture or the double was the thing that was wrong.

**1. `biome` was `"unknown"` in a loaded Overworld chunk.** Not a chunk
problem. `prismarine-block` builds its `Biome` class with
`require('prismarine-biome')(registry.version)`, passing a Version object where
`prismarine-biome` only accepts a version _string_; it therefore treats the
Version as a registry, finds no biome table on it, and returns its empty
placeholder for every id. `block.biome.name` is unconditionally `""` with these
versions, and the adapter's identifier check turned that into `"unknown"`. The
numeric id beside it was correct all along. Biome is now resolved from that id
against `bot.registry`, which is `minecraft-data`'s table on 1.16.1 and the
server's dimension codec on the versions that send one. The Mineflayer double
used to return `{ name: "forest" }`, a shape the real library never produces,
which is precisely why a green test suite let this through; it now returns the
same nameless biome the real library does.

**2. The human player was reported as `"player"`.** Correct, and useless.
Minecraft names every player entity `player`; identity lives in the account
name and the UUID. Entity records now carry `username` and `uuid` as additive
optional protocol fields, so two people can no longer collapse into one
identity. Nothing social was built on top of this: the point is that the
observation is now semantically capable of supporting it.

**3. Perception was saturated.** The observation held exactly 64 resource
entries: 55 stone and 9 coal, because a single nearest-N search standing on
stone returns stone. Every tree in sight was invisible to cognition, and the
planner's `reachable_wood` fact was consequently zero in a world full of wood.
Resources are now gathered per category and balanced: a guaranteed quota each,
a small shared overflow budget, the same hard ceiling as before. The list is
usually shorter than it was and always more informative.

**4. Passive entity sensing was noise.** 80 animals, 70 of them outside the
configured exploration area, some 190 blocks away, none of them usable. The
observation now reports only animals inside the region Person may actually
enter and within reach of it, nearest first, bounded. This is a perception
decision and deliberately not a safety one: the runtime's snapshot still holds
every entity the body can see, and the permission gate still refuses the
out-of-region ones for their own reason.

### The failed run before the successful one

The first attempt spawned outside the configured exploration area and reported
`spawn_outside_bounds`. That refusal is correct and is unchanged. What was
wrong is that the command then held the terminal for thirty seconds and was
killed by hand.

The cause was in `disconnect`, which quit the session and then ended the client
a second time two hundred milliseconds later. In `minecraft-protocol`,
`Client.end` arms a thirty-second `closeTimer` that destroys the socket if it
has not closed on its own, and the handler that clears that timer runs exactly
once, on the first close, after which it sets `ended` and removes its own
listeners. Whenever the server's close arrived inside those two hundred
milliseconds, which on a LAN world it usually does, the second end armed a
timer nothing would ever clear. The successful run and the failed run differed
only in who won that race.

The client is now ended once, the close is awaited with a bound, the timer is
cleared explicitly and the socket is destroyed if the server never answers. A
regression test runs the entire failure in a child process and waits for it:
with the old code that child takes 31.5 seconds, with the fix it exits
immediately.

### Live re-validation: pending

No Minecraft server was reachable while these four fixes were made. No Java
process is running and nothing is listening on a Minecraft port. The fixes are
implemented against the real installed libraries and covered by conformance
tests that use `prismarine-registry`, `prismarine-chunk` and `prismarine-block`
for 1.16.1 directly, but **none of them has been seen working against
Minecraft**. The next live action is a second `person observe`, and the things
to check in its output are: `biome` is a real biome name, the operator appears
under their own account name, `resources` shows a mix of categories rather than
one, and `passiveAnimals` is a short list of animals that are actually nearby.
