# Held-out D: INVALID, not interpretable for R2

The R2 held-out run of world D (`experiments/r2/heldout/d-setback.json`,
commit `e26fc0a`, 2026-09-29) entered a runtime livelock that has nothing to
do with affect. **D is INVALID and NOT INTERPRETABLE FOR R2.** It is kept
here permanently and is not replaced by a rerun in the R2 report.

## The first divergence into livelock

Reproduced under P0 (affect off), seed 101, medium horizon:

| Tick | Decision   | What happened                                                                                                                                                                                           |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 5660 | 30         | Nothing urgent: the idle placeholder goal, `wait_safely` accepted (validator L1)                                                                                                                        |
| 6000 | 30         | The world spawns a skeleton 6 blocks from Person, out of its view; `wait_safely` is interrupted after 340 ticks, `threat_appeared`. Legitimate.                                                         |
| 6000 | 31         | Idle again, `wait_safely` accepted (L1, no kernel preemption: the kernel rates the unseen skeleton `nearby`, not `immediate`), interrupted by the skill's own `threat_appeared` check after **0 ticks** |
| 6000 | 32 to 5000 | The same cycle. The fixture's clock advances only while skills run, so it never moves again; the skeleton never approaches or shoots; Person, who cannot perceive it, has no reason to do anything else |

The completed medium and long runs each spent 4969 of their 5000 decisions at
tick 6000 and ended at the decision cap. The short-horizon runs ended at their
tick bound just before the cycle began. No safety override was issued in any
of them.

Two further defects surfaced here: each livelocked run wrote about 1400
snapshots of 3.2 MB, because snapshots are never pruned (25 GB for the world
in all); and the loop produced no error, only an ever-growing journal.

## Abort

Once the failure was reproduced under P0, the runs still in progress were
stopped at 21:39:54 +05:30 on 2026-09-29, by the operator's decision, rather
than spending compute on degenerate 5000-decision loops. No `results.json`
was written for D.

## Runs

| Condition | Horizon | Seed | State                     | Decisions    | Experienced ticks | Most at one tick                |
| --------- | ------- | ---- | ------------------------- | ------------ | ----------------- | ------------------------------- |
| P0        | short   | 101  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| P0        | short   | 102  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| P0        | short   | 103  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| P0        | short   | 104  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| P0        | short   | 105  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| P0        | medium  | 101  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | medium  | 102  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | medium  | 103  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | medium  | 104  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | medium  | 105  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | long    | 101  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | long    | 102  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | long    | 103  | completed                 | 5000         | 6000              | 4969 at tick 6000               |
| P0        | long    | 104  | aborted (partial journal) | 4890 started |                   | 34238 events, last at tick 6000 |
| P0        | long    | 105  | aborted (partial journal) | 4803 started |                   | 33629 events, last at tick 6000 |
| A15       | short   | 101  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| A15       | short   | 102  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| A15       | short   | 103  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| A15       | short   | 104  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| A15       | short   | 105  | completed                 | 31           | 5660              | 3 at tick 1460                  |
| A15       | medium  | 101  | aborted (partial journal) | 4706 started |                   | 32974 events, last at tick 6000 |
| A15       | medium  | 102  | aborted (partial journal) | 4684 started |                   | 32820 events, last at tick 6000 |
| A15       | medium  | 103  | not started               |              |                   |                                 |
| A15       | medium  | 104  | not started               |              |                   |                                 |
| A15       | medium  | 105  | not started               |              |                   |                                 |
| A15       | long    | 101  | not started               |              |                   |                                 |
| A15       | long    | 102  | not started               |              |                   |                                 |
| A15       | long    | 103  | not started               |              |                   |                                 |
| A15       | long    | 104  | not started               |              |                   |                                 |
| A15       | long    | 105  | not started               |              |                   |                                 |
| R2rec     | short   | 101  | not started               |              |                   |                                 |
| R2rec     | short   | 102  | not started               |              |                   |                                 |
| R2rec     | short   | 103  | not started               |              |                   |                                 |
| R2rec     | short   | 104  | not started               |              |                   |                                 |
| R2rec     | short   | 105  | not started               |              |                   |                                 |
| R2rec     | medium  | 101  | not started               |              |                   |                                 |
| R2rec     | medium  | 102  | not started               |              |                   |                                 |
| R2rec     | medium  | 103  | not started               |              |                   |                                 |
| R2rec     | medium  | 104  | not started               |              |                   |                                 |
| R2rec     | medium  | 105  | not started               |              |                   |                                 |
| R2rec     | long    | 101  | not started               |              |                   |                                 |
| R2rec     | long    | 102  | not started               |              |                   |                                 |
| R2rec     | long    | 103  | not started               |              |                   |                                 |
| R2rec     | long    | 104  | not started               |              |                   |                                 |
| R2rec     | long    | 105  | not started               |              |                   |                                 |
| R2act     | short   | 101  | not started               |              |                   |                                 |
| R2act     | short   | 102  | not started               |              |                   |                                 |
| R2act     | short   | 103  | not started               |              |                   |                                 |
| R2act     | short   | 104  | not started               |              |                   |                                 |
| R2act     | short   | 105  | not started               |              |                   |                                 |
| R2act     | medium  | 101  | not started               |              |                   |                                 |
| R2act     | medium  | 102  | not started               |              |                   |                                 |
| R2act     | medium  | 103  | not started               |              |                   |                                 |
| R2act     | medium  | 104  | not started               |              |                   |                                 |
| R2act     | medium  | 105  | not started               |              |                   |                                 |
| R2act     | long    | 101  | not started               |              |                   |                                 |
| R2act     | long    | 102  | not started               |              |                   |                                 |
| R2act     | long    | 103  | not started               |              |                   |                                 |
| R2act     | long    | 104  | not started               |              |                   |                                 |
| R2act     | long    | 105  | not started               |              |                   |                                 |

## Files

`r2-heldout-d-setback-journals.tar.gz` holds every run directory of the
attempt (journals, reports, configurations, worlds, run records) without the
cognition snapshots, which are derivable from the journals and totalled 25 GB.
SHA-256 `eb1b7d87fdef2f5959ace3d732d89d92e0a49dddde9c7dbb7a71cf3f3e46c79e`.
The snapshots were deleted from `runs/` on 2026-09-29 to reclaim disk; the
evidence store replays the journal when no snapshot exists, so none of the
evidence depended on them.

## Replacement

Held-out D2 (`experiments/benchmarks/heldout-d2/`) replaces this world as the
held-out class D world. It was generated by a procedure and seed committed
before generation, and frozen before any run. This world is kept as it is and
is never re-used as evidence; its rerun after ADR 0015 is a regression check
only.
