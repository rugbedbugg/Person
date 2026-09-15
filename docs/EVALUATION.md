# Evaluation

## What the automated suite proves

Run `mise run check`, or the individual commands in the README.

| Area           | Where                                                                               | What it establishes                                                        |
| -------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Protocol       | `packages/protocol/ts/protocol.test.ts`, `packages/protocol/tests/test_protocol.py` | One contract, two runtimes, identical verdicts on a shared corpus          |
| Skills         | `tests/skills/`                                                                     | Real effects, real evidence, real failure modes against the fixture body   |
| Safety         | `tests/safety/`                                                                     | Protected areas, permissions, kernel verdicts, limit clamping, attribution |
| Architecture   | `tests/architecture/`, `tests/python/test_architecture.py`                          | The boundary itself, as executable rules                                   |
| Planning       | `packages/planner/tests/`                                                           | Feasible, minimal, deterministic plans for every survival goal             |
| Policy         | `packages/policy/tests/`                                                            | Uncertainty, risk preference, mode behaviour, envelope suppression         |
| Persistence    | `packages/persistence/tests/`                                                       | Duplicates, corruption, truncation, snapshots, rebuild                     |
| Cognition      | `apps/cognition/tests/`                                                             | Context bucketing, goal stack, loop behaviour, restart reuse               |
| CLI            | `tests/cli/`                                                                        | Argument parsing, validation, migration, inspection                        |
| Vertical slice | `tests/integration/`                                                                | The whole loop, across two processes, twice, with a restart in between     |

## Operational metrics in the reports

Each episode produces `runs/reports/episode-<id>.json` from the runtime and
`runs/evidence/reports/learning-<id>.json` from cognition. Between them:

```
decisions, accepted, replaced, rejected
learned vs fallback decisions, and the fallback rate
successes, failures, emergencies
health lost, resource deltas, elapsed ticks
per-skill tick budgets: runs, mean and max elapsed, budget pressure,
  and the split between navigation and interaction
safety overrides with trigger, level, action and preempted skill
storage provenance records
goal history: queued, suspended, resumed, completed, blocked
routine and skill statistics with posterior means
prediction error: counts by severity, and the worst misses
```

The fallback rate is the learning metric worth watching: high early, lower
later, while safety overrides and critical safety violations stay where they
are.

## Prediction error

Measured since Milestone 1, and deliberately inert: every skill contract's
declared effects are compared with the symbolic state the next observation
reports, and the result is recorded as evidence and summarised in both reports.
It changes no decision. A test replays a journal with and without the records
and asserts the policy statistics are identical.

Severity distinguishes a contract that is wrong from a skill that failed. A
successful skill can still have been wrong about what it would achieve, and
that is the interesting case: it is how `eat_to_target` was found to be
claiming it consumed a single item.

## What is not measured yet

Causal belief accuracy, transfer between environments, memory retention and
consolidation precision are all future scope. The evidence
format is designed so they can be computed later from episodes recorded now:
expected effects are stored next to observed effects, the executed action is
distinguishable from the requested one, every event carries world, session,
episode and training context, and fixture episodes record their RNG seed.

That is a claim about the data, not about the capability. Nothing here learns a
world model. Prediction error is now recorded, which is the input such a model
would need, and no model consumes it.

Nothing in this suite has been run against a Minecraft server. See
`REALITY_VALIDATION.md`.

## Held-out evaluation

`fixtures/worlds/` currently holds the acceptance world and a safety probe
world. Held-out evaluation worlds, with their own evidence stores, belong to
the next milestone; keeping training and evaluation evidence separate is
already supported by the training-context key on every statistic.
