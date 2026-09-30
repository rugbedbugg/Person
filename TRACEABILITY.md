# Traceability

Each row maps a requirement from `docs/PERSON_SPEC.md` and the implementation
brief to the code that implements it and the tests that hold it in place. The
point of this document is auditability: a reader should be able to check any
claim without reading the whole tree.

## Architectural invariant and trust boundary

| Requirement                                 | Implementation                                                                                          | Tests                                                                                                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python proposes, Node decides               | `apps/node-runtime/src/skills/dispatch.ts` (the only path), `apps/node-runtime/src/safety/validator.ts` | `tests/architecture/architecture.test.ts` (no proposal reaches an executor without passing the validator)                                                           |
| No raw action channel from Python           | `packages/protocol/schemas/skill-invocation.schema.json`, `common.schema.json` (`skillParameters`)      | `tests/architecture/architecture.test.ts`, `packages/protocol/ts/protocol.test.ts`, `packages/protocol/tests/test_protocol.py`, `tests/python/test_architecture.py` |
| Cognition holds no Minecraft access         | `adapters/minecraft/` is the only Mineflayer importer                                                   | `tests/architecture/architecture.test.ts`, `tests/python/test_architecture.py`                                                                                      |
| Node stays authoritative if cognition fails | `apps/node-runtime/src/ipc/cognition-channel.ts` (`CognitionUnavailableError`, decision timeout)        | `apps/cognition/tests/test_loop.py` (malformed input dropped), channel direction check in `tests/architecture/`                                                     |
| Cognition can only send decisions           | `CognitionChannel.#ingest` direction filter                                                             | `tests/architecture/architecture.test.ts`                                                                                                                           |

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
| All 24 skills implemented for real           | `apps/node-runtime/src/skills/impl/`                     | `tests/skills/`, `tests/integration/survival-routine.test.ts`                  |
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
| Owned storage deposit and withdrawal                    | `skills/impl/storage.ts`, `runtime/placement-ledger.ts`                | `tests/skills/storage.test.ts`                                                                             |
| Storage provenance records                              | `PlacementLedger.recordStorage`                                        | `tests/skills/storage.test.ts`, `tests/integration/survival-routine.test.ts`                               |
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

| Requirement                                                                  | Implementation                                               | Tests                                                     |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------- |
| WorldModel, Language, Social, Exploration providers                          | `apps/cognition/python/person_cognition/future_providers.py` | `test_future_providers_refuse_to_pretend_they_work`       |
| A placeholder leaves when its capability is built (memory, projects, affect) | `person_cognition.memory`, `.projects`, `.affect`            | `test_no_placeholder_outlives_the_capability_it_reserved` |
| No premature implementation                                                  | every placeholder raises                                     | same                                                      |
| No LLM, no neural policy, no heavy dependencies                              | absent by construction                                       | `tests/python/test_architecture.py`                       |

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

## Information seeking

| Requirement                                           | Implementation                                             | Tests                                               |
| ----------------------------------------------------- | ---------------------------------------------------------- | --------------------------------------------------- |
| Evidence facts are established only by perception     | `person_planner.EVIDENCE_FACTS`                            | `packages/planner/tests/test_evidence.py`           |
| A peripheral percept is a lead, not an identification | `person_planner.state.recognised`                          | same                                                |
| Path risk is judged from perceived threats only       | `buildObservation` hostiles-derived `pathRisk`             | `tests/observation/vision.test.ts`                  |
| The periphery does not say whose a thing is           | `entityRecord` in `observation/builder.ts`, entity schema  | `tests/observation/vision.test.ts`, protocol corpus |
| Missing evidence is named by a counterfactual         | `person_planner.evidence_needed`                           | same                                                |
| Glances go through the ordinary skill path            | `look` spec, `skills/impl/perception.ts`, `_emit_look`     | `tests/observation/look.test.ts`, integration suite |
| Search is bounded and ends honestly                   | `person_cognition/search.py`, `CognitionLoop._seek`        | `apps/cognition/tests/test_information_seeking.py`  |
| Exhaustion is not absence; the goal reopens           | `NOT_FOUND`, `GoalStack.reopen`, `_reopen_unfound`         | same                                                |
| Unperceived physical truth changes no decision        | observation-only inputs to the search                      | `tests/integration/information-seeking.test.ts`     |
| Bearings agree with gaze directions                   | `observation/relative.ts` `side()`                         | `tests/observation/look.test.ts`                    |
| Searches are journalled, never scored                 | `information_search` event, schema v3; `UNSCORED_ROUTINES` | persistence suite, cognition suite                  |

## Memory (ADR 0007)

