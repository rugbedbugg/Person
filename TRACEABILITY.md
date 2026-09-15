# Traceability

Each row maps a requirement from `docs/PERSON_SPEC.md` and the implementation
brief to the code that implements it and the tests that hold it in place. The
point of this document is auditability: a reader should be able to check any
claim without reading the whole tree.

## Architectural invariant and trust boundary

| Requirement                                 | Implementation                                                                                     | Tests                                                                                                                                                               |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python proposes, Node decides               | `apps/node-runtime/src/runtime/person-runtime.ts`, `apps/node-runtime/src/safety/validator.ts`     | `tests/architecture/architecture.test.ts` (no proposal reaches an executor without passing the validator)                                                           |
| No raw action channel from Python           | `packages/protocol/schemas/skill-invocation.schema.json`, `common.schema.json` (`skillParameters`) | `tests/architecture/architecture.test.ts`, `packages/protocol/ts/protocol.test.ts`, `packages/protocol/tests/test_protocol.py`, `tests/python/test_architecture.py` |
| Cognition holds no Minecraft access         | `adapters/minecraft/` is the only Mineflayer importer                                              | `tests/architecture/architecture.test.ts`, `tests/python/test_architecture.py`                                                                                      |
| Node stays authoritative if cognition fails | `apps/node-runtime/src/ipc/cognition-channel.ts` (`CognitionUnavailableError`, decision timeout)   | `apps/cognition/tests/test_loop.py` (malformed input dropped), channel direction check in `tests/architecture/`                                                     |
| Cognition can only send decisions           | `CognitionChannel.#ingest` direction filter                                                        | `tests/architecture/architecture.test.ts`                                                                                                                           |

## Protocol

| Requirement                                       | Implementation                                                                           | Tests                                                                               |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Versioned protocol `shroud-learning-v2`           | `packages/protocol/ts/version.ts`, `packages/protocol/python/person_protocol/version.py` | `packages/protocol/ts/protocol.test.ts`, `packages/protocol/tests/test_protocol.py` |
| Replay metadata on every message                  | `packages/protocol/schemas/common.schema.json` (`envelope`)                              | both protocol suites                                                                |
| One canonical schema representation               | `packages/protocol/schemas/*.json` compiled by both runtimes                             | `test_node_and_python_validators_agree_on_the_whole_corpus`                         |
| Unknown schema versions rejected with diagnostics | `ProtocolValidator.validate` in both bindings                                            | both protocol suites                                                                |
| Malformed messages rejected, logged, not executed | `packages/protocol/*/framing`, `CognitionChannel.#ingest`                                | `packages/protocol/*` framing tests, `apps/cognition/tests/test_loop.py`            |
| Core message types present                        | `SCHEMA_FILES` in both bindings                                                          | `tests/architecture/architecture.test.ts`                                           |

## Observation and context

| Requirement                         | Implementation                                       | Tests                                            |
| ----------------------------------- | ---------------------------------------------------- | ------------------------------------------------ |
| Normalised semantic observation     | `apps/node-runtime/src/observation/builder.ts`       | `tests/integration/vertical-slice.test.ts`       |
| No raw Mineflayer objects exposed   | `Observation` schema, `unevaluatedProperties: false` | protocol suites, architecture tests              |
| Coarse decision context             | `apps/cognition/python/person_cognition/context.py`  | `apps/cognition/tests/test_context_and_goals.py` |
| Deterministic context serialisation | `DecisionContext.identifier`                         | same                                             |
| No context explosion                | seven bounded dimensions                             | `test_the_context_space_stays_small`             |

## Skills

