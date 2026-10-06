# Tracked single-skill live validation evidence

Three `person skill-test` reports from the first live Minecraft skill
execution, 2026-09-16, against `person-test-world-1` (Java 1.16.1, LAN,
Peaceful). `wait_safely` once, `return_home` twice. Full narrative and
interpretation: `REALITY_VALIDATION.md`, "First live skill execution".

These are immutable copies of what `person skill-test` actually wrote under
`runs/validation/skill-tests/` (gitignored, local to the operator's machine).
They are tracked here so the claim in `REALITY_VALIDATION.md` has a citable,
version-controlled artifact behind it rather than resting on a local file
nobody else can read.

## Provenance

| Tracked file                                                    | Source SHA-256 (of the original, unredacted report)                |
| --------------------------------------------------------------- | ------------------------------------------------------------------ |
| `person-test-world-1-ada-wait_safely-st_mu3w5z9d_78158279.json` | `f1941b2e723d7eb810c9d2fd9739823d8ecc0023372c8829bfa092a76d489043` |
| `person-test-world-1-ada-return_home-st_mu3wadax_6a72c352.json` | `10d8d8c3ced91fd90411ad9664bb24add6c2b617f3e21d9f05183354286da367` |
| `person-test-world-1-ada-return_home-st_mu3wii0a_c0010f88.json` | `96ad546d0c9d742c0cd47a1d77430cef57f78991a41f820b3a00b5f419df9e89` |

The source SHA-256 is computed over the **original** report exactly as
`person skill-test` wrote it, before the redaction described below. Verifying
it therefore requires the original local file, not the tracked copy; that is
intentional; it lets a reader who does have the original (the operator, on
this machine) confirm the tracked copy is a faithful redaction of it, without
the hash itself carrying the redacted content.

## Sensitivity audit

All three original reports were inspected for credentials, auth tokens, server
addresses, private hostnames, local filesystem paths, and usernames that
should not be public.

**One category was found and redacted:** `learning.evidenceBefore.directory`
and `learning.evidenceAfter.directory` held the absolute local path
`/home/rugbedbugg/Projects/Python/Person/runs/evidence` in every report. That
path reveals the operator's system username and directory layout and carries
no evidential value; the fields that matter for the claim (`exists`, `files`,
`policyRevision`, `digest`) are unaffected. Both fields are replaced with the
literal string `<redacted: local filesystem path>` in the tracked copies.
Nothing else in either field was touched: the digest, `policyRevision` and
`changed: false` are exactly what `person skill-test` recorded.

**One category was found and deliberately kept:** every observation in every
report carries the operator's Minecraft account, `username: "Shroud"` and
`uuid: "1ed03c15-b62c-33e4-8e93-cd19bc1d57e3"`, as the nearby player entity.
This is not new exposure: the same username and UUID are already committed and
public, in `REALITY_VALIDATION.md`'s "Second contact" section and in
`docs/PROJECT_HISTORY.md`, from a decision the operator made before this audit
ran. Redacting it from these three files while it stands unredacted twelve
lines above them in the same repository would not protect anything and would
make the artifact harder to cross-check against the narrative it supports. If
this judgment is wrong, say so and it will be redacted and the narrative
sections corrected to match.

No credentials, auth tokens, server address, host, or port appear in any
report. Host and port are runtime-only overrides
(`packages/config/ts/override.ts`) and are never written to a config file or a
report.

## What this does NOT establish

Preserving these three artifacts is not a validation upgrade. Per
`docs/CURRENT_STATE.md` and `REALITY_VALIDATION.md`:

- Only `wait_safely` and `return_home` are live-validated. The other nineteen
  skills remain unproven.
- Both live worlds were Peaceful; hostile behaviour, night, and emergency
  preemption remain unproven live.
- Two navigation samples are two samples; the pathfinder-on-real-terrain
  blocker in `REALITY_VALIDATION.md` stands, only partly addressed.
- No autonomous episode has ever run live.
- Tick budgets remain the fixture's invented numbers, unrevised by these runs.

## Fields worth reading directly

Each report's `effectComparison`, `learning`, `navigation`, `completionEvidence`
and `timeline` blocks are the load-bearing evidence for the claims in
`REALITY_VALIDATION.md`'s summary table. They are unmodified from the original
except for the one redaction above.