| Requirement                                               | Implementation                                     | Tests                                                            |
| --------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------- |
| The store is rebuilt from encoded episodes only           | `MemoryStore.apply`, `CognitiveReducers`           | `test_only_encoded_episodes_can_become_memories`                 |
| Encoding copies a whitelist, never a message              | `person_cognition/memory/encoding.py`              | `test_encoding_copies_only_whitelisted_fields`, integration      |
| Unperceived physical truth never becomes a memory         | encoding reads only cognition-facing messages      | `tests/integration/memory.test.ts`                               |
| Recall is a typed cue, no free-form query or limit        | `Cue`, `Memory.recall`                             | `test_recall_takes_a_typed_cue_and_nothing_else`, architecture   |
| At most three memories per recall                         | `RECALL_LIMIT`, `rank`                             | `test_a_relevant_cue_retrieves_a_small_bounded_subset`           |
| Relevance gates; recency and salience rank                | `RecallRules`                                      | `test_recent_and_salient_...`, `test_relevance_gates_...`        |
| Forgetting is inaccessibility, never erasure              | `RecallRules.threshold`; the store has no delete   | `test_old_memories_become_inaccessible_without_being_erased`     |
| Provenance survives persistence                           | `Provenance`, `memory_encoded` payload             | `test_restart_keeps_memories_and_their_provenance_...`           |
| Memories are never refreshed from the world               | frozen `Episode`; no update path                   | `test_stale_memory_is_not_overwritten_by_what_is_true_now`       |
| Recall is labelled memory and never becomes perception    | `Recalled.source`; planner reads observations only | `test_recall_is_labelled_memory_and_never_becomes_perception`    |
| A restart does not inject the store                       | `WorkingMemory` unpersisted; recall only on cue    | `test_restart_does_not_inject_the_store`, integration            |
| No invented referent for an action (C4)                   | `encoding.acted` keeps no target                   | `test_an_action_on_some_tree_...`, integration                   |
| A fruitless search is remembered as not found, not absent | `encoding.searched`, `NOT_FOUND`                   | `test_a_search_that_found_nothing_is_remembered_as_exactly_that` |
| Fixture and live memories never mix                       | `MemoryStore.episodes_in`                          | `test_fixture_memories_never_surface_in_a_live_world`            |

## Self-motion and places (ADR 0008)

| Requirement                                               | Implementation                                   | Tests                                                               |
| --------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| Self-motion is relative, quantized, and carries no frame  | `observation/self-motion.ts`, observation schema | `tests/observation/self-motion.test.ts`, protocol corpus            |
| The frame is the facing at the previous observation       | `selfMotion()`                                   | same                                                                |
| Integration drifts; doubt never shrinks                   | `spatial/integration.py`                         | `test_a_square_walk_comes_back_near_the_start_and_less_sure`        |
| Being lost starts a new frame                             | `integrate`, `continuity: "discontinuous"`       | `test_being_lost_starts_a_new_frame_rather_than_guessing`           |
| Places are cognitive and recognised with confidence       | `spatial/places.py`, `Spatial.settle`            | `test_recognition_is_a_confidence_and_falls_with_doubt`             |
| The map changes only through felt motion                  | `Spatial.feel`; architecture rule                | `test_the_map_changes_only_through_felt_motion`, architecture       |
| A restart resumes with more doubt and reveals nothing     | `resumed`, `SpatialMap`                          | `test_places_persist_and_a_restart_resumes_...`                     |
| Shifting the whole world changes nothing in Person's mind | frame-free sense and model                       | `tests/integration/spatial.test.ts`                                 |
| Home is where Person built its shelter                    | `settle("shelter", label="home")`                | `test_home_is_where_person_built_its_shelter`                       |
| Search memory is keyed by place: shorter, never absence   | `revisit_budget`, `_seek`, `_reopen_unfound`     | `test_returning_to_a_searched_place_...`, `test_the_same_place_...` |

## Cognitive home (C8)

| Requirement                                             | Implementation                                      | Tests                                                                                                        |
| ------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| No home distance reaches cognition                      | observation builder and schema                      | `test_the_observation_carries_no_home_distance`, `tests/safety/containment-and-belief.test.ts`, architecture |
| `at_home` is Person's belief                            | `Spatial.home_relation`, `symbolic_state(home=...)` | `test_without_a_belief_person_is_not_taken_to_be_home`                                                       |
| Doubt makes home uncertain                              | `home_relation` drift rule                          | `test_enough_doubt_makes_home_unknown_...`, `test_being_lost_makes_home_unknown`                             |
| The night return follows belief, not the body           | `SurvivalGoalProvider.propose(home=...)`            | `test_the_night_return_follows_belief_not_the_body`                                                          |
| Containment enforces on the body, independent of belief | `SafetyKernel.assess`                               | `tests/safety/containment-and-belief.test.ts`                                                                |
| Exact home distance is operator-only                    | `physicalHomeDistanceBefore/After`                  | `tests/validation/skill-test.test.ts`, `tests/integration/skill-validation.test.ts`                          |

## Projects (ADR 0009)

| Requirement                                            | Implementation                             | Tests                                                                                |
| ------------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------ |
| A project starts only when calm and with a home        | `ProjectManager.consider`                  | `test_a_calm_person_...`, `test_no_project_is_taken_up_under_pressure_...`           |
| An urgent need interrupts; the project resumes after   | goal stack, `ProjectManager.track`         | `test_hunger_interrupts_a_project_which_resumes_...`                                 |
| Projects survive restart and are re-examined first     | `ProjectBook`, `reexamine`, bounded recall | `test_an_unfinished_project_survives_restart_...`                                    |
| Obsolete projects close; impossible ones are abandoned | `reexamine`, `BLOCKS_TO_ABANDON`           | `test_a_project_the_world_already_satisfied_...`, `test_a_project_blocked_again_...` |
| No coordinate or runtime target in project state       | cognitive anchors only; architecture rule  | `test_project_state_holds_no_coordinate_...`, architecture                           |
| Same evidence, same projects, wherever the world is    | frame-free inputs                          | `tests/integration/projects.test.ts`                                                 |

## Affect (ADR 0010)

