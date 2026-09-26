# ADR 0012: Causal hypotheses and controlled experiments

**Status:** Proposed
**Date:** 2026-09-26
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** typed, falsifiable hypotheses; LLM proposals count as
reasoning and never as evidence; uncertainty-driven, bounded experiments
through the ordinary goal machinery; memory, belief and knowledge kept
distinct, with knowledge promotion deferred (2026-09-26)

---

## Context

ADR 0011 taught Person one narrow belief: how reliable each skill's declared
effect is. It cannot say _why_ a skill sometimes works and sometimes does not.
`PERSON_SPEC` sections 22.1 and 22.2 ask for the next step: notice an
unexpected effect, form a hypothesis, design a bounded experiment, vary one
factor, compare outcomes and update confidence. This ADR adds the smallest
honest version of that loop:

```text
prediction error / unexplained variation
    -> a question
    -> a proposed, structured causal hypothesis
    -> a safe controlled experiment, as an ordinary goal
    -> observed result
    -> evidence update, observational or interventional
    -> revised confidence
```

### Audit

- **Evidence stream.** Every settled prediction is already classified per
  declared effect by ADR 0011's audited classifier: `supports`, `partial`,
  `contradicts` or `inconclusive`, with its reason. Hypothesis evidence is
  built on those verdicts and nothing else.
- **Conditions Person has.** The observation carries the weather and the day
  phase Person perceives, and Person's own map says which place it believes
  it is at, and how sure it is. Those are the only conditions a hypothesis may
  name.
- **Outcome honesty.** A harvest whose digging produced nothing was reported
  as `inventory_full`, which ADR 0011 rightly treats as "not attempted". That
  was a mislabel whenever the inventory was not full. Harvesting and hunting
  now stop after two fruitless tries and report `no_yield`, a genuine attempt
  whose effect did not follow; `inventory_full` is kept for a full inventory.
- **Language model.** No language model is wired into Person. The proposer
  interface below is written so that one can be plugged in without changing
  what counts as evidence; the proposer that runs today is deterministic.
- **Learning modes.** Unchanged, and applied as ADR 0011 applies them: `off`
  learns nothing, `shadow` learns into an isolated table no decision reads,
  `supervised` learns into the active table. Experiments change behaviour, so
  they run only under `supervised`.

## Decision

### Representation

1. **Hypotheses are typed, structured and falsifiable.** A hypothesis reads
   "WHEN condition C, IF Person does A, THEN observable outcome O is less (or
   more) likely than when C does not hold, judged on the next observation".
   Its fields are a condition (`variable`, `value`), an intervention (a skill
   Person has), an outcome (`fact`, `direction`), a horizon, provenance,
   evidence, and a lifecycle. There is no `hypothesis: str`. A rationale may be
   attached for people to read; nothing parses or acts on it.
2. **A closed vocabulary.** Conditions are `weather`, `day_phase` and `place`,
   with values from the observation schema or from Person's own map (a place
   must be one Person has formed). The intervention must be a non-emergency
   skill the runtime offered at session start. The outcome must be one of that
   skill's declared effects that ADR 0011 can evaluate, so every hypothesis can
   be contradicted by something Person can observe. No coordinates, entity
   handles, hidden block state, pathfinder state, code predicates, queries or
   free-text meanings.
3. **One factor at a time.** A hypothesis names exactly one condition, and the
   experiment varies exactly that condition. Unconditional reliability is ADR
   0011's belief and is not duplicated here. Passive associations with no
   intervention are not proposed in this phase.
4. **No object identity (C4).** Nothing is keyed by the thing acted on.

### Reasoning is not evidence

5. **Proposers reason; they do not testify.** A proposer, deterministic or a
   language model, receives a bounded reasoning context only: the anomaly, up
   to eight of Person's own classified trials with the conditions it
   perceived, the vocabulary, the skills offered, and its current reliability
   belief for that effect. It never sees the observation, the journal, a world
   snapshot, positions, skill targets or debug data. It returns candidate
   proposals, which are untrusted data.
6. **The grounding gate.** A proposal becomes a hypothesis only if it passes
   schema and vocabulary checks, cites at least one premise from its context,
   and claims no authority. Proposals that name privileged state, invent a
   variable, request a capability Person was not offered, lack an observable
   outcome, cannot be falsified, or carry a confidence are rejected and
   journalled as `hypothesis_rejected` with the reasons.
