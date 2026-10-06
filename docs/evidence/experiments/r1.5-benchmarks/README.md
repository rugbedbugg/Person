# R1.5: affect benchmark characterisation

Development runs of the R1.5 suite (ADR 0013), 2026-09-29. **TESTED IN
FIXTURE only.** Nothing here is Minecraft evidence, and nothing here bears on
whether Person feels anything (`docs/RESEARCH.md`). No affect rule or
parameter was changed in this phase. Three correctness bugs were found and
fixed, and the baseline below was measured after them.

## What was run

Four worlds, each built to present one decision geometry
(`fixtures/worlds/benchmarks/development/`), each with a plan in
`experiments/benchmarks/development/`:

| Class | World       | Built to present                                                       | Learner    |
| ----- | ----------- | ---------------------------------------------------------------------- | ---------- |
| A     | wide margin | one goal ahead by more than any affect swing                           | off        |
| B     | near tie    | the home project's storage milestone and the tools goal 10 to 20 apart | off        |
| C     | exploration | several food routines of different risk, the learner deciding          | supervised |
| D     | setback     | a hostile encounter at tick 4000, then a long calm                     | off        |

Every class ran P0 (affect off), P1 (record-only) and P2 (active) on seeds 1
to 5, at three horizons in Person's time: short (6000 ticks, about one
valence half-life), medium (24000, two control half-lives), long (72000, six).
That is 180 runs per pass. The held-out suite (`experiments/benchmarks/heldout/`)
was frozen by its manifest and **not run**.

Files: per class, `metrics.csv` (one row per run), `results.json` (plan,
bounds, comparisons, metadata and distributions; decision traces omitted) and
`summary.txt`. `pooled-final.txt` pools the final baseline;
`pooled-before-fixes-4af3751.txt` and `pooled-after-first-fix-be319f9.txt`
are the two earlier passes, kept as the evidence for the bugs below.

## Three bugs the suite exposed

| Commit    | Bug                                                                                                     | How it showed                                                           |
| --------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `5660eba` | The runtime killed cognition before it handled the episode's end: no `episode_ended`, no final snapshot | experienced time read 0; every earlier run, R1's included, was affected |
| `be319f9` | Blocking an already blocked goal recorded a new "blocked" event, appraised every idle cycle             | valence and control pinned at -1 for 53 to 94% of long runs             |
| `005148b` | An abandoned project's goal stayed a candidate and was pursued again                                    | 20 to 59 decisions per long run spent on commitments already given up   |

A fourth, `fb73391`, surfaced while fixing the first: a restore from a
snapshot at the journal's tail broke the evidence chain.

The second pass changed the story more than any affect rule could have. With
the abandoned goals lingering, affect had near ties to act on in worlds A and
C at medium and long horizons, and P2 diverged from P1 on 5 of 5 seeds there.
Those divergences were artefacts of the bug: once it was fixed, A and C
offered affect no opportunity and P2 matched P1 exactly. **An apparent affect
effect can be a defect elsewhere, and the negative control does not catch
that kind**; only reading the journals did.

## The ten questions

Figures are pooled over the five seeds of the final baseline (commit
`95fab0b`, clean tree). "Opportunity" means some affect state the current
architecture can reach would have made a different candidate win; "changed"
means the affect actually present did.

**1. How often does affect have a real opportunity?** Rarely, and only where
the world makes it. Priority-channel opportunities in P1: A 0%, C 0% and D 0%
of goal decisions at every horizon; B 32% (135 of 425) at the short horizon,
and no more after, since all of B's near ties come early. Over the long
horizon of all four classes, 135 of 1586 goal decisions (8.5%).

**2. How often does active affect use an opportunity?** When it has one,
nearly always: in B, P2 changed the choice at 45 of its 50 opportunities
(90%), and P2's decisions diverged from P1's on 5 of 5 seeds at every horizon.
Nowhere did a choice change without an opportunity (0 in every run, as it
must).

