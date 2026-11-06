#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p encrypted-volume

quiet() {
    if [ "${DEBUG:-0}" = "1" ]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi
}

if [ "${DEBUG:-0}" = "1" ]; then
    export LOG_DRIVER=json-file
else
    export LOG_DRIVER=none
fi

if [ "$(uname -s)" = "Linux" ] && [ -n "${DISPLAY:-}" ] && [ -d /tmp/.X11-unix ]; then
    COMPOSE_FILES="-f compose.yml -f compose.x11.yaml"
    VNC=0
    xhost +SI:localuser:"$(whoami)" >/dev/null 2>&1 || true
else
    COMPOSE_FILES="-f compose.yml -f compose.vnc.yaml"
    VNC=1
fi

trap 'quiet docker compose $COMPOSE_FILES down' EXIT INT TERM

quiet docker compose $COMPOSE_FILES build
quiet docker compose $COMPOSE_FILES up -d api proxy
echo "Open http://localhost:8080 for the app."

if [ "$VNC" = "1" ]; then
    quiet docker compose $COMPOSE_FILES up -d vnc-relay
    echo "Open http://127.0.0.1:6080/vnc.html to see the sandboxed browser."
fi

quiet docker compose $COMPOSE_FILES create browser
echo
echo "Enter the passphrase to unlock (first run: to create) the encrypted data volume:"
docker start -ai "$(docker compose $COMPOSE_FILES ps -a -q browser)"