7. **Every hypothesis starts with no evidence.** Its premises are recorded and
   motivate it; they do not confirm it. Only trials after it was proposed count,
   so the data a hypothesis was fitted to cannot be counted in its favour, and
   a model's stated confidence has no weight at all.
8. **LLM latent knowledge is not Person's knowledge.** A model's familiarity
   with Minecraft may suggest a conjecture. It never enters Person's knowledge
   and never counts as evidence. Initial knowledge is a separate source
   (`INITIAL`) and does not need rediscovering.

### Evidence and standing

9. **Arms, and kinds of evidence.** Each trial of the intervention, judged on
   the outcome, falls into the "condition held" or "condition did not hold"
   arm. A trial Person made _as_ the experiment for this hypothesis is
   interventional (weight 1). A trial from ordinary life that happens to match
   is observational (weight 0.5): Person acted, but did not choose the
   condition to test it. The kinds are stored separately.
10. **Inconclusive trials teach nothing.** Refusals, safety takeovers,
    preemptions, missing prerequisites and missing observations stay
    inconclusive as in ADR 0011, and a trial is also inconclusive if the
    condition changed while it ran, or, for a place condition, if Person was
    not sure where it was. A capability denial is evidence about permission,
    not about the world.
11. **Strength and confidence are separate.** Relation strength is the
    difference between the two arms' estimated success rates, in the claimed
    direction. Confidence is how much evidence stands behind it, from the
    thinner of the two arms. Few trials stay visibly uncertain.
12. **Defeasible standing.** A hypothesis is `supported`, `weakened` or
    `contradicted` only with enough evidence _and_ at least one
    interventional trial in each arm: correlation alone never settles it.
    Standing is recomputed from evidence every time, so later evidence can
    reverse it. Before that its lifecycle shows: `proposed`, `testable`,
    `under_test`, `retired`. No hypothesis is ever `true`, `proven` or a fact.

### Experiments

13. **Curiosity is a small epistemic motive.** An investigation is considered
    for an unresolved hypothesis, scored inspectably as uncertainty times
    relevance times discrimination, discounted by the intervention's cost and
    risk (through the existing tolerance factor) and by open projects. It is
    not random exploration and not a personality trait.
14. **An experiment is an ordinary commitment.** It names its hypothesis, the
    intervention, the expected observation, the two arms, a repetition budget,
    stopping conditions, and its estimated cost and risk. Each trial is an
    ordinary goal (`INVESTIGATE`) that the planner, the policy, the validator,
    the capability policy and the safety kernel treat like any other. There is
    no science loop. Urgent needs preempt it; an interrupted trial resumes as
    any suspended goal does.
15. **Bounded.** One open investigation; a fixed number of trials per arm and
    of attempts in total; a daily trial budget in experienced time; no
    intervention above a risk limit; no intervention that consumes materials.
    Investigations start only when Person's pressing needs are calm and it is
    not night, and trials rank below ordinary projects.
16. **Affect and safety.** Affect reaches experiments only through the
    existing tolerance factor; there is no curiosity-to-affect or
    hypothesis-to-emotion coupling. Curiosity grants no authority: nothing
    about an experiment reaches the runtime except an ordinary skill proposal.

### Use of beliefs

17. **Bounded, supervised influence.** Under `supervised` only, a `supported`
    hypothesis whose condition holds now adds a term of at most ±0.1 to the
    score of routines that use its intervention, recorded separately on each
    candidate (`hypothesis_effect`). It creates no goal and cannot make an
    inapplicable routine win.

### Memory, belief and knowledge

18. **Four separate things.** Episodic memory: "I experienced E". Consolidated
    memory: "across remembered experiences, P recurred". Belief: "given my
    evidence, I hold H with this confidence". Knowledge: "I accept H strongly
    enough to rely on it as part of my world model". Consolidation compresses
    experience and never creates truth; repeated recall is not knowledge;
    storage is not endorsement; knowledge is Person's epistemic status, never
    physical truth, and stays defeasible and provenance-bearing.
