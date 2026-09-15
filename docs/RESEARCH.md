# Research framing

Person is a testbed for a narrower question than "build AGI":

> Can a persistent embodied agent develop stable, transferable behavioural
> adaptations from autobiographical experience, without hard-coding every
> response and without giving a language model direct control of the world?

This milestone does not answer that question. It builds the substrate the
question needs: a bounded body, a trustworthy boundary, and evidence that stays
interpretable long after the code that produced it has changed.

## Claim discipline

Person is not conscious, not sentient, not an AGI, and not a demonstration of
human-equivalent cognition. What this milestone demonstrates is exactly what
its tests assert, and nothing more:

- a bounded agent that survives in a deterministic fixture world;
- a safety boundary that holds under test;
- evidence that survives a restart and changes a later decision.

Capability claims should stay tied to reproducible behaviour. A convincing
episode is an anecdote; the test suite and the episode reports are the record.

## What is preserved for later study

Future work on prediction error, causal belief, memory consolidation and
transfer needs data that is easy to discard by accident. It is preserved here
on purpose:

| Preserved                                            | Why it matters later                                                                                  |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `observationVersion` on every observation            | Semantic changes stay distinguishable across time                                                     |
| `expectedEffects` next to `effects` in every outcome | Prediction and outcome can be compared without re-running the episode                                 |
| `requestedSkill` separate from `executedSkill`       | Interventions are distinguishable from intentions, which is what separates correlation from causation |
| `trainingContext` on every statistic and event       | Fixture, peaceful and normal evidence never merge                                                     |
| `contextId` on every decision and outcome            | Situations can be grouped without re-deriving them from raw observations                              |
| `rngSeed` on fixture episodes                        | Deterministic replay of the exact episode                                                             |
| `previous_event_id` chaining                         | An unbroken, orderable history, verifiable after the fact                                             |
| Raw counts rather than scores                        | A new scoring function re-reads history instead of invalidating it                                    |
| `evidence_refs` on every statistic                   | A future belief can point back at the episodes that produced it                                       |

Nothing here implements prediction, causal inference, consolidation or
transfer. The claim is about the format, not the capability.

## The research programme this belongs to

The specification lays out phases beyond this one: a predictive world model,
memory consolidation, social cognition, affect, language, projects, and
eventually multiple independent People. The architectural decisions that matter
for those are already made:

- cognition and execution are separate processes with an asymmetric contract,
  so no later cognitive system inherits physical authority by accident;
- providers for memory, world model, affect, language, social and projects
  exist as minimal interfaces that raise rather than returning empty results;
- evidence is append-only, so consolidation can build beliefs from episodes
  without rewriting the episodes;
- statistics are keyed by training context, so transfer between environments is
  measurable rather than assumed.

## Open questions this milestone does not touch

Whether routines learned in the fixture transfer to Minecraft. Whether a coarse
context is coarse enough to generalise and fine enough to be useful. Whether
Beta-scored routine selection remains adequate as the skill library grows, or
whether a structured world model becomes necessary. Whether goal suspension
scales from survival interruptions to multi-day projects.

Each of those is answerable with the data this milestone records, which is the
point of recording it this way.
