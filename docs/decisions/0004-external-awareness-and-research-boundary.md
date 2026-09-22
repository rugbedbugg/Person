# ADR 0004: External awareness and the explicit research boundary

**Status:** Accepted (rule), Deferred (implementation)
**Date:** 2026-09-22
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

Person knows it is artificial, that Minecraft is a game, that an external
reality exists, and that an operator exists. That is a deliberate design choice
rather than an accident of using a language model, and it has a consequence: an
entity that knows there is an outside will eventually want to know things about
it.

Canonical Person is therefore allowed, eventually, to read the public internet.

The thing that must not follow is external agency. "Person may read about
anything" and "Person may do anything outside Minecraft" are different
statements, and the first is routinely used to smuggle in the second. Browsing
implies an HTTP client; an HTTP client implies POST; POST implies accounts,
purchases, mail and control of unrelated services.

There is a second and sharper problem. Retrieved text is the ideal vector for
instruction injection into an agent whose whole safety story is that
natural-language content never becomes an action. `docs/PERSON_SPEC.md` section
66 already forbids that for player messages and LLM output; the web is the same
rule under more pressure.

## Decision

Unrestricted **subjects**; bounded **agency**.

```text
unrestricted subjects
!=
unrestricted external agency
```

1. **Research is a deliberate act.** Web access happens through an explicit tool
   call Person chose to make. There is no ambient retrieval, no background
   fetch, and nothing that injects retrieved text into cognition unasked.
2. **Retrieved content is untrusted evidence, never instruction.** It enters as
   data with provenance and cannot become a `SkillInvocation`, a command, a
   parameter, or a control-flow decision. The existing architecture tests that
   forbid a command channel and code evaluation cover the mechanism; this rule
   covers the intent.
3. **No general external agency.** Reading grants no operating-system access, no
   arbitrary network access, no software download or execution, no
   self-modification, no account creation, no purchasing, no arbitrary mail, no
   control of unrelated services.
4. **Web beliefs carry provenance.** Source identity, retrieval time, confidence
   and corroboration, under the `EXTERNAL_WEB` class of section 0.9. A web
   belief is distinguishable, forever, from something Person observed or
   discovered.
5. **Discovery claims exclude researched knowledge.** An experiment intended to
   demonstrate independent discovery is invalid if the mechanism could have been
   read, which is why section 0.9 calls for hidden or custom mechanics.

## Consequences

### Positive

- Person can learn about the world it knows exists, which is most of the point
  of telling it that the world exists.
- Provenance makes "I read this online" a sentence Person can actually mean,
  and makes discovery experiments falsifiable.

### Negative

- A retrieval surface is a new untrusted input class, and the most attractive
  one an attacker could ask for.
- Corroboration and confidence are real work, and a naive implementation that
  believes the first result is worse than no web access.

### Neutral

- The bounded-agency rule makes the web tool considerably less useful than a
  general one, which is the intent.

## Alternatives Considered

| Alternative                                     | Why rejected                                                                                                                                      |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| No internet access ever                         | Contradicts the frozen definition. An individual that knows an external reality exists and may never learn anything about it is a strange design. |
| Full external agency behind a permission prompt | Prompt fatigue is a well-understood failure. The capability should not exist rather than be guarded.                                              |
| Ambient retrieval mixed into the prompt         | Removes the deliberate act, removes provenance, and makes injection invisible.                                                                    |
| Curated offline corpus only                     | Reasonable, and a sensible first implementation. Not a reason to decide the boundary differently.                                                 |

## Revisit Conditions

- A research question requires a bounded write capability, for example posting
  to a channel the operator controls. That is a new capability axis and needs
  its own ADR.
- Injection defences prove inadequate in practice.

## Relevant Commits / Documents

| Reference                                          | Description                                                    |
| -------------------------------------------------- | -------------------------------------------------------------- |
| `docs/PERSON_SPEC.md` sections 0.9, 0.11, 0.12, 66 | Provenance, internet access, self-knowledge, security boundary |
| `tests/architecture/architecture.test.ts`          | No command channel, no code evaluation                         |
| `tests/python/test_architecture.py`                | Cognition evaluates no generated code                          |