| Requirement                                  | Implementation                                           | Tests                                                                          |
| -------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Typed SkillSpec contract                     | `packages/skills/specs/*.json`, `skill-spec.schema.json` | `packages/skills` registries load and validate at import; `tests/architecture` |
| All 21 skills implemented for real           | `apps/node-runtime/src/skills/impl/`                     | `tests/skills/`, `tests/integration/survival-routine.test.ts`                  |
| Implementations match the library exactly    | `SKILL_IMPLEMENTATIONS`                                  | `tests/architecture/architecture.test.ts`                                      |
| No placeholder implementations               | same                                                     | `tests/architecture/architecture.test.ts`                                      |
| Precondition enforcement                     | `SkillRegistry.resolveParameters`, per-skill guards      | `tests/skills/resources.test.ts`, `tests/skills/food-and-shelter.test.ts`      |
| Effect evidence                              | `SkillContext.note`, `ExecutionResult.evidenceKinds`     | `tests/skills/*`                                                               |
| Time and resource bounds                     | `SkillRunner.run` checkpoint                             | `tests/skills/resources.test.ts` (TIMED_OUT)                                   |
| Interruption, unreachable, death, disconnect | `SkillRunner` error mapping                              | `tests/skills/resources.test.ts`, `tests/integration/survival-routine.test.ts` |
| Exactly one terminal state                   | `TerminalStatus` in the schema and runner                | protocol suites, skill suites                                                  |

## Safety

| Requirement                                             | Implementation                                                         | Tests                                                                                                      |
| ------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| L0 to L4 hierarchy                                      | `apps/node-runtime/src/safety/safety-kernel.ts`                        | `tests/safety/kernel.test.ts`                                                                              |
| Deterministic emergency mechanism                       | `SafetyKernel.assess` is a pure function of the snapshot               | `test_the_emergency_assessment_is_deterministic`                                                           |
| ACCEPT, REJECT, PREEMPT, REPLACE                        | `apps/node-runtime/src/safety/validator.ts`, `PersonRuntime.#decide`   | `tests/safety/kernel.test.ts`, `tests/safety/attribution.test.ts`                                          |
| Protected areas enforced at four levels                 | `safety/protected-areas.ts`, `PersonRuntime.guard`, skill-level checks | `tests/safety/permissions.test.ts`                                                                         |
| Route cannot clip a protected area                      | `ProtectedAreas.routePermitted`, guard in path search                  | `test_a_path_may_not_clip_a_protected_area`, `test_navigation_cannot_route_through_a_protected_area`       |
| Existing-container deposit impossible                   | schema constant, `PermissionGate.mayDeposit`, embodiment refusal       | `tests/safety/permissions.test.ts`, `tests/skills/storage.test.ts`, `packages/config/tests/test_config.py` |
| Owned storage deposit and withdrawal                    | `skills/impl/storage.ts`, `runtime/world-memory.ts`                    | `tests/skills/storage.test.ts`                                                                             |
| Storage provenance records                              | `WorldMemory.recordStorage`                                            | `tests/skills/storage.test.ts`, `tests/integration/survival-routine.test.ts`                               |
| Villagers, named, tamed animals, players never targeted | `PermissionGate.mayHunt`, guard `canTargetEntity`                      | `tests/safety/permissions.test.ts`, `tests/skills/food-and-shelter.test.ts`                                |
| Player combat out of scope                              | schema constant `players.combat: false`                                | `tests/safety/permissions.test.ts`                                                                         |
| Limits clamped down, never up                           | `safety/validator.ts` `clamp`                                          | `tests/safety/kernel.test.ts`                                                                              |

## Attribution

| Requirement                                | Implementation                                             | Tests                                                                         |
| ------------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Outcome names requested and executed skill | `skill-outcome.schema.json`, `PersonRuntime.#buildOutcome` | `tests/safety/attribution.test.ts`, `tests/architecture/architecture.test.ts` |
| Requested `gather_wood`, executed `flee`   | runtime REPLACE path                                       | `tests/safety/attribution.test.ts`                                            |
| Learning credits the executed skill        | `RoutineStatistics.apply`                                  | `packages/policy/tests/test_policy.py`, `apps/cognition/tests/test_loop.py`   |
| Rejected proposal executes nothing         | `PersonRuntime.#decide` REJECT path                        | `tests/safety/attribution.test.ts`                                            |

## Goals and planning

| Requirement                                                          | Implementation                                                         | Tests                                                      |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------- |
| GoalProvider separate from routine selection                         | `apps/cognition/python/person_cognition/goals.py` vs `packages/policy` | `apps/cognition/tests/test_context_and_goals.py`           |
| Goal states and the goal stack                                       | `GoalStack`                                                            | same                                                       |
| Interruption and resumption                                          | `GoalStack.update`                                                     | `test_goals_suspend_and_resume_around_an_emergency`        |
| Homeostasis produces urgency, not commands                           | `homeostasis`, `SurvivalGoalProvider`                                  | `test_hunger_raises_the_priority_of_securing_food`         |
| Symbolic planner from preconditions and effects                      | `packages/planner/python/person_planner/search.py`                     | `packages/planner/tests/test_planner.py`                   |
| Equivalent safe sequences for food, shelter, tools, cooking, storage | same                                                                   | `test_every_survival_goal_has_a_feasible_plan`             |
| Plans are minimal and deterministic                                  | `_is_minimal`, sorted dedupe                                           | `test_plans_are_minimal`, `test_planning_is_deterministic` |

