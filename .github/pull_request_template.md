# Pull Request Template

## Scope

<!-- One-line summary of what this PR changes -->

## Architectural Impact

<!-- Check one: -->

- [ ] None — bug fix, test, docs, refactor within established boundaries
- [ ] Minor — extends existing capability without boundary changes
- [ ] Major — changes a category in `docs/OWNERSHIP.md` §3 (requires both maintainer approvals)

**Affected boundaries (if any):**

- [ ] Node/Python trust boundary
- [ ] Protocol schemas
- [ ] Safety kernel / permissions
- [ ] SkillSpec semantics
- [ ] Evidence format / learning semantics
- [ ] Persistent state model
- [ ] Major runtime architecture
- [ ] Multi-Person architecture

## Tests Run

```
mise run check
```

**Result:** [PASS / FAIL — if FAIL, explain why]

## Validation Distinctions

<!-- Be explicit about what has/hasn't been validated -->

| Capability                 | Fixture | Conformance | Live Minecraft |
| -------------------------- | ------- | ----------- | -------------- |
| <!-- e.g., gather_wood --> | [ ]     | [ ]         | [ ]            |

**No live validation claimed unless actually performed against Minecraft.**

## Protocol Changes

<!-- If any schema changed: -->

- Schema file(s):
- Version impact: [backward-compatible / breaking — requires new protocolVersion]
- Cross-runtime validation: [both runtimes updated and tested]

## Safety / Trust Boundary Changes

<!-- If any: describe the change and why it's safe -->

## Documentation Updated

- [ ] AGENTS.md
- [ ] docs/PERSON_SPEC.md
- [ ] docs/CURRENT_STATE.md
- [ ] REALITY_VALIDATION.md
- [ ] docs/PROJECT_HISTORY.md
- [ ] TRACEABILITY.md
- [ ] docs/decisions/ (new ADR)
- [ ] Other:

## Known Limitations / Follow-up

<!-- What this PR doesn't address, or what should be revisited -->

---

## Reviewer Checklist

- [ ] `mise run check` passes
- [ ] Commits signed, messages follow `[Title]: Subject` format
- [ ] Architectural impact correctly assessed
- [ ] Validation claims honest (no fixture→live upgrade)
- [ ] Canonical docs updated
- [ ] ADR created if architectural boundary changed
- [ ] No history rewriting on shared branches