**3. Do the two channels differ?** Yes. The priority channel is the only one
that acted. The exploration channel had scored, multi-candidate routine
choices only in C (55 across its five long runs), where active tolerance
averaged about 1.16, yet found one opportunity in principle and changed
nothing.
Candidates that are parameter variants of one routine tie at every tolerance;
different routines differ by more than the tolerance range can move (about
0.04 to 0.1 in score); hunting, the riskier alternative, never became
plannable when a choice was made; and lowering tolerance never reverses an
order in which the safer routine already leads. Under the learner-off
classes the deterministic fallback decides, so the channel is closed by
construction.

**4. Is record-only behaviourally identical to off?** Yes: 0 of 5 seeds
diverged in each of the 12 class-horizon cells, in all three passes (36
cells, 180 paired runs).

**5. Does affect stay bounded and recover?** Bounded by construction, and
after the fixes it recovers. Final values over the long horizon are within
0.04 of baseline in every class. In D, valence after the setback stood at
-0.59 at the short horizon, -0.07 at the medium and 0.00 at the long; control
at -0.75, -0.27 and -0.02. Over the long horizon no dimension spent more than
8% of the time within 0.1 of a bound. Before the fixes, valence and control
ended every long run at -1.

**6. Where does saturation occur, and why?** The large effect was the
re-block bug above. What remains are properties of the ADR 0010 appraisal
table, for R2:

- repeated legitimate events accumulate faster than they decay: in B, goal
  completions and project progress pushed valence toward +1 early, near the
  bound for 75% of the short horizon (P1), before it settled;
- one world event is appraised once per goal it completes: placing a chest
  completed the survival storage goal and two project milestones, three
  appraisals of one act;
- a sustained threat is appraised once per observation, so its weight depends
  on how often Person observes (7 appraisals, 12 ticks apart, in D's encounter);
- the idle placeholder goal, unplannable by design, is appraised as blocked
  (once per blockage now, not once per cycle).

No appraisal was recorded twice. Records that look identical occur only when
a dimension already sits at a bound, where a clamped change leaves the prior
state unchanged; the metric is named for that
(`affect_identical_appraisal_records`).

**7. Is there a world where affect predictably matters without being forced?**
B. Its base priorities sit 10 to 20 apart, inside the architecture's swing
(37.5 to lift an outgoing goal over a protective one, 50 the other way), and
active affect changed the outcome on every seed. Nothing in B was tuned for
affect: the gap comes from the ordinary goal priorities.

**8. Do the wide-margin controls stay invariant?** Yes: in A, 0 opportunities
and 0 divergences at every horizon. (Before the project fix they diverged,
for the reason under "Three bugs".)

**9. Are development and held-out separated?** Yes, and enforced:
separate directories, disjoint seeds (1 to 5 against 101 to 105), held-out
worlds that differ in layout, facing, initial state and adversity, a manifest
of SHA-256 hashes checked by `tests/cli/benchmarks.test.ts`, and a harness
that refuses a held-out plan without `--heldout`. The held-out set has never
been run.

**10. Can every run be reproduced exactly?** Yes. Runs are deterministic:
the same cell twice, and a plan run serially against four at once, give
identical metrics and traces (`tests/cli/experiment.test.ts`). Every run
records its commit, whether the tree was clean, the plan, configuration and
world with their hashes, its seed, horizon and condition.

## Limits worth keeping in view

- **Seeds are weaker than they look.** In B and D all five seeds produced the
  same run; the seed only lays out resource clusters, and in those worlds the
  layout changed nothing Person did. A and C varied with the seed. B's and
  D's results are single trajectories, repeated.
- One world per class; one learner setting per class.
- Hunger, harm and recovery are measured from per-decision deltas, not
  continuous sampling.
- The exploration channel was only opened in C.

## For R2

Any change to appraisal should be judged first against this baseline on the
development suite, and then once on the held-out suite. The findings under
question 6 are what R2 can address; the harness and the benchmark definitions
should not change in the same step.
