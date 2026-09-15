# Implementation report

Milestone: the Person survival vertical slice and evidence substrate.
Date: 2026-09-15.

## Implemented

**Runtime foundation.** Two processes with an asymmetric contract. Node spawns
the Python cognition process over stdio, stays the parent, and keeps control of
the body if cognition crashes, hangs, or sends something it is not entitled to
send. mise pins Node 22.23.2 and Python 3.12; npm and uv pin every direct
dependency exactly.

**Versioned protocol `shroud-learning-v2`.** Eleven message types defined by
canonical JSON Schemas in `packages/protocol/schemas/`, compiled by Ajv on the
Node side and `jsonschema` on the Python side. A shared corpus of 11 valid and
18 invalid messages is run by both, and a contract test executes the Node
validator as a subprocess and asserts the two agree on every entry. Framing is
newline-delimited JSON with a one-megabyte cap and a bounded reader.

**Embodiment port with two implementations.** Skills are written once against
`Embodiment`. `MineflayerEmbodiment` drives a real 1.16.1 client;
`FixtureWorld` is a deterministic simulation. Fixture tests therefore exercise
the same skill code that runs against Minecraft.

**Safety kernel and validator.** An L0 to L4 hierarchy owned entirely by Node.
The kernel is a pure function of the world snapshot, evaluated before every
proposal and at every execution checkpoint. The validator returns ACCEPT,
REJECT, PREEMPT or REPLACE, clamps cost limits down to the skill contract, and
re-checks parameters and permissions. Protected areas are enforced at proposal
validation, route selection, skill execution and each destructive interaction.

**Twenty-one skills, all really implemented.** Emergency, food, resources,
crafting, shelter and storage, each with a canonical SkillSpec and a working
implementation. An architecture test asserts the two sets are identical, and
another asserts no implementation contains a placeholder.

**Executed-action attribution.** Every `SkillOutcome` carries both the
requested and the executed skill. When the runtime replaces a proposal, the
executed skill receives the attempt and the requested skill receives a
preemption and no attempt. The canonical case is tested end to end across two
processes: requested `gather_wood`, executed `flee`, credited to `flee`.

**Cognition.** A coarse decision context of seven bounded dimensions; a
homeostatic survival goal provider; a goal stack with queue, activate, suspend,
resume, block and complete; a means-ends planner that derives strategies from
skill preconditions and effects and returns only minimal, contract-feasible
plans; a routine model that supports nesting with stable content-derived
identifiers; a deterministic fallback policy and an evidence policy with a
Beta posterior, risk-dominant scoring and a safe exploration envelope.

**Evidence and restart.** An append-only, fsynced, chained journal; atomic
checksummed snapshots; strict reading that refuses corruption, ignores
duplicates and drops only a crash-truncated tail; restore that replays after
the newest valid snapshot and falls back to a full rebuild whenever the
snapshot is unusable or disagrees with the journal. Statistics are keyed by
training context so fixture and live evidence never merge.

**Learning modes.** off, shadow and supervised, never transitioned
automatically. Every shipped configuration is off.

**CLI.** `person run | learn | validate | inspect`, with `shroud` and
`shroud-train` aliases, strict argument parsing, clear configuration errors,
legacy configuration migration and legacy checkpoint refusal.

**Reporting.** A per-episode JSON report from the runtime and a learning
summary from cognition, together answering every question in the
observability requirements with semantic identifiers.

**Future interfaces.** Memory, WorldModel, Affect, Language, Social, Project
and Exploration providers exist as minimal protocols with placeholder
implementations that raise, so nothing can mistake one for a working system.

## Reused from legacy Shroud

The donor was read extensively and adapted. Nothing was copied verbatim: every
transplant was rewritten against the new boundary, and the Person abstractions
exist for Person's reasons.

