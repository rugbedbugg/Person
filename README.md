# Person

[![CI](https://github.com/rugbedbugg/Person/actions/workflows/ci.yml/badge.svg)](https://github.com/rugbedbugg/Person/actions/workflows/ci.yml)

A persistent autonomous artificial inhabitant for Minecraft Java Edition 1.16.1.

Person is not a chatbot attached to Minecraft, not a language model driving
Mineflayer, and not a reinforcement-learning bot. It is a bounded embodied agent
built around one invariant:

> Python may propose intentions. Node decides what is physically permitted.

The Python cognition process perceives semantically, forms goals, plans from
declared skill contracts, picks a routine, and proposes one bounded skill at a
time. The Node runtime validates every proposal, can replace it outright when
safety demands, executes it under hard limits, and reports what actually
happened. Learning is credited to what ran, never to what was asked for.

On top of the survival vertical slice and its evidence substrate, Person now
has a perception firewall with bounded gaze, planner-owned information seeking,
episodic memory recalled by typed cue, a drifting sense of place and home,
persistent projects, a small decaying affect that biases near choices, learned
reliability of its skills' effects, and typed causal hypotheses it tests with
its own bounded experiments. All of that is TESTED IN FIXTURE only. It does not
implement language, social cognition, relationships, semantic or
autobiographical memory, consolidation, a knowledge store, or redstone.
`docs/CURRENT_STATE.md` is the factual snapshot, `docs/ARCHITECTURE.md` shows
where each part attaches, and `docs/PERSON_SPEC.md` says what Person is
intended to become.

## Installation

Requires Node.js 22, Python 3.12, [mise](https://mise.jdx.dev) and
[uv](https://docs.astral.sh/uv/).

```bash
mise trust
mise install          # Node 22.23.2, Python 3.12, uv
npm install           # Node dependencies, exact pins
uv sync --all-packages  # Python workspace, exact pins
```

## Quick start

Run one episode in the deterministic fixture world. No Minecraft server is
contacted, and learning is off.

```bash
node apps/cli/src/bin/person.ts run --config examples/fixture.toml
```

Person starts hungry with nothing, finds food, eats, gathers wood, builds a
shelter, makes tools, places a chest, flees when a hostile arrives, and writes
an episode report to `runs/reports/`.

## Usage

```
person run      --config <file> [--port <n>] [--host <h>] [--json] [--episode-id <id>]
person learn    --mode off|shadow|supervised --config <file> [--port <n>] [--json]
person observe  --config <file> [--port <n>] [--host <h>] [--json] [--out <file>]
person status   --config <file> [--json] [--follow [--interval <ms>]]
person validate <file> [--migrate]
person inspect  evidence|skills|config|predictions [--config <file>] [--json]
person compare  <reference-observation.json> <actual-observation.json> [--json]
person experiment --plan <plan.json> [--out <directory>] [--json]
person preflight --config <file> --server-dir <dir> --backup <dir> [--found] [--json]
person world-manifest --server-dir <dir> --purpose <text>

Every connecting command also accepts:
person ... --operator-intervention[=reason]   mark the run as contaminated
```

`shroud` is an alias for `person`, and `shroud-train` for `person learn`, for
compatibility with the previous runtime's habits.

`preflight` is the read-only, fail-closed check before a founding or an
embodiment, and `world-manifest` records a new world's identity once; the
procedure around them is `docs/FOUNDING_RUNBOOK.md`.

`observe` connects, takes one observation and stops. It is the smallest thing
that can be done against a live Minecraft world, and the right first one.
`status` reads what the runtime last wrote and never connects, so watching
Person cannot change what Person does. `experiment` runs a research plan in the fixture
world, every condition on every world seed, and reports each metric per run
(`experiments/`, ADR 0013). `compare` diffs a capture against a
reference and flags fields that look like defaults nothing ever filled in.

Minecraft assigns a new LAN port every time a world is opened, so `--port` is
runtime information rather than configuration. It overrides the file for one
invocation and is never written back; a changed port never means editing
`config.toml`.

```bash
node apps/cli/src/bin/person.ts validate examples/fixture.toml
node apps/cli/src/bin/person.ts observe --config examples/fixture.toml --out capture.json
node apps/cli/src/bin/person.ts compare capture.json capture.json
node apps/cli/src/bin/person.ts inspect skills
node apps/cli/src/bin/person.ts inspect evidence --config examples/fixture.toml
node apps/cli/src/bin/person.ts learn --mode shadow --config examples/fixture.toml
```

Learning never turns itself on. `person run` uses the mode written in the
configuration file, which every shipped example sets to `off`; `person learn`
is the only way to put a learner in control, and the safety kernel still has
the final say over every physical action.

## Configuration

TOML, validated against `packages/config/schema/person-config.schema.json` by
both runtimes. See `examples/fixture.toml` and `examples/minecraft-lan.toml`.

```toml
configVersion = 2
personId = "ada"
worldId = "fixture-world-01"

[runtime]
embodiment = "fixture"        # or "minecraft"
trainingContext = "fixture"   # fixture | minecraft_peaceful | minecraft_normal | replay
outputDirectory = "../runs"
rngSeed = 20260915

[learning]
mode = "off"                  # off | shadow | supervised

[cognition]
command = ["uv", "run", "person-cognition"]

[world]
home = { x = 0, y = 64, z = 0 }
exploration = { min = { x = -48, y = 56, z = -48 }, max = { x = 48, y = 80, z = 48 } }
resourceAreas = [{ min = { x = -48, y = 56, z = -48 }, max = { x = 48, y = 80, z = 48 } }]
protectedAreas = [{ min = { x = 20, y = 56, z = 20 }, max = { x = 28, y = 80, z = 28 } }]

[permissions.containers.existing]
withdraw = true
deposit = false               # the only legal value
```

Several capabilities have exactly one legal setting: Person never deposits into
a container it did not place, never targets players, villagers, named animals
or tamed animals, and protected-area enforcement is always strict.
`docs/SAFETY.md` explains why each of those is a schema constant rather than a
preference.

A legacy Shroud V1 configuration can be migrated:

```bash
node apps/cli/src/bin/person.ts validate old-config.json --migrate
```

Learning is never carried across a migration, and a V1 Q-learning checkpoint is
recognised and refused rather than converted.

## Running against Minecraft

Use a disposable world you own, opened to LAN, with a dedicated offline bot
identity. `docs/LAN_TESTING.md` opens with a **First contact** section that
walks the whole thing once:

```bash
bash scripts/lan-check.sh my-world.toml --port <PORT>
node apps/cli/src/bin/person.ts observe --config my-world.toml --port <PORT>
node apps/cli/src/bin/person.ts status  --config my-world.toml
```

Person joins as an ordinary non-operator survival player. The world host keeps
cheats; Person never gets them, and has no way to send a command at all.

**Person has acted in Minecraft only briefly.** On a disposable LAN world:
two observations (2026-09-15, 2026-09-16) and three single-skill validations
(`wait_safely` once, `return_home` twice, 2026-09-16), all before the
perception firewall. On a local dedicated server (2026-09-29): a six-check
checkpoint of the current body contract (observation v7, gaze, the perception
firewall, the kernel's threat detection, restart reconstruction), one
`look_around` validation, and the first two autonomous episodes, of eight
decisions each. Twenty of the twenty-three skills have never been validated
live, and most safety mechanisms have been proven only in the fixture and
against a conformance double. `REALITY_VALIDATION.md` is explicit about what
that leaves open, and about where the evidence for those runs lives.

## Development and testing

```bash
npm run typecheck     # tsc --noEmit
npm run build         # tsc emit to dist/
npm test              # Node test runner
npm run format:check  # prettier

uv run pytest         # Python tests
uv run ruff check .   # lint
uv run ruff format --check .
uv run mypy           # strict, on package sources

mise run check        # all of the above
```

The fixture world in `fixtures/` is the deterministic integration environment.
Skills are written once against an embodiment port, so the fixture tests
exercise the same skill code that runs against Mineflayer.

## Documentation

| Document                   | Contents                                             |
| -------------------------- | ---------------------------------------------------- |
| `docs/ARCHITECTURE.md`     | Processes, packages, the decision loop               |
| `docs/PROTOCOL.md`         | The versioned cross-process contract                 |
| `docs/SKILLS.md`           | Skill contracts and the library                      |
| `docs/SAFETY.md`           | The safety hierarchy and capability model            |
| `docs/LEARNING.md`         | Context, evidence, scoring, restart                  |
| `docs/LAN_TESTING.md`      | Manual Minecraft validation ladder                   |
| `docs/RESEARCH.md`         | Research framing and claim discipline                |
| `docs/EVALUATION.md`       | What the suite proves, and what it does not          |
| `docs/PERSON_SPEC.md`      | The authoritative architecture specification         |
| `TRACEABILITY.md`          | Requirements mapped to code and tests                |
| `IMPLEMENTATION_REPORT.md` | What was built, reused, deferred and left unverified |

## License

MIT. See `LICENSE`.
