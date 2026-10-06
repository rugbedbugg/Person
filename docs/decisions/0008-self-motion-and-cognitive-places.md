# ADR 0008: Self-motion and cognitive places

**Status:** Accepted (operator, 2026-09-25), including rule 19
**Date:** 2026-09-25
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** Option 1, bounded proprioceptive self-motion (2026-09-25)

---

> **Operator decision, 2026-09-25: accepted, rule 19 included.**
> `not_found_in_bounded_search` at believed place P is evidence only about that
> search at P: not that the resource is absent at P, nearby, or anywhere.
> Changing the believed place therefore changes whether the earlier result
> applies. The numbers in this ADR are current implementation parameters.

## Context

Person perceives things relative to where it is facing (ADR 0002) and
remembers episodes (ADR 0007), but it has no sense of where it is. Memory of
an earlier fruitless search is therefore recalled and ignored: without "here",
"I searched here" cannot be said.

Four sources of spatial knowledge were considered, and the operator chose the
first:

1. a proprioceptive, vestibular sense of Person's own motion;
2. place identifiers issued by the runtime (`docs/SEMANTIC_TARGETING.md`);
3. landmarks alone, which need persistent object identity (C4);
4. a deliberate coordinate check (`PERSON_SPEC` section 24.4).

The runtime knows Person's exact position, yaw, pitch and path. Person must
not. An organism's sense of its own motion is imprecise, relative, and drifts,
and that is the property worth keeping.

One existing channel predates this: `Observation.home.homeDistance`, the
runtime's estimate of the straight-line distance from Person to its home at
any range, through walls, with no drift. The planner's `at_home`, the night
return-home goal, the safety envelope and the context's home band all read it.
It carries more spatial certainty than this ADR permits, and it is not the
foundation of the spatial model.

## Decision

### The sense (runtime → cognition)

1. **Self-motion is perception, not motor truth.** Every observation carries a
   `selfMotion` percept. The runtime derives it from the exact pose, as the
   vision layer derives percepts from the exact eye pose, and only the
   quantized result crosses the firewall. `WorldSnapshot` stays privileged.
2. **No absolute frame.** No coordinate, chunk, compass heading, absolute yaw
   or pitch, world axis or path node reaches cognition through this channel.
3. **The reference frame is explicit.** `selfMotion` describes the change
   between the previous observation sent in this session and this one.
   Translation is the horizontal displacement of Person's feet, expressed
   relative to the body facing Person had at the previous observation.
   Rotation is the change in facing between the two. The first observation of
   a session has nothing to compare against and says so (`continuity:
"start"`).
4. **Translation is coarse.** A direction in eight equal 45-degree sectors,
   named with the percept bearing words and the same left/right convention,
   and a distance band (`none`, `tiny`, `short`, `moderate`, `far`) with a
   distance estimate on the same coarsening grid percepts use.
5. **Rotation is coarse.** The change in facing rounded to the nearest 45
   degrees and named: `none`, `slight_left`, `left`, `sharp_left`,
   `about_face`, `sharp_right`, `right`, `slight_right`. Glances are exactly
   one step, so a deliberate look is felt exactly; navigation turns are not.
6. **Vertical motion is felt coarsely** (`level`, `up`, `down`), so a fall or
   a climb is an experience. It is not integrated into place position.
7. **External movement is experienced movement.** Knockback, water, falling
   and server correction are changes in pose between observations, so Person
   feels them as motion like any other. A displacement no locomotion could
   produce in the elapsed time, a dimension change, or a revival is reported
   as `continuity: "discontinuous"` with no translation: Person notices that
   the scene jumped and does not know how far it moved. The limit is that a
   small teleport inside the locomotion bound is felt as ordinary motion. That
   is wrong and bounded, and it is recorded rather than corrected.
8. **No randomness.** Quantization is deterministic, so tests reproduce.

### The model (cognition)

9. **Path integration with uncertainty.** Cognition integrates self-motion
   into a position and facing in its own frame, whose origin is wherever
   Person first started integrating. It is not a world frame: it has no
   relation to Minecraft's axes or origin. Each integrated step adds
   uncertainty in proportion to the distance moved and to the accumulated
   uncertainty in facing, and nothing ever reduces it. A discontinuity makes
   the estimate unusable ("lost") until Person starts again from a fresh
   origin.
10. **The map is never corrected from hidden truth.** Nothing reads the
    snapshot, the placement ledger or `homeDistance` into the spatial model.
    The runtime may know Person's estimate is wrong; Person may not.
11. **Places are cognitive.** A `Place` is created by cognition at moments
    that matter (a search, a completed action, building a shelter) with an
    opaque identifier (`place_1`, `place_2`, ...) that encodes no position.
    It holds the estimated position and uncertainty at formation, and a
    coarse scene signature: which subjects were perceived there.
