# Safety

Safety belongs to the Node runtime. Cognition cannot override it, cannot see
enough to route around it, and is told after the fact what actually happened.

## The hierarchy

```
L0  hard safety                     Node only
L1  emergency survival              Node only
L2  active survival goal            cognition proposes, Node validates
L3  routine optimisation            cognition proposes, Node validates
L4  exploration                     cognition proposes, only inside the safe envelope
```

## What the kernel acts on

The kernel is evaluated before every proposal and at every execution
checkpoint. It is a pure function of the world snapshot, so the same world
always produces the same verdict; a test asserts that directly.

| Trigger                                         | Level | Action          |
| ----------------------------------------------- | ----- | --------------- |
| Standing in lava or fire                        | L0    | `flee`          |
| Air below threshold (drowning, suffocation)     | L0    | `flee`          |
| Position outside permitted territory            | L0    | `return_home`   |
| Critical health with a hostile in contact range | L1    | `flee`          |
| Three or more hostiles in contact range         | L1    | `dig_in`        |
| A hostile in contact range                      | L1    | `flee`          |
| Critical hunger with edible food held           | L1    | `eat_to_target` |
| Critical health, food held, hunger not full     | L1    | `eat_to_target` |

## Verdicts

The validator returns one of `ACCEPT`, `REJECT`, `PREEMPT`, `REPLACE`.

- `REJECT` when the skill is unknown or unimplemented, the version does not
  match, the parameters fail the spec, or a required permission is not granted.
  Nothing executes.
- `REPLACE` when an emergency applies and cognition asked for something else.
  The emergency skill runs; the outcome records the requested skill as
  `PREEMPTED` and credits the executed one.
- `ACCEPT` otherwise, including when cognition happened to propose exactly what
  the emergency called for.
- Mid-execution, a checkpoint that finds an emergency raises `PREEMPT`: the
  running skill stops, the emergency skill runs, and the outcome reports both.

Cost limits are clamped down to the skill contract and never up. A proposal
asking for a larger budget than the spec allows is accepted with the reason
code `limits_clamped_to_spec` rather than being silently honoured.

## Protected areas

Protected areas override every other permission and fail closed. They are
enforced at four places, because validating a destination once is not enough:

1. proposal validation, through the permission gate;
2. route selection, through the guard the runtime installs in the embodiment,
   which is consulted for every step the path search considers;
3. skill execution, when a skill picks a target;
4. each individual destructive or building interaction.

Configuration also refuses a home whose shelter footprint would overlap a
protected area, so Person is never told to live somewhere it may not build.

## Capabilities

Capabilities are explicit in configuration, and several have exactly one legal
value, enforced by the schema as well as by the runtime:

```toml
[permissions.containers.existing]
withdraw = true
deposit  = false   # the only legal value

[permissions.hunting]
passiveUnnamedAnimals = true
namedAnimals          = false   # the only legal value
tamedAnimals          = false   # the only legal value

[permissions.players]
combat = false   # the only legal value

[permissions.villagers]
harm = false     # the only legal value

[permissions.protectedAreas]
enforcement = "strict"   # the only legal value
```

Belt and braces: even with a hand-edited configuration that somehow passed
validation, the permission gate refuses a deposit into a container without a
Person-owned provenance record, and the fixture and Mineflayer embodiments both
refuse it again at the point of the transfer.

## No generated code

Nothing in the runtime or cognition evaluates generated code. There is no
`eval`, no `new Function`, no `exec`, no shell out, and no path from
natural-language content to a Minecraft command. Architecture tests assert this
on both sides. New physical capability arrives as a reviewed skill
implementation, never as a runtime artefact.