| Requirement                                                   | Implementation                                     | Tests                                                                       |
| ------------------------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------- |
| A perceived threat raises unease; an unperceived one does not | `appraise_threat` over the observation             | `test_a_perceived_threat_raises_unease`, `tests/integration/affect.test.ts` |
| Harm, success and failure are appraised                       | `appraise_harm`, `appraise_outcome`                | `test_harm_...`, `test_success_and_repeated_failure_...`                    |
| Every change records its cause                                | `Affect.feel`, `affect_appraised`                  | `test_every_change_is_recorded_with_its_cause`                              |
| Decay in experienced time; restart resumes                    | `decay`, `AffectRecord`                            | `test_affect_decays_...`, `test_a_restart_resumes_affect_...`               |
| Bounded, recorded priority bias; no urgent goal adjusted      | `Affect.bias`, `CognitionLoop._biased`             | `test_the_bias_is_bounded_...`, `test_projects.py`                          |
| Different histories, different near choices                   | generic protective/outgoing sensitivity            | `test_different_experience_makes_a_different_near_choice_...`               |
| Affect creates no goal and cannot outrank hunger              | bias applies to proposals only                     | `test_affect_cannot_create_a_goal_or_outrank_an_urgent_one`                 |
| Exploration tolerance, never authority                        | `Affect.tolerance`, `EvidencePolicyProvider.score` | `test_calm_explores_and_unease_prefers_the_familiar_...`, protocol scan     |
| No threshold-to-action; no privileged input                   | affect state read only in `affect.py`              | `test_affect_code_reads_nothing_privileged_and_runs_no_skill`               |
| Memory salience untouched                                     | ADR 0007 constants                                 | `test_memory_salience_and_recall_are_untouched_by_affect`                   |
| Same evidence, same affect, wherever the world is             | frame-free inputs                                  | `tests/integration/affect.test.ts`                                          |

## Learned effect reliability (ADR 0011)

| Requirement                                     | Implementation                                       | Tests                                                                                        |
| ----------------------------------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Only genuine, evaluable attempts teach          | `attempt_reason`, `classify`, `EVALUABLE_FACTS`      | `test_what_was_not_a_genuine_attempt_...`, `test_beliefs_ledger_facts_...`                   |
| One outcome is not certainty; evidence reverses | Beta(1,1) estimate, `strength`                       | `test_one_outcome_is_not_certainty`, `test_later_contradicting_evidence_...`                 |
| Unknown differs from balanced                   | no estimate without evidence                         | `test_no_experience_is_not_the_same_as_balanced_experience`                                  |
| Keyed by skill and fact, never target (C4)      | `Trial`, `EffectBelief`                              | `test_trials_and_beliefs_are_keyed_by_skill_and_fact_only`                                   |
| Learning mode decides where evidence goes       | `admitted_to`, `EffectBeliefs` tables                | `test_off_learns_nothing_shadow_only_shadow_...`, `test_shadow_learning_changes_no_decision` |
| Bounded, separately recorded policy term        | `reliability_term`, `ScoredCandidate.learned_effect` | `test_supported_reliability_can_change_a_close_choice_...`                                   |
| Beliefs persist; the mind is not filled         | reducer over `effect_evidence`                       | `test_active_beliefs_survive_restart_...`                                                    |
| Statistics, memory and affect untouched         | reducers ignore `effect_evidence`                    | `test_routine_statistics_memory_and_affect_ignore_effect_evidence`                           |
| Same felt evidence, same learning               | frame-free inputs                                    | `tests/integration/effect-learning.test.ts`                                                  |

## Causal hypotheses and experiments (ADR 0012)

| Requirement                                         | Implementation                                         | Tests                                                                                   |
| --------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Typed, falsifiable, closed-vocabulary hypotheses    | `CausalHypothesis`, `vocabulary`, `evaluable_effects`  | `test_a_hypothesis_has_no_executable_...`, `test_every_concept_a_hypothesis_names_...`  |
| Reasoning is not evidence; quarantine               | `admit`, `quarantine.refusal`, `ModelProposer`         | `test_a_language_model_reasons_for_person_...`, `test_malformed_privileged_...`         |
| Premises motivate, never confirm                    | evidence counts only after proposal                    | `test_the_motivating_trials_are_premises_not_evidence`                                  |
| Strength apart from confidence; reversible          | `relation`, `confidence`, `standing`                   | `test_one_supporting_trial_...`, `test_later_evidence_reverses_the_conclusion`          |
| Intervention outweighs correlation                  | `KIND_WEIGHT`, `controlled`                            | `test_correlation_counts_for_less_than_intervention_...`                                |
| Experiments are ordinary, bounded goals             | `InvestigationManager`, `design`, `INVESTIGATE`        | `test_experiment_trials_pass_the_ordinary_...`, `test_the_experiment_budget_terminates` |
| Denial and mid-trial change teach nothing           | `_learn_causes`                                        | `test_a_refused_trial_...`, `test_a_condition_that_changes_mid_trial_...`               |
| Interrupted and resumed                             | `InvestigationManager.track`                           | `test_urgent_needs_interrupt_an_experiment_and_it_resumes`                              |
| Learning modes gate learning and action             | book tables, supervised-only investigations            | `test_off_learns_nothing_...`, `test_shadow_hypotheses_change_no_decision`              |
| Bounded, recorded policy term                       | `hypothesis_term`, `ScoredCandidate.hypothesis_effect` | `test_a_supported_hypothesis_can_change_a_close_choice_...`                             |
| Memory, belief and knowledge distinct               | separate reducer; no knowledge status                  | `test_episodic_memory_and_causal_belief_...`, `test_nothing_becomes_knowledge_...`      |
| Hidden rule discovered; frame- and hazard-invariant | the whole loop                                         | `tests/integration/causal-learning.test.ts`                                             |
| Curiosity grants no authority                       | no experiment case in safety or skills                 | `trusted safety knows nothing of curiosity`                                             |

## Affect modes and experiments (ADR 0013)