19. **Promotion deferred.** This phase stops at hypothesis to
    evidence-updated belief. Hypotheses are not episodes and are not stored in
    episodic memory. No consolidation and no knowledge store are implemented.
    Later promotion needs repeated evidence, variation, handled contradiction,
    a threshold and provenance; a single observation never becomes knowledge.
    Provenance classes are kept distinct (`INITIAL`, `PERSONAL_OBSERVATION`,
    `PERSONAL_EXPERIMENT`, `INFERENCE`, `TAUGHT`, `OPERATOR`, `EXTERNAL_WEB`),
    and source never equals certainty. Only the first three are produced now.

### Persistence

20. **Journal schema v9.** `causal_trial`, `hypothesis_proposed`,
    `hypothesis_rejected`, `hypothesis_evidence` and `investigation_changed`.
    Hypotheses and investigations are rebuilt from these alone; cognition has
    no journal access.

The evidence weights, arm sizes, standing thresholds, budgets, priority, risk
limit, score weights, context size and the condition vocabulary are
implementation parameters.

### Settled while implementing

Within the decisions above, and recorded so the code can be checked against
them:

- **When Person wonders.** A question is raised after any conclusive trial
  whose history shows variation (the effect sometimes followed and sometimes
  did not) or repeated failure; a success after failures is variation too. One
  settled prediction raises at most one question, about the first declared
  effect Person could judge, and at most three unresolved hypotheses are held
  about one effect. Repeated failure alone makes every condition the failures
  shared a guess.
- **Discrimination.** An experiment on a condition Person has never lived
  through on both sides is worth nothing yet, so it is not started.
- **Patience.** An investigation that makes no progress for a day of
  experienced time is retired (`condition_not_encountered`), so waiting for a
  condition cannot hold the one open slot for ever.
- **What an inconclusive trial also covers.** A condition that changed between
  the decision and the observation that judged it, and a place condition when
  Person was not sure where it was.
- **Affect.** Trial goals receive no affect priority bias; affect reaches an
  experiment only through the tolerance factor on its risk, and through the
  ordinary appraisal of any action's outcome.
- **Two defects found on the way, fixed separately.** Harvests that yielded
  nothing were reported as `inventory_full` (now `no_yield`, after two
  fruitless tries), and a decision context id could exceed the protocol's
  64-character limit, which dropped the decision (the `contextId` field now
  allows 128).

## Consequences

### Positive

- Person can notice that a skill works under one condition and not another,
  test that, and change a close choice because of it, with every step in the
  journal.
- A model can be allowed to reason for Person without being allowed to know
  for it.

### Negative

- Only single-condition hypotheses about declared, evaluable effects. Richer
  causal structure (several factors, delayed effects, effects on facts the
  skill does not declare) needs a later decision.
- Conditions Person cannot choose, such as the weather, are tested only when
  they happen; an experiment waits for its condition.

### Neutral

- Journal schema v9. The goal protocol gains the `INVESTIGATE` goal type.

## Alternatives Considered

| Alternative                            | Why rejected                                                               |
| -------------------------------------- | -------------------------------------------------------------------------- |
| Natural-language hypotheses            | Meaning would live only in the model; nothing could check or falsify it.   |
| Start a hypothesis at the model's word | Makes latent knowledge evidence (operator).                                |
| Count the motivating trials            | The hypothesis was fitted to them; that is double counting.                |
| A dedicated experiment executor        | Would bypass drives, planner, validator and safety.                        |
| Random exploration as curiosity        | Entropy is not a research objective (`PERSON_SPEC` 22.1).                  |
| A knowledge store now                  | Not needed for the experiment loop; deferred to keep the phase reviewable. |

## Revisit Conditions

- Belief-to-knowledge promotion and memory consolidation (the next phase).
- A language model is wired in as a proposer.
- Multi-factor or delayed-effect hypotheses are needed.
- Taught, operator or external sources arrive.

## Relevant Commits / Documents

| Reference                                            | Description                        |
| ---------------------------------------------------- | ---------------------------------- |
| `docs/PERSON_SPEC.md` sections 22, 25.1, 26          | Experimentation, consolidation     |
| ADR 0007, ADR 0010, ADR 0011                         | Memory, affect, effect reliability |
| `apps/cognition/python/person_cognition/hypotheses/` | The implementation                 |
