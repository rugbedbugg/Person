# 0002: Person v2 to Person v3 (environment profiles and experience keys)

ADR 0025 split Person's core from its first environment. Three versioned
formats changed with it. None of them is rewritten on disk: each older form
is read as the current one, in memory, by a reader that understands both.

## Configuration: `configVersion` 2 to 3

Read by `environments/minecraft/ts/legacy.ts` (`upgradeConfigDocument`) and
`packages/config/python/person_config/load.py` (a frozen copy of the v2
schema, `packages/config/schema/legacy/person-config-v2.schema.json`).
`person validate <file> --migrate` prints what the reading changed; the file
is never written.

| configVersion 2                                          | configVersion 3                                                         |
| -------------------------------------------------------- | ----------------------------------------------------------------------- |
| `runtime.trainingContext = "fixture"`                    | `environment.kind = "minecraft"`, `runtime.embodiment = "fixture"`      |
| `runtime.trainingContext = "minecraft_peaceful"`         | `environment.kind = "minecraft"`, `environment.difficulty = "peaceful"` |
| `runtime.trainingContext = "minecraft_normal"`           | `environment.kind = "minecraft"`, `environment.difficulty = "normal"`   |
| `runtime.embodiment = "minecraft"`                       | `runtime.embodiment = "mineflayer"`                                     |
| `server`, `bot`, `authorization`, `world`, `permissions` | unchanged; owned by the Minecraft profile's schema                      |

`environment.difficulty` is required for the Mineflayer body and refused for
the fixture body, which defines its own dynamics. A v2 `trainingContext` of
`"replay"` is not a configured context any more: replay is the experience
context of records, never of a running body.

## Protocol: `shroud-learning-v2` to `person-v3`

Observation version 8 to 9: the Minecraft fields (`vitals`, `environment`,
`inventory`, `permissions`, `affordances`, `nearby`, `home`, `navigation`)
moved under `payload`, validated by
`environments/minecraft/schemas/observation-payload.schema.json`;
`trainingContext` became `experience`
(`{context, environmentKind, embodimentKind, environmentVariant}`) on
`Observation`, `SessionHello` and episode events. Emergency trigger and action
vocabularies come from the environment manifest.

As before, there is no in-place protocol migration and both runtimes reject an
unrecognised version by name. The protocol corpus under
`fixtures/protocol-corpus/` was regenerated with
`scripts/migrations/observation_v9.py`. Captured v8 observations are history
and stay as they were.

## Journal: `person-evidence-v19` to `person-event-v20`

Records v1 to v19 are read unchanged. Their `training_context` is mapped to an
experience key by `packages/persistence/python/person_persistence/legacy.py`,
and `to_json` writes such a record back exactly as it was read, so a rebuilt
snapshot never launders an old record into a new one.

| `training_context`   | Experience key                        |
| -------------------- | ------------------------------------- |
| `fixture`            | `lived:minecraft/fixture`             |
| `minecraft_peaceful` | `lived:minecraft/mineflayer/peaceful` |
| `minecraft_normal`   | `lived:minecraft/mineflayer/normal`   |
| `replay`             | `replay:minecraft/unknown`            |

New in v20: every record carries `experience`, and the `belief_revised` event
type (ADR 0026). The journal types are `CanonicalEvent`, `EventJournal`,
`EventStore`; the former `Evidence*` names remain as aliases (ADR 0027).
Cognition snapshots moved to version 2; a version 1 snapshot is not reused,
and the store is rebuilt from the journal instead.

## Validation reports

`SkillValidationReport` schema version 2: `trainingContext` became
`experience`, the stream's short name (for example
`lived:minecraft/mineflayer/peaceful`). Version 1 reports are history and are
not rewritten.