## Routines and policy

| Requirement                            | Implementation                                       | Tests                                                                          |
| -------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------ |
| Routine model with hierarchy           | `apps/cognition/python/person_cognition/routines.py` | routine expansion covered in `apps/cognition/tests`                            |
| Stable routine identifiers             | `routine_identifier` (content hash)                  | `apps/cognition/tests/test_loop.py` restart test                               |
| Deterministic fallback policy          | `DeterministicPolicyProvider`                        | `packages/policy/tests/test_policy.py`                                         |
| EvidencePolicyProvider                 | `EvidencePolicyProvider`                             | same                                                                           |
| Beta posterior with uncertainty        | `OutcomeCounts.posterior_lower`                      | `test_uncertainty_is_reflected_in_the_estimate`                                |
| Risk dominates convenience             | `ScoringWeights`                                     | `test_a_costly_routine_loses_to_a_safer_one`                                   |
| Safe exploration envelope              | `packages/policy/python/person_policy/envelope.py`   | `test_exploration_is_suppressed_outside_the_safe_envelope`                     |
| Learning modes off, shadow, supervised | `EvidencePolicyProvider.propose`                     | `packages/policy/tests/test_policy.py`                                         |
| Learning disabled by default           | config schema plus shipped examples                  | `tests/architecture/architecture.test.ts`, `tests/python/test_architecture.py` |

## Evidence and persistence

| Requirement                                | Implementation                                              | Tests                                                                                          |
| ------------------------------------------ | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Immutable append-only journal              | `packages/persistence/python/person_persistence/journal.py` | `packages/persistence/tests/test_persistence.py`, `tests/python/test_architecture.py`          |
| Event fields including chaining            | `events.py`                                                 | `test_records_are_chained_and_readable`                                                        |
| Duplicate detection                        | `EvidenceJournal.read`                                      | `test_duplicate_records_are_detected_and_ignored`                                              |
| Corrupted evidence not silently accepted   | same                                                        | `test_a_corrupt_record_is_an_error_not_a_silent_skip`                                          |
| Truncated tail handled                     | same                                                        | `test_a_truncated_tail_is_dropped_and_counted`                                                 |
| Atomic snapshots with checksum             | `snapshot.py` `write_atomic_json`                           | `test_snapshots_are_atomic_and_checksummed`                                                    |
| Invalid snapshot ignored                   | `SnapshotStore.latest_valid`, `EvidenceStore.restore`       | `test_snapshots_are_atomic_and_checksummed`, `test_a_snapshot_that_disagrees_with_the_journal` |
| Rebuild from evidence                      | `EvidenceStore.restore`                                     | `test_restart_replays_from_the_snapshot_and_rebuilds_without_one`                              |
| Facts persisted, not scores                | `RoutineStatistics` counts only                             | `test_statistics_round_trip_through_a_snapshot`                                                |
| Statistics never merge across environments | training-context key                                        | `test_statistics_never_merge_across_training_contexts`                                         |
| Restart reuse                              | `CognitionLoop.on_session_hello`                            | `test_learning_survives_a_restart_of_the_process`, `tests/integration/vertical-slice.test.ts`  |

## Legacy and demonstrations

| Requirement                                                | Implementation                                  | Tests                                                             |
| ---------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------- |
| Versioned configuration migration                          | `packages/config/ts/migrate.ts`                 | `tests/cli/cli.test.ts`                                           |
| V1 Q-learning checkpoint refused with the exact diagnostic | `LEGACY_CHECKPOINT_DIAGNOSTIC` in both runtimes | `tests/cli/cli.test.ts`, `packages/config/tests/test_config.py`   |
| Learning never carried across migration                    | `migrateConfig`                                 | `tests/cli/cli.test.ts`                                           |
| Reviewed demonstration manifests                           | `persistence/demonstrations.py`                 | `test_demonstration_manifests_require_review_and_a_matching_hash` |

