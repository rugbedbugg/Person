# ADR 0015: One contact range and bounded simulated progress under runtime control

**Status:** Accepted (2026-09-30)
**Date:** 2026-09-30
**Authors:** @rugbedbugg
**Reviewers:** @rugbedbugg, @upayanmazumder
**Operator decision:** fix the zero-time livelock found in the R2 held-out D
run on a separate correctness branch, without leaking the hidden hostile into
cognition, choosing the semantics consistent with the safety ADRs
(2026-09-29); architecture accepted, and renamed from "simulated time that
always moves", which claimed more than the decision (2026-09-30)

---

## Context

The R2 held-out D run (`docs/evidence/experiments/r2-interoception/heldout/d-setback-INVALID/`)
froze at tick 6000. A skeleton spawned about 7.5 blocks from Person, out of
its view. From then on:

- the kernel rated it `nearby`, because its contact range
  (`immediateThreatDistance`) is 7, and `nearby` never preempts;
- `wait_safely` refused to wait, because it carried its own privileged check
  for any threat within **8** blocks;
- the refusal took 0 ticks, and the fixture clock advances only inside
  actions, so the skeleton never moved;
- Person, who could not see it, had no reason to do anything but wait, and
  proposed the same wait 4969 times.

`look_around` carried the same second threshold. In the band between 7 and 8
blocks, the skill refused, the kernel did not take over, and nothing else
happened. It is a safety rule outside the kernel that neither acts nor informs.

ADR 0005 gives environmental authority to the runtime and says refusals are
honest. `docs/SAFETY.md` puts contact-range threats at L1, in the kernel. ADR
0002 says the perception firewall is not a safety boundary, so the fix must
not work by changing what Person perceives.

Zero-tick outcomes that did not succeed, across every journal on the
machine:

| Where           | INTERRUPTED | FAILED                                              | UNREACHABLE                    |
| --------------- | ----------- | --------------------------------------------------- | ------------------------------ |
| held-out D      | 58,711      | 66                                                  | 0                              |
| everywhere else | 0           | 1,104 (`deposit_owned_storage`, nothing to deposit) | 253 (`no_route`, three skills) |

The longest streak of identical zero-time failures outside D was 3. A first
count that looked only at completion and interruption events missed the
failures; a 1-tick floor for every zero-tick non-success was implemented on
that count and broke the R1.5 reference replays for B and C, which is how the
error was found.

## Decision

1. **Contact range has one definition, the kernel's.** `wait_safely` and
   `look_around` stop for a hostile only when the kernel rates the moment
   `immediate`. There is no skill-local margin.
   - `look_around` is an ordinary skill, so the kernel preempts it, as before.
   - `wait_safely` is an emergency skill. The kernel does not preempt an
     emergency skill mid-flight, so the skill stops itself, reporting
     `threat_appeared`, and the validator replaces Person's next proposal with
     `flee`. That is one honest handoff, not a loop.
2. **Runtime control cannot stop simulated time.** When an executed skill
   ends in anything but `SUCCESS` after 0 ticks, and either it was
   `INTERRUPTED` or the runtime was in control of it (`runtimeTookControl`:
   the validator replaced the proposal, or the kernel preempted it), dispatch
   calls the optional embodiment hook `passTick()`, and the fixture advances by
   exactly one tick. Both can come from knowledge Person does not have.
   Runtime control is defined by provenance, not by `SkillOutcome.emergency`,
   which is also true when Person itself proposed what an emergency called
   for.
   - It runs after the outcome is built, so nothing in the tick is attributed
     to the attempt.
   - One tick is a guarantee of progress, not a model of reaction time: there
     is no measurement to set a longer one from.
   - The Minecraft body does not implement the hook; a server's clock runs on
     its own.
   - Person's own zero-tick failures, and all successes, are untouched. No
     recorded run had a zero-tick non-success under runtime control, so no
     existing run changes, and the R1.5 references replay exactly.
