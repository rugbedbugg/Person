# 0001: Shroud V1 configuration to Person configVersion 2

Implemented in `packages/config/ts/migrate.ts`, exercised by
`tests/cli/cli.test.ts`.

Run it with:

```bash
node apps/cli/src/bin/person.ts validate old-config.json --migrate
```

The command prints the migrated configuration and the notes below. It does not
write anything: the operator reviews the result and saves it deliberately.

## Field mapping

| Shroud V1         | Person v2                 | Notes                                                                                                |
| ----------------- | ------------------------- | ---------------------------------------------------------------------------------------------------- |
| `server`          | `server`                  | Unchanged. Still loopback only, still 1.16.1 only.                                                   |
| `bot`             | `bot`                     | Unchanged. Still offline auth, still a dedicated username.                                           |
| `home`            | `world.home`              | Unchanged.                                                                                           |
| `exploration`     | `world.exploration`       | Unchanged.                                                                                           |
| `resourceAreas`   | `world.resourceAreas`     | Unchanged.                                                                                           |
| `protectedAreas`  | `world.protectedAreas`    | Defaults to empty when absent.                                                                       |
| `outputDirectory` | `runtime.outputDirectory` | Unchanged.                                                                                           |
| `worldId`         | `worldId`                 | Defaults to `migrated-world` when absent.                                                            |
| `bot.username`    | `personId`                | Lowercased and filtered to the identifier charset.                                                   |
| `difficultyMode`  | `runtime.trainingContext` | `peaceful-training` becomes `minecraft_peaceful`; anything else becomes `minecraft_normal`.          |
| `authorization`   | `authorization`           | Rebuilt with the four required assertions, plus `normalDifficulty` derived from the difficulty mode. |

## Fields that are not carried across

| Shroud V1      | Why                                                                                                                                                                                             |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `learningMode` | It names a learner that no longer exists. Person starts at `learning.mode = "off"` and never enables learning implicitly. The migration reports this as a note rather than dropping it quietly. |
| `spawn`        | Person validates its spawn against the exploration bounds instead of a separate spawn box.                                                                                                      |
| `maxChunks`    | Chunk retention is an adapter concern in Person, not a configuration knob.                                                                                                                      |

## Fields that are added

`permissions` did not exist in V1 and is required in v2. The migration supplies
the conservative defaults: pre-existing containers are withdraw-only and never
deposited into, hunting is limited to unnamed untamed passive animals, player
combat and villager harm are off, building is enabled, and protected-area
enforcement is strict. Several of those have exactly one legal value and cannot
be widened by editing the file afterwards.

`cognition.command` is added as `["uv", "run", "person-cognition"]`. Adjust it
if the cognition process is launched differently.
