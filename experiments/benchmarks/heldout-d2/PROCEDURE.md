# Held-out D2: generation procedure

**Declared on 2026-09-30, and committed before the world was generated.**
The seed and every rule below are fixed here first, so the world is decided
by this document and `scripts/benchmarks/generate-setback.ts`, not by anyone
who has seen it.

## Why D2 exists

Held-out D (`experiments/benchmarks/heldout/d-setback.json`) is **INVALID and
NOT INTERPRETABLE FOR R2**: the zero-time livelock of ADR 0015 froze it. It is
kept permanently and never re-used as evidence. D2 replaces it as the
held-out class D world.

## Rules

- **No tuning.** Nothing about R2 is tuned from D or from D2. D2's results may
  not be used to change R2's parameters, the benchmark, or this procedure.
- **Frozen before running.** The generated world and its plan are committed
  with a SHA-256 manifest before any run. Changing any file afterwards needs
  an explicit operator decision and a new manifest.
- **Run once,** as part of a held-out evaluation the operator authorizes.

## Class D, setback and recovery

A calm life with food, wood, tools and an owned chest, one hostile encounter,
then a long quiet period. The ranges below span the two class D worlds that
exist: development D and the invalid held-out D.

## Random numbers

- Seed string: `person-heldout-d2-2026-09-30`.
- Draw `i` (from 0) is the first 8 bytes of SHA-256 of `<seed>:<i>`, read as
  an unsigned big-endian integer and divided by 2^64, giving `u` in [0, 1).
- `choice(list)` is `list[floor(u * length)]`; `int(lo, hi)` is
  `lo + floor(u * (hi - lo + 1))`, both ends included.
- A compass direction is `choice` of the 8 unit steps, in this order: (1,0),
  (1,1), (0,1), (-1,1), (-1,0), (-1,-1), (0,-1), (1,-1). A point at
  direction `d` and radius `r` from spawn is
  `(round(d.x * r / |d|), 64, round(d.z * r / |d|))`.
- Draws are made in exactly the order listed below.

## Draws, in order

1. `spawnYaw`: choice of 0, π/2, π, 3π/2.
2. Starting food: int(14, 16).
3. Sweet berry bushes: centre at direction, radius int(6, 10); count 12,
   spread 2.
4. Oak logs: centre at direction, radius int(9, 14); count 30, spread 3.
   Redrawn (direction then radius) while the centre is within 6 blocks of the
   berry centre.
5. Owned chest: position at direction, radius int(3, 5). Redrawn while it is
   within 3 blocks of either cluster centre. Contents: bread `8 * int(4, 8)`,
   then a cooked meat, choice of `cooked_beef`, `cooked_porkchop`,
   `cooked_mutton`, `cooked_chicken`, count `8 * int(2, 4)`.
6. Starting inventory: a stone pickaxe, plus choice of 64 oak planks or 40
   oak logs.
7. The hostile: choice of `zombie`, `skeleton`; it spawns at tick
   `200 * int(15, 35)`, at an offset from Person of direction, distance
   int(4, 9); it despawns `200 * int(3, 5)` ticks later.

A redraw loop gives up after 100 attempts. If it does, or if any position is
outside the fixture's exploration box (-48 to 48 on x and z), the seed string
gets the suffix `-r1`, then `-r2`, and so on, and generation starts again from
draw 0. The first valid world is D2, and the suffix used is recorded.

## Fixed

Biome `forest`, ground level 63, spawn (0, 64, 0), health 20, air 300, armour
0, saturation 2, time of day 1000, start tick 0, world seed 1, no blocks and
no initial entities. Name `bench-d2-setback-heldout`.

## The plan

Split `heldout`, class D, config `examples/fixture.toml`. Conditions as the R2
held-out plans: P0 (affect off), A15 (active, interoception off), R2rec
(record-only, interoception on), R2act (active, interoception on). Seeds 201
to 205, distinct from every earlier split. Horizons short 6000, medium 24000
and long 72000 experienced ticks, at most 5000 decisions, learning off.
