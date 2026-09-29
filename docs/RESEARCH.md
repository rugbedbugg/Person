# Research framing

Person is a testbed for a narrower question than "build AGI":

> Can a persistent embodied agent develop stable, transferable behavioural
> adaptations from autobiographical experience, without hard-coding every
> response and without giving a language model direct control of the world?

This milestone does not answer that question. It builds the substrate the
question needs: a bounded body, a trustworthy boundary, and evidence that stays
interpretable long after the code that produced it has changed.

## Claim discipline

No claim is made that Person is conscious or possesses subjective experience.
Person is not claimed to be sentient or an AGI, and is not a demonstration of
human-equivalent cognition. Whether an agent like it could have phenomenal
experience is an open question this project may study; it is not something
any result here settles. What the work demonstrates is exactly what its tests
assert, and nothing more:

- a bounded agent that survives in a deterministic fixture world;
- a safety boundary that holds under test;
- evidence that survives a restart and changes a later decision.

Capability claims should stay tied to reproducible behaviour. A convincing
episode is an anecdote; the test suite and the episode reports are the record.

The same discipline applies to affect. Person has a small functional affect
(ADR 0010): a continuous, decaying internal state that biases near choices.
Research on it may establish claims of the form "persistent affect causally
changes how decisions are organised over time" or "affect improves or worsens
recovery under these fixture conditions". It cannot establish that Person
feels emotion, is conscious, or has phenomenal experience:

- observable behaviour is not phenomenal consciousness;
- functional affect is not proof of feeling;
- a self-report would not be proof of sentience.

New research code names affect functionally (`affective_state`,
`apply_appraisal`, `affect_mode`) rather than in words that presuppose
experience.

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

Some of that later work now exists, TESTED IN FIXTURE only: prediction error
feeds learned effect beliefs (ADR 0011), and causal hypotheses are tested by
Person's own experiments (ADR 0012). Consolidation and transfer do not exist.

## The research programme this belongs to

The specification lays out phases beyond the survival slice: a predictive world
model, memory consolidation, social cognition, affect, language, projects, and
eventually multiple independent People. Episodic memory, places, projects,
affect, effect beliefs and causal hypotheses have since been built; the rest
have not. The architectural decisions that matter
for those are already made:

- cognition and execution are separate processes with an asymmetric contract,
  so no later cognitive system inherits physical authority by accident;
- providers for the systems not yet built (world model, language, social,
  exploration) exist as minimal interfaces that raise rather than returning
  empty results, and each leaves when its system is built;
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
