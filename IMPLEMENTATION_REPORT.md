# Implementation report

This report is cumulative. Milestone 0 below is the original record and is
unchanged; Milestone 1 follows it.

---

# Milestone 0: survival vertical slice and evidence substrate

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

---

# Milestone 1: reality validation

Date: 2026-09-15. Branch `feat/lan-validation`, from tag `v0.1.0-foundation`.

The full account is in `REALITY_VALIDATION.md`. This section records what
changed in the repository.

## The constraint that shaped this milestone

No Minecraft server was reachable: no Java process on the machine, nothing
listening on the configured LAN port, and no way to open a world from here.
Stages A through G of the validation order all require one.

The work therefore split in two. Everything that needs a live server is
prepared, instrumented and documented, and is reported as not run. Everything
that does not need one was done, which turned out to be more than expected: the
Mineflayer adapter was audited against the installed library and data sources,
and that audit found six defects the fixture could never have shown.

## Files changed

| Area                                                                                                                      | Change                                                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `adapters/minecraft/src/classify.ts`                                                                                      | New. Entity classification against the registry category, with an explicit huntable allowlist, a neutral-mob set, and custom-name extraction from sparse metadata.                                                                                                                        |
| `adapters/minecraft/src/embodiment.ts`                                                                                    | Entity view rebuilt; dimension, biome, light, armour and free slots read from the world; readiness and world-rule validation at connect; `inspectContainer`; server-authoritative recipes; partial smelt collection; container error mapping; damage tracking; diggable-ground reporting. |
| `adapters/minecraft/src/registry.ts`                                                                                      | Armour point table and armour slot indices for 1.16.1.                                                                                                                                                                                                                                    |
| `apps/node-runtime/src/embodiment/types.ts`                                                                               | Port gains `inspectContainer`, `EntityView.neutral`, `WorldSnapshot.recentlyDamaged`, `lastDamageTick` and `diggableGround`.                                                                                                                                                              |
| `apps/node-runtime/src/safety/safety-kernel.ts`                                                                           | `threats()` as the one definition of what counts; neutral mobs count once damaged; refuge chosen only where one can be dug.                                                                                                                                                               |
| `apps/node-runtime/src/skills/impl/emergency.ts`                                                                          | Emergency skills use the kernel's threat definition rather than a second copy.                                                                                                                                                                                                            |
| `apps/node-runtime/src/skills/impl/storage.ts`                                                                            | Withdrawals read live container contents.                                                                                                                                                                                                                                                 |
| `apps/node-runtime/src/skills/timing.ts`                                                                                  | New. Measures where a skill's ticks go by wrapping the port.                                                                                                                                                                                                                              |
| `apps/node-runtime/src/skills/executor.ts`                                                                                | Runs skills through the instrumented port; timing travels with the outcome.                                                                                                                                                                                                               |
| `apps/node-runtime/src/reporting/episode-report.ts`                                                                       | Per-skill tick budget aggregation and a budget-pressure line in the summary.                                                                                                                                                                                                              |
| `apps/cognition/python/person_cognition/prediction.py`                                                                    | New. Prediction error comparison and payload construction.                                                                                                                                                                                                                                |
| `apps/cognition/python/person_cognition/loop.py`                                                                          | Captures the predicted state, settles it against the next observation, records it as evidence.                                                                                                                                                                                            |
| `apps/cognition/python/person_cognition/reporting.py`                                                                     | Prediction-error summary in the learning report.                                                                                                                                                                                                                                          |
| `packages/persistence/python/person_persistence/events.py`                                                                | Evidence schema v2, reading v1 and v2, with `prediction_error` refused under v1.                                                                                                                                                                                                          |
| `packages/planner/python/person_planner/search.py`                                                                        | Plan cost accounts for parameter magnitude.                                                                                                                                                                                                                                               |
| `packages/skills/specs/eat_to_target.json`                                                                                | Contract corrected from measurement.                                                                                                                                                                                                                                                      |
| `apps/cli/src/observe.ts`                                                                                                 | New. Observation capture, semantic comparison, suspicious-default detection.                                                                                                                                                                                                              |
| `apps/cli/src/commands.ts`, `bin/person.ts`, `inspect.ts`                                                                 | `person observe`, `person compare`, `person inspect predictions`.                                                                                                                                                                                                                         |
| `fixtures/src/world.ts`, `blocks.ts`                                                                                      | Same contract as the adapter: neutrals, damage memory, diggable ground, `inspectContainer`.                                                                                                                                                                                               |
| `tests/support/mineflayer-double.ts`                                                                                      | New. A Mineflayer double built on real 1.16.1 data.                                                                                                                                                                                                                                       |
| `tests/adapter/`, `tests/safety/protected-routes.test.ts`, `apps/cognition/tests/test_prediction.py`, planner regressions | New tests, listed below.                                                                                                                                                                                                                                                                  |
| `docs/SEMANTIC_TARGETING.md`, `REALITY_VALIDATION.md`                                                                     | New documents.                                                                                                                                                                                                                                                                            |
| `docs/LAN_TESTING.md`                                                                                                     | Stage A and B rewritten around the new instruments.                                                                                                                                                                                                                                       |

