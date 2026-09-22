# Baritone 1.16.5 navigation feasibility

Phase 1 spike. Branch `feat/baritone-feasibility`, parent `45d3c9c` (the merge of
PR #1 into `feat/lan-validation`). Dated 2026-09-22.

This document answers one question with evidence: can Person drive a
Baritone-backed Minecraft 1.16.5 motor system while keeping an authoritative
protected-region veto over path planning, replanning and execution?

Nothing was implemented. No production source changed. No Minecraft client was
run. Everything below is source analysis at named revisions plus inspection of
the published Baritone artifact. None of it is live validation, and none of it
should ever be cited as live validation.

## 1. Verdict

**NO-GO as specified, with a narrow viable path that needs an operator
decision first.**

The invariant is technically achievable. Baritone's path search has a genuine
hard-exclusion mechanism, and it is a better one than Person currently uses
against Mineflayer. But reaching it requires modifying Baritone's internal,
non-API classes and carrying that fork, because:

1. The published Baritone artifact ships its implementation ProGuard-obfuscated.
   Only `baritone.api` is readable and supported. The hard-exclusion machinery is
   not in `baritone.api`.
2. Baritone's own protected-area hook, `CalculationContext.isPossiblyProtected`,
   is an unfinished stub, and it is wired only into block breaking and block
   placement. It does not affect walking into a region at all.
3. Of the 205 settings in the public API, none expresses a forbidden region.
   The one avoidance system that exists is a soft cost multiplier, and the source
   shows it is applied after the hard-exclusion check, so it can never forbid.

That triggers stop condition 5 (enforcement requires invasive unsupported
internals). Two further findings triggered stop condition 7 (architectural
contradiction needing an operator decision), and they matter more than the
mechanism question:

- **Baritone is a client-side mod.** It runs inside a real, graphical Minecraft
  client. Person today runs Mineflayer, a headless protocol client with no game
  installation, no assets and no display. This is a much larger change to how
  Person is run and tested than "swap the motor backend" suggests.
- **There is no Baritone branch for 1.16.1**, which is the version Person is
  actually validated against. Upstream goes 1.15.2 then 1.16.5. Adopting Baritone
  forces a world and server migration first.

And one finding on the Person side that is independent of Baritone and more
urgent than it:

- **Against the real Mineflayer body, the protected-area route veto is not
  authoritative for every movement family.** Details in section 3.3, as corrected
  by Phase 2. Recorded as deviation C7 and repaired in Phase 2.

## 2. What was examined

### Upstream Baritone

| Item                                         | Value                                                   |
| -------------------------------------------- | ------------------------------------------------------- |
| Repository                                   | `github.com/cabaletta/baritone`                         |
| Branch                                       | `1.16.5`                                                |
| Branch tip                                   | `dbfb44d0492572ca41cb8a76695f273ad6da84a5` (2023-08-14) |
| Tip commit subject                           | `deprecate 1.16.5`                                      |
| Last functional commit, and the one analysed | `9df406d` (`v1.6.5`)                                    |
| Minecraft version                            | 1.16.5                                                  |
| Loaders                                      | Forge and Fabric, both published                        |
| License                                      | LGPL-3.0                                                |

The branch tip is a deprecation notice. It replaced the entire README with:

> This branch of Baritone is deprecated. It will no longer recieve updates.
> Updates to older versions of Minecraft will not be merged into this branch,
> even if a newer branch is not deprecated (this branch will be skipped). Bug
> reports that only affect deprecated branches will not be addressed.

So 1.16.5 is frozen. That cuts both ways: a carried patch would never face
upstream drift, but there will never be another upstream fix either.

### Build requirements, from `build.gradle` at `9df406d`

| Item                   | Value                                              |
| ---------------------- | -------------------------------------------------- |
| Gradle wrapper         | 4.9 (from 2018; will not run on Java 11 or newer)  |
| Java source and target | 1.8                                                |
| ForgeGradle            | `com.github.ImpactDevelopment:ForgeGradle:3.0.115` |
| MixinGradle            | `com.github.ImpactDevelopment:MixinGradle:0.6.2`   |
| Fabric Loom            | `net.fabricmc:fabric-loom:0.7-SNAPSHOT`            |
| MCP mappings           | snapshot `20201028-1.16.3`                         |

Repository reachability checked on 2026-09-22. All of them still serve:
`maven.minecraftforge.net`, `impactdevelopment.github.io/maven`,
`dogforce-games.com/maven`, `maven.fabricmc.net` and `jcenter.bintray.com`
answer at the root, and `files.minecraftforge.net/maven` serves artifacts over
plain HTTP even though its directory root returns 404. The five-year-old
`0.7-SNAPSHOT` Loom dependency still resolves, to
`fabric-loom-0.7-20220702.150149-34`.

This is better than expected for a 2021 toolchain, and it is the reason section
7 reports a measured result rather than a guess.

### Published artifact

| Item                                    | Value                                                              |
| --------------------------------------- | ------------------------------------------------------------------ |
| File                                    | `baritone-api-1.6.5.jar`                                           |
| Size                                    | 518897 bytes                                                       |
| SHA-256                                 | `c35c36b0582b7adb71e607a4288900bb36e34ff3e63cb4c35f06456bdba1d6dc` |
| Classes under `baritone/api/`           | 176                                                                |
| Classes in the root `baritone/` package | 221, obfuscated (`a.class`, `aa.class`, `ab.class`, ...)           |

This is the decisive artifact fact. The supported API is readable. The
implementation, including every class named in section 4, is obfuscated in the
distributable.

### Environment

Java 21.0.12 (Temurin) and Java 8.0.504 (Temurin, installed during this spike)
were available. Gradle 4.9 was not previously present. No Minecraft client, no
game assets, no licensed account, no display server, and no 1.16.5 server were
available, so no Baritone runtime test was possible. See section 7.

The Baritone clone and the downloaded jar live in the session scratchpad only.
Nothing from Baritone was copied into this repository, and nothing should be:
Person is MIT and Baritone is LGPL-3.0.

## 3. Stage A: the Person side as it actually is

### 3.1 The dispatch pipeline

A proposal reaches the world through exactly one road, `dispatchSkill` in
`apps/node-runtime/src/skills/dispatch.ts`:

```
SkillInvocation
  -> InvocationValidator.validate(invocation, snapshot)     safety/validator.ts
  -> ValidationDecision (ACCEPT / REPLACE / REJECT)
  -> SkillRunner.run(...)                                   skills/executor.ts
  -> skill implementation                                   skills/impl/*.ts
  -> Embodiment method                                      embodiment/types.ts
  -> PhysicalGuard consulted inside the embodiment
  -> SkillOutcome, credited to the skill that actually ran
```

`PhysicalGuard` is built by the runtime, never by cognition
(`runtime/person-runtime.ts:178` and `validation/skill-test.ts:290`), and
installed with `setGuard` before `connect()`. It is three predicates:

```ts
canEnter:        (position) => permissions.mayEnter(position).allowed
canModify:       (position) => ...mayBuild / mayHarvest...
canTargetEntity: (entity)   => ...mayHunt / mayDefend...
```

`mayEnter` resolves to `ProtectedAreas.permitted`, which is a single-point test:
inside the exploration box, and not inside any protected box.

### 3.2 Where the veto actually lives today

Four layers, and they are not equally strong:

| Layer                             | What it checks                                        | Strength                   |
| --------------------------------- | ----------------------------------------------------- | -------------------------- |
| Skill code (`skills/navigate.ts`) | destination, and approach candidates, via `mayEnter`  | hard, but destination only |
| Embodiment `moveTo`               | `#requireGuard(target, "enter")`                      | hard, but target only      |
| Path search                       | `exclusionAreasStep` on each considered step          | see 3.3                    |
| Safety kernel `assess`            | current position each tick, L0 `protected_area_entry` | reactive, after entry      |

`ProtectedAreas.routePermitted` and `firstViolation` exist and do a straight-line
block sweep, but production calls them in exactly one place,
`observation/builder.ts:281`, to compute the `returnPathKnown` fact for
cognition. They are not part of the movement veto. `safety/validator.ts` contains
no protected-area check at all.

### 3.3 The Mineflayer finding (new deviation C7)

`MineflayerEmbodiment.#configureMovement` installs the exclusion this way:

```ts
movements.exclusionAreasStep.push((block) =>
  this.#guard?.canEnter(point(position)) === false ? 100 : 0,
);
movements.exclusionAreasBreak.push(() => 100);
movements.exclusionAreasPlace.push(() => 100);
```

> **Corrected on 2026-09-22 by the Phase 2 investigation.** The reasoning below
> was wrong on its central point, and the correction is recorded here rather
> than quietly edited away. The claim was that the exclusion is only a cost
> penalty. It is not: every movement generator that consults the exclusion ends
> with `if (cost > 100) return`, and since base move costs are 1 or 2, a step
> scored 100 totals 101 and the move is never generated. Measured against the
> real pathfinder, Person walks a 124-step detour rather than take a
> 12-step crossing that would have cost less under a penalty model. C7 survives,
> but for narrower and different reasons: see `docs/CURRENT_STATE.md`, C7, and
> the tests in `tests/safety/pathfinder-containment.test.ts`.

Reading `node_modules/mineflayer-pathfinder/lib/movements.js`:

- `exclusionStep(block)` sums the registered functions and the result is added to
  the movement cost (`cost += this.exclusionStep(block)`, line 284 and others).
  What this reading missed is that the callers then test `cost > 100` and return,
  so the addition is the input to a rejection rather than a price.
- Ordinary movement costs in the same file are **1 to 2** per step (lines 307,
  366, 481, 506, 530, 566), which is what makes 100 clear the threshold.
- Breaking: `safeToBreak` requires `this.exclusionBreak(block) < 100` (line 273).
  With the adapter returning exactly 100, breaking inside a protected area is
  genuinely forbidden.

The part of this section that survived Phase 2 is narrower: `moveTo` guards only
the destination, not the steps in between, so nothing at execution time
re-checks a path; and two movement generators do not participate in the
exclusion at all, which is the real defect C7 now names.

The fixture body is stricter than the real one. `FixtureWorld.#walkable` consults
`guard.canEnter` and skips the node outright, and `#assertEnter` re-checks every
executed step. That is a true per-step veto.

This gap is invisible in the test suite. In `tests/safety/protected-routes.test.ts`
the two behavioural tests ("a route around a protected area is found", "a
destination reachable only through a protected area is refused") run against
`FixtureWorld` through `harness()`. The third test uses `MineflayerEmbodiment`
but asserts only that the exclusion function was installed and returns non-zero
inside the box. It cannot assert routing behaviour, because the mineflayer
double's `pathfinder.goto` is `async () => {}`.

Nothing here is a regression and no test is wrong. The tests assert what they
say they assert. The deviation is that the documented guarantee, a veto that
holds during navigation and replanning, is met by the fixture body and only
approximated by the Minecraft body.

## 4. Stage B: Baritone 1.16.5 upstream audit

All line references are at `9df406d`.

**Hard exclusion exists, and the search honours it.**
`ActionCosts.COST_INF` is `1000000` (deliberately not `Double.MAX_VALUE`, because
costs get summed). In `AStarPathFinder.calculate0`, each candidate move is
pruned outright:

```java
double actionCost = res.cost;
if (actionCost >= ActionCosts.COST_INF) {
    continue;
}
```

The node is never entered into the open set. This is a real prohibition, not a
penalty, and if a region makes the goal unreachable the search exhausts and
reports failure rather than routing through. That is the behaviour the brief
requires for tests 2 and 3.

**The soft avoidance system cannot be promoted into a hard one.** `Favoring` is a
`Long2DoubleOpenHashMap` of multiplicative coefficients, default 1.0, built from
mob positions at calculation start and applied as `actionCost *=
favoring.calculate(hashCode)`. Crucially that multiply happens _after_ the
`COST_INF` prune in the same loop, so no coefficient, however large, can prune a
node. `Settings.avoidance` (default false), `mobAvoidanceCoefficient`,
`mobSpawnerAvoidanceRadius` and friends are all this system, and all spherical
and mob-derived.

**Baritone's own protection hook is a stub, and it is in the wrong place.**

```java
public boolean isPossiblyProtected(int x, int y, int z) {
    // TODO more protection logic here; see #220
    return false;
}
```

It is consulted by `CalculationContext.costOfPlacingAt` and
`breakCostMultiplierAt`, and by `BuilderProcess` at lines 1102 and 1136. Grepping
the whole of `src/main` finds no other caller. No traversal cost function
consults it. Implementing it would forbid building and mining inside a region and
would not affect walking into one.

**Execution re-verifies cost every tick.** `PathExecutor.onTick` re-costs the
upcoming movements against the live context:

```java
for (int i = 1; i < Baritone.settings().costVerificationLookahead.value
        && pathPosition + i < path.length() - 1; i++) {
    if (((Movement) path.movements().get(pathPosition + i))
            .calculateCost(behavior.secretInternalGetCalculationContext())
            >= ActionCosts.COST_INF && canCancel) {
        cancel();
```

`costVerificationLookahead` defaults to 5. This is the single most useful fact in
the audit: any mechanism expressed as `COST_INF` gets replanning safety and
dynamic policy change for free, because Baritone already re-checks it five
movements ahead on every tick and cancels when a step becomes impossible.

**Process control runs before movement each tick.** `PathingBehavior.onTick`
calls `baritone.getPathingControlManager().preTick()` and only then `tickPath()`,
which is what calls `current.onTick()` and applies movement. So a registered
`IBaritoneProcess` gets to speak before the avatar moves that tick.
`PathingControlManager.preTick` maps `CANCEL_AND_SET_GOAL` onto
`secretInternalSetGoal` plus `cancelSegmentIfSafe`.

**But cancellation is conditional.** `cancelSegmentIfSafe` only acts
`if (isSafeToCancel())`, and `isSafeToCancel` is the value the previous
`PathExecutor.onTick` returned. Mid-movement states that report unsafe (falls,
parkour, sneak-placing) defer the cancel until the atomic movement completes.
Baritone's own `COST_INF` re-verification carries the same `&& canCancel` gate.

**Public API surface.** `IBaritone` exposes `getPathingBehavior`,
`getPathingControlManager`, `getCustomGoalProcess`, `getPlayerContext`,
`getGameEventHandler`, `getSelectionManager`, `getCommandManager` and the
built-in processes. `IPathingBehavior` exposes `getPath()`, `getCurrent()`,
`isPathing()`, `cancelEverything()` and `forceCancel()`. `IPath` exposes
`positions()` and `movements()`, so a planned route is fully inspectable before
and during execution. None of it exposes a spatial constraint.

**Baritone already contains exactly the mechanism that is needed, bound to the
wrong thing.** `BetterWorldBorder` describes itself as "a 'rule' for the path
finder, prevents proposed movements from attempting to venture into the world
border, and prevents actual movements from placing blocks in the world border".
It is a plain XZ box, and `AStarPathFinder.calculate0` consults it twice, once
for fixed-offset movements and once for dynamic ones, each time with `continue`:

```java
if (!moves.dynamicXZ && !worldBorder.entirelyContains(newX, newZ)) {
    continue;
}
...
if (moves.dynamicXZ && !worldBorder.entirelyContains(res.x, res.z)) { // see issue #218
    continue;
}
```

So a hard, per-node, spatial prune already exists in the search loop, is already
correct for both movement shapes, and is already mirrored on the placement side
through `costOfPlacingAt`. It is simply derived from the vanilla world border
rather than from a supplied region set. This matters a lot for sizing the work in
section 5: the patch is a generalisation of existing, proven code, not a new
design.

**Client-side only.** `CalculationContext` imports
`net.minecraft.client.entity.player.ClientPlayerEntity` and takes its world from
`baritone.getPlayerContext().world()`. Baritone is a mod inside a running
Minecraft client. There is no headless mode.

## 5. Stage C: candidate mechanisms

Each is judged against the brief's nine criteria. The hard acceptance bar is that
no permitted Baritone-controlled movement may leave the avatar occupying a
forbidden position.

### C1. Native avoidance settings (`avoidance`, `mobAvoidanceCoefficient`)

Planning: discourages only, and provably cannot prune, because the multiply is
applied after the `COST_INF` check. Replanning: rebuilt each calculation, still
soft. Execution: nothing. Dynamic: no, snapshot at calculation start.
Maintainability: excellent, pure settings. Information boundary: clean.
Failure semantics: none, it never fails, it just costs more.

**Verdict: reject.** This is exactly the "a high path cost makes entry unlikely"
case the brief rules out.

### C2. Block-type lists (`blocksToAvoid`, `blocksToDisallowBreaking`)

Expresses block types, not coordinates. Cannot represent a box. Not applicable.

**Verdict: reject.**

### C3. Implement `CalculationContext.isPossiblyProtected`

Planning: hard, but only for breaking and placing. Walking into the region is
untouched, because no traversal cost function calls it. Replanning and dynamic:
inherited from the cost system, and would be good, if it covered movement.
Maintainability: it is upstream's own intended hook, but it lives in
`baritone.pathing.movement`, which is obfuscated in the published jar, and
`CalculationContext` is constructed directly at many sites, so a subclass is not
injectable without patching those sites anyway. Information boundary: clean.

**Verdict: reject as sufficient.** Necessary but partial. It would give Person a
hard no-build, no-mine region and no protection at all against simply walking in.

### C4. Custom `IBaritoneProcess` with top priority, inspecting the path

Register via `IPathingControlManager.registerProcess`. Each tick, read
`IPathingBehavior.getPath()` and `IPathExecutor.getPosition()`, test the
remaining positions against the region, and return `CANCEL_AND_SET_GOAL` on a
hit. Pure public API, no fork.

Planning: **no**. Baritone's search knows nothing about the region and will
happily compute a route straight through it. This is inspect-then-reject, which
the brief rules out on its own terms, and the rejection does not inform the next
calculation, so it can loop.

Replanning: same defect, plus one tick of detection latency per new candidate
path.

Execution: partial. `preTick` does run before movement is applied, so a clean
same-tick veto is possible in the common case. But `cancelSegmentIfSafe` is gated
on `isSafeToCancel()`, so a cancel issued mid-fall or mid-parkour is deferred
until that movement completes, and that movement can land inside the region.

Races: one tick (50 ms) of detection granularity, plus the deferred-cancel
window. Uninterruptible movement: this is precisely where it fails. Dynamic
policy: fine, it is re-evaluated every tick. Maintainability: excellent, public
API only, and the 1.16.5 API is frozen. Information boundary: the process runs
on the motor side, so nothing leaks upward. Failure semantics: honest, it can
report denial.

**Verdict: reject as the authoritative veto. Keep as a defence-in-depth layer.**
It is a good backstop and a bad guarantee.

### C4b. The vanilla Minecraft world border

Not on the brief's list, and worth recording because it is the only hard spatial
containment available with no fork at all. The world border is enforced by the
server, not by trusting the client, and Baritone already prunes against it in the
search loop.

Planning: hard. Replanning: hard, same code path. Execution: enforced by the
game itself, which pushes the player back and deals damage outside the border.
Races: none worth naming, because it is server-side. Maintainability: perfect,
it is vanilla. Information boundary: clean.

Limits that stop it being the answer: there is exactly one border per dimension,
it is a square centred on a point, it is XZ only with no Y component, it cannot
express several disjoint protected boxes, and it contains Person _inside_ a
region rather than keeping Person _out of_ one. Setting it also requires an
operator command, which Person must never hold.

**Verdict: not a solution to protected areas, but a genuinely useful outer
containment fence for an experimental world, obtainable today at zero cost.**
Worth proposing to the operator on its own merits, separately from Baritone.

### C5. Fork: wire a region predicate into the `COST_INF` path

Carry a patch that gives `CalculationContext` a region predicate and consults it
in the movement cost functions, or equivalently at the single node-expansion
chokepoint in `AStarPathFinder.calculate0` where `res` is produced.

Planning: **hard**, by construction, via the existing prune. Replanning: **hard**,
every recalculation uses the same cost functions. Execution: **hard**, and free,
because `PathExecutor` already re-costs five movements ahead every tick and
cancels on `COST_INF`. Dynamic policy: **supported**, same mechanism, a predicate
change is picked up within `costVerificationLookahead` movements. Failure
semantics: **clean**, an unreachable goal exhausts the search and reports failure
rather than trespassing.

Races: the same bounded deferred-cancel window as C4 applies to a policy change
that lands mid-movement. A region that was forbidden at plan time is never
entered; a region that _becomes_ forbidden while the avatar is mid-parkour may be
entered by that one in-flight movement.

Correctness subtlety that must not be missed: the predicate has to veto a
movement's **swept volume**, not just its destination voxel. `MovementFall`,
`MovementParkour` and `MovementDiagonal` pass through blocks between source and
destination. Vetoing only `res.x, res.y, res.z` would leave a real hole.

Maintainability: this is the weak point, but it is less bad than it first looks.
It requires building Baritone from source, because the implementation is
obfuscated in the published jar, and it is a fork of non-API internals. Three
things soften that: the 1.16.5 branch is deprecated and frozen, so the patch
would never need rebasing; the change is a generalisation of `BetterWorldBorder`,
which is existing proven code in the same loop, rather than a new design; and the
project does still configure (section 7), so the fork is buildable in principle.

Information boundary: clean. The predicate is evaluated inside the motor process
and only ever answers yes or no.

**Verdict: viable, and the only viable one, but it is a fork of unsupported
internals, which is stop condition 5.**

## 6. Hard acceptance and the physics boundary

If C5 were implemented correctly, "no permitted Baritone-controlled movement
results in the avatar occupying a forbidden position" would hold for
motor-caused movement, with the bounded exception noted above.

Everything else has to be classified honestly rather than claimed:

**Motor-caused**, meaning the path system chose it, and C5 covers it: walking,
sprinting, jumping, ascending, descending, diagonals, parkour, controlled falls,
ladder and vine climbing, and any movement Baritone initiates.

**World-caused**, meaning the motor system does not control it and no path
predicate can prevent it: mob knockback, explosion knockback, falling into a
region after a block is removed beneath the avatar, being pushed by water or
lava flow, piston displacement, boat and minecart motion, ice sliding, and server
position correction after a desync.

**External or operator-caused**: `/tp` and other operator commands, plugin
teleports, world edits that move the avatar, respawn placement.

The right architectural reading is that the veto makes it impossible for Person
to _choose_ to enter a protected region, and the existing L0
`protected_area_entry` assessment remains the answer for arriving there by
physics or by operator action. Those two are different mechanisms for different
causes, and the safety document should say so rather than implying one covers
both. That distinction is already the spirit of deviation C2.

## 7. Stage D: not built, and why

The brief gates Stage D on Stages B and C identifying a credible clean mechanism.
They did not. The only mechanism that satisfies the invariant requires forking
unsupported internals, which is a listed stop condition. Building a spike on top
of it would be deciding the architectural question by momentum rather than
putting it to the operator, so the spike stops here.

Two independent blockers would have limited Stage D anyway:

1. **No Minecraft runtime.** Baritone is a client mod. Running tests 1 to 6
   requires a licensed, installed, graphical Minecraft 1.16.5 client plus a
   1.16.5 server. None of that exists in this environment. Any proof built here
   would have been a model of the mechanism, not evidence about Baritone, and
   labelling it otherwise would be dishonest.
2. **Build reproducibility: better than expected, and measured.** This one was
   tested rather than assumed. Gradle 4.9 runs correctly under Temurin 8.0.504,
   `buildSrc` compiles, and the entire 2021 buildscript classpath resolves from
   the declared repositories, including the five-year-old
   `net.fabricmc:fabric-loom:0.7-SNAPSHOT` (which resolves to
   `0.7-20220702.150149-34`). `gradle tasks` **succeeded**, in 1m 3s:

   ```
   BUILD SUCCESSFUL in 1m 3s
   ```

   It took three attempts. The first two failed on transient `Connection reset`
   and `Read timed out` errors against `files.minecraftforge.net` over plain
   HTTP, and each attempt got further as the dependency cache filled. That host
   is flaky, not gone.

   So the project **configures** in 2026. A full compile was not attempted, and
   that is the part that would exercise ForgeGradle's Minecraft decompile and
   remap plus the ProGuard step, so "configures" must not be read as "builds".
   Stop condition 6 is **not** triggered at the configuration level.

What tests 1 to 6 will require when they are run, so this is not re-derived:
a disposable 1.16.5 LAN world, a dedicated account that is not the Mineflayer
account, a patched Baritone build, a minimal local control surface that is not
Minecraft chat, and per-tick position logging to `motor_debug` so that "never
occupied a forbidden position" is proved against recorded positions rather than
asserted from the absence of a complaint.

## 8. C5 embodiment findings

Against a Baritone-backed client body, the current `Embodiment` port splits three
ways.

**Maps cleanly.** `moveTo` is the natural fit, and is the one method Baritone
exists to provide. `waitTicks`, `connect`, `disconnect` and `setGuard` are
backend-neutral. `findBlocks` maps onto Baritone's world cache, though see the
information-boundary note below.

**Minecraft-client facts, independent of Baritone.** `snapshot()`'s vitals
(health, food, saturation, air, armor, statusEffects, alive), `dimension`,
`timeOfDay`, `weather`, `biome`, `lightLevel`, `inventory`, `freeSlots`,
`blockAt`, `containerAt`, `inspectContainer`, `dig`, `place`, `craft`, `smelt`,
`consume`, `attack`, `deposit`, `withdraw`. These would come from the Minecraft
client, not from Baritone, and would need a Fabric or Forge implementation
written by hand. Baritone contributes nothing to them. This is the real size of
the port: a Baritone backend is mostly _not_ Baritone.

**Mineflayer conveniences rather than portable concepts.** `stuck` reflects
mineflayer-pathfinder's `path_reset` event. `lastSafePosition`,
`recentlyDamaged` and `lastDamageTick` are adapter-maintained bookkeeping, easy
to reproduce but not facts the world reports. `registerOwnedStorage` is Person's
own ledger. `resources` and `hazards` being pre-filtered inside `snapshot()` is a
Mineflayer-era convenience; a client body would want to fill them differently.

**Where the data belongs.**

| Category                  | Examples                                                                                                                            |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Motor-private             | path nodes, `CalculationContext`, `BlockStateInterface`, the chunk cache, per-tick collision and hitbox state, movement internals   |
| Trusted runtime           | exact avatar position, the protected-region predicate result, vitals, inventory, guard verdicts, whether a goal was refused and why |
| Bounded Person perception | whatever `observation/perception.ts` already shapes, unchanged by this phase                                                        |

**Proposed interface delta, not to be implemented now.** No protocol change is
needed: `SkillInvocation` semantics are satisfiable by a Baritone backend as they
stand, since skills only ever ask for a destination and a tick budget. The one
change worth making eventually is to let `snapshot()` be asynchronous, or to
split the total snapshot into a cheap vitals read and an explicit world query,
because a client body cannot always answer a total synchronous snapshot without
blocking a game tick. That is a bigger decision than this phase should take, and
it is the decision C5 was already holding open. This spike does not resolve C5;
it sharpens it, and adds the finding that the port is mostly client-facing rather
than Baritone-facing.

## 9. Information-boundary findings

Enforcing the veto does **not** require leaking anything upward. The predicate is
a function from a position to a boolean, evaluated inside the motor process. The
trusted runtime supplies the region definition downward; the motor answers yes or
no and reports refusals as reason codes. Cognition sees a skill outcome, the same
as today.

That holds for every candidate evaluated, which is a genuinely good result: the
information firewall is not in tension with containment here.

Spike diagnostics, when Stage D is eventually run, must write privileged data
(exact positions, path node lists, cost values, cancel reasons) to explicitly
marked `motor_debug` or `privileged_telemetry` fields. That is operator
engineering data. It is not perception and must never be routed into an
`Observation`.

## 10. Risks and blockers

1. **Stop condition 5 triggered.** The only sufficient mechanism forks
   unsupported internals.
2. **Stop condition 7 triggered, twice.** Baritone is client-side only, and
   Person is on 1.16.1 with no Baritone branch for it.
3. **Stop condition 6, not triggered.** The project configures under Gradle 4.9
   and Java 8, and every 2021-era dependency still resolves. A full compile was
   not attempted. The Forge HTTP mirror is flaky and needed retries.
4. **Upstream is deprecated.** No fixes will ever come. Frozen is stable, but it
   is also abandoned.
5. **Licensing.** Baritone is LGPL-3.0, Person is MIT. A modified Baritone must
   be distributed as LGPL with source. Keeping the fork in its own repository and
   consuming a built artifact preserves the boundary. Vendoring modified source
   into this repository would not, and must not happen.
6. **Operational cost.** A graphical client per Person instance, a licensed
   account, roughly a gigabyte of game install, and a display or virtual
   framebuffer. There is no obvious CI story.
7. **C7, and it is the near-term one.** The current Mineflayer route veto does
   not cover every movement family. True today, in production, regardless of what
   happens with Baritone. Repaired in Phase 2; see `docs/CURRENT_STATE.md`, C7.

## 11. Recommended Phase 2

The smallest next milestone, and deliberately not a Baritone milestone:

**Close C7 against the body Person actually uses.** Prove the veto against the
real `mineflayer-pathfinder` rather than a double, and close whichever movement
families turn out not to honour it.

(Phase 2 did this. The measurement changed the diagnosis: the exclusion already
rejects rather than prices, and the actual gap was two generators that do not
consult it. See `docs/CURRENT_STATE.md`, C7.)

That is a small, self-contained change to a system Person already runs, it
removes a real gap between the fixture body and the live one, and it produces
the executable containment tests (the equivalents of tests 1, 2, 3 and 6) that a
future Baritone backend will have to pass. Doing it first means the Baritone
question can later be decided on its merits rather than under pressure.

There is also one thing worth doing that costs almost nothing and is independent
of all of the above: **set a vanilla world border on the experimental world.**
It is server-enforced rather than bot-trusted, it needs no code, and it gives a
real outer containment fence while the rest of this is being decided. It is not a
protected-area mechanism (section 5, C4b) and should not be described as one.

The Baritone question itself should go back to the operator as three decisions,
in this order: whether Person's body may require a graphical Minecraft client at
all; whether Person moves from 1.16.1 to 1.16.5; and only then, whether a
maintained LGPL fork of a deprecated branch is an acceptable dependency. Only the
third is really about Baritone, and it is the least of the three.

## 12. Reproducing this analysis

```bash
# Upstream source, in a scratch directory, never inside this repository
git clone --branch 1.16.5 --single-branch --depth 50 \
  https://github.com/cabaletta/baritone.git upstream
cd upstream && git checkout 9df406d

# The hard-exclusion prune
grep -n "COST_INF" src/main/java/baritone/pathing/calc/AStarPathFinder.java

# The stub protection hook and its only callers
grep -rn "isPossiblyProtected" src/main

# Per-tick cost re-verification during execution
grep -n "costVerificationLookahead" src/main/java/baritone/pathing/path/PathExecutor.java

# Process control runs before movement
grep -n "preTick\|tickPath" src/main/java/baritone/behavior/PathingBehavior.java

# Published artifact: supported API versus obfuscated implementation
curl -sLO https://github.com/cabaletta/baritone/releases/download/v1.6.5/baritone-api-1.6.5.jar
sha256sum baritone-api-1.6.5.jar
unzip -l baritone-api-1.6.5.jar | awk '{print $4}' | grep -c '^baritone/api/'
unzip -l baritone-api-1.6.5.jar | awk '{print $4}' | grep -E '^baritone/[^/]+\.class$' | head

# The hard spatial prune that already exists, bound to the vanilla world border
grep -n "worldBorder.entirelyContains" src/main/java/baritone/pathing/calc/AStarPathFinder.java
sed -n '18,50p' src/main/java/baritone/utils/pathing/BetterWorldBorder.java

# Configuration probe. Gradle 4.9 needs Java 8; the wrapper's own download
# fails on TLS under Java 8, so fetch the distribution with curl instead.
# The Forge HTTP mirror is flaky: expect to retry two or three times.
curl -sLO https://services.gradle.org/distributions/gradle-4.9-bin.zip && unzip -q gradle-4.9-bin.zip
JAVA_HOME=<path-to-temurin-8> ./gradle-4.9/bin/gradle tasks --no-daemon

# Person side: the exclusion cost is additive, and ordinary steps cost 1 to 2
grep -n "exclusionStep\|cost = 1\|cost = 2" node_modules/mineflayer-pathfinder/lib/movements.js
grep -n "exclusionAreasStep" -A 10 adapters/minecraft/src/embodiment.ts
```