| Requirement                                                             | Implementation                                               | Tests                                                                                                |
| ----------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `off`: affect does not evolve and reaches no decision                   | `Affect.advance`, `Affect.feel` return early                 | `test_off_appraises_nothing_and_the_state_never_moves`                                               |
| `record_only` appraises and journals exactly as `active`                | one appraisal path; `Affect.feel`                            | `test_record_only_journals_exactly_what_active_journals`                                             |
| Only `active` affect reaches a decision                                 | `Affect.bias`, `Affect.tolerance` answer neutrally otherwise | `test_only_active_affect_reaches_a_decision`, `test_neither_consumption_point_answers_unless_active` |
| The mode is consulted only where state evolves and where it is consumed | `affect.py`                                                  | `test_the_mode_is_consulted_only_at_the_consumption_boundary`                                        |
| Negative control: `off` and `record_only` decide identically            | same                                                         | `test_off_and_record_only_make_the_same_decisions`, `tests/cli/experiment.test.ts`                   |
| The mode is Person's configuration, never the runtime's                 | `[affect] mode`, `CognitionSettings.affect_mode`             | `packages/config/tests/test_config.py`, `instrumentation stays outside Person and the runtime`       |
| The recorded bias always accounts for the priority                      | `GoalStack.update` refreshes base and bias with priority     | `test_the_recorded_bias_always_accounts_for_the_priority`                                            |
| Independent, seeded, reproducible runs with full metadata               | `apps/cli/src/experiment.ts`                                 | `tests/cli/experiment.test.ts`                                                                       |
| The seed changes the world and never reaches Person                     | seed applied to the fixture definition only                  | `the seed changes the world and never reaches Person`                                                |
| No aggregate score                                                      | `measure` returns named metrics only                         | by construction; `docs/evidence/experiments/README.md`                                               |

## Affect benchmark characterisation (R1.5, ADR 0013)

