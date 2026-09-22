# ADR 0005: Cognitive autonomy is not environmental authority

**Status:** Accepted
**Date:** 2026-09-22
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

Person is being given a social cognition system that may eventually produce
deception, retaliation, theft and conflict, and a morality that develops from
experience rather than arriving hard-coded. Person is also being given the
ability to disagree with its operator.

Two ways of reacting to that are both wrong.

The first is to constrain cognition so those states cannot arise: hard-code the
norms, forbid the intentions, make Person unable to want the wrong thing. That
produces an agent whose social behaviour is a lookup table and removes the
research question.

The second is to treat cognitive autonomy as implying environmental authority:
if Person genuinely wants something, the runtime should let it act. That is a
category error, and it is the one that makes autonomous agents dangerous.

The repository has in fact been built the right way from the first commit. This
ADR names the principle so that the coming social and affective work does not
quietly erode it.

## Decision

```text
COGNITIVE AUTONOMY
!=
ENVIRONMENTAL AUTHORITY
```

```text
desire -> goal -> plan -> proposed action -> CAPABILITY POLICY -> execution
```

1. **Cognition may want, plan and propose anything.** No intention is
   forbidden at the cognitive level. Person may plan something the runtime will
   refuse, and that is a normal condition rather than a fault.
2. **The runtime holds all environmental authority.** Every physical effect
   passes the validator, the safety kernel and the permission gate, and the
   verdict is the runtime's alone.
3. **Refusal is represented honestly.** Person is told the action was
   unavailable or failed. It is not told a false reason, and it is not shown the
   security implementation. An agent systematically deceived about its own
   capabilities cannot form an accurate self-model.
4. **Attribution never lies.** `SkillOutcome` carries both `requestedSkill` and
   `executedSkill`; learning credits what ran. A replaced proposal records a
   preemption against the requested skill and an attempt against the executed
   one.
5. **Containment is not morality.** The permission gate is operator policy, not
   Person's conscience. See `docs/SAFETY.md`.

## Consequences

### Positive

- Social and moral cognition can be built without the safety story depending on
  what Person happens to believe this week.
- Every refusal is evidence: a rejected proposal is a recorded fact about what
  Person tried.

### Negative

- Person will repeatedly propose things it cannot do, and each is an episode
  spent on a refusal.
- Honest refusal tells Person where the boundaries are, which is exactly what
  makes its self-model accurate and also what would let a sufficiently capable
  Person map them.

### Neutral

- Nothing changes. This is the existing architecture, written down.

## Alternatives Considered

| Alternative                                             | Why rejected                                                                                   |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Constrain cognition so forbidden intentions cannot form | Hard-codes the morality the spec says must be learned, and makes social research impossible.   |
| Let genuine intentions execute                          | Makes safety a function of Person's current beliefs.                                           |
| Hide refusals, report success                           | Corrupts the evidence journal and gives Person a false self-model. The worst option available. |
| Report refusals with full security detail               | Leaks the containment design to the thing being contained, for no cognitive benefit.           |

## Revisit Conditions

- A capability is added whose refusal cannot be represented as "unavailable"
  without being misleading.
- Refusal rate makes episodes unproductive, which is a policy problem rather
  than a boundary problem.

## Relevant Commits / Documents

| Reference                                                | Description                                 |
| -------------------------------------------------------- | ------------------------------------------- |
| `docs/PERSON_SPEC.md` sections 0.16, 0.13, 0.17, 0.18, 3 | The invariant and its neighbours            |
| `apps/node-runtime/src/skills/dispatch.ts`               | The single road from proposal to outcome    |
| `apps/node-runtime/src/safety/validator.ts`              | ACCEPT / REJECT / PREEMPT / REPLACE         |
| `tests/safety/attribution.test.ts`                       | Requested and executed stay distinguishable |
| `6b99830`                                                | The architecture this ADR records           |