## CLI, reporting and observability

| Requirement                                  | Implementation                                        | Tests                                      |
| -------------------------------------------- | ----------------------------------------------------- | ------------------------------------------ |
| `person run`, `learn`, `validate`, `inspect` | `apps/cli/src/`                                       | `tests/cli/cli.test.ts`                    |
| `shroud` and `shroud-train` aliases          | `package.json` bin, `main()` argv handling            | `tests/cli/cli.test.ts`                    |
| Clear configuration errors                   | `ConfigError` diagnostics                             | `tests/cli/cli.test.ts`                    |
| Per-episode JSON report                      | `apps/node-runtime/src/reporting/episode-report.ts`   | `tests/integration/vertical-slice.test.ts` |
| Human-readable summary                       | `summariseEpisode`                                    | CLI output                                 |
| Learning-side report                         | `apps/cognition/python/person_cognition/reporting.py` | `apps/cognition/tests/test_loop.py`        |
| Semantic identifiers, no opaque codes        | reason codes throughout                               | `tests/integration/vertical-slice.test.ts` |

## Fixture and acceptance

| Requirement                                  | Implementation                                    | Tests                                      |
| -------------------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| Deterministic fixture world                  | `fixtures/src/world.ts`, `fixtures/worlds/*.json` | every skill and integration test           |
| Vertical slice acceptance scenario           | `tests/integration/vertical-slice.test.ts`        | itself                                     |
| Threat injected once, preemption, resumption | `fixtures/worlds/vertical-slice.json` events      | same                                       |
| Full survival routine                        | `tests/integration/survival-routine.test.ts`      | itself                                     |
| Seeds recorded for replay                    | `EpisodeReport.rngSeed`, `EpisodeEvent.rngSeed`   | `tests/integration/vertical-slice.test.ts` |

## Future interfaces

| Requirement                                                                  | Implementation                                               | Tests                                               |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------- |
| Memory, WorldModel, Affect, Language, Social, Project, Exploration providers | `apps/cognition/python/person_cognition/future_providers.py` | `test_future_providers_refuse_to_pretend_they_work` |
| No premature implementation                                                  | every placeholder raises                                     | same                                                |
| No LLM, no neural policy, no heavy dependencies                              | absent by construction                                       | `tests/python/test_architecture.py`                 |

## Real embodiment validation (Milestone 1)

| Requirement                                   | Implementation                                                | Tests                                          |
| --------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------- |
| Entity classification from authoritative data | `adapters/minecraft/src/classify.ts`                          | `tests/adapter/mineflayer-conformance.test.ts` |
| Custom name read from sparse metadata         | `classify.ts` `customName`                                    | same, including the unrecognised-shape case    |
| Hostility covers registry-unknown mobs        | `classify.ts` `EXTRA_HOSTILE_MOBS`                            | same                                           |
| Neutral mobs threaten only after damage       | `classify.ts` `NEUTRAL_MOBS`, `SafetyKernel.threats`          | same, and `tests/safety/kernel.test.ts`        |
| Damage memory                                 | `MineflayerEmbodiment` health handler, `FixtureWorld.#damage` | conformance suite                              |
| Armour, biome and light read from the world   | `MineflayerEmbodiment.#armorPoints`, `#biomeAt`, `#lightAt`   | conformance suite                              |
| Free slots from the inventory window          | `MineflayerEmbodiment.snapshot`                               | conformance suite                              |
| Server-authoritative recipes                  | `MineflayerEmbodiment.craft`                                  | conformance suite                              |
| Empty craft and empty smelt fail              | `craft`, `smelt`                                              | conformance suite                              |
| Partial smelt output collected                | `smelt`                                                       | conformance suite                              |
| Container transfer error mapping              | `containerFailure`                                            | conformance suite                              |
| Dig tool choice and excavation safety         | `dig`                                                         | conformance suite                              |
| Placement reference search and confirmation   | `place`                                                       | conformance suite                              |
| Attack guard and reach                        | `attack`                                                      | conformance suite                              |

## Spawn readiness and world rules

