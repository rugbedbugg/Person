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
affect, social cognition, projects, or redstone; see `docs/ARCHITECTURE.md` for
where those attach.

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
person run      --config <file> [--json] [--episode-id <id>]
person learn    --mode off|shadow|supervised --config <file> [--json]
person validate <file> [--migrate]
person inspect  evidence|skills|config [--config <file>] [--json]
```

`shroud` is an alias for `person`, and `shroud-train` for `person learn`, for
compatibility with the previous runtime's habits.

```bash
node apps/cli/src/bin/person.ts validate examples/fixture.toml
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
identity. `docs/LAN_TESTING.md` is the validation ladder and is explicit about
what the automated suite does not prove.

## Development and testing

```bash
npm run typecheck     # tsc --noEmit
npm run build         # tsc emit to dist/
npm test              # Node test runner, 71 tests
npm run format:check  # prettier

uv run pytest         # 102 tests
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