| Source                                                                                                                                                                                 | Destination                                                                                                                                                        | Adaptation                                                                                                                                                                                                                                                                                                          |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/minecraft.js` connect, movement configuration, dig safety checks, placement reference search and confirmation loop, drop collection, navigation timeout and `path_reset` handling | `adapters/minecraft/src/embodiment.ts`                                                                                                                             | Rewritten to implement the `Embodiment` port. Safety decisions removed and replaced by the Person guard, which is consulted on every step the path search considers, not only at the destination.                                                                                                                   |
| `src/minecraft.js` `flee`, `digIn`, `retreat`, `leaveShelter`                                                                                                                          | `apps/node-runtime/src/skills/impl/emergency.ts`, `apps/node-runtime/src/skills/shelter-access.ts`                                                                 | Kept the shape: short hops rather than one long route, bounded defensive strike only against a hostile in contact, refuge dug away from the threat and sealed, shelter doorway opened and resealed. Rewritten against the port so the fixture exercises the same code.                                              |
| `src/shelter.js` `shelterPlan`, `entrance`, `verifyShelter`                                                                                                                            | `apps/node-runtime/src/skills/shelter-plan.ts`, `shelter-access.ts`                                                                                                | Same three by three by three enclosure and two-block doorway, with roof ordering preserved. Verification moved into the skill so it produces completion evidence.                                                                                                                                                   |
| `src/crafting.js` `planCraft`                                                                                                                                                          | `apps/node-runtime/src/skills/recipes.ts`                                                                                                                          | Kept the recursive ensure-and-expand shape and the preferred-wood normalisation. Extended with stone tools, furnace and chest, and given a typed error naming the first missing material.                                                                                                                           |
| `src/safety.js` `LOGS`, `HAZARDS`, `THREATS`, `RANGED_THREATS`, `FOOD`                                                                                                                 | `adapters/minecraft/src/registry.ts`, `apps/node-runtime/src/skills/materials.ts`                                                                                  | Split into a Minecraft name mapping for the adapter and a semantic item classification for skills. Extended with cooked food, smelting, fuel values and tool tiers.                                                                                                                                                 |
| `src/config.js` `contains`, `intersects`, `point`, bounds validation, loopback host pin, 1.16.1 pin, offline auth, dedicated username                                                  | `packages/config/ts/geometry.ts`, `packages/config/ts/load.ts`                                                                                                     | Kept the geometric validation and the authorisation assertions. Moved schema checking into a shared JSON Schema both runtimes read, and added the home-footprint-inside-exploration check.                                                                                                                          |
| `src/report.js` atomic summary writing with temp file and rename                                                                                                                       | `apps/node-runtime/src/reporting/episode-report.ts`, `apps/node-runtime/src/runtime/world-memory.ts`, `packages/persistence/python/person_persistence/snapshot.py` | Same technique, applied to every durable write on both sides.                                                                                                                                                                                                                                                       |
| `bin/shroud.js` strict argument parsing, refusal of duplicates and incomplete options                                                                                                  | `apps/cli/src/bin/person.ts`                                                                                                                                       | Same discipline, new command set.                                                                                                                                                                                                                                                                                   |
| `bin/rl-bridge.js` and `trainer/src/shroud_rl/bridge.py` newline-delimited JSON over stdio with size caps                                                                              | `packages/protocol/ts/framing.ts`, `packages/protocol/python/person_protocol/framing.py`, `apps/node-runtime/src/ipc/cognition-channel.ts`                         | Kept the transport choice and the bounded-buffer discipline. Replaced the request-response lockstep with a typed message stream, and added direction filtering so cognition cannot send a runtime message type.                                                                                                     |
| `test/minecraft-fixture.js`                                                                                                                                                            | `fixtures/src/world.ts`                                                                                                                                            | Concept reused, implementation replaced. The new fixture drops the `minecraft-data` and `prismarine-*` dependencies and models blocks, entities, containers, hunger, damage, hostile pursuit, day phase and scripted events with its rules visible in one file. It also pathfinds, which the donor fixture did not. |
| `src/planner.js` `isNight` and day-phase thresholds                                                                                                                                    | `apps/cognition/python/person_cognition/context.py`                                                                                                                | Thresholds reused as the day-phase buckets.                                                                                                                                                                                                                                                                         |
| `src/escape.js` clearance-based escape scoring                                                                                                                                         | `flee` direction selection                                                                                                                                         | Simplified to a greedy clearance improvement over sampled directions, since the fixture and Mineflayer both provide route search underneath.                                                                                                                                                                        |

## Rewritten or discarded

Discarded deliberately, as instructed:

- the tabular Q-learning policy, the seven-action space, `RL_ACTIONS`,
  `actionMask`, epsilon-greedy exploration and V1 checkpoints;
- `src/routine-primitives.js`, `src/routine-learner.js` and
  `src/routine-journal.js`, whose abstract state and reward function were built
  around that action space;
- `src/rl-bridge.js` request-response lockstep and `enforceDecision`, replaced
  by the typed validator at the trust boundary;
- the `gymnasium` and `numpy` dependency, which the evidence-guided learner does
  not need;
- `src/cache.js` and `src/world-cache.js` chunk eviction, which belongs to the
  adapter's own concerns and is not needed by the fixture;
- `src/resume.js` inventory reconciliation, which encoded a V1 recovery
  protocol. Ownership is now tracked as provenance records in `WorldMemory`;
  the reconciliation behaviour itself is not reimplemented, and that is listed
  below as a gap.

No Person abstraction exists because legacy Shroud needed it. The donor
contributed implementation knowledge, not architecture.

## Architectural deviations

1. **npm workspaces are not used.** The repository is one npm package with Node
   subpath `imports` aliases (`#protocol`, `#skills`, `#config`,
   `#node-runtime`, `#minecraft-adapter`, `#fixture-world`). Node refuses to
   strip types from TypeScript inside `node_modules`, so workspace symlinks
   would have forced a compile step before every test run. The directory
   structure is unchanged and the boundaries are enforced by architecture tests
   rather than by package manifests.