| Requirement                                     | Implementation                         | Tests                                          |
| ----------------------------------------------- | -------------------------------------- | ---------------------------------------------- |
| Connection does not imply readiness             | `MineflayerEmbodiment.#awaitReadiness` | `tests/adapter/mineflayer-conformance.test.ts` |
| Bounded wait, no reconnect loop                 | same, `READINESS_TIMEOUT_MS`           | same, including the never-ready case           |
| Dimension detection                             | `#dimension`                           | same                                           |
| Game mode, difficulty, daylight cycle validated | `#assertWorldRules`                    | same                                           |

## Skill completion evidence

| Requirement                                          | Implementation                                        | Tests                          |
| ---------------------------------------------------- | ----------------------------------------------------- | ------------------------------ |
| A craft that produced nothing is a failure           | `MineflayerEmbodiment.craft`                          | conformance suite              |
| A smelt that produced nothing is a failure           | `smelt`                                               | conformance suite              |
| Live container contents before deciding what to take | `inspectContainer`, `skills/impl/storage.ts`          | conformance and storage suites |
| Partial container transfers keep what moved          | `deposit`, `withdraw`                                 | conformance suite              |
| A refuge is only attempted where one can be dug      | `WorldSnapshot.diggableGround`, `SafetyKernel.assess` | `tests/safety/kernel.test.ts`  |

## Prediction error

| Requirement                                   | Implementation                                  | Tests                                                              |
| --------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| Expected effects compared with observed state | `person_cognition/prediction.py`                | `apps/cognition/tests/test_prediction.py`                          |
| Attributed to the skill that ran              | `CognitionLoop.on_skill_outcome`                | same                                                               |
| Persisted as immutable evidence               | `prediction_error` event, schema v2             | same                                                               |
| Schema widened compatibly                     | `SUPPORTED_EVIDENCE_SCHEMAS`                    | `packages/persistence/tests/test_persistence.py`, prediction suite |
| Never influences policy                       | `RoutineStatistics.apply` has no case for it    | `test_prediction_errors_are_persisted_but_never_scored`            |
| Reported                                      | `LearningSummary`, `person inspect predictions` | prediction suite                                                   |

## Tick budgets

| Requirement                               | Implementation                           | Tests                                            |
| ----------------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| Time measured at the port, not per skill  | `apps/node-runtime/src/skills/timing.ts` | exercised by every skill test through the runner |
| Navigation, interaction and waiting split | same                                     | same                                             |
| Budget pressure per skill in the report   | `summariseTickBudgets`                   | `tests/integration/vertical-slice.test.ts`       |

## Route-level protected areas

| Requirement                                            | Implementation                                         | Tests                                           |
| ------------------------------------------------------ | ------------------------------------------------------ | ----------------------------------------------- |
| Legal endpoints, illegal straight line                 | `FixtureWorld.#findPath` via the guard                 | `tests/safety/protected-routes.test.ts`         |
| No legal detour means refusal without partial movement | same                                                   | same                                            |
| Replanning cannot cross a protected area               | `exclusionAreasStep` installed by `#configureMovement` | same, asserted on the exclusion function itself |
| A protected destination is refused before planning     | `MineflayerEmbodiment.moveTo`                          | same                                            |

## Reality comparison tooling

| Requirement                             | Implementation                                                   | Tests                   |
| --------------------------------------- | ---------------------------------------------------------------- | ----------------------- |
| Capture one real observation            | `apps/cli/src/observe.ts` `captureObservation`, `person observe` | `tests/cli/cli.test.ts` |
| Semantic difference against a reference | `compareObservations`, `person compare`                          | same                    |
| Suspicious defaults flagged             | `SUSPICIOUS` rules                                               | same                    |

## Pre-LAN readiness (Milestone 1 patch)