| Requirement                                                           | Implementation                                                  | Tests                                                                                                                |
| --------------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| What each decision was chosen from is journalled, never read back     | `goal_selected.candidates`, `routine_selected` tolerance scores | `apps/cognition/tests/test_decision_basis.py`                                                                        |
| The largest possible affect swing comes from the affect code itself   | `bias_swings`, `person-cognition --affect-bounds`               | `test_the_largest_possible_swing_between_goal_characters`, `test_the_bounds_are_exported_without_running_cognition`  |
| Opportunity and change are measured per channel                       | `apps/cli/src/affect-analysis.ts`                               | `tests/cli/affect-analysis.test.ts`                                                                                  |
| A choice never changes without an opportunity                         | same                                                            | `running cells at once measures exactly what running them in turn does`                                              |
| Horizons are bounded in Person's time                                 | `Horizon.maxExperiencedTicks` through `runtime.maxTicks`        | `a run ends at whichever bound comes first, in Person's experienced time`                                            |
| Development and held-out are separated and the held-out set is frozen | `experiments/benchmarks/`, manifest, `--heldout`                | `tests/cli/benchmarks.test.ts`, `a held-out plan does not run unless it is asked for by name`                        |
| An episode's end reaches Person before it is stopped                  | `CognitionChannel.stop` waits a bounded moment                  | `tests/integration/episode-end.test.ts`                                                                              |
| The chain continues after a snapshot at the journal tail              | `EvidenceStore.restore`                                         | `test_the_chain_continues_after_a_snapshot_taken_at_the_journal_tail`                                                |
| A persisting blockage is one event                                    | `GoalStack.block`                                               | `test_blocking_a_goal_that_is_already_blocked_is_not_a_new_event`, `test_a_blockage_that_persists_is_appraised_once` |
| An abandoned project leaves no goal behind                            | `GoalStack.abandon`, `ProjectManager.track`                     | `test_an_abandoned_project_leaves_no_goal_behind`                                                                    |

## Interoceptive affect (R2, ADR 0014)

| Requirement                                                        | Implementation                                                | Tests                                                                                                                                                                   |
| ------------------------------------------------------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cognition is not given saturation or exhaustion; breath is bubbles | `observationVersion` 8, `breathBubbles`                       | `hidden saturation never reaches cognition`, `breath is felt as the bubbles a player sees`, `test_hidden_hunger_mechanics_never_reach_cognition`                        |
| Hunger, harm and breath press as conditions in experienced time    | `Interoception`, `Affect.apply_tonic`, `settle`               | `test_persistent_hunger_keeps_weighing_on_affect_without_new_events`, `test_low_health_is_a_sustained_vulnerability`, `test_running_short_of_breath_is_felt`            |
| Tonic affect does not depend on observation cadence                | exact relaxation under a held offset, unrounded between steps | `test_hunger_pressure_depends_on_experienced_time_not_observations`, `test_doubling_the_observation_cadence_does_not_double_threat_affect`                              |
| The body never moves control                                       | `TONIC_CAPS`, R2 harm                                         | `test_recovering_health_lifts_valence_but_not_control`, `test_one_damage_event_is_appraised_once`                                                                       |
| One damage event is one appraisal                                  | `Interoception._transitions`                                  | `test_one_damage_event_is_appraised_once`                                                                                                                               |
| One causal event is one appraisal, its consequences listed         | `CognitionLoop._appraise_step`, `combined`                    | `test_one_act_that_completes_several_goals_is_one_appraisal`                                                                                                            |
| A threat is onset, escalation and exposure; no identity needed     | `Interoception._threat`                                       | `test_a_visible_threat_is_one_onset_and_then_an_exposure`, `test_a_threat_that_clears_stops_pressing_and_a_new_one_is_a_new_onset`, `test_no_hostile_needs_an_identity` |
| The idle placeholder is never appraised                            | `_appraise_step` skips `maintenance` goals                    | `test_the_idle_placeholder_is_never_appraised`                                                                                                                          |
| Tonic updates are journalled and survive a restart                 | `affect_tonic` (schema v10), `AffectRecord`                   | `test_tonic_updates_are_journalled_with_their_causes`, `test_a_restart_resumes_the_tonic_state`                                                                         |
| Interoception off reproduces R1.5 exactly                          | the switch at R2's contribution points only                   | `tests/integration/r15-reference.test.ts`, `test_the_switch_leaves_r1_5_appraisal_exactly_as_it_was`, `test_the_switch_is_consulted_only_where_r2_contributes`          |
| Trusted safety knows nothing of interoceptive affect               | no dependency                                                 | `trusted safety knows nothing of interoceptive affect`                                                                                                                  |

## Zero-time correctness (ADR 0015)

| Requirement                                                                            | Implementation                                                           | Tests                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Contact range has one definition, the kernel's                                         | `wait_safely`, `look_around` use `threatState === "immediate"`           | `tests/safety/zero-time-interruption.test.ts`: boundaries at 7, 8 and 16 blocks for both skills                                                                                                                                         |
| Seeing a hostile changes what Person knows, not what the body allows                   | the skills read the kernel, never the observation                        | `seeing the hostile changes what Person knows, not what the body allows`                                                                                                                                                                |
| Nothing about an unseen hostile reaches cognition                                      | outcomes unchanged                                                       | `a wait that completes beside an unseen hostile says nothing about it`                                                                                                                                                                  |
| Neither a zero-time interruption nor zero-time runtime control stops a simulated world | `Embodiment.passTick`, `runtimeTookControl`, called from `dispatchSkill` | `the fixture world moves on after an attempt interrupted before any time passed`, `a kernel replacement that fails at 0 ticks moves the world one tick`, `runtime control means replacement or preemption, not an emergency-type skill` |
| A repeated zero-time failure ends as a fault                                           | `StallDetector`, `STALL_LIMIT`, reason `runtime_livelock`                | `the stall detector fires on the limit-th identical zero-time failure, not before`, `an episode that repeats one zero-time failure ends as a runtime livelock`                                                                          |
| The held-out D world passes its skeleton (regression only)                             | the above                                                                | `the original held-out D world no longer freezes at its skeleton`                                                                                                                                                                       |
| A goal already satisfied is never queued or completed                                  | `GoalStack.update`                                                       | `test_a_goal_proposed_already_satisfied_is_never_queued_or_completed`, `test_no_goal_type_is_queued_when_proposed_already_satisfied`, `test_food_already_at_its_goal_is_neither_chosen_nor_appraised`                                   |
| The corrected R1.5 baseline, bridged to the historical one                             | `fixtures/regression/r15-affect-corrected/`                              | `tests/integration/r15-reference.test.ts`                                                                                                                                                                                               |
| Snapshots are bounded                                                                  | `SnapshotStore(keep=SNAPSHOTS_KEPT)`                                     | `test_only_the_newest_snapshots_are_kept`, `test_a_damaged_newest_snapshot_falls_back_to_a_kept_older_one`                                                                                                                              |

## Identity and continuity (ADR 0017, I1)

| Requirement                                                 | Implementation                                             | Tests                                                                                                                                                                               |
| ----------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A new root begins with its founding, then its first session | `plan_root`, `CognitionLoop.on_session_hello`              | `test_a_new_root_begins_with_its_founding_then_its_first_session`                                                                                                                   |
| A founded root opens only as its own Person                 | `plan_root`                                                | `test_a_root_opens_only_as_its_own_person`, `test_a_legacy_root_opens_only_as_the_person_who_wrote_it`                                                                              |
| A canonical Person is founded only by the founding command  | `plan_root`, `found`, `person-cognition --found`           | `test_even_a_fully_configured_canonical_person_is_not_founded_by_startup`, `test_the_founding_command_founds_once_and_startup_then_resumes`                                         |
| Snapshots are bound to their Person                         | `EvidenceStore.identity`, `SnapshotStore.write(identity=)` | `test_a_snapshot_of_another_person_is_refused_before_it_is_loaded`                                                                                                                  |
| One process per root                                        | `RootLock`                                                 | `test_one_live_process_holds_a_root_and_a_dead_ones_lock_is_taken_over`                                                                                                             |
| Sessions pair; a crash invents nothing                      | `ContinuityRecord`, `session_payload`                      | `test_sessions_pair_by_id_and_a_crash_leaves_no_end`, `test_after_a_crash_nothing_is_invented_and_the_next_start_says_so`                                                           |
| A gap is learned as a category, not remembered              | `gap_category`, `SelfKnowledge`                            | `test_the_gap_is_a_coarse_category_with_fixed_bounds`, `test_a_restart_learns_the_gap_and_how_the_last_session_ended`, `test_a_clock_that_went_backwards_is_unknown_not_continuous` |
| Legacy roots stay readable, never given a founding          | `plan_root`                                                | `test_a_legacy_root_is_read_and_resumed_but_never_given_a_founding`                                                                                                                 |
| Cognition gets a bounded projection, not the record         | `SelfKnowledge`                                            | `test_cognition_receives_a_bounded_projection_not_the_record`                                                                                                                       |

## Operational state (ADR 0017, I2)

| Requirement                                                              | Implementation                                                                   | Tests                                                                                                                                                   |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Losing the world interrupts, it does not fail, and it is recorded        | `PersonRuntime` (`WorldAvailability`, reconnect budget), `on_world_availability` | `losing the world with no reconnection budget interrupts the episode, it does not fail it`                                                              |
| Reconnecting continues the same Person and session                       | runtime reconnect, fresh `SelfMotionSense`                                       | `reaching the world again continues the same Person in the same session`                                                                                |
| Time without the world is not experienced; nothing is invented across it | `Memory.lose_continuity`, `Interoception.lose_continuity`                        | `test_minecraft_disappearing_while_cognition_lives_is_a_state_not_an_end`, `test_restart_after_a_long_world_absence`                                    |
| Suspension is retrospective, from the session boundary                   | `session_payload` (`suspension`), `ContinuityRecord.world_at_previous_end`       | `test_crash_while_embodied_is_a_suspension_after_a_crash_with_nothing_invented`, `test_clean_shutdown_while_embodied_is_a_suspension_after_a_clean_end` |
| Only real changes are recorded                                           | the state guard in `on_world_availability`                                       | `test_repeated_connect_and_disconnect_cycles_record_only_real_changes`                                                                                  |
| Legacy stores acquire no lifecycle history                               | `CognitionLoop._lifecycle`                                                       | `test_a_legacy_store_acquires_no_lifecycle_history`                                                                                                     |
| Person knows only whether the world is available                         | `OperationalView`                                                                | `test_person_knows_only_whether_the_world_is_available`                                                                                                 |

## Life status (ADR 0017, I3)

| Requirement                                                            | Implementation                                              | Tests                                                                                                                                                               |
| ---------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A respawn keeps the same Person, memory, experienced time and projects | `on_life_event`, runtime `#respawn`, `FixtureWorld.respawn` | `test_respawn_keeps_the_same_person_memory_time_and_projects`, `a respawn continues the same Person in the same session`                                            |
| The respawned body invents no recovery or movement                     | `_drop_body_continuity`, fresh `SelfMotionSense`            | `test_the_first_observation_after_respawn_invents_no_recovery_or_movement`                                                                                          |
| A death is one salient memory of what Person knew; nothing privileged  | `encoding.died`, `LifeEvent` schema                         | `test_the_death_is_one_salient_memory_of_what_person_knew`, `test_nothing_privileged_about_the_death_reaches_person`                                                |
| Permadeath is irreversible, whatever the configuration                 | `LifeRecord`, startup refusal                               | `test_permadeath_is_irreversible_and_no_configuration_resurrects`, `a permadeath ends the Person, and no later configuration resumes it`                            |
| A crash right after a terminal death still reconstructs termination    | the terminal flag on `person_died`                          | `test_a_crash_right_after_a_terminal_death_still_reconstructs_termination`                                                                                          |
| A crash before a respawn resumes the same Person awaiting it           | `lifeStatus` in `CognitionReady`, runtime startup respawn   | `test_a_crash_before_the_respawn_resumes_the_same_person_awaiting_it`, `a Person left awaiting a respawn is respawned by the next run before it perceives anything` |
| Repeated deaths or respawns change nothing                             | the status guards                                           | `test_a_repeated_death_or_respawn_changes_nothing`                                                                                                                  |
| World availability and life status stay separate                       | separate reducers and handlers                              | `test_world_availability_and_life_status_stay_separate`                                                                                                             |
| Only the runtime reports a death                                       | `on_life_event`, architecture allowlist                     | `test_cognition_cannot_end_itself_or_die_by_its_own_conclusion`, `cognition may only send decisions; the runtime owns every verdict`                                |
| Legacy stores still read                                               | `plan_root`                                                 | `test_a_legacy_store_still_reads_and_records_a_real_death`                                                                                                          |

