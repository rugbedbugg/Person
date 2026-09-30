# Held-out A2, B2 and C2: generation procedure

**Declared on 2026-09-30 and committed before any of the three worlds was
generated.** The seeds and every rule below are fixed first, so each world is
decided by this document and `scripts/benchmarks/generate-classes.ts`, not by
anyone who has seen it. Decided with the operator and the external reviewer;
the reasoning is summarised under "Why this design".

Together with held-out D2 (`../heldout-d2/`) they form the four-world V2
held-out suite.

## Rules

- **No tuning.** Nothing about R2 is tuned from A2, B2, C2 or D2, and their
  results may not change R2's parameters, the benchmark, or this procedure.
- **Generated once, no retries, no redraws.** Each world is generated exactly
  once from its declared seed. No draw is repeated and no seed is changed.
- **Valid by construction, checked by assertion.** Each world copies its
  class-defining bundle whole from a known instance of its class; only layout
  is new. A static class validator then asserts that the world is an instance
  of its class. It is an assertion, not a search: **if a world fails, stop.**
  Keep the failed world and its record, and ask the operator. Do not
  regenerate.
- **Frozen before running.** The worlds, plans and validator records are
  committed with a SHA-256 manifest before any run. Changing any file needs
  an explicit operator decision and a new manifest.
- **Run once,** as part of the V2 suite the operator authorizes.

## Seeds

Generation seeds, one per class, so that the generation streams never share
draws:

| World | Generation seed                |
| ----- | ------------------------------ |
| A2    | `person-heldout-a2-2026-09-30` |
| B2    | `person-heldout-b2-2026-09-30` |
| C2    | `person-heldout-c2-2026-09-30` |

Run seeds are separate, and shared by the whole V2 suite: 201 to 205 for A2,
B2, C2 and D2 alike.

## Random numbers

As for D2: draw `i` (from 0) is the first 8 bytes of SHA-256 of
`<seed>:<i>`, read as an unsigned big-endian integer and divided by 2^64;
`choice(list)` is `list[floor(u * length)]` and `int(lo, hi)` is
`lo + floor(u * (hi - lo + 1))`. A point at `degrees` and `radius` from spawn
is `(round(cos(degrees) * radius), 64, round(sin(degrees) * radius))`, x and z.
The spawn yaw faces the world direction `atan2(-cos(yaw), -sin(yaw))`: yaw 0
faces negative z.

## Class-defining bundles

Taken whole from one of the two known instances of each class, never mixed:

| Class | Bundle from                   | Carries                                                                                                               |
| ----- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| A     | development or old held-out A | vitals, inventory, berry count, the chest's contents (the cooked meat's kind is drawn), the herd's kind and formation |
| B     | development or old held-out B | vitals and inventory (tool readiness sets the tie); no chest, no herd                                                 |
| C     | development or old held-out C | vitals, inventory, berry count, the chest's contents, the herd's kind and formation; learner supervised               |

"Formation" is each herd member's offset from the first member, as in the
source world.

## Draws, in order

1. The bundle: choice of development, old held-out.
2. `spawnYaw`: choice of 0, π/2, π, 3π/2.
3. The berry direction: for A and B, choice of the 8 compass directions (0°,
   45°, ... 315°); for C, the facing plus choice of -45°, -20°, 0°, 20°, 45°,
   so the berries start in view. Radius int(6, 10) for A and B, int(4, 8) for
   C. Berry count from the bundle, spread 2.
4. The logs: the berry direction plus 180° plus choice of -45°, 0°, 45°;
   radius int(9, 14); count 30, spread 3.
5. If the bundle has a chest: its position at the berry direction plus choice
   of -90°, 90°, radius int(3, 5); then the cooked meat's kind, choice of
   `cooked_beef`, `cooked_porkchop`, `cooked_mutton`, `cooked_chicken`.
6. If the bundle has a herd: its first member at, for A, a compass direction
   and radius int(16, 20); for C, the facing plus choice of -45°, -20°, 0°,
   20°, 45°, radius int(5, 8). The other members keep the bundle's formation.

These placements never collide, so nothing is ever redrawn: the logs lie on
the far side of spawn from the berries, and the chest to one side.

## Fixed

Biome `forest`, ground level 63, spawn (0, 64, 0), time of day 1000, start
tick 0, world seed 1, no blocks, no events. Name
`bench-<class>2-<class name>-heldout`.

## Static class validity

`scripts/benchmarks/initial-observation.ts` reads the observation a world
gives before its first decision. `scripts/benchmarks/validate_class.py` asks
the frozen goal and project providers what is legitimate there. Neither runs
the decision loop, acts, learns, or looks at a trajectory.

- **A, wide margin:** at the initial observation, the top legitimate goal
  leads the second by more than `affect.bias_swings()` allows affect to lift
  the second over it.
- **B, near tie:** in one declared post-adoption witness state (shelter
  complete, home known, daytime, calm; inventory and everything else
  unchanged), the home project is adopted by the real `ProjectManager`, and
  its next milestone is storage. The storage milestone and the tools goal are
  both legitimate, and their base priorities are 10 to 20 apart, within
  affect's swing between them. No third goal dominates both beyond that swing,
  and the providers agree with the frozen priority formulas. **This asserts
  that the world contains the latent near tie, not that Person will reach
  it;** whether it does is an experimental result.
- **C, exploration opportunity:** at the initial observation, securing food
  is the top legitimate goal; at least two different kinds of food
  acquisition are perceived (foraging, hunting, taking from storage); and the
  learner is supervised.

Before this procedure was committed, the validators passed all six known
worlds (development and old held-out A to C) and failed every targeted
mutation (`tests/python/test_class_validators.py`), and 12 throwaway seeds per
class all passed (`tests/benchmarks/generate-classes.test.ts` checks the
construction). None of them was a declared seed.

## The plans

Split `heldout`, config `examples/fixture.toml`, learner from the bundle (C
supervised, A and B off). Conditions as the R2 held-out plans: P0 (affect
off), A15 (active, interoception off), R2rec (record-only, interoception on)
and R2act (active, interoception on). Seeds 201 to 205. Horizons short 6000,
medium 24000 and long 72000 experienced ticks, at most 5000 decisions.

## Why this design

- Classes A to C are defined by a decision geometry, not a layout, so drawing
  every field at random could produce a world outside its class. Copying the
  class-defining bundle whole keeps each world an instance of its class; mixing
  fields from two sources could create interactions neither source had.
- A retry on validation failure would amount to choosing a world for its
  cognitive geometry after seeing it, so there is none. A failure is
  reported, not hidden.
- B's tie is latent in both known B worlds: it appears only after the shelter
  is built and the home project adopted, about 150 ticks in. A check at the
  first decision would reject both, so B is checked in the declared witness
  state instead.
- Class C's check counts only what Person perceives, so C's food sources are
  placed inside the initial field of view (200° horizontal).
