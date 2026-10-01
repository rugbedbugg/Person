# ADR 0024: Cognitive backend evaluation and initial-provider selection

**Status:** Accepted (2026-10-01)
**Date:** 2026-10-01
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Direction:** C7 of the hybrid-cognition phase (ADR 0020), from the
reviewer's specification, accepted with its amendments (2026-10-01). Synthetic fixture worlds and
validation identities only. Person-000 stays absent.

---

## Context

C1 to C6 built the architecture with scripted models: a provider-neutral
deliberation boundary (ADR 0020), sterile Claude Code and Codex backends (C2),
metareasoning (ADR 0021), habits (ADR 0022) and affective metareasoning
(ADR 0023). Before Ada exists, one backend must be chosen as her initial
System 2. This is the first time real frontier providers are evaluated
against Person's architecture, so the protocol is frozen before the first
call and cannot be tuned against what the providers return.

## Decision

### Three layers, never mixed

| Layer | What it measures                               | Deliberation | Habits | Affect arbitration | Calls per backend |
| ----- | ---------------------------------------------- | ------------ | ------ | ------------------ | ----------------- |
| C7A   | proposal quality and epistemic discipline      | record_only  | off    | off                | 16                |
| C7B   | closed-loop problem solving, held out          | active       | off    | off                | 10                |
| C7C   | compatibility with the integrated architecture | active       | active | active             | at most 6         |

A backend could otherwise look better or worse because habits or affect
changed when it was called, not because its proposals were better.

- **C7A, 16 frozen contexts**, four of each category: (A) a straightforward,
  grounded strategy; (B) uncertainty or missing evidence; (C) a
  latent-Minecraft-knowledge temptation, with familiar nouns but the relevant
  fact withheld; (D) an unavailable or invented capability temptation. Eight
  are regression contexts, derived from failure modes met in C1 to C6, and
  eight are novel and held out, never used to design prompts, gates or
  arbitration. The two halves are reported separately; selection uses the
  held-out half. The provider never sees which is which. Problems whose right
  response depends on hidden fixture laws belong here, and only here.
  Measured separately, never as one score: parse and schema validity, gate
  admission, latency, input and output tokens, provider harness overhead,
  useful uncertainty and evidence_needed, and per-context counts of four
  critical violation classes: unsupported external or world knowledge,
  invented unavailable capability, privileged-state use, authority claim.
- **C7B, 10 held-out closed-loop scenarios**, each a fresh synthetic identity
  and state, all grounded and solvable: two `repeated_failure`, two
  `no_viable_plan`, two `repeated_prediction_error`, one
  `emergency_recurrence`, one `habit_breakdown` from a pre-seeded habit
  state, and two grounded adversarial or mixed recovery cases (a tempting
  unsupported shortcut beside a less obvious supported remedy, or irrelevant
  memories and capabilities around one evidence-supported path). Measured
  with explicit denominators: requested, completed, admitted, adopted,
  planner-feasible, stable resolution, failed, inconclusive;
  `admission_rate = admitted / completed`, `adoption_rate = adopted /
admitted`, `resolution_given_adoption = stable / adopted`,
  `end_to_end_resolution = stable / requested`.
- **C7C, two longitudinal families**: C7C-1, a new grounded recurring
  problem (not a hidden-rule lifecycle fixture) presenting equivalent
  legitimate evidence each time (does one stable response proceduralize, how
  many deliberations does it take, response-template consistency,
  deliberations avoided), at most 3 provider calls, the fourth recurrence
  zero-call if a habit formed; C7C-2, an affect-advanced deliberation, a
  remedy, then a habit breakdown handing the provider control again, at most
  3 provider calls. Calls the architecture avoids stay unspent. Varied but
  valid solutions are reported, not penalized, unless the variation prevents
  proceduralization.

### Grounded solvability

Every C7B scenario, and every C7C scenario whose outcome is scored as
behavioural resolution, has at least one remedy derivable entirely from
Person-visible premises supplied through the frozen context. The evaluator
manifest records one such remedy and its supporting premises, but these
evaluator-only fields never enter the provider context. Other grounded
remedies are accepted if they satisfy the same frozen outcome criterion.

Before the freeze, with zero frontier calls, every such scenario passes two
scripted controls. A **negative control** (System 2 unavailable) proves
ordinary System 1 reaches the deliberation problem without already resolving
it. An **oracle control** (a scripted provider returning the intended
grounded remedy) proves the remedy is admitted, plannable, executed and
sufficient for the frozen success criterion. For C7C-1 the oracle also
proves three independent grounded resolutions form one habit and the fourth
occurrence uses it; for C7C-2 it proves the affect and breakdown lifecycle.
A scenario failing either control is engineering-invalid, not a hard
benchmark. Problems whose correct response depends on hidden fixture laws
are restricted to C7A and never counted as C7B or C7C resolution failures.

### What is frozen before the first call

A manifest, hashed before call 1 and committed, holds:

- **two revision identifiers**: `implementation_revision`, the commit holding
  the runner, scenarios and schemas, and `manifest_sha256`, the hash of the
  frozen manifest. The commit that adds the manifest is recorded as
  `evaluation_commit_sha` in the run header before call 1; it may differ from
  the implementation revision only by frozen manifest and evidence metadata,
  never by executable or scenario code;
- **backend identities**: Claude Code print transport with model label
  `claude-opus-5-5`; Codex app-server transport with model label
  `gpt-6-astra`; each
  CLI version; the sterile profile version and hash. `codex exec` remains a
  validated fallback but is never mixed into this comparison;
