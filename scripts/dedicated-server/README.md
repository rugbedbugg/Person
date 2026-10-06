# Local 1.16.1 research server

Engineering infrastructure for validating Person against real Minecraft
without a person at the game. Authorized by the operator on 2026-09-29 for
local, single-Person test infrastructure. It is not part of Person: nothing
here reaches cognition except through the ordinary `Observation`.

## What it sets up

- Mojang's official `server.jar` for 1.16.1 and Mojang's Log4j mitigation
  for 1.12 to 1.16.5 (`log4j2_112-116.xml`), both verified against pinned
  SHA-1 and SHA-256 hashes before anything runs, and again on every launch.
- A server bound to `127.0.0.1`, `online-mode=false` for local offline
  accounts, survival (forced), no operators, command blocks off, RCON and
  query off, a whitelist of one account and `max-players=1`.
- Everything under `runs/servers/<name>/`, which git ignores, apart from
  `~/.minecraft` and any personal world.

Do not expose it: no port forwarding, no firewall change, no other bind
address, and never an operator for Person.

## Use

```bash
scripts/dedicated-server/setup.sh person-1161 --accept-eula   # once
runs/servers/person-1161/run.sh                               # start
echo "stop" > runs/servers/person-1161/console.fifo           # stop cleanly
```

`--accept-eula` writes `eula=true`, which is acceptance of the Minecraft
EULA (https://www.minecraft.net/eula). Only the operator can give it; without
it the server refuses to start.

`run.sh` reads server console commands from `console.fifo`, so something must
hold the pipe open while it runs (for example `sleep infinity > console.fifo &`).
Console commands are operator actions on the world: any connecting command run
after them should carry `--operator-intervention=<reason>`.

The runtime refuses a frozen daylight cycle, so keep `doDaylightCycle` on; to
keep a validation controlled, turn off mob spawning instead.

## Checkpoint probe

`scripts/dedicated-checkpoint.ts` drives the real Mineflayer adapter against a
running server and checks gaze, visible versus hidden threats, the kernel's
independence and the absence of privileged fields, using the server console
as the independent witness. Its results for 2026-09-29 are in
`docs/evidence/dedicated-server/2026-09-29/` and `REALITY_VALIDATION.md`,
"Dedicated-server validation".