3. **A stalled episode ends as a fault.** The runtime ends an episode with
   `runtime_livelock` after `STALL_LIMIT` (16) consecutive decisions that took
   no time, did not succeed, and were identical: same tick, goal, requested
   and executed skill, verdict and statuses. This covers the zero-tick
   `FAILED` and `UNREACHABLE` outcomes without changing their meaning. It
   changes nothing Person does before the limit.
4. **Nothing new reaches cognition.** An outcome beside an unseen hostile says
   exactly what it said before. No field names the hostile.

## The regression rerun

The original held-out D was rerun with the real learner as a regression check
(P0 and R2act, seed 101, medium horizon; output under `runs/`, not evidence).
With the interruption-only floor it found a second loop: from tick 6020 the
kernel replaced every proposal with `flee`, and `flee` failed after 0 ticks
with `no_safe_route`, most likely from inside the shelter. The stall detector
ended the episode as `runtime_livelock` after 16 identical decisions. That is
why the floor covers runtime control as well as interruptions.

With the floor as decided, both runs reach the end of the horizon (72
decisions, tick 24108, `tick_budget_reached`). At most 3 decisions share a
tick, as in the old runs. `flee` fails 10 times while the skeleton is near, and
Person loses 12 health, because the fixture skeleton shoots through walls.

## Consequences

### Positive

- The held-out D world no longer freezes: an unseen hostile either stays
  outside contact range and Person waits, or closes in and the kernel takes
  over.
- One place to change what counts as contact range.

### Negative

- Person may now keep waiting with a skeleton 8 to 12 blocks away, which is
  within its fixture reach of 12. Damage then reaches Person as ordinary
  bodily evidence, and the kernel acts on health. If that proves unsafe, the
  fix is to revise the kernel's threat model, not to reintroduce a skill-local
  one.
- A zero-time failure repeated fewer than 16 times, or a rejected proposal,
  still does not move the fixture's clock. The detector counts rejections too,
  since they take no time and do not succeed.
- A zero-time **success** repeated at one tick is not guarded: scripted
  cognition asking for `return_home` while home does so. The real learner has
  not been seen to.
- Whether every non-success should cost simulated time is deferred: it would
  change existing fixture trajectories.
- The kernel orders `flee` without knowing whether fleeing is possible, for
  example from inside a sealed shelter, and the fixture skeleton's ranged
  attack ignores walls. Whether the kernel should stand fast in a shelter, and
  how the fixture models line of fire, are separate decisions.

## Alternatives considered

| Alternative                                                                             | Why not                                                                                    |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Keep the 8-block margin and return a generic outcome that blocks identical resubmission | Keeps a second safety definition outside the kernel, and adds a rule that shapes cognition |
| A 20-tick floor, one `wait_safely` step                                                 | No basis for the value, and it would move a fixture hostile three blocks per failed act    |
| Advance the fixture on every decision                                                   | Changes every existing run and the frozen R1.5 references                                  |
| A 1-tick floor for every zero-tick non-success                                          | Shifts existing B and C runs and breaks the R1.5 reference replays                         |

## Verification

`tests/safety/zero-time-interruption.test.ts`:

- boundaries at 7, 8 and 16 blocks for both skills;
- a seen and an unseen hostile give the same outcome;
- nothing about an unseen hostile appears in an outcome;
- the floor applies to zero-tick interruptions, to a kernel replacement that
  fails at 0 ticks, and to a preemption whose emergency skill does not
  succeed at 0 ticks; not to Person's own zero-tick failures, successes or
  timed attempts;
- runtime control means replacement or preemption, not an emergency-type
  skill, nor Person proposing what the emergency called for;
- the stall detector fires on the 16th identical zero-time failure, resets on
  any difference, and ends a scripted `deposit_owned_storage` loop;
- an idle wait beside an unseen hostile never repeats at one tick, and the
  kernel still takes over;
- the original held-out D world passes its skeleton. This is a regression run
  only; held-out D stays INVALID for R2.

Each part of the fix was reverted on its own and a test failed each time.