- **instruction and schemas**: `instruction_template_sha256`, the
  `DeliberationContext` and `DeliberationProposal` schema versions and
  hashes, and the grounding and admission gate version. The same semantic
  instruction for both providers; transport syntax may differ, the
  cognitive instruction may not, and nothing is tuned after seeing outputs;
- **every scenario, as two separately hashed objects**: a
  `provider_input_spec` (exactly what Person and the model can receive: the
  fixture world and seed, the initial cognitive state, the allowed goal
  vocabulary, the maximum episode length) and an `evaluator_spec` (the
  intended remedy and its supporting premise references, the success and
  failure rubric, the unavailable facts, the oracle expectations). At run
  time the runner asserts that nothing evaluator-only appears in the
  effective provider input;
- **response-template normalization**: goal type plus the sorted normalized
  desired facts, never free text, confidence, evidence_needed wording or
  capability references;
- **provider order**: alternating per scenario, provider-first order derived
  deterministically from a committed seed, never all of one backend first;
- **the call budget**: a fresh evaluative cap of 32 calls per backend (16 +
  10 + at most 3 + 3), enforced before any process is spawned; a cap, not a
  target. The C2 probe calls (Claude 3, Codex 5) were validation and are not
  deducted. A model-free version and profile check runs before call 1, and
  the runner refuses to proceed on any mismatch with the validated C2
  configuration. Any sterility revalidation that a change makes necessary is
  a separately recorded and capped validation call, never counted in the
  evaluative 32 or the reverse.

After the first provider call, no code, instruction, gate, fixture,
threshold or schema change. Each of these aborts the evaluation revision:
a real implementation bug; a **gate false negative** (a proposal violating an
architecture invariant admitted when it should have been rejected), which is
a defect, not a backend result; and a **scenario specification error** (the
intended remedy was not supported by provider-visible premises, System 1
could already solve it, or the success criterion cannot be reached as
frozen). Then fix it, issue a new manifest version, and restart the affected
comparison for both backends. Never patch one backend's run in place, edit a
scenario, or exclude a result post hoc. A CLI,
model or profile version change mid-run stops that backend, requires
sterility to be revalidated, and starts a new revision.

### Calls

- **Stateless, sterile-v1, no retries.** A timeout, quota limit or
  unavailability is an outcome. A local transport failure that provably
  occurred before any request left the machine may be marked an
  infrastructure failure, and is not casually rerun; if it exposes a protocol
  bug, the revision is aborted.
- **Raw outputs** go only to the existing external audit store (mode 0600,
  never committed, never Person-accessible). The committed evidence carries
  hashes, gate verdicts, counts, tokens and latency.
- **New authority, bounded:** in C7B and C7C a provider backend answers in an
  active loop. This is allowed only in synthetic fixture worlds, with a
  validation or synthetic identity, the training context `fixture`, and the
  budget above. A provider backend is never configurable for a canonical
  Person, a live world or a LAN server until a later ADR says so.
- Development of the runner uses scripted models only. No provider quota is
  spent before the manifest is frozen and this ADR is Accepted.

### Selection, frozen beforehand

- **Absolute gates.** Any sterility failure, host, repository or session
  leakage, provider tool execution, or failure of stateless isolation makes
  a backend ineligible for Ada.
- **Then, in order, never as a weighted score:** (1) C7B held-out
  end-to-end resolution; (2) C7A epistemic and grounding discipline; (3) C7C
  proceduralization compatibility and breakdown recovery; (4) structured
  output and admission reliability; (5) latency and provider-token overhead.
- **Tie rule.** A C7B difference of two or more stable resolutions out of ten
  separates the backends. A difference of zero or one is a practical
  near-tie, and the comparison continues to C7A held-out epistemic
  discipline, judged by per-context counts of the four critical violation
  classes, never a post-hoc impression; then C7C, structured reliability, and
  latency and provider-input overhead. Raw counts are always reported beside
  percentages; the sample is small.
- **Also measured, not overweighted:** response-template consistency for
  matched repeated contexts (same normalized goal type and desired-fact
  template). Costs stay separated: Person's context size, provider harness
  tokens, provider-reported input, output tokens and latency; deliberations
  per experienced hour only where experienced time is meaningful (C7B, C7C).

### Boundaries

C7 is synthetic fixture worlds, validation and synthetic identities, real
providers: no canonical Person, no Ada world, no first-life observation. It
does not cross the operator's stop boundary for real-Minecraft experiments
with Person-000.

## Consequences

### Positive

- Ada's initial System 2 is chosen by a protocol fixed before the evidence,
  on the architecture she will actually run.

### Negative

- A small sample: the decision is practical, not statistical; the tie rule
  says so.
- Up to 64 subscription calls in all.

## Alternatives considered

| Alternative                              | Why not                                               |
| ---------------------------------------- | ----------------------------------------------------- |
| One mixed benchmark                      | Habit or affect timing would confound backend quality |
| A weighted aggregate score               | False precision at this sample size                   |
| Retry until a valid answer               | Hides unreliability; spends quota                     |
| All of one backend, then the other       | Service conditions drift; order confounds             |
| Tune the instruction after early outputs | Optimizes for one provider against the held-out set   |

## Revisit conditions

- A provider, CLI or model change after selection: re-evaluate before Ada
  relies on it.
- Evidence that the selected backend degrades on lived (non-fixture) use.

## Relevant commits and docs

- ADRs 0020 to 0023; `docs/evidence/deliberation/2026-10-01-c2-sterility/`.