## Mineflayer lifetime (ADR 0017, first-Ada readiness E1)

| Requirement                                                            | Implementation                                           | Tests                                                                                                                                                                                                                                                                                        |
| ---------------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A respawn is reported only once the body is back and the world ready   | `MineflayerEmbodiment.respawn`                           | `a respawn is reported only once the server has put the body back and the world is ready`, `a living body is not respawned`                                                                                                                                                                  |
| A respawn that did not happen is refused, and never reported           | `MineflayerEmbodiment.respawn`, `PersonRuntime.#respawn` | `a server that never respawns the body is a refusal, not a respawn`, `losing the connection during a respawn is a refusal`, `a respawn outside the exploration area is refused`, `a death with a server that never respawns ends the episode awaiting a respawn, without crashing`           |
| Joining dead connects to a dead body                                   | `MineflayerEmbodiment.connect` (`death` before `spawn`)  | `joining as a player who left dead connects to a dead body instead of timing out`, `a body found dead is reported dead, respawned by the adapter, and the same Person carries on`                                                                                                            |
| A retired client cannot change its replacement                         | client generations in `MineflayerEmbodiment`             | `a retired client's late end cannot disconnect its replacement`, `a retired client's late error cannot disconnect its replacement`, `a failed reconnection leaves the body disconnected, and a later one succeeds`, `an explicit disconnect retires the client, so its own end says nothing` |
| Losing the world while dead reconnects, and the death is recorded once | the runtime's death branch                               | `a death around a reconnection is found on the new connection`, `a connection lost while dead is reconnected, found still dead, and respawned once`                                                                                                                                          |
| A shutdown reconnects nothing                                          | `PersonRuntime`                                          | `an ordinary run with a reconnection budget connects exactly once, and its shutdown reconnects nothing`                                                                                                                                                                                      |

## First-Ada readiness (ADR 0018)

