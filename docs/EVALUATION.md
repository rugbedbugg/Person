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
safety overrides with trigger, level, action and preempted skill
storage provenance records
goal history: queued, suspended, resumed, completed, blocked
routine and skill statistics with posterior means
```

The fallback rate is the learning metric worth watching: high early, lower
later, while safety overrides and critical safety violations stay where they
are.

## What is not measured yet

Prediction error, causal belief accuracy, transfer between environments,
memory retention and consolidation precision are all future scope. The evidence
format is designed so they can be computed later from episodes recorded now:
expected effects are stored next to observed effects, the executed action is
distinguishable from the requested one, every event carries world, session,
episode and training context, and fixture episodes record their RNG seed.

That is a claim about the data, not about the capability. Nothing in this
milestone learns a world model, and the reports do not contain a prediction
error column because nothing yet produces one.

## Held-out evaluation

`fixtures/worlds/` currently holds the acceptance world and a safety probe
world. Held-out evaluation worlds, with their own evidence stores, belong to
the next milestone; keeping training and evaluation evidence separate is
already supported by the training-context key on every statistic.