2. **Package languages.** `protocol`, `skills` and `config` are dual-language
   (canonical JSON assets plus a thin binding for each runtime). `planner`,
   `policy` and `persistence` are Python distributions in a uv workspace. The
   brief's tree does not say which language each package is; this is the
   concrete realisation.

3. **All durable evidence is written by cognition.** The brief assigns learning
   and persistence to Python and execution to Node. Rather than splitting the
   journal, there is exactly one writer. Node writes its own episode report and
   a small provenance cache, both atomically. The consequence is listed under
   limitations.

4. **`PREEMPT` appears only mid-execution.** At proposal time an emergency
   produces `REPLACE`; a checkpoint during execution produces `PREEMPT`, the
   running skill stops, and the emergency skill runs. Both verdicts exist in the
   schema and both are exercised by tests.

5. **Cost limits are clamped rather than rejected.** A proposal asking for a
   larger budget than its spec allows is accepted with the reason code
   `limits_clamped_to_spec`, since clamping is the safe direction and rejecting
   would make a harmless over-request fatal.

6. **Two message types beyond the listed set.** `SessionHello` and
   `CognitionReady` carry the handshake: learning mode, training context,
   evidence directory, seed, skill library revision, and what cognition
   restored. Without them the session has no authoritative start.

7. **`permissions` and `affordances` were added to the Observation.** Cognition
   would otherwise have to read configuration to know whether building or
   hunting is allowed, or whether the ground here can be dug. Both now come from
   the side that enforces them.

8. **No SQLite.** The specification suggests SQLite as the initial store. This
   milestone uses an append-only JSONL journal plus atomic JSON snapshots, which
   is what the append-only evidence requirements actually ask for, with one
   fewer dependency. Nothing prevents a later SQLite index over the same
   journal.

9. **`docs/PERSON_SPEC.md` was reformatted once by Prettier** during a
   repository-wide format, which rewrote its list markers from `*` to `-`. The
   markers were restored and the file added to `.prettierignore`. Its content
   was not otherwise altered, but the file's mtime changed and the original
   trailing blank line was not restored.

