#!/usr/bin/env bash
# Pre-flight for a real Minecraft LAN session.
#
# Reports two separate things, because they fail for different reasons and at
# different times:
#
#   1. whether this machine is set up to run Person at all;
#   2. whether a Minecraft world is currently listening.
#
# The second is expected to fail while you are still preparing. Only the first
# is a problem you have to fix before opening a world.
#
# Usage: scripts/lan-check.sh <config.toml> [--port <PORT>] [--run]

set -uo pipefail

CONFIG=""
PORT=""
RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="${2:-}"; shift 2 ;;
    --run) RUN=1; shift ;;
    -h|--help)
      echo "Usage: scripts/lan-check.sh <config.toml> [--port <PORT>] [--run]"
      exit 0 ;;
    *) CONFIG="$1"; shift ;;
  esac
done

if [ -z "$CONFIG" ]; then
  echo "Usage: scripts/lan-check.sh <config.toml> [--port <PORT>] [--run]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/apps/cli/src/bin/person.ts"
setup_ok=1

say() { printf '%-9s %s\n' "$1" "$2"; }
ok()   { say "ok"    "$1"; }
bad()  { say "PROBLEM" "$1"; setup_ok=0; }
note() { say "note"  "$1"; }

echo "== Local setup =="

node_version="$(node --version 2>/dev/null || echo none)"
case "$node_version" in
  v22.*) ok "Node $node_version" ;;
  none)  bad "Node is not on PATH; run: mise install" ;;
  *)     note "Node $node_version (the project pins 22; mise exec will use the right one)" ;;
esac

python_version="$(uv run python --version 2>/dev/null || echo none)"
if [ "$python_version" = "none" ]; then
  bad "uv cannot start Python; run: uv sync --all-packages"
else
  ok "$python_version via uv"
fi

if [ -d "$ROOT/node_modules/mineflayer" ]; then
  ok "Node dependencies installed"
else
  bad "node_modules is missing mineflayer; run: npm install"
fi

if uv run python -c "import person_cognition" >/dev/null 2>&1; then
  ok "Python cognition package importable"
else
  bad "person_cognition is not importable; run: uv sync --all-packages"
fi

echo
echo "== Configuration =="
if config_output="$(node "$CLI" validate "$CONFIG" 2>&1)"; then
  echo "$config_output" | sed 's/^/  /'
else
  bad "configuration is not usable:"
  echo "$config_output" | sed 's/^/  /'
fi

# The port on the command line wins, exactly as it does for the real commands.
config_host="$(uv run python -c "
import sys, tomllib
with open(sys.argv[1], 'rb') as handle:
    print(tomllib.load(handle).get('server', {}).get('host', ''))
" "$CONFIG" 2>/dev/null || echo "")"
config_port="$(uv run python -c "
import sys, tomllib
with open(sys.argv[1], 'rb') as handle:
    print(tomllib.load(handle).get('server', {}).get('port', ''))
" "$CONFIG" 2>/dev/null || echo "")"

HOST="${config_host:-127.0.0.1}"
TARGET_PORT="${PORT:-$config_port}"
PORT_SOURCE="configuration"
[ -n "$PORT" ] && PORT_SOURCE="--port"

identity="$(uv run python -c "
import sys, tomllib
with open(sys.argv[1], 'rb') as handle:
    document = tomllib.load(handle)
print(document.get('bot', {}).get('username', '(none)'), document.get('personId', '(none)'))
" "$CONFIG" 2>/dev/null || echo "(unknown) (unknown)")"
echo
echo "== Identity =="
ok "Person will join as: $(echo "$identity" | cut -d' ' -f1)   (personId: $(echo "$identity" | cut -d' ' -f2))"
note "That is the entity to watch for in game. Keep it a non-operator survival player."

echo
echo "== Learning mode =="
mode="$(uv run python -c "
import sys, tomllib
with open(sys.argv[1], 'rb') as handle:
    print(tomllib.load(handle)['learning']['mode'])
" "$CONFIG" 2>/dev/null || echo unknown)"
if [ "$mode" = "off" ]; then
  ok "learning is off, which is what a first contact run wants"
else
  note "learning mode is '$mode'; the first LAN runs should use 'off'"
fi

echo
echo "== Minecraft server =="
if [ -z "$TARGET_PORT" ]; then
  note "no port configured or supplied; pass --port <PORT> once the world is open to LAN"
elif ! [[ "$TARGET_PORT" =~ ^[0-9]+$ ]]; then
  bad "port '$TARGET_PORT' is not a number"
else
  note "target $HOST:$TARGET_PORT (from $PORT_SOURCE)"
  if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$HOST/$TARGET_PORT" 2>/dev/null; then
    ok "something is listening on $HOST:$TARGET_PORT"
  else
    note "nothing is listening on $HOST:$TARGET_PORT yet"
    note "this is expected until you open the world to LAN; it is not a setup problem"
  fi
fi

echo
if [ "$setup_ok" = "1" ]; then
  echo "LOCAL SETUP READY."
else
  echo "LOCAL SETUP NOT READY: fix the items marked PROBLEM above."
fi
echo "Server reachability is reported separately above and is not part of that verdict."

echo
echo "Before connecting, confirm all of the following:"
echo "  - the world is disposable and yours"
echo "  - it is opened to LAN, and the port above is the one Minecraft displayed"
echo "  - the port changes every time you reopen the world; pass the new one with --port"
echo "  - difficulty and runtime.trainingContext agree (peaceful with minecraft_peaceful)"
echo "  - cheats may stay on for you; Person must remain a non-operator survival player"
echo "  - anything you care about is inside world.protectedAreas"

if [ "$RUN" = "1" ]; then
  echo
  echo "== One observation =="
  if [ -n "$PORT" ]; then
    node "$CLI" observe --config "$CONFIG" --port "$PORT"
  else
    node "$CLI" observe --config "$CONFIG"
  fi
else
  echo
  echo "Next: node apps/cli/src/bin/person.ts observe --config $CONFIG --port <PORT>"
fi

[ "$setup_ok" = "1" ] || exit 1
