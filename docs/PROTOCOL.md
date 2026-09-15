# Protocol

Version: `shroud-learning-v2`

Every message carries `protocolVersion`, `messageId`, `personId`, `sessionId`,
`worldId`, `tick`, `timestamp` and `type`. That set is what makes a recorded
trace replayable and debuggable later, so it is required on every message
rather than only where it currently seems useful.

## One schema, two runtimes

The canonical schemas live in `packages/protocol/schemas/`. The Node binding
compiles them with Ajv; the Python binding validates with `jsonschema`. Neither
runtime has a hand-written approximation of the contract.

`fixtures/protocol-corpus/` holds valid and invalid messages. Both runtimes run
the whole corpus, and `packages/protocol/tests/test_protocol.py` executes the
Node validator as a subprocess and asserts that the two agree on every entry. A
schema change that only one side understands fails the build.

## Message types

Sent by the runtime:

| Type                 | Meaning                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| `SessionHello`       | Session facts: learning mode, training context, evidence directory, seed, skill library revision |
| `Observation`        | Normalised semantic world state                                                                  |
| `ValidationDecision` | The authoritative verdict on a proposal                                                          |
| `SkillStarted`       | Execution has begun, with the starting vitals and inventory                                      |
| `SkillOutcome`       | What actually happened                                                                           |
| `EmergencyEvent`     | The kernel acted at L0 or L1                                                                     |
| `EpisodeEvent`       | Episode started or ended                                                                         |

Sent by cognition:

| Type              | Meaning                                                          |
| ----------------- | ---------------------------------------------------------------- |
| `CognitionReady`  | Handshake, plus what was restored from evidence                  |
| `GoalDecision`    | The active goal and the whole goal stack                         |
| `PolicyDecision`  | The selected routine, its candidates, and the evidence behind it |
| `SkillInvocation` | The single physical request cognition can make                   |

The channel drops anything from cognition that is not in the second list.

## SkillInvocation

```json
{
  "type": "SkillInvocation",
  "decisionId": "...",
  "goalId": "goal_secure_food",
  "routineId": "r_5f2a9c31...",
  "routineStepIndex": 0,
  "skillId": "gather_wood",
  "skillVersion": 1,
  "parameters": { "target_amount": 16, "max_distance": 48 },
  "limits": { "maxTicks": 2400, "maxDistance": 64, "minHealth": 6 }
}
```

`parameters` accepts scalars only, and the schema sets
`unevaluatedProperties: false`. There is no place to put a command, a script,
a chat line or a coordinate list, and the runtime checks the parameters again
against the skill's own spec before anything runs.

## Requested and executed

`SkillOutcome` always carries both `requestedSkill` and `executedSkill`, and
they may differ:

```
requested: gather_wood     requestedSkillStatus: PREEMPTED
executed:  flee            status: SUCCESS
emergency: true
```

Learning credits `executedSkill`. The requested skill records a preemption and
no attempt, so a skill can never accumulate a record for work it did not do.
`expectedEffects` carries the declared effects of the skill that actually ran,
which is what a future world model needs to compare prediction with outcome.

## Transport and framing

Newline-delimited JSON over the cognition subprocess's stdin and stdout. One
JSON object per line, one megabyte per frame, no embedded newlines.

A malformed frame is logged and dropped. It cannot desynchronise the stream,
cannot grow a buffer without bound, and cannot cause anything to execute. The
line reader discards its buffer and reports an error if a peer sends an
unterminated frame larger than the limit.

## Versioning

An unknown `protocolVersion` is rejected by name, with the version the runtime
does speak. A backward-incompatible change takes a new version string rather
than mutating this one, so old evidence stays interpretable instead of being
silently reinterpreted.