## Architecture deviations

None. The trust boundary is unchanged: cognition still cannot name a
coordinate, still cannot send a command, and still cannot influence a safety
decision. Three additions were made inside the existing shape:

1. **The embodiment port grew three fields and one method.** `neutral`,
   `recentlyDamaged`, `diggableGround` and `inspectContainer` are all facts the
   runtime observes and the runtime uses. None of them reaches cognition except
   through the normalised observation, and `diggableGround` replaced a
   duplicate computation in the observation builder rather than adding one.
2. **The evidence schema moved to v2**, additively. v1 journals are read
   unchanged; only new records carry v2, and a v1 record claiming a v2 event
   type is rejected. This is the compatibility rule `migrations/README.md`
   already described.
3. **Prediction error is recorded but cannot act.** The statistics reducer has
   no case for it, and a test replays a journal with and without the records to
   prove the policy statistics are identical.

## Real Minecraft findings

Six defects and seven smaller corrections, all described with their evidence in
`REALITY_VALIDATION.md`. In short: entity metadata is an object and was treated
as an array, which would have thrown on first contact; named animals were
therefore never detected, making a named cow a legal hunting target; hostile
classification missed mobs the registry files as unknown; neutral mobs were
invisible to the safety kernel; the first withdrawal from any container always
failed; and crafting could fail on its own wood-species bookkeeping.

Separately, the observation carried three fields that were structurally valid
and semantically empty, and the planner tied on cost between parameterisations
of the same plan, which both diluted evidence and produced absurd magnitudes.

## New tests

