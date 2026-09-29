#!/usr/bin/env bash
# Sets up a local Minecraft 1.16.1 research server for Person under runs/servers/.
#
#   scripts/dedicated-server/setup.sh <name> [--username <name>] [--seed <n>] [--accept-eula]
#
# Downloads Mojang's official server jar and Log4j mitigation, verifies both
# against pinned hashes before anything runs, and writes a configuration that
# is bound to 127.0.0.1, offline, survival, whitelist-of-one, with no
# operators. It writes eula=true only with --accept-eula, which records the
# operator's acceptance of the Minecraft EULA (https://www.minecraft.net/eula);
# without it the server refuses to start, as Mojang intends.
set -euo pipefail
name="${1:?usage: setup.sh <name> [--username <name>] [--seed <n>] [--accept-eula]}"
shift
username="PersonAda"
seed="20260929"
accept=false
while [ $# -gt 0 ]; do
  case "$1" in
    --username) username="$2"; shift 2 ;;
    --seed) seed="$2"; shift 2 ;;
    --accept-eula) accept=true; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
here="$(cd "$(dirname "$0")" && pwd)"
repository="$(cd "$here/../.." && pwd)"
target="$repository/runs/servers/$name"
mkdir -p "$target"
cd "$target"

SERVER_URL="https://piston-data.mojang.com/v1/objects/a412fd69db1f81db3f511c1463fd304675244077/server.jar"
LOG4J_URL="https://launcher.mojang.com/v1/objects/02937d122c86ce73319ef9975b58896fc1b491d1/log4j2_112-116.xml"
[ -f server.jar ] || curl -fsSL --retry 3 -o server.jar "$SERVER_URL"
[ -f log4j2_112-116.xml ] || curl -fsSL --retry 3 -o log4j2_112-116.xml "$LOG4J_URL"
echo "a412fd69db1f81db3f511c1463fd304675244077  server.jar" | sha1sum -c --quiet
echo "02937d122c86ce73319ef9975b58896fc1b491d1  log4j2_112-116.xml" | sha1sum -c --quiet
echo "2782d547724bc3ffc0ef6e97b2790e75c1df89241f9d4645b58c706f5e6c935b  server.jar" | sha256sum -c --quiet
echo "29534615b561487bccd3f2ec859b172bc642096cef4f8606754ead7eca5050dd  log4j2_112-116.xml" | sha256sum -c --quiet
[ "$(stat -c %s server.jar)" = "37968964" ]

sed "s/^level-seed=.*/level-seed=$seed/; s/^level-name=.*/level-name=$name/" \
  "$here/server.properties" > server.properties
uuid="$(python3 -c '
import hashlib, sys, uuid
h = bytearray(hashlib.md5(("OfflinePlayer:" + sys.argv[1]).encode()).digest())
h[6] = (h[6] & 0x0F) | 0x30
h[8] = (h[8] & 0x3F) | 0x80
print(uuid.UUID(bytes=bytes(h)))
' "$username")"
printf '[\n  {\n    "uuid": "%s",\n    "name": "%s"\n  }\n]\n' "$uuid" "$username" > whitelist.json
echo "[]" > ops.json
echo "[]" > banned-players.json
echo "[]" > banned-ips.json
cp "$here/run.sh" run.sh
chmod +x run.sh
if $accept; then
  printf '#Accepted by the operator for a local Person research server on %s (https://www.minecraft.net/eula)\neula=true\n' "$(date -I)" > eula.txt
  echo "EULA acceptance recorded in $target/eula.txt"
else
  echo "Not accepting the EULA on your behalf: rerun with --accept-eula once you have read and accepted it."
fi
echo "Ready: $target (start with $target/run.sh; the console reads $target/console.fifo)"
