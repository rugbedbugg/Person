# Raw journal archives

The raw journals behind the committed experiment results are stored as GitHub
release assets, not in Git history. The releases are evidence archives, not
Person releases: their tags start `evidence-`, and they are marked as
prereleases so none is ever the latest release.

Release `evidence-raw-journals-2026-09-30`:
https://github.com/rugbedbugg/Person/releases/tag/evidence-raw-journals-2026-09-30

| Asset                                          | Bytes      | SHA-256                                                            | Originating commit | Runs | Events  | Supports                                                                             | Status                                    | `MANIFEST.json` SHA-256                                            |
| ---------------------------------------------- | ---------- | ------------------------------------------------------------------ | ------------------ | ---- | ------- | ------------------------------------------------------------------------------------ | ----------------------------------------- | ------------------------------------------------------------------ |
| `r1-affect-modes-journals.tar.gz`              | 1,425,276  | `964119297f67dda3a27c49cb94bd1efb731096998bb71fc48d2bc85f834da714` | `aaac2bd`          | 30   | 14,366  | R1 affect-mode matrix, `r1-affect-modes/`                                            | historical                                | `2000e82b470cd23dd4e12c6073fc35c76fafab8040234f2be9fab2009e6ec7ff` |
| `r1-affect-modes-supervised-journals.tar.gz`   | 1,494,090  | `c6644c31f93bd1c8d8803e47cb32e3ed6f4b8806713c89ffba1ea5d9677a801b` | `cc5f408`          | 30   | 15,044  | R1 supervised matrix, `r1-affect-modes-supervised/`                                  | historical                                | `e7fc1dc79a81e3ced8366d3893d243c60000f6a6b7838336ede2a6cd3744e150` |
| `r1.5-after-first-fix-be319f9-journals.tar.gz` | 14,269,584 | `fca8849d895793605b69b3c2841b4f448b473761c6b7c56cd2c1a537f4962298` | `be319f9`          | 180  | 164,815 | R1.5 after the first fix, `r1.5-benchmarks/pooled-after-first-fix-be319f9.txt`       | superseded                                | `94c55d8244ed155e0821a619c7a4a0702bd1650da76461b25153d283021743d2` |
| `r1.5-before-fixes-4af3751-journals.tar.gz`    | 14,658,607 | `186f5046b2a94de8553723dbc30326651af8993c263021f9367ce5c5b466c1ff` | `4af3751`          | 180  | 170,493 | R1.5 before its correctness fixes, `r1.5-benchmarks/pooled-before-fixes-4af3751.txt` | superseded                                | `55c5a42b3796dc0fd46678fd95cbc0552e8530187bb5b73b633e60c9838694de` |
| `r1.5-benchmarks-journals.tar.gz`              | 13,428,158 | `30699cb99c096f887b93080e8eb4e2addbd5bc69ae9628d1e1eb9889d857fd39` | `95fab0b`          | 180  | 155,755 | R1.5 benchmark results, `r1.5-benchmarks/`                                           | historical                                | `894ee652ecb08340fefb9faffc1c8dc20f3f53de657ae4d0cdb9913487c9a6a6` |
| `r2-development-journals.tar.gz`               | 18,999,224 | `dbba166e4ce7976a7e73a03dd77a507dcf734a7ca2f13f7f5a247ff6d74a7281` | `2573e03`          | 240  | 213,816 | R2 development results, `r2-interoception/development/`                              | historical (phantom `SECURE_FOOD` defect) | `94a0a64daad69b535c67aa9e4c569fa7ee1ff76fc505f6dbd460043512eda2e8` |
| `r2-heldout-a-c-journals.tar.gz`               | 12,137,434 | `cf187ceadc7829dcf688a06b3978925ccf1b42cc5cc5f7294b38a55cade968b9` | `e26fc0a`          | 180  | 133,296 | R2 held-out A to C results, `r2-interoception/heldout/`                              | historical (phantom `SECURE_FOOD` defect) | `1e189f02393ad1ce286329a6ddd10b35ccd06437c64011cc377315be4c98da79` |

The invalid R2 held-out D journals are in the release
`evidence-r2-heldout-d-invalid`; see `r2-interoception/heldout/d-setback-INVALID/`.

## What an archive holds

Every file of every run directory in the group, byte for byte, stored under
its path relative to `runs/`, and `MANIFEST.json` beside them (schema
`person-journal-archive-v1`): for each run its condition, seed, horizon,
originating commit and terminal status, and for each journal its size,
SHA-256 and event count; with totals. The manifest is metadata around the
original bytes; no journal is rewritten. Cognition snapshots are not included:
they were deleted to reclaim disk, and are derivable from the journals.

`scripts/evidence/archive-journals.py` builds the archives deterministically
(sorted paths, fixed timestamps and owners); a second build of the same group
was byte-identical. Every archive was checked against its own manifest, and
every asset was downloaded from the release and its SHA-256 and size
verified, on 2026-09-30.

The metadata files `config.json`, `run.json` and `results.json` contain
absolute local paths from the machine that ran them, in five fields: the
output and evidence directories and the cognition command. The journals
contain none, and nothing contains credentials. They were published unchanged
so that their bytes and hashes stay the originals.

## Rebuilt from journals alone

Before the local copies may be deleted, one run of each journal generation was
rebuilt from its journal alone, with no snapshot, by
`scripts/evidence/rebuild-from-journal.py` in a worktree at the commit that
wrote it, and compared with what the run recorded at its end. Final affect is
compared as the analysis records it: the last appraised state settled to the
episode's end with that commit's own decay.

| Generation      | Run                                            | Events replayed | Routine and skill statistics         | Final affect | Experienced ticks         |
| --------------- | ---------------------------------------------- | --------------- | ------------------------------------ | ------------ | ------------------------- |
| R1, `cc5f408`   | `r1-affect-modes-supervised/P2/seed-3`         | 515 of 515      | unavailable: no learning report then | match        | unavailable: not recorded |
| R1.5, `95fab0b` | `bench-c-exploration/P2/long/seed-3`           | 1,588 of 1,588  | 19 and 52, match                     | match        | 71,676, match             |
| R2, `2573e03`   | `r2-dev-b-near-tie/R2act/long/seed-1`          | 1,566 of 1,566  | 9 and 19, match                      | match        | 71,956, match             |
| R2, `e26fc0a`   | `r2-heldout-c-exploration/R2act/long/seed-101` | 1,264 of 1,264  | 11 and 24, match                     | match        | 71,600, match             |

Every rebuild started with no snapshot, found no truncated or duplicate record,
and left no restore note.
