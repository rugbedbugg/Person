# ADR 0020: Hybrid cognition: Person-owned structure, replaceable deliberation

**Status:** Accepted (2026-09-30)
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Direction:** the operator agreed the hybrid-cognition thesis and delegated
its continuation to the reviewer before stepping away; the reviewer set the
new cognitive phase (C1 to C7) before E4, after it became clear that Person
has no general reasoning model, and accepted this ADR with the amendments
below (2026-09-30). Person-000 stays absent throughout. The final gate
verifies that Ada's configuration conforms to this ADR; it does not re-decide
it.

---

## Context

Everything Person decides today comes from hand-built structure: goal
priorities, a bounded planner over the skill library, learned effect
reliability (ADR 0011), deterministic hypothesis proposal (ADR 0012),
projects (ADR 0009), memory (ADR 0007) and affect (ADR 0010, 0014). When that
structure has no answer, Person has no way to think about why. The E3
rehearsal and the ADR 0019 air check show the shape of it: a local emergency
response succeeds every time (`restore_air`), the same emergency keeps
returning, and nothing in Person can notice that the higher-level strategy
(staying in deep water) is the problem.

The frozen architecture already anticipates a language model: a separate
provider process (PERSON_SPEC sections 6 and 40), never Person (section 39),
never authoritative, never in control of the world (section 1.2), with Person
operational without it (section 5). ADR 0012 already fixed how a model may
propose: from a bounded reasoning context, through a grounding gate, with its
confidence given no weight and its latent knowledge never counted as
Person's. This ADR extends those rules from hypotheses to deliberation in
general.

## Decision

### The thesis

Person is a persistent hybrid cognitive architecture. Routine cognition,
learned procedures, safety, memory, beliefs, projects and affect are
Person-owned. General-purpose foundation models are replaceable, stateless
deliberative services, invoked only when ordinary cognition is insufficient.
Successful deliberative strategies may become evidence-backed contextual
procedures, reducing future dependence on general deliberation. The model is
neither Person's identity, memory, ground truth nor physical controller.

### Invariants

```text
LLM                   != Person
LLM context           != memory
LLM output            != belief
LLM proposal          != action
LLM success once      != habit
habit                 != immutable rule
affect                != command
emergency response    != deliberation
```

1. **The trust boundary is unchanged.** A deliberation runs inside cognition,
   on the cognition side of the protocol. Its output can only become what
   cognition already produces: a goal, a project change, a plan request or a
   question, compiled by Person's planner and judged by the runtime's
   validator and safety kernel (ADR 0005). Emergencies never wait for it and
   never pass through it (ADR 0019).
2. **What and why; never how.** A deliberative model cannot request, bind,
   sequence or parameterize a physical `SkillInvocation`. A proposal names
   goals, project kinds and desired and expected facts in Person's
   vocabulary; it may cite offered capabilities, unordered, only as evidence
   that a strategy is feasible. Person's planner turns an admitted strategy
   into routines and skills (how), and the runtime decides whether they are
   physically permitted (whether). No coordinates, commands or code. Only a
   later ADR may amend this.
3. **A bounded context, and nothing else.** A model sees only a
   `DeliberationContext` built by cognition from projections that already
   exist, each within the firewalls it already obeys: the self-knowledge and
   operational projections (ADR 0017), the current bounded observation's
   cognitive summary (ADR 0002), recalled memories within recall's limits
   (ADR 0007), beliefs with their uncertainty (ADR 0011, 0012), active goals
   and projects, recent failures and prediction errors, Person's
   capabilities, and the reason deliberation was requested. Every collection
   is capped. Never the journal, a world snapshot, a position, the repository
   or anything the runtime alone knows. **Raw affect is not in the context**
   until C6 adds it, under its own ADR, as a versioned extension; before then
   affect reaches deliberation only through what it already legitimately
   shapes, such as a goal's priority (ADR 0010).
4. **Proposals are untrusted and gated.** A proposal becomes anything only if
   it passes a grounding gate like ADR 0012's: the schema, Person's
   vocabulary, at least one premise cited from the context, no capability
   Person was not offered, no privileged state, no claimed authority. A
   model's stated confidence is recorded and given no weight. Rejections are
   journalled with their reasons.
5. **Reasoning is allowed; latent world knowledge is not Person's (ADR 0004
   rule 5, ADR 0012 rule 8).** The model is instructed that the context is the
   complete factual basis of the deliberation: it may reason over those
   premises, never import Minecraft- or world-specific facts. Every expected
   world effect in an admitted strategy must be supported by a cited Person
   belief, an offered capability's declared effect, or a cited current
   premise; an unsupported consequence is an unsupported world claim and is
   rejected. Anything Person later relies on because of a deliberation
   carries `DELIBERATION` provenance, a discovery experiment is invalid if
   deliberation was available to it, and C7 scores outside-knowledge leakage
   as a violation.