| Requirement                                                             | Implementation                    | Tests                                                                                                                                                                                              |
| ----------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A validation identity is its own namespace                              | `VALIDATION`, `is_validation`     | `test_a_validation_identity_is_its_own_namespace`                                                                                                                                                  |
| It is founded only by the founding command, with a name and designation | `founded_explicitly`, `plan_root` | `test_ordinary_startup_never_founds_a_validation_identity`, `test_a_validation_founding_needs_a_name_and_a_designation`, `test_a_founded_validation_identity_resumes_like_a_canonical_person`      |
| Inspection is read-only: no lock, no file created or touched            | `inspect_root`, `lock_holder`     | `test_inspecting_an_absent_root_creates_nothing`, `test_inspecting_a_live_root_changes_nothing_in_it`, `test_the_inspect_command_prints_the_report_and_starts_nothing`                             |
| Inspection reports state, life status and the lock holder               | `inspect_root`                    | `test_inspection_reports_a_death_awaiting_respawn_and_a_termination`, `test_inspection_tells_a_legacy_root_from_a_founded_one`, `test_inspection_reports_who_holds_the_lock_and_whether_they_live` |

## Preflight, world manifest and backups (ADR 0018, E2b)

| Requirement                                                         | Implementation                       | Tests                                                                                                                                                                                         |
| ------------------------------------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A correct setup passes and pins revision, config and world          | `preflight`                          | `a complete, correct setup for a founding passes and pins what it checked`                                                                                                                    |
| The preflight is read-only                                          | `preflight`                          | `the preflight changes nothing it looks at`, `the preflight reads a real root through cognition, without touching it`                                                                         |
| Every unsafe or unproven condition fails closed                     | `preflight`                          | `the preflight refuses …` (one test per defect, including an inspection that cannot run)                                                                                                      |
| Embodiment needs a founded, living root of this Person              | `preflight`                          | `embodying needs a founded root of this Person, never a terminated one`                                                                                                                       |
| A world's manifest is written once, into a generated, pinned world  | `writeWorldManifest`, `manifestPath` | `a world's manifest is written once, into a generated and pinned world`                                                                                                                       |
| A backup is verified, excludes the lock, and never touches the root | `scripts/evidence/backup-root.py`    | `test_a_backup_is_a_verified_byte_copy_and_leaves_the_root_untouched`, `test_a_backup_is_refused_while_the_root_is_being_lived`, `test_a_backup_inside_its_own_root_or_of_nothing_is_refused` |

## Deaths at the edges (ADR 0017, found by E3)

| Requirement                                                     | Implementation                                           | Tests                                                                                                                                            |
| --------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| A death during the last decision is reported in its own session | `PersonRuntime` checks world and body before the budgets | `a death during the last decision is reported before the session ends`                                                                           |
| A skill whose body is dead at its end is a death                | `SkillRunner`                                            | `a move that fails because the body died ends the skill as DEATH, not FAILED`, `a move that fails on a living body is still an ordinary failure` |
| A move stops the moment the body dies                           | `MineflayerEmbodiment.moveTo`                            | `a move stops the moment the body dies, instead of running out its timeout`                                                                      |

## Air-deprivation emergency (ADR 0019)

| Requirement                                                        | Implementation                        | Tests                                                                                                                                                                                                 |
| ------------------------------------------------------------------ | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| An air emergency restores air, never flees                         | `SafetyKernel.assess` (`restore_air`) | `an air emergency is answered by restoring air, not by fleeing`, `with a hostile nearby and air critical, the runtime restores air instead of fleeing`                                                |
| Air comes first; ordinary flee keeps its meaning                   | `SafetyKernel.assess`                 | `air still comes first with a hostile nearby, and ordinary flee keeps its meaning`                                                                                                                    |
| Open water: swim up; blocked straight up: the next open column     | `restoreAir`, `nearestAir`, `ascend`  | `in open water the body swims up to air`, `with the way straight up blocked, the body reaches air by the next open column`, `holding jump in open water rises until the head is in air, then lets go` |
| No reachable air: a bounded failure, no digging, no zero-time loop | `restoreAir`                          | `with no reachable air the skill fails cleanly, bounded, and digs nothing`, `an air emergency with no way out is one emergency per decision, and a respawn leaves none of it`                         |
| Death, respawn and world loss end the escape                       | skill checkpoints, `ascend`           | `a body that drowns during the escape ends it as DEATH`, `a world lost during the escape ends it as DISCONNECTED`, `a stroke ends when the body dies`, `a stroke ends when the connection is lost`    |
| Under-water plants are never air                                   | `blockKind`                           | `plants that grow only under water read as water, so they are never mistaken for air`                                                                                                                 |
| The fixture loses air under water                                  | `FixtureWorld`                        | `the fixture loses air under water, and breathes again at the surface`                                                                                                                                |

## Deliberation boundary (ADR 0020, C1)

| Requirement                                                                                                        | Implementation                                        | Tests                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The context is projections only: no affect, positions or evidence; building it records and recalls nothing         | `CognitionLoop.deliberation_context`, `build_context` | `test_the_context_is_projections_only_with_no_affect_positions_or_evidence`                                                                                                                                                              |
| Every collection is capped; hashing is canonical                                                                   | `CAPS`, `canonical_json`                              | `test_every_collection_is_capped`, `test_serialisation_is_canonical_for_hashing`                                                                                                                                                         |
| What and why only; no skill invocation, sequence or parameters                                                     | proposal schema, `gate`                               | `test_the_gate_rejects_what_person_could_not_justify` (invocation, ordered approach)                                                                                                                                                     |
| Premises cited; capabilities offered; expected effects justified by Person's beliefs, declared effects or premises | `gate`, `_supported`                                  | `test_the_gate_rejects_what_person_could_not_justify`, `test_a_grounded_proposal_is_admitted`                                                                                                                                            |
| No privileged text, digits or commands; confidence has no weight                                                   | `gate`                                                | `test_the_gate_rejects_what_person_could_not_justify`, `test_a_confident_answer_earns_nothing_for_its_confidence`                                                                                                                        |
| Malformed is a rejected answer; no answer is unavailable; a crash leaves the request unmatched                     | `Deliberator`                                         | `test_malformed_text_is_a_rejected_answer`, `test_a_provider_with_no_answer_is_unavailable_and_person_carries_on`, `test_an_adapter_that_raises_is_an_unavailable_backend`, `test_a_request_left_unanswered_by_a_crash_stays_unanswered` |
| One id and pinned input hashes per deliberation; raw text only in the audit artifact                               | `Deliberator`                                         | `test_a_deliberation_is_one_request_and_one_answer_under_one_id`, `test_raw_text_goes_only_to_the_audit_artifact`                                                                                                                        |
| Off by default; off invokes nothing; active does not exist                                                         | settings, `Deliberator`                               | `test_mode_off_invokes_and_records_nothing`, `test_the_deliberator_itself_refuses_to_run_when_off`, `test_deliberation_mode_is_off_by_default_and_active_does_not_exist_yet`                                                             |
| `record_only` changes nothing but its own evidence; the loop never calls it                                        | structural isolation                                  | `test_record_only_changes_nothing_but_its_own_evidence`, `test_nothing_in_the_decision_loop_calls_for_deliberation`                                                                                                                      |
| Deliberations per experienced hour, by reason                                                                      | `deliberation_rate`                                   | `test_the_rate_of_deliberation_is_per_experienced_hour_and_by_reason`                                                                                                                                                                    |

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

## Single-skill live validation (Milestone 2)

| Requirement                                          | Implementation                                                                    | Tests                                                                                |
| ---------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| One path from SkillInvocation to SkillOutcome        | `apps/node-runtime/src/skills/dispatch.ts`, called by the runtime and the harness | `tests/architecture/architecture.test.ts`                                            |
| The harness cannot bypass the executor               | no `runner.run` and no `SKILL_IMPLEMENTATIONS` in `validation/skill-test.ts`      | same                                                                                 |
| The normal safety kernel decides                     | `InvocationValidator` and `SafetyKernel` built exactly as the runtime builds them | `tests/validation/skill-test.test.ts`                                                |
| A REJECT is reported and nothing runs                | `dispatchSkill` reject path, `report.safety`                                      | same                                                                                 |
| A REPLACE never credits the requested skill          | `requestedSkillStatus`, `actualSkill` in the report                               | same                                                                                 |
| `--skill` resolves only to a registered SkillSpec    | `SkillRegistry.has`/`get` before anything connects                                | `tests/validation/skill-test.test.ts`, `tests/cli/cli.test.ts`                       |
| No arbitrary action channel through the CLI          | no free-form option; scalar spec parameters only                                  | `tests/cli/cli.test.ts`, `tests/validation/skill-test.test.ts`                       |
| Parameters validated by the canonical rules          | `SkillRegistry.resolveParameters`                                                 | `tests/validation/skill-test.test.ts`                                                |
| Cost limits come from the spec, never the caller     | `invocation.limits = spec.costLimits`, clamped again by the validator             | same                                                                                 |
| Pre- and post-skill observations, both schema-valid  | `runSkillValidation`, `protocolValidator`                                         | same                                                                                 |
| Effects compared with the existing machinery         | `person_cognition/effects.py` over `symbolic_state` and `prediction.compare`      | `apps/cognition/tests/test_effects.py`, `tests/integration/skill-validation.test.ts` |
| An unobservable effect is not a failure              | `UNOBSERVABLE_FACTS`, verdict `not_observable`                                    | same                                                                                 |
| A comparison that cannot run stays honest            | `unavailableComparison`, verdict `inconclusive`                                   | `tests/integration/skill-validation.test.ts`                                         |
| Validation runs change no learning state             | `learningFingerprint` before and after, recorded in the report                    | `tests/validation/skill-test.test.ts`                                                |
| Validation evidence is stored separately             | `runs/validation/skill-tests/`, `writeSkillValidationReport`                      | same                                                                                 |
| Operator setup leaves Person inert                   | `confirmSetup` gate before any dispatch                                           | same                                                                                 |
| Operator setup needs explicit continuation           | `confirmOnStdin`; a closed input aborts                                           | `tests/validation/skill-test-exit.test.ts`                                           |
| An invalid post-setup state refuses the measured run | connected, alive, Overworld, in bounds, not in a protected area                   | `tests/validation/skill-test.test.ts`                                                |
| No teleport capability is added                      | setup is a human action; the CLI exposes no position argument                     | `tests/cli/cli.test.ts`                                                              |
| Operator setup is recorded as contamination          | `operatorIntervention` defaulted on for `--operator-setup`                        | `tests/validation/skill-test.test.ts`                                                |
| `person status` distinguishes a validation run       | `RuntimeStatus.phase`, `command=skill-test`                                       | same                                                                                 |
| Every path releases body, timers and input           | `finally` disconnect with a bound; readline closed and released                   | `tests/validation/skill-test-exit.test.ts`, `tests/validation/skill-test.test.ts`    |
| A report that cannot be written is reported          | `finish` catches the write failure                                                | `tests/validation/skill-test.test.ts`                                                |