10. **No CI workflow was added.** The repository is not published on GitHub and
    is not currently a git repository at all, so the standing CI, CD and README
    policy does not yet apply. `mise run check` runs the whole gate locally and
    is what a pipeline would call.

## Automated test results

All commands were run from the repository root on 2026-09-15.

```
$ npm run typecheck
> tsc --noEmit -p tsconfig.json
(no output, exit 0)

$ npm run build
> tsc -p tsconfig.build.json
(no output, exit 0; dist/ emitted)

$ npm run format:check
Checking formatting...
All matched files use Prettier code style!

$ npm test
# tests 71
# pass 71
# fail 0
# duration_ms 35740.666952

$ uv run pytest
102 passed in 5.57s

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
55 files already formatted

$ uv run mypy
Success: no issues found in 32 source files
```

Coverage by area, 173 tests in total:

| Suite                          | Tests   | Covers                                                                                 |
| ------------------------------ | ------- | -------------------------------------------------------------------------------------- |
| Protocol (Node and Python)     | 10 + 37 | Corpus conformance, cross-runtime agreement, framing, envelopes                        |
| Skills                         | 14      | Effects, evidence, bounds, timeout, unreachable, death, disconnect, storage provenance |
| Safety                         | 22      | Protected areas at every level, permissions, kernel verdicts, clamping, attribution    |
| Architecture (Node and Python) | 10 + 10 | The boundary itself, no command channel, no code generation, learning off by default   |
| Planner                        | 14      | Feasible, minimal, deterministic plans for every survival goal                         |
| Policy                         | 11      | Uncertainty, attribution, risk preference, modes, envelope suppression                 |
| Persistence                    | 10      | Duplicates, corruption, truncation, snapshots, rebuild, demonstrations                 |
| Configuration                  | 5       | Schema, cognition cross-check, legacy checkpoint refusal                               |
| Cognition                      | 15      | Context, goals, suspension and resumption, loop, restart reuse                         |
| CLI                            | 7       | Parsing, validation, migration, inspection                                             |
| Integration                    | 8       | The full survival routine, emergencies, the vertical slice with restart                |

The vertical slice acceptance scenario
(`tests/integration/vertical-slice.test.ts`) runs the real cognition process
twice against one fixture world and asserts: food recognised, gathered and
eaten; shelter gathered and built; every decision explainable with a semantic
context and an evidence trail; an injected hostile producing an emergency
override whose outcome credits `flee`; an unbroken event chain with unique ids;
and a restarted process appending to the same chain and making a decision
informed by evidence recorded before the restart.

Critical safety violations in deterministic tests: 0.

## Manual validation remaining

None of the automated suite touches a Minecraft server. `docs/LAN_TESTING.md`
is the ladder. Specifically unverified:

1. Mineflayer connection, authentication, spawn validation and disconnection
   against a live 1.16.1 LAN world.
2. Every skill against the real server: placements the server may refuse,
   crafting through the real recipe registry, furnace timing, container
   transfers, and drops landing where the collector can reach them.
3. `mineflayer-pathfinder` behaviour on real terrain, including the guard
   rejecting steps into protected areas during live replanning.
4. Real hostile behaviour, damage rates, and whether the flee clearances and
   dig-in refuge are adequate at Normal difficulty.
5. Whether the tick budgets in the skill specs are realistic at 20 ticks per
   second on a real server.
6. Death and respawn in a live world.
7. Multi-day autonomous survival with a restart in the middle.

The fixture tests prove the skill logic, the boundary and the evidence
pipeline. They do not prove any of the seven items above, and no claim in this
report should be read as proving them.

## Known limitations

- The Mineflayer adapter has never been run against a server. It is written
  carefully and typechecks, and it is the component most likely to need work.
- There is no dig-down skill, so `mine_stone` and `mine_coal` need exposed
  stone or ore. The fixture worlds provide surface stone accordingly.
