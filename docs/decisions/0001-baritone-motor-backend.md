# ADR 0001: Baritone as the planned primary motor backend

**Status:** Accepted (direction), Deferred (implementation)
**Date:** 2026-09-22
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder

---

## Context

Mineflayer 4.39.0 with `mineflayer-pathfinder` 2.4.5 is the current embodiment.
It is the only implementation of the `Embodiment` port that talks to a real
server, and it works: two live observations and two live skill validations have
been performed through it.

`REALITY_VALIDATION.md` names pathfinding on real terrain as "the single most
likely source of skill failures", and that judgement was made before any skill
had run live. `mineflayer-pathfinder` is a reimplementation of movement in
JavaScript against a partial client. Baritone is a mature Minecraft movement and
world-interaction engine that runs inside a real client and has years of
adversarial use behind it.

The architectural risk is not technical. It is that a motor layer which knows
the exact geometry of every loaded chunk is one refactor away from becoming
Person's perception. `docs/PERSON_SPEC.md` section 8 forbids that, and ADR
0002 is the rule; this ADR is where the temptation actually arrives.

## Decision

Baritone will be evaluated as the planned primary Minecraft motor layer, behind
the existing trust boundary and behind the perception firewall.

```text
Person cognition
    -> trusted runtime / capability boundary
    -> BaritoneEmbodiment                       (implements the existing port)
    -> local IPC / bridge
    -> Java/Fabric or equivalent client integration
    -> Baritone public API
    -> Minecraft
```

Binding rules:

1. **Baritone is motor cortex, not cognition.** Person decides what and why; the
   motor layer decides how. Baritone selects routes, not goals.
2. **Baritone implements the existing `Embodiment` port.** It is a third body
   beside `MineflayerEmbodiment` and `FixtureWorld`, not a new architecture.
   Skills are not rewritten for it.
3. **No Baritone command strings reach cognition**, and none are constructed
   from anything cognition sent. The port's typed methods are the whole surface.
4. **Baritone's world knowledge stays behind the perception firewall.** Whatever
   geometry it holds internally, the observation Person receives is produced by
   `apps/node-runtime/src/observation/`, subject to ADR 0002.
5. **The physical guard must survive the transition.** Protected-area
   enforcement currently works because the runtime installs a step-exclusion
   function that the path search consults on every node. A Baritone backend that
   cannot be given an equivalent per-step veto is not acceptable, and
   establishing that it can is the first question the spike answers.
6. **Mineflayer is not removed.** It stays as the reference body until Baritone
   has passed the same validation ladder, and `FixtureWorld` stays permanently.

The canonical development target will likely move from Minecraft Java 1.16.1 to
1.16.5 as part of this work, because that is the nearest sensible compatibility
target. **That migration has not happened.** Until it does, 1.16.1 is the truth
and `docs/CURRENT_STATE.md` says so.

## Consequences

### Positive

- Route quality and terrain handling stop being Person's problem.
- A second real body proves the `Embodiment` port is an abstraction rather than
  a Mineflayer alias, which is the same thing `FixtureWorld` proves in the
  deterministic direction and has never been tested against a second real one.
- The perception firewall acquires a reason to exist that is concrete rather
  than anticipatory.

### Negative

- A JVM, a mod loader and a real Minecraft client enter the runtime. The
  process topology gains a bridge and a failure mode neither existing body has.
- Baritone's API is not a stable public contract in the way `minecraft-data` is.
- The conformance-double strategy that made the Mineflayer adapter testable
  without a server does not obviously transfer.

### Neutral

- Two bodies with real servers means two validation ladders. Live evidence for
  one says nothing about the other, and the training-context key already keeps
  such evidence apart.

## Alternatives Considered

| Alternative                                                    | Why rejected                                                                                                                                                 |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Keep `mineflayer-pathfinder` and improve it                    | The failure modes are in route quality on real terrain, which is exactly the part a reimplementation is worst at. Effort spent here does not transfer.       |
| Expose Baritone goals directly to cognition                    | This is the failure this ADR exists to prevent. A Baritone goal string is an arbitrary command channel, and the trust boundary rests on there not being one. |
| Replace the `Embodiment` port with a Baritone-shaped interface | Rewrites 21 working skills and discards the fixture body, to serve a backend that has not been evaluated.                                                    |
| Do nothing until a skill actually fails live                   | Defensible, and it is what happens if the spike finds a blocker. The decision recorded here is the direction, not a commitment to build.                     |

## Revisit Conditions

- The spike finds that Baritone cannot be given a per-step movement veto.
- Live validation through Mineflayer completes the gathering, crafting, mining,
  placement, container and hunting stages without pathfinding being the
  dominant failure cause.
- The bridge's latency makes tick budgets meaningless.

## Relevant Commits / Documents

| Reference                                       | Description                       |
| ----------------------------------------------- | --------------------------------- |
| `docs/PERSON_SPEC.md` section 6.1               | Embodiment direction              |
| `docs/CURRENT_STATE.md`, "Known Deviations", C5 | The port is Mineflayer-shaped     |
| `apps/node-runtime/src/embodiment/types.ts`     | The port Baritone would implement |
| `REALITY_VALIDATION.md`, remaining blockers     | Pathfinder on real terrain        |
| ADR 0002                                        | Perception firewall               |

## Implementation Notes

The smallest safe spike, in order, stopping at the first refusal:

1. Stand a Baritone-capable client up beside the existing world and confirm it
   accepts a per-step exclusion predicate at all. **Stop here if it does not.**
2. Implement `BaritoneEmbodiment` covering `connect`, `disconnect`, `snapshot`,
   `moveTo`, `setGuard` and nothing else.
3. Run `person skill-test --skill return_home` through it. `return_home` is the
   only skill that is pure navigation, it is already live-validated through
   Mineflayer, and the comparison is therefore meaningful.
4. Compare the two reports.

Explicitly untouched during that spike: the protocol schemas, the skill specs,
the skill implementations, the safety kernel, the permission gate, the
observation builder, the cognition process, the evidence format, and
`MineflayerEmbodiment` itself.