12. **Recognition is uncertain.** Person is "probably at place P" when its
    current estimate lies within P's radius once the doubt it has accumulated
    since forming P is allowed for, with a confidence that falls as that doubt
    grows. Within one frame error accumulates along a single path, so the
    doubt Person already had when it formed P does not separate it from P. A
    matching scene signature raises the confidence, which never reaches
    certainty. Recognition never means the runtime confirmed anything.
13. **Landmarks are coarse.** A signature is a set of subjects (wood, stone,
    container, ...), never the identity of a particular object. C4 remains
    unresolved and nothing here assumes that a tree seen now is the tree seen
    before.
14. **Routes are relations between places**: the estimated displacement from
    one place to the next as Person travelled, with its uncertainty. There is
    no global map.
15. **Home is where Person built its shelter.** The place in which Person
    experienced completing `build_basic_shelter` is labelled home in its own
    model, and so is the place it is at after successfully going home with
    `return_home`: a belief from its own action's outcome, which labels a
    place and moves no estimate. `homeDistance` is not used for this.
16. **Persistence through Person's own records.** Places and routes are
    journalled as `place_formed` and `place_visited` events, and the estimate
    at the end of an episode travels in `episode_ended`, exactly as memory
    does. A restart resumes from the last estimate with added uncertainty,
    because Person cannot know it was not moved while it was not running
    (ADR 0006 rule 2). A restart reveals nothing about the body's location.
17. **Episodes are placed.** A memory encoded while Person believes it is at a
    place carries that place and the confidence of the belief. A cue may name
    a place; memories from that place are then more relevant than the same
    memories elsewhere.
18. **Search memory, used as evidence.** When a search begins, Person recalls
    searches at the place it believes it is in. If it recalls an earlier
    search there that sought everything it now seeks and found none of it,
    the new search is shorter, in proportion to its confidence that it is the
    same place, and never shorter than a minimum. The conclusion is still
    `not_found_in_bounded_search`. It never becomes "there is no wood here",
    and the goal still reopens the moment wood is seen.
19. **"Not found" is about a place.** A goal blocked by a fruitless search
    reopens when what it sought is seen, and also when Person no longer
    believes it is at the place it searched from, because somewhere else was
    not searched. Returning to the searched place reopens nothing by itself.

Numbers such as sector widths, band edges, uncertainty rates, radii,
confidence rules and budgets are current implementation parameters and can be
retuned without a new ADR.

## Consequences

### Positive

- Search memory becomes useful: Person does not repeat a full sweep of a place
  it recognises, and it still looks a little.
- Moving the entire world changes nothing in Person's mind. A test enforces
  this.
- Person can be lost, and it can be wrong about where it is, provably.

### Negative

- The estimate drifts, so Person will fail to recognise places it has
  returned to and will sometimes "recognise" places it has not.
- `homeDistance` remained a drift-free homing channel beside the new model
  (C8). Resolved 2026-09-25: see the decision below.

### Neutral

- `observationVersion` 5 adds `selfMotion`. Journal schema v5 adds
  `place_formed` and `place_visited`.

## Alternatives Considered

| Alternative                             | Why rejected                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Runtime place identifiers               | An authoritative spatial truth supplied to Person. Rejected by the operator as the foundation.   |
| Landmarks only                          | Needs persistent object identity, which is C4.                                                   |
| A coordinate instrument now             | Deferred. It would be a deliberate act with its own provenance, and is compatible with this ADR. |
| Report yaw deltas in degrees            | Floating-point rotation is an absolute heading one sum away.                                     |
| Add Gaussian noise                      | Unreproducible, and quantization already makes the estimate honestly imperfect.                  |
| Snap the map when Person is `at_home`   | That is the runtime correcting Person's map from hidden truth.                                   |
| Build a grid map in the cognitive frame | A map replacement, not a sense of place. Places and routes are what the spec asks for.           |

## Revisit Conditions

- **The coordinate instrument is built.** It becomes a separate provenance for
  a fix, never passive telemetry.
- **C4 is resolved.** Landmarks can then carry object identity.
- **`homeDistance` (C8): decided 2026-09-25.** Exact physical distance from
  home may exist in trusted containment and operator tooling. It is not a
  Person sense and never crosses into the observation, cognition, memory or
  the spatial model. Person's relation to home (`at_home`, `near`, `far`,
  `unknown`) is derived from its own places and doubt, and feeds the
  planner's `at_home`, the night return-home goal, the decision context and
  the cognition-side exploration envelope.

## Relevant Commits / Documents

| Reference                          | Description                                          |
| ---------------------------------- | ---------------------------------------------------- |
| ADR 0002                           | The perception firewall this sense is inside         |
| ADR 0006                           | Gaps are learned, not experienced                    |
| ADR 0007                           | The memory places are attached to                    |
| `docs/PERSON_SPEC.md` section 24.4 | Spatial memory by places, routes, relative direction |
| `docs/SEMANTIC_TARGETING.md`       | The runtime-identifier direction not taken here      |
| `docs/CURRENT_STATE.md`, C4, C8    | Referents, and the legacy homing channel             |
