#!/usr/bin/env bash
# Local Person 1.16.1 research server. Verifies both official files, then
# always launches with Mojang's 1.12-1.16.5 Log4j mitigation. Console input
# comes from console.fifo, so the operator harness can send server commands.
set -euo pipefail
cd "$(dirname "$0")"
JAVA="$HOME/.local/share/mise/installs/java/temurin-8.0.504+1/bin/java"
echo "a412fd69db1f81db3f511c1463fd304675244077  server.jar" | sha1sum -c --quiet
echo "02937d122c86ce73319ef9975b58896fc1b491d1  log4j2_112-116.xml" | sha1sum -c --quiet
echo "2782d547724bc3ffc0ef6e97b2790e75c1df89241f9d4645b58c706f5e6c935b  server.jar" | sha256sum -c --quiet
echo "29534615b561487bccd3f2ec859b172bc642096cef4f8606754ead7eca5050dd  log4j2_112-116.xml" | sha256sum -c --quiet
[ "$(stat -c %s server.jar)" = "37968964" ]
grep -qx 'server-ip=127.0.0.1' server.properties
grep -qx 'online-mode=false' server.properties
[ "$(tr -d '[:space:]' < ops.json)" = "[]" ]
[ -p console.fifo ] || mkfifo console.fifo
exec "$JAVA" -Xms512M -Xmx1G -Dlog4j.configurationFile=log4j2_112-116.xml -jar server.jar nogui < console.fifo