6. **Stateless and sterile.** Each call is independent: no repository, no
   journal, no files, no web, no shell, no tools, no inherited MCP servers,
   no provider-side conversation. Provider memory must never become a second,
   hidden memory for Person.
7. **Inspectable, not introspective.** Each deliberation has an id shared by
   its records. The journal records why it was requested; the provider, model
   and version as the adapter (not the model) reports them; the context and
   proposal schema versions; canonical-JSON hashes of the context and of the
   instruction template, so the effective input is pinned; the output hash;
   the structured, gated proposal and its verdict; and, from C3, what Person
   did next. Raw provider text never enters the journal; it is kept as a
   hash-linked operator audit artifact outside anything cognition can read.
   No chain of thought is requested or stored. A request left unmatched by a
   crash stays unmatched.
8. **Optional, and fails closed.** `deliberation_unavailable` means the
   provider produced no response (timeout, quota, authentication, backend);
   Person carries on with its ordinary cognition. A malformed response is a
   completed deliberation whose proposal the gate rejected. No provider is
   switched silently within a session. The mode is configuration, like
   affect's: `off` (the default everywhere: nothing is invoked or recorded),
   `record_only` (invoked and recorded, reaching nothing), and `active`, which
   exists only once C3's adoption and arbitration ADR does. Nothing enables
   deliberation because a provider happens to be available.
9. **C1 has no behavioural path.** An admitted proposal changes no goal,
   project, planner input, routine, policy, belief, hypothesis, memory,
   affect, learning or invocation, and C1 is never called from a live
   decision loop, because even a noncausal call spends the world's time.

### Increments

- **C1** the provider-neutral boundary: context, proposal, gate, the
  `CognitiveModel` interface, journalling and the audit artifact. Scripted
  models and offline evaluation only; a structural-isolation test shows
  `record_only` changes nothing but the new evidence.
- **C2** sterile Claude Code and Codex backends behind it.
- **C3** metareasoning: when to deliberate, with budgets and cooldowns; the
  air-recurrence case as an adversarial fixture.
- **C4, C5** proceduralization: habit candidates from real outcome evidence,
  promotion, confidence and invalidation.
- **C6** affect in automatic-versus-deliberate arbitration only.
- **C7** synthetic evaluation of both backends on Person-specific contexts,
  and the initial backend choice.

C3 to C6 each get their own decision record before they are implemented.
Instrumentation from C1 on: deliberations per experienced hour, by trigger,
and later proceduralization, habit success and invalidation.

## Implementation status

- **C1:** `person_cognition/deliberation/`: the model interface, the bounded
  context, the proposal schema and grounding gate, the deliberator with its
  journal records and audit artifact, and the rate metric. Evidence schema
  v14. Nothing in the decision loop calls it; a structural-isolation test
  shows `record_only` changes nothing but its own evidence. TESTED with
  scripted models; no provider is wired.

## Consequences

### Positive

- Person can notice and reason about a situation its routines cannot handle,
  without ceding identity, memory, belief or control.
- Discovery and dependence stay measurable: every model contribution is
  provenanced, and deliberation frequency is an outcome, not a hidden cost.

### Negative

- A model's latent knowledge is a standing contamination risk for any
  "Person learned this" claim; provenance and a deliberation-off mode are the
  only defences.
- Subscription CLIs are a new, externally controlled dependency with their
  own availability and version drift.

## Alternatives considered

| Alternative                                 | Why not                                                      |
| ------------------------------------------- | ------------------------------------------------------------ |
| Call the model on every observation         | Makes the model the mind; unaffordable and untestable        |
| Let the model emit skill invocations        | Moves "how" out of Person's planner and past its learning    |
| Keep provider conversations for continuity  | A hidden second memory outside the journal and the firewalls |
| Shape the interface around one provider CLI | Couples Person's cognition to a vendor's tooling             |
| Cache responses as habits                   | Memoization, not proceduralization: no outcome evidence      |

## Revisit conditions

- Evidence that cognition cannot resolve a class of situation safely even
  with deliberation.
- A proposal to let a model name skills for direct execution.
- A local or open model replacing the subscription backends.

## Relevant commits and docs

- PERSON_SPEC sections 1.2, 5, 6, 22.2, 39 and 40; ADRs 0002 to 0005, 0007,
  0010 to 0012, 0017 and 0019.
- The air-recurrence observation:
  `docs/evidence/dedicated-server/2026-09-30-adr0019-air-check/`.
