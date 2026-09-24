# ADR 0007: Episodic memory and bounded recall

**Status:** Proposed
**Date:** 2026-09-24
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Settles:** ADR 0003 rule 2 (the retrieval model), for the foundation

---

## Context

ADR 0003 separated the evidence journal (engineering truth) from Person's
recollection (cognitive state) and deferred the retrieval model. Until now
Person had no recollection at all: the symbolic state is recomputed from each
observation, a restarted process remembers nothing, and the only placeholder,
`MemoryProvider.retrieve(query: dict, limit: int)`, was an arbitrary-query
interface of exactly the kind ADR 0003 rule 1 forbids.

Three things constrain what can be built now:

- **The perception firewall (ADR 0002)** decides what Person experienced.
  Memory can only be as honest as its inputs, which is why the peripheral
  ownership leak was closed before this work began.
- **C4 is unresolved.** Skills still choose their own targets from privileged
  state, so the runtime cannot say which thing an action was done to.
- **There is no spatial model.** Person cannot say "here", so no memory can be
  about a place.

`docs/PERSON_SPEC.md` sections 24 and 25 describe six memory types,
consolidation and interference. This ADR does not build them. It fixes the
boundaries every later memory system must keep, and specifies the narrow
foundation that keeps them now.

## Decision

### Boundaries (durable)

1. **Memory is not the evidence store.** The journal records that an episode
   was _encoded_, as a `memory_encoded` event, because that is engineering
   truth like any other. Person's memory store is a reducer over those events
   and nothing else: no other event type can create, change or reveal a
   memory. A stored record and a recalled memory are different facts, and the
   second is produced only by recall.
2. **Legitimate inputs only.** An episode is encoded from what cognition was
   actually given or actually did: cognition-facing percepts, Person's own
   decisions and searches, the outcome the runtime reported (what executed,
   its status, the inventory change and the health cost Person felt), and
   emergencies the runtime announced. Encoding copies named fields through a
   whitelist, never a message wholesale. Nothing is encoded from a
   `WorldSnapshot`, the placement ledger, coordinates, pathfinder state,
   entity handles, debug state, or a skill's internal choice of target.
3. **Recall is a typed, bounded cue.** Cognition's only read path is
   `Memory.recall(cue)`, where a `Cue` names subjects and episode kinds from
   closed vocabularies. There is no text query, no caller-chosen limit, no
   enumeration, and no method that returns the store.
4. **Recall is small.** Every recall returns at most `RECALL_LIMIT` memories
   (3). A cue that matches more returns the best of them, never all.
5. **Ranking is inspectable.** A memory's score is its cue relevance times its
   accessibility. Relevance is the fraction of the cue's subjects the episode
   is about, and zero relevance excludes it. Accessibility decays with
   Person's experienced time since encoding, and salience slows the decay:

   ```text
   half_life     = base_half_life × (1 + salience_stretch × salience)
   accessibility = 0.5 ^ (age / half_life)
   recallable    = accessibility ≥ recall_threshold
   score         = relevance × accessibility
   ```

   The constants live in one replaceable `RecallRules` value (initially one
   Minecraft day of half-life, a stretch of 9, a threshold of 0.05). They are
   engineering defaults, not psychological claims, and changing them requires
   no ADR.

6. **Forgetting is inaccessibility, not deletion.** A memory whose
   accessibility has fallen below the threshold is not returned, and it is
   still in the store and in the journal. Nothing in this foundation erases
   a memory.
7. **Provenance is kept, not flattened.** Every episode records its source
   (`perceived`, `proprioceptive`, `action_outcome`, `own_decision`), the
   protocol message or evidence event it came from, the tick and the training
   context. The source vocabulary is open to `inferred`, `taught`,
   `operator` and `external`, mapping onto `PERSON_SPEC` section 22.2, and
   those are recorded as future, not accepted.
8. **A memory is not refreshed from the world.** Episodes are immutable.
   Nothing compares a memory with current perception or with physical truth
   and edits it. A memory can be stale, incomplete, or contradicted by what
   Person now sees, and it stays exactly as encoded.
9. **Recall is labelled.** A recalled item is a `Recalled`, marked
   `source="memory"` with the age it had when recalled. It never enters the
   observation or the planner's symbolic state, both of which come from
   current perception only.
10. **Memory is not belief.** "I saw wood" is recorded. "There is wood" is not
    concluded from it. Building beliefs from memories is future work.
11. **No invented referents.** An action is remembered by the skill that
    executed and what Person felt happen, never by the object it was done to.
    Nothing links a remembered percept to a remembered action. Until C4 is
    resolved there is no evidence for that link, and memory does not make one
    up.