| Requirement                                               | Implementation                                                           | Tests                                                                          |
| --------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| LAN port is runtime configuration, not file configuration | `packages/config/ts/override.ts` `withConnectionOverride`                | `tests/cli/observe-safety.test.ts`, `tests/cli/status.test.ts`                 |
| `--port` and `--host` on every connecting command         | `apps/cli/src/bin/person.ts`, `runCommand`, `observeCommand`             | `tests/cli/status.test.ts`                                                     |
| The override never reaches the file                       | `withConnectionOverride` returns a copy                                  | `test_the LAN port override never reaches the configuration file`              |
| First-run connection diagnostics                          | `adapters/minecraft/src/diagnose.ts`                                     | `tests/adapter/connection-diagnostics.test.ts`                                 |
| A refused login fails immediately rather than timing out  | `MineflayerEmbodiment.connect` races spawn against error, kick and close | same                                                                           |
| Chunk data distinguished from general unreadiness         | `classifyReadiness`                                                      | `tests/adapter/mineflayer-conformance.test.ts`                                 |
| `person observe` runs no skill and moves nothing          | `captureObservation`                                                     | `tests/cli/observe-safety.test.ts`                                             |
| `person observe` writes no learning evidence              | same                                                                     | same                                                                           |
| `person observe` disconnects, bounded                     | disconnect race in `captureObservation`                                  | same                                                                           |
| `person status` read-only telemetry                       | `apps/node-runtime/src/reporting/status.ts`, `statusCommand`             | `tests/cli/status.test.ts`, `tests/architecture/architecture.test.ts`          |
| `person status --follow` reprints only on change          | `followStatus`                                                           | `tests/cli/status.test.ts`                                                     |
| Telemetry never reaches a decision                        | status is written by the runtime and read by the CLI only                | `tests/architecture/architecture.test.ts`                                      |
| Operator intervention marked in evidence and status       | `PersonRuntime` episode events, `StatusWriter`                           | `tests/integration/vertical-slice.test.ts`, `tests/cli/observe-safety.test.ts` |
| Person cannot issue a server command                      | no chat or command path exists                                           | `tests/architecture/architecture.test.ts`                                      |
| Pre-flight separates setup from reachability              | `scripts/lan-check.sh`                                                   | run by hand; output shown in `docs/LAN_TESTING.md`                             |

## First-contact corrections (Milestone 1 patch 2)

| Requirement                                               | Implementation                                                              | Tests                                                                      |
| --------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Biome resolved through the real client data               | `adapters/minecraft/src/registry.ts` `resolveBiome`, `MineflayerEmbodiment` | `tests/adapter/biome.test.ts`, `tests/adapter/perception.test.ts`          |
| Biome unavailability stays an explicit, testable fallback | `resolveBiome` returns `"unknown"` only for a missing block or unknown id   | `tests/adapter/biome.test.ts`, `tests/adapter/perception.test.ts`          |
| Stable player identity in the observation                 | `EntityView.username`/`uuid`, `entityRecord`, schema `entityList`           | `tests/adapter/perception.test.ts`, `tests/observation/perception.test.ts` |
| Two players cannot collapse into one identity             | same                                                                        | same                                                                       |
| Identity is additive and old evidence stays readable      | optional schema properties, `observationVersion` unchanged                  | `fixtures/protocol-corpus/valid/observation-player-identity.json`          |
| Category-balanced resource perception                     | `apps/node-runtime/src/observation/perception.ts` `gatherResources`         | `tests/adapter/perception.test.ts`                                         |
| Abundant stone cannot hide wood                           | per-category quota plus shared overflow                                     | same                                                                       |
| Resource output bounded and deterministic                 | `balanceResources`, `nearestBlocks`                                         | same                                                                       |
| Perception constants live in one place                    | `PERCEPTION` in `observation/perception.ts`, used by both bodies            | `tests/adapter/perception.test.ts`, `tests/observation/perception.test.ts` |
| Passive animals shaped to the usable region               | `shapeEntities` with `areas.permitted` in `buildObservation`                | `tests/observation/perception.test.ts`                                     |
| Shaping is not a safety boundary                          | the runtime snapshot keeps every entity; `mayHunt` unchanged                | same                                                                       |
| Hunting protections unchanged                             | `PermissionGate.mayHunt`, `protectedTarget`                                 | same, and `tests/safety/permissions.test.ts`                               |
| A failed observe exits cleanly, no orphan timer           | `MineflayerEmbodiment.disconnect` ends once and clears the close timer      | `tests/cli/observe-exit.test.ts`                                           |
| `spawn_outside_bounds` refusal unchanged                  | `MineflayerEmbodiment.connect`                                              | same                                                                       |
| Observe starts no cognition process                       | `captureObservation`                                                        | `tests/cli/observe-safety.test.ts`                                         |