- The fixture is a simulation, not Minecraft. Its rules are visible in
  `fixtures/src/` precisely so that nobody mistakes it for one.
- The planner is bounded by depth, branch quotas and a node budget. It is not
  complete: a goal needing a deeper or wider search than the caps allow returns
  no plan, and the goal is blocked rather than failing silently.
- Goals are survival only. Projects, social commitments and self-generated
  goals are future scope; the goal stack already supports suspension and
  resumption for them.
- Death ends the episode. There is no respawn and recovery loop.
- Evidence is written by cognition, so if the cognition process dies
  mid-episode the last outcome is missing from the journal. The runtime's
  episode report still records it, and the journal's chain stays intact.
- The donor's inventory reconciliation on resume was not reimplemented. Person
  tracks provenance of what it placed, but does not reconcile an inventory that
  changed while it was not running.
- `loot_permitted_container` withdraws up to `amount` of every item type it
  finds, rather than choosing.
- One Person per runtime. Nothing in the architecture prevents more; nothing
  supports it yet either.

## Risk areas

Most likely to fail first under real Minecraft conditions, in order:

1. **Placement confirmation.** The donor fought this: the server can accept the
   world update before the inventory packet arrives, or refuse a placement the
   client believed succeeded. The adapter retries and then fails explicitly,
   which is the right shape, but the timings are untested.
2. **Pathfinder.** Real terrain, mobs in the way, and the exclusion areas the
   guard installs interact in ways a straight-line fixture cannot reproduce.
   Expect `no_route` failures that the fixture never produces.
3. **Furnace timing.** `smelt` waits on the output slot with a generous margin.
   Server lag or a full output slot could still time out.
4. **Drop collection.** After a kill or a dig, the adapter walks to the drop.
   Drops that scatter, fall, or land in a protected area will not be collected.
5. **Flee adequacy.** The clearance target and hop sizes were tuned against a
   fixture whose mobs move deterministically. Real mobs, especially ranged ones,
   may need the donor's larger margins.
6. **Tick budgets.** Every spec has a `maxTicks`. If real operations are slower
   than the fixture suggests, skills will report `TIMED_OUT` rather than
   failing informatively.

## Research readiness

The evidence format preserves what later research will need, and does not
implement any of it.

Preserved: semantically versioned observations; expected effects stored next to
observed effects on every outcome; the executed action distinguishable from the
requested one, which is what separates an intervention from an intention;
world, session, episode and training-context provenance on every event; RNG
seeds on fixture episodes; an unbroken `previous_event_id` chain; raw counts
rather than scores, so a new scoring function re-reads history; and
`evidence_refs` on every statistic so a future belief can point back at the
episodes that produced it.

This means prediction-error analysis, causal-belief learning, memory
consolidation, held-out generalisation tests and transfer experiments can be
built on episodes recorded now. It does not mean any of them exist. Nothing in
this milestone predicts, infers causes, consolidates memories or measures
transfer, and the reports contain no prediction-error column because nothing
produces one.

## Next milestone

The smallest sensible next stage is to close the gap this report is most
explicit about, before adding any new capability:

1. **Run the LAN ladder** in `docs/LAN_TESTING.md` end to end on a disposable
   world, and fix what it finds. Expect the work to land in
   `adapters/minecraft/src/embodiment.ts` and in the tick budgets in
   `packages/skills/specs/`. Nothing above the embodiment port should need to
   change, and if it does, that is the finding worth having.
2. **Record a live evidence store** in `minecraft_peaceful`, separate from the
   fixture store by construction, and compare routine statistics between the
   two. That is the first real transfer measurement the architecture supports.
3. **Add prediction-error logging.** Every outcome already carries expected and
   observed effects. Computing the difference and storing it as a derived
   column is a small change that turns the existing evidence into the input a
   `WorldModelProvider` needs, without implementing one.

After that, held-out fixture worlds and the first `WorldModelProvider`
implementation become worth attempting. Adding memory, affect or language
before the body is validated against a real server would build on an
unverified foundation.
