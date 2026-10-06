# ADR 0025: Person's core, environment profiles and experience contexts

**Status:** Accepted (2026-10-06)
**Date:** 2026-10-03
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Supersedes, in part:** the pre-ADR "training-context separation" decision
(`docs/decisions/README.md`, key historical decisions) and protocol
`shroud-learning-v2`. Both remain readable; neither is written any more.

---

## Context

Person is a persistent developmental agent architecture for constructing and
revising beliefs through embodied experience. Minecraft is its first
controlled environment. Until this decision the code said otherwise in three
places at once:

- The core protocol's `Observation` was Minecraft: vitals, biome, inventory,
  hostiles and homes were top-level fields of Person's one sensory message,
  and every neutral package (planner, policy, cognition) read them directly.
- The skill schema enumerated Minecraft categories, permissions and
  completion evidence, so the generic `SkillInvocation` infrastructure could
  not describe any other body's skills.
- `trainingContext` (`fixture`, `minecraft_peaceful`, `minecraft_normal`,
  `replay`) fused four different things into one token: which environment,
  which body, which variant of the environment, and whether the record is a
  lived experience or a replay of one.

None of these was wrong for a Minecraft bot. All of them were wrong for
Person, because each one let Minecraft's ontology stand in for Person's
categories without any test being able to tell.

## Decision

1. **Person's core is environment-neutral; an environment is a profile.**
   `environments/<kind>/environment.json` declares, as data, everything an
   environment owns: its observation payload schema, the configuration
   sections it owns, its skill library and vocabulary, its emergency
   vocabulary, its embodiments and the Python entry point of its cognitive
   profile. The core discovers installed profiles from those manifests and
   never imports an environment's code. Minecraft is the only profile.

2. **The observation is an envelope with an environment payload.**
   Observation version 9: `observationVersion`, `experience`, `selfMotion`,
   `cognition`, `previousOutcome` and `payload`. Everything Minecraft about the
   world (vitals, environment, inventory, permissions, affordances, nearby,
   home, navigation) is under `payload`, validated by Minecraft's own schema.
   Protocol version `person-v3`.

3. **The Minecraft profile keeps strong types.** Moving vocabulary behind the
   boundary is not erasing it into dictionaries: `MinecraftObservation`,
   `MinecraftConfig` and `MinecraftSkillSpec` (TypeScript) and
   `MinecraftPercepts` (Python) stay fully typed. Another environment
   implements the same core contracts (`CognitiveEnvironment`, the envelope,
   the generic skill contract) without pretending to be Minecraft; an
   architecture test loads a toy second profile and plans with it, without
   any core change.

4. **One experience key replaces `trainingContext`.** `ExperienceKey` has four
   parts: `context` (`lived` or `replay`), `environmentKind`, `embodimentKind`
   and `environmentVariant`. It partitions every statistic, effect belief and
   memory exactly as the training context did, and keeps the old guarantee:
   fixture evidence never stands in for live evidence, and replay is never
   new lived experience. The fixture world is a second body of the Minecraft
   environment, not a second environment.

5. **Configuration version 3.** The core schema owns identity, runtime,
   learning, lifecycle and cognition, plus `environment.kind` and
   `runtime.embodiment`; the environment's schema owns its sections
   (Minecraft: `environment.difficulty`, `server`, `bot`, `authorization`,
   `world`, `permissions`). Both are validated together, with nothing left
   over that neither owns. A version 2 document is read as version 3 in
   memory and never rewritten.

6. **Not over-generalised.** Person-000 (Ada) is the baseline. The profile
   boundary is drawn where Minecraft's vocabulary crossed into Person's
   categories, not around hypothetical environments; no plugin system,
   registry service or dynamic loading beyond reading a manifest exists.

## Consequences

### Positive

- A reader of the core can no longer mistake Minecraft's ontology for
  Person's; tests fail if a core module names a Minecraft word or imports
  the profile.
- Fixture versus live separation is now one field of a structured key, and
  replay is a separate axis rather than a fourth "context".

### Negative

- One more indirection: neutral code receives percepts and facts through the
  environment profile rather than reading the observation.
- Some body-measurement fields remain in core messages (see Neutral).

### Neutral

- Compatibility-only, still in core and documented in
  `docs/CURRENT_STATE.md` ("Known Deviations", C9): `SkillOutcome`
  `healthBefore`/`foodBefore` and their after-values, `SkillStarted`
  `startHealth`/`startFood`, cost limits' `minHealth`, and the
  `GoalDecision` goal-type enum. Core cognition still journals and costs
  some of them as reported numbers. Changing those is a protocol change of
  its own.
- The Node runtime still hosts Minecraft's skill implementations and safety
  kernel; it is the trusted runtime of the one environment, and the
  physical-authority boundary (ADR 0005) is unchanged.

## Alternatives Considered

| Alternative                                      | Why Rejected                                                                                             |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Keep Minecraft fields in the core observation    | Every neutral package keeps reading Minecraft directly; the boundary exists only in prose                |
| Generic `dict` payload with no environment types | Erases the strong types that make Minecraft's safety and skills checkable; neutrality only in appearance |
| A plugin framework for many environments         | Speculative; Ada needs one environment and a boundary that tests can hold                                |
| Keep `trainingContext`, add `environmentKind`    | Leaves replay and body fused into one token                                                              |

## Revisit Conditions

- A second real environment is proposed: its profile must need no core
  change, or this ADR is wrong about where the boundary is.
- A compatibility-only field (Neutral, above) needs to change.

## Relevant Commits / Documents

| Reference                                         | Description                                  |
| ------------------------------------------------- | -------------------------------------------- |
| `environments/minecraft/environment.json`         | The Minecraft profile manifest               |
| `packages/epistemics/.../experience.py`           | `ExperienceKey`                              |
| `migrations/0002-person-v2-to-person-v3.md`       | Config, protocol and journal migration       |
| `tests/python/test_epistemic_architecture.py`     | Core/environment boundary tests (Python)     |
| `tests/architecture/environment-boundary.test.ts` | Core/environment boundary tests (TypeScript) |
