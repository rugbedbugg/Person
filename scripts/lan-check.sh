#!/usr/bin/env bash
# Pre-flight for a real Minecraft LAN session.
#
# Validates the configuration, shows what the runtime will and will not be
# allowed to do, and optionally runs a single-decision episode so the first
# contact with a live server is one bounded action rather than a whole run.
#
# Usage: scripts/lan-check.sh <config.toml> [--run]

set -euo pipefail

CONFIG="${1:-}"
RUN="${2:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/apps/cli/src/bin/person.ts"

if [[ -z "$CONFIG" ]]; then
  echo "Usage: scripts/lan-check.sh <config.toml> [--run]" >&2
  exit 2
fi

echo "== Configuration =="
node "$CLI" validate "$CONFIG"

echo
echo "== Skill library =="
node "$CLI" inspect skills | head -5
echo "  ..."

echo
echo "== Evidence store =="
node "$CLI" inspect evidence --config "$CONFIG"

echo
echo "Before connecting, confirm all of the following:"
echo "  - the world is disposable and yours"
echo "  - it is opened to LAN and server.port matches the displayed port"
echo "  - cheats are off and the daylight cycle is natural"
echo "  - the bot username is a dedicated offline identity, not your account"
echo "  - world.home has a solid three by three floor"
echo "  - anything you care about is inside world.protectedAreas"

if [[ "$RUN" == "--run" ]]; then
  echo
  echo "== One episode =="
  node "$CLI" run --config "$CONFIG"
else
  echo
  echo "Re-run with --run to start an episode, or follow docs/LAN_TESTING.md."
fi