12. **Persistence passes through recall.** Episodes survive a restart because
    the journal does. Working memory does not survive, and a restarted Person
    starts with nothing in mind. Its past comes back only through cued recall,
    bounded as above.

### Foundation (this phase)

- **Episodic memory** of five kinds: `perceived` (a category recognised that
  was not recognised a moment before), `acted` (a skill outcome), `endangered`
  (an emergency the runtime announced), `hurt` (a drop in health between two
  observations), `searched` (a bounded search that concluded).
- **Working memory**: a small bounded list of what was just encoded or
  recalled, never persisted.
- **Salience**: a fixed table by kind and subject, with a bonus for the first
  episode about a subject. It is not affect and not personality.
- **Time**: accessibility uses Person's experienced ticks, which advance only
  while cognition is receiving observations, and resume where they stopped
  after a restart. ADR 0006 rule 2 applies: a gap in which the process did not
  run is not experienced time.
- **Training contexts do not mix.** A memory formed in the fixture is never
  recalled in a live world, and the other way around.
- **Learning modes do not gate memory.** `learning.mode` decides whether
  statistics may steer the policy. It does not decide whether Person
  experiences things, so episodes are encoded in every mode, `off` included.
  Validation runs (`person skill-test`) start no cognition and encode nothing.
- **Search memory**: a concluded search is remembered as what it was. An
  exhausted search is remembered as `not_found_in_bounded_search`, never as
  absence. Recalling it is reported in the next search's reason codes and
  journal record. It changes nothing about how Person searches: without a
  spatial model Person cannot tell whether it is in the place it searched.

## Consequences

### Positive

- Person has a past that survives a restart and can be recalled.
  Measurement is possible because recall is a narrow, journalled operation:
  the journal holds every episode, and each `memory_recalled` event says
  which ones Person got back.
- Every memory can answer "why does Person have this?" from its own record.
- The retrieval path is small enough to test against every rule above.

### Negative

- Recall fails silently in the sense a person's does: an old, weak memory is
  there and does not come back. That will look like a bug.
- Without place, memory cannot yet change most decisions. The first uses are
  reporting and instrumentation, deliberately.
- The composite snapshot body changes shape. Older snapshots are refused, and
  the journal rebuilds state in full once.

### Neutral

- Journal schema v4 adds `memory_encoded` and `memory_recalled`.
- `MemoryProvider` leaves `future_providers.py`: memory is no longer a
  placeholder.

## Alternatives Considered

| Alternative                                     | Why rejected                                                                                                             |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Keep `retrieve(query: dict, limit: int)`        | An arbitrary query with a caller-chosen limit is database access under another name (ADR 0003 rule 1).                   |
| A separate memory file beside the journal       | Two durable stores that could disagree. Journalling the encoding keeps one authoritative history and one rebuild path.   |
| Build memory by re-reading all journal events   | Recall would then reach decisions and runtime records Person never experienced as episodes. Only encoded episodes count. |
| Delete memories that decay                      | Irreversible, destroys the evidence that forgetting happened, and contradicts `PERSON_SPEC` section 25.2.                |
| Weighted sum of relevance, recency and salience | A sum lets a highly salient but irrelevant memory outrank a relevant one. Relevance as a gate is what makes recall cued. |
| Bind actions to the last seen matching percept  | This is the C4 referent problem solved by guessing. The binding would be false whenever the skill chose another target.  |
| Semantic memory now                             | Consolidation needs repeated episodes and a belief model. Out of scope, and specified to come later (Phase 7).           |

## Revisit Conditions

- **C4 is resolved.** Actions can then be remembered with their referent.
- **The spatial model exists (Phase C).** Episodes can carry a place, and
  search memory can legitimately change where Person looks.
- **Consolidation and belief.** A memory can support a belief with provenance
  once a belief model exists.
- **Retrieval quality becomes a capability axis to raise (ADR 0003).** That is
  a change to `RecallRules`, raised by name.

## Relevant Commits / Documents

| Reference                                            | Description                                      |
| ---------------------------------------------------- | ------------------------------------------------ |
| ADR 0003                                             | The firewall this ADR implements                 |
| ADR 0002                                             | What Person can experience, and so can remember  |
| ADR 0006                                             | Experienced time and gaps                        |
| `docs/PERSON_SPEC.md` sections 22.2, 24, 25          | Provenance classes, memory types, retrieval      |
| `docs/CURRENT_STATE.md`, Known Deviations C3, C4, C6 | The ledger rename, referents, and the memory gap |
| `apps/cognition/python/person_cognition/memory/`     | The implementation                               |