| Suite                                          | Tests              | Covers                                                                                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/adapter/mineflayer-conformance.test.ts` | 27                 | Entity metadata and classification, damage memory, readiness, world rules, dimension, armour, light, biome, free slots, crafting authority, empty-craft failure, container inspection, transfer error mapping, deposit refusal, partial smelt, dig tool choice and safety, placement references and confirmation, attack guard and reach, eating, block search with position-less palette entries |
| `tests/safety/protected-routes.test.ts`        | 4                  | Detour around a protected strip, refusal with no legal detour and no partial movement, the pathfinder exclusion function as the replanning guarantee, refusal before any route is planned                                                                                                                                                                                                         |
| `apps/cognition/tests/test_prediction.py`      | 12                 | Effect semantics, severity classification, unexplained changes, volatile-fact suppression, settlement on the next observation, attribution to the executed skill, unobserved predictions, persistence, and that replaying prediction records changes no policy statistic                                                                                                                          |
| `packages/planner/tests/test_planner.py`       | 6 added            | Parameter-aware cost, sensible magnitudes, substantively different alternatives, using materials already held, no pointless repetition, expensive routes ranked last                                                                                                                                                                                                                              |
| `tests/safety/kernel.test.ts`                  | 1 added, 1 revised | Refuge chosen only where one can be dug, and fleeing where one cannot                                                                                                                                                                                                                                                                                                                             |
| `tests/cli/cli.test.ts`                        | 5 added            | Parsing, capture, capture to file, structural gaps and suspicious defaults, and a self-comparison finding nothing                                                                                                                                                                                                                                                                                 |

Totals: 108 Node tests and 120 Python tests, 228 in all, up from 173.

## Manual validation remaining

Unchanged in substance from Milestone 0 and now much better equipped. The
ladder in `docs/LAN_TESTING.md` starts with `person observe`, which connects,
validates readiness and world rules, takes one observation and stops. Nothing
below that rung has been climbed. The full blocker list is in
`REALITY_VALIDATION.md`.

## Next milestone

Unchanged, and now the only thing worth doing: run the ladder against a
disposable LAN world. Everything needed to do it, and to learn something from
doing it, is in place.

---

# Milestone 1 patch: pre-LAN readiness

Date: 2026-09-15. Branch `feat/lan-validation`.

A small readiness patch made immediately before the first live LAN run. No new
cognitive capability, no new skills, no planner or policy change.

## Why

The LAN port Minecraft assigns changes every time a world is reopened, so
treating it as file configuration would mean editing a file before every
session. And the first live connection is the least diagnosable moment in the
system: nothing downstream has run, so a failure there had no evidence beyond a
spawn timeout.

## Files changed

| Area                                              | Change                                                                                                                                                                                               |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `packages/config/ts/override.ts`                  | New. `--host` and `--port` overrides applied in memory, never written back, with validation and a human description of the resulting target.                                                         |
| `adapters/minecraft/src/diagnose.ts`              | New. Classifies connection failures into fourteen distinct reasons, each with an operator hint.                                                                                                      |
| `adapters/minecraft/src/embodiment.ts`            | `connect` races spawn against error, kick and close, so a refused login fails at once instead of waiting out the spawn timeout. Readiness distinguishes missing chunk data from general unreadiness. |
| `apps/node-runtime/src/embodiment/types.ts`       | `EmbodimentError` carries an operator hint.                                                                                                                                                          |
| `apps/node-runtime/src/reporting/status.ts`       | New. Atomic status file, renderer, staleness.                                                                                                                                                        |
| `apps/node-runtime/src/runtime/person-runtime.ts` | Writes status through the lifecycle; accepts and records an operator-intervention declaration.                                                                                                       |
| `apps/cli/src/observe.ts`                         | Optional body injection for tests, a status snapshot, a bounded disconnect, and a much fuller human-readable observation.                                                                            |
| `apps/cli/src/commands.ts`, `bin/person.ts`       | `--port`, `--host`, `--operator-intervention`, `person status`, `person status --follow`.                                                                                                            |
| `scripts/lan-check.sh`                            | Rewritten to separate "local setup ready" from "server currently reachable".                                                                                                                         |
| `docs/LAN_TESTING.md`                             | A First contact section: eleven numbered steps from opening the world to reading the result.                                                                                                         |

## Deviations

None. The trust boundary is untouched: `--port` is a runtime argument the
operator supplies, telemetry is written by the runtime and read only by the
CLI, and an architecture test asserts nothing on the decision path or in
cognition can read it back. Person still has no way to send a chat message or a
server command, which is also now asserted by a test.

## New tests

| Suite                                          | Tests   | Covers                                                                                                                                                                                                                                       |
| ---------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/adapter/connection-diagnostics.test.ts` | 8       | Each network failure class, version mismatch, kick classification, chat-component kicks, immediate failure on a refused login, close before spawn, spawn timeout                                                                             |
| `tests/cli/observe-safety.test.ts`             | 7       | Observe calls no physical operation and changes nothing, writes no evidence or report, records status, marks operator intervention, reports failure through status, survives a hung disconnect, and the port override never reaches the file |
| `tests/cli/status.test.ts`                     | 10      | Flag parsing, port and host validation, operator-intervention parsing, rendering, staleness, missing store, read-only by construction, follow reprinting only on change                                                                      |
| `tests/integration/vertical-slice.test.ts`     | 2 added | A marked run is recorded as contaminated in evidence and status; a clean run is not                                                                                                                                                          |
| `tests/architecture/architecture.test.ts`      | 3 added | No server-command path, no teleport on the port, telemetry is one-way                                                                                                                                                                        |

Totals: 138 Node tests and 120 Python tests, 258 in all.

## Still true

Person has never connected to a Minecraft server. This patch prepares the first
connection; it does not perform it.

---

# Milestone 1 patch 2: first-contact corrections

Date: 2026-09-15. Branch: `feat/lan-validation`.

## Why

Person connected to a real Minecraft 1.16.1 LAN world, spawned inside bounds,
produced a schema-valid Observation, reported its home correctly and
disconnected cleanly. `person observe` did exactly what it was built to do.

