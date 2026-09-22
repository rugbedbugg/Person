# Safety

Safety belongs to the Node runtime. Cognition cannot override it, cannot see
enough to route around it, and is told after the fact what actually happened.

## Three different things called safety

The runtime enforces three concerns through one mechanism. They are not the
same concern, and treating them as one makes a claim about Person that is not
true.

| Concern                       | What it protects               | Whose property it is                       |
| ----------------------------- | ------------------------------ | ------------------------------------------ |
| **Self-preservation**         | Person, from the world         | Person's own. A creature that avoids lava. |
| **Experimental containment**  | the experiment, from Person    | The operator's. A configured fence.        |
| **Shared-world and property** | other inhabitants, from Person | Operator policy standing in for a norm.    |

- **Self-preservation** is fleeing fire, surfacing from drowning, eating when
  starving, digging in against a swarm. This is behaviour Person would want if
  it were choosing, and the kernel does it faster than deliberation could.
- **Experimental containment** is the exploration box, the protected areas and
  the resource areas. These exist so a disposable test world stays disposable
  and a live experiment stays inside its bounds. They are the operator's
  decision about this run, not a fact about Person.
- **Shared-world and property policy** is the refusal to harm players,
  villagers, named animals and tamed animals, and the refusal to deposit into a
  container Person did not place. Today these are configured constants with one
  legal value. They stand in for social norms Person does not yet have.

The third category is the one to watch. `docs/PERSON_SPEC.md` section 0.18 says
Person's morality must develop from experience rather than arrive hard-coded,
and section 0.16 says containment and morality are separate systems. **The
permission gate is not Person's conscience.** When Person eventually has norms,
they will be a cognitive system that can disagree with the gate, and the gate
will still win. That is the intended relationship, not a temporary compromise.

Nothing in this framing changes what the runtime does. It changes what the
runtime is claimed to mean.

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

| Trigger                                         | Level | Action          | Concern           |
| ----------------------------------------------- | ----- | --------------- | ----------------- |
| Standing in lava or fire                        | L0    | `flee`          | self-preservation |
| Air below threshold (drowning, suffocation)     | L0    | `flee`          | self-preservation |
| Position outside permitted territory            | L0    | `return_home`   | **containment**   |
| Critical health with a hostile in contact range | L1    | `flee`          | self-preservation |
| Three or more hostiles in contact range         | L1    | `dig_in`        | self-preservation |
| A hostile in contact range                      | L1    | `flee`          | self-preservation |
| Critical hunger with edible food held           | L1    | `eat_to_target` | self-preservation |
| Critical health, food held, hunger not full     | L1    | `eat_to_target` | self-preservation |

The third row is the odd one out: leaving the exploration box is not dangerous
to Person, and it sits at L0 because it must not be negotiable, not because it
is a threat. That is recorded as contradiction C2 in `docs/PERSON_SPEC.md`
section 0.24. Whether the kernel eventually grows a containment level distinct
from L0 is an open decision; **no production change has been made for it.**

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

A refusal is reported to Person honestly, as unavailable or failed, without
exposing the containment design. See ADR 0005.

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

Enforcement point 2 is load-bearing for any future motor backend: a body that
cannot be handed a per-step veto cannot enforce this. ADR 0001 makes that the
first question the Baritone spike must answer.

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

## Capability authority

Cognition may want, plan and propose anything. The runtime decides what
happens. A Person that plans something forbidden is behaving normally, and the
refusal is recorded rather than prevented at the level of thought.

```text
desire -> goal -> plan -> proposed action -> capability policy -> execution
```

Minecraft command authority is a separate capability axis and is off at every
Person configuration, canonical and Super-Person alike. There is no generic
`execute_command(string)` capability, and an architecture test asserts Person
has no way to issue a server command. See `docs/PERSON_SPEC.md` sections 0.16
and 0.17, and ADR 0005.

## Operator intervention

Operator actions are declared, not detected. `--operator-intervention` and the
`operatorSetup` phase of `person skill-test` write a marker into the episode
events, the status file and the validation report, so a debugging session
cannot later be counted as an acceptance run. Person has no teleport capability
and the CLI exposes none: moving Person is something a human does and says they
did.

## No generated code

Nothing in the runtime or cognition evaluates generated code. There is no
`eval`, no `new Function`, no `exec`, no shell out, and no path from
natural-language content to a Minecraft command. Architecture tests assert this
on both sides. New physical capability arrives as a reviewed skill
implementation, never as a runtime artefact.

When web research eventually exists, retrieved text enters under the same rule:
untrusted evidence, never instruction. See ADR 0004.
