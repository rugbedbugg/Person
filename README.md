# Person

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

This milestone implements the survival vertical slice and the evidence
substrate that later work depends on. It does not implement language, memory,
belief, affect, social cognition, projects, or redstone; see
`docs/ARCHITECTURE.md` for where those attach, and `docs/PERSON_SPEC.md` Part 0
for what Person is intended to become.

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

Every connecting command also accepts:
person ... --operator-intervention[=reason]   mark the run as contaminated
```

`shroud` is an alias for `person`, and `shroud-train` for `person learn`, for
compatibility with the previous runtime's habits.

`observe` connects, takes one observation and stops. It is the smallest thing
that can be done against a live Minecraft world, and the right first one.
`status` reads what the runtime last wrote and never connects, so watching
Person cannot change what Person does. `compare` diffs a capture against a
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

**Person has acted in Minecraft twice, and that is all.** Two live
observations (2026-09-15, 2026-09-16) and three live single-skill validations
(`wait_safely` once, `return_home` twice, 2026-09-16) have been run against a
disposable LAN world. The other nineteen skills have never run live, no
autonomous episode has ever run live, and every safety mechanism has been proven
only in the fixture and against a conformance double. `REALITY_VALIDATION.md` is
explicit about what that leaves open, and about where the evidence for those
runs lives.

## Development and testing

```bash
npm run typecheck     # tsc --noEmit
npm run build         # tsc emit to dist/
npm test              # Node test runner, 188 tests
npm run format:check  # prettier

uv run pytest         # 129 tests
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