The Observation it produced was also wrong in three ways and preceded by a
failure that would not exit. This patch fixes those four things and nothing
else. No new capability, no new skill, no planner change, no learning change.

## What the first real observation exposed

| Symptom                                             | Actual cause                                                                                                                                                   |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `biome: "unknown"` in a loaded Overworld chunk      | `prismarine-block` builds its Biome class from `registry.version` rather than the registry, so `prismarine-biome` returns a nameless placeholder for every id. |
| The human operator reported as `name: "player"`     | Correct species name, no identity. Minecraft calls every player entity `player`; the account name and UUID were being discarded.                               |
| 64 resources, 55 of them stone, no wood at all      | A single nearest-N search across all kinds. Standing on stone, the budget is spent before anything else is reached.                                            |
| 80 passive animals, 70 outside the exploration area | No relevance filter at all on the entity lists.                                                                                                                |
| `spawn_outside_bounds` needed Ctrl-C                | `disconnect` ended the client twice; `minecraft-protocol` arms a 30s close timer per end and clears it only on the first close.                                |

## Files changed

| Area                                              | Change                                                                                                                                                                           |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/node-runtime/src/observation/perception.ts` | New. Every perception constant in one place, the category map, the balanced selection, and the entity-shaping helper. Used by both bodies.                                       |
| `apps/node-runtime/src/observation/builder.ts`    | Resource categories come from `perception.ts`; entity lists are shaped and bounded; entity records carry `username` and `uuid` when the body has them.                           |
| `apps/node-runtime/src/embodiment/types.ts`       | `EntityView` gains `username` and `uuid`.                                                                                                                                        |
| `adapters/minecraft/src/registry.ts`              | New `resolveBiome`, resolving the biome id against the client's own registry, with the upstream defect documented at the call site.                                              |
| `adapters/minecraft/src/embodiment.ts`            | Biome resolution, player identity normalisation, per-category resource search, and a disconnect that ends the client once and leaves no armed timer behind.                      |
| `fixtures/src/world.ts`                           | Same balanced search as the Minecraft body, and fixture entities can carry an identity.                                                                                          |
| `packages/protocol/schemas/*.json`                | `minecraftUsername` definition; `username` and `uuid` added to the entity list as optional properties.                                                                           |
| `packages/protocol/ts/types.ts`                   | `EntityRecord` gains the two optional fields.                                                                                                                                    |
| `apps/cli/src/observe.ts`                         | The rendered observation shows the resource mix by category and names players by account name.                                                                                   |
| `tests/support/mineflayer-double.ts`              | Biomes now have the shape `prismarine-block` really produces; `findBlocks` sorts by distance like the real one; optional emulation of the socket shutdown, close timer included. |
| `tests/support/observe-exit-child.ts`             | New. One failed observe in its own process, for the lifecycle test to wait on.                                                                                                   |

## Protocol change

Additive and unversioned. `username` and `uuid` are optional properties on the
existing entity list: an observation written before this patch still validates,
and one written after it validates under the same `observationVersion`. Both
runtimes read the same schema files, and the shared corpus gained a valid
message that uses both fields and an invalid one that misuses `username`, so
Node and Python are checked against the change rather than trusted to agree.

## Deviations

None. Perception shaping is not a safety boundary and is not allowed to become
one: the snapshot the safety kernel, the permission gate and the physical guard
read is unshaped, and a test asserts an animal dropped from the observation is
still refused by the permission gate for its own reason.

## New tests

| Suite                                  | Tests   | Covers                                                                                                                                                                                                         |
| -------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/adapter/biome.test.ts`          | 6       | The upstream defect pinned, resolution against the real registry, every 1.16.1 biome round-tripping to a protocol identifier, and both unknown fallbacks                                                       |
| `tests/adapter/perception.test.ts`     | 7       | Biome through the body, the unknown fallback, stone not hiding wood, budget bounds, determinism, two distinguishable players, unusable identities dropped                                                      |
| `tests/observation/perception.test.ts` | 7       | Out-of-region animals omitted while staying refused for their own reason, protections intact, bounded and nearest-first, hostiles never region-filtered, two players surviving into a schema-valid observation |
| `tests/cli/observe-exit.test.ts`       | 1       | A rejected spawn exits on its own, non-zero, with the reason, in a real child process                                                                                                                          |
| `tests/cli/observe-safety.test.ts`     | 1 added | Observe opens no cognition channel and spawns no process                                                                                                                                                       |
| `fixtures/protocol-corpus`             | 2 added | Player identity accepted, malformed username rejected, in both runtimes                                                                                                                                        |

Totals: 160 Node tests and 122 Python tests, 282 in all. `mise run check` is
green.

## Still true

These fixes have not been seen working against Minecraft. No server was
reachable while they were made. The next live action is a second
`person observe`.

# Milestone 2: single-skill live validation harness

Date: 2026-09-16. Branch: `feat/lan-validation`.

## Why

The second `person observe` against Minecraft came back clean: real biome,
the operator's own username and UUID, balanced resource perception, a short
list of nearby animals, learning off. Observation is finished.

The next thing Person does is act, and the first time it acts it should be
because a human asked for exactly one thing and watched what happened. That
needs an instrument, and the instrument must not be a second way to run
Person: it has to be the same safety kernel, the same permission gate, the same
executor and the same outcome accounting an autonomous run will use later.

## The invariant this milestone is really about

Before this patch there was one path from a `SkillInvocation` to a
`SkillOutcome` and it lived inside `PersonRuntime.#decide`, wound together with
the cognition channel. A harness could not use it without starting cognition,
and a harness that reimplemented it would be a second place to forget the
safety kernel.

So the path was extracted rather than copied. `skills/dispatch.ts` now holds
it, `PersonRuntime` calls it, and the validation harness calls it. The
architecture test that used to assert "person-runtime validates before it
executes" now asserts something stronger: dispatch validates before it
executes, there are exactly two execution sites in it, and neither the runtime
nor the harness runs a skill or touches a skill implementation directly.

## Files changed

| Area                                                 | Change                                                                                                                                                                                                              |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/node-runtime/src/skills/dispatch.ts`           | New. The one road from a SkillInvocation to a SkillOutcome: validate, execute what the verdict allowed, hand over to the emergency skill on preemption, credit what ran. Extracted verbatim from the decision loop. |
| `apps/node-runtime/src/runtime/person-runtime.ts`    | `#decide` now dispatches instead of validating and executing itself. Its hooks send the same messages to cognition in the same order as before.                                                                     |
| `apps/node-runtime/src/validation/skill-test.ts`     | New. The harness: connect, optional operator setup, pre-observation, one dispatch, post-observation, release the body, compare effects, write the report.                                                           |
| `apps/node-runtime/src/validation/report.ts`         | New. The validation report and its terminal summary.                                                                                                                                                                |
| `apps/node-runtime/src/validation/effects.ts`        | New. Runs the cognition package's prediction-error comparison once over the two observations, and degrades to "inconclusive" rather than failing the run.                                                           |
| `apps/node-runtime/src/validation/learning-state.ts` | New. Fingerprints the evidence store by content hash, so "learning unchanged" is measured rather than asserted.                                                                                                     |
| `apps/node-runtime/src/reporting/status.ts`          | Optional `phase`, so `person status` can tell a validation run from an autonomous one and an operator-setup pause from an executing skill.                                                                          |
| `apps/cognition/python/person_cognition/effects.py`  | New. The comparison, expressed entirely in terms of `symbolic_state` and the existing `compare`. Adds only the verdict vocabulary and the list of facts an observation cannot carry.                                |
| `apps/cognition/python/person_cognition/__main__.py` | `--compare-effects <request>`: a one-shot analysis that returns before any loop, policy or evidence store is constructed.                                                                                           |
| `apps/cli/src/skill-test.ts`                         | New. `person skill-test`, the operator-setup prompt, and the terminal summary.                                                                                                                                      |
| `apps/cli/src/bin/person.ts`                         | `skill-test`, `--skill`, `--operator-setup`.                                                                                                                                                                        |
| `fixtures/src/world.ts`                              | `disconnect` and `dropConnection` invalidate the cached snapshot. A body that still answers "connected" from a stale snapshot hides the thing the hook simulates.                                                   |

## How the trust boundary is preserved

- `--skill` resolves against the registry and nothing else. An unknown name is
  refused before a connection is opened.
- Parameters are resolved by `SkillRegistry.resolveParameters`, so the only
  parameters that exist are the ones a SkillSpec declares, and they are scalars.
  A test asserts no registered skill exposes anything shaped like a coordinate.
- There is no free-form argument. The parser rejects `--command`, `--script`,
  `--position` and the like as unknown options, which is also tested.
- Cost limits come from the spec, not from the caller.
- The kernel's verdict is authoritative and reported verbatim. A REJECT runs
  nothing; a REPLACE reports the requested skill as PREEMPTED and names the
  emergency skill that actually ran.
- Home comes from `WorldMemory`, as it always did. Nothing in the CLI or the
  invocation can say where home is.

## Learning neutrality

A validation run is not an experience. It writes no evidence, no episode
report, and no policy snapshot, and it starts no cognition loop. The evidence
directory is fingerprinted by content hash before and after the run and both
fingerprints go into the report, so a run that accidentally changed learning
state would be obvious in its own record rather than discovered later.

The physical result is not discarded: it is stored separately, under
`runs/validation/skill-tests/`, with both observations, the outcome, the safety
decision and the effect comparison.

## The effect comparison

Reused, not rebuilt. `person_cognition.effects` is a thin shell over
`person_planner.symbolic_state` and `person_cognition.prediction.compare`, the
same pair that settles prediction error during a live run. The harness writes a
request, runs the configured cognition command once with `--compare-effects`,
and reads the answer back as JSON.

Nothing physical crosses that boundary in either direction: the request is two
observations and a list of declared effects, and the answer is a verdict per
fact. A fact an Observation cannot carry (`rested`, `stored_surplus`,
`withdrawn`, `looted`) is reported as `not_observable` rather than as a failed
prediction, and a Python test asserts those facts really are underivable. If
the comparison cannot run at all, every fact is `inconclusive` and the report
says why; the skill still ran and the report is still written.

## Operator setup

`return_home` has to start away from home, and Person has no teleport
capability. Rather than giving it one, `--operator-setup` pauses the run after
connection and readiness, prints `READY FOR OPERATOR SETUP`, and waits for the
operator to press Enter. Person is physically inert throughout: a test records
every call made to the body and asserts none of them happened before the
confirmation.

Before the measured run begins, the state is re-checked: still connected, still
alive, in the Overworld, inside the configured exploration area and not in a
protected area. Any of those failing refuses the test rather than measuring
something else. Whether the human actually moved Person is never guessed at,
and a run that used the setup phase is recorded as operator-contaminated.

## Deviations

One, deliberate. The effect comparison runs a Python subprocess, which no
other Node command does. The alternative was a second implementation of the
comparison in Node, which would drift from the first one and quietly make a
validation report and a prediction-error record mean different things. The
subprocess is a pure function over two JSON documents: it starts no loop,
reads no evidence, proposes nothing, and cannot fail the run.

## New tests

| Suite                                        | Tests     | Covers                                                                                                                                                                                                                                                                                              |
| -------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/validation/skill-test.test.ts`        | 19        | wait_safely and return_home end to end, unknown skill, bad parameters, REJECT, REPLACE, pre/post observations, learning unchanged, report shape, status phases, operator setup inert and explicitly confirmed, invalid setup states, disconnect mid-skill, bounded disconnect, report write failure |
| `tests/validation/skill-test-exit.test.ts`   | 4         | The whole command in a real child process: success, refusal, operator setup answered, operator setup abandoned. Each must exit without being killed                                                                                                                                                 |
| `tests/integration/skill-validation.test.ts` | 3         | The real comparison end to end: an effect the world confirms, one it cannot carry, and a comparison that cannot run                                                                                                                                                                                 |
| `apps/cognition/tests/test_effects.py`       | 7         | Match, mismatch, not observable, missing post-observation, the unobservable facts really being unobservable, and the entry point never returning anything that could become a request                                                                                                               |
| `tests/cli/cli.test.ts`                      | 2 added   | `skill-test` parsing, and that no free-form option is accepted                                                                                                                                                                                                                                      |
| `tests/architecture/architecture.test.ts`    | rewritten | Dispatch is the only path, and neither caller bypasses it                                                                                                                                                                                                                                           |

Totals: 188 Node tests and 129 Python tests, 317 in all. `mise run check` is
green.

## Still true

Neither skill has been run against Minecraft through this harness. No server
was reachable while it was built. The next live actions are `wait_safely` and
then `return_home` with `--operator-setup`, in that order.
