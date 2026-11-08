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

LINK_URL='http://127.0.0.1:10001/'

if command -v xpra >/dev/null 2>&1; then
    export XPRA_CLIENT=1
else
    export XPRA_CLIENT=0
fi

trap 'quiet docker compose down' EXIT INT TERM

echo "Building (this can take several minutes)..."
if ! quiet docker compose create --build; then
    echo "Build failed - rerun with DEBUG=1 to see why." >&2
    exit 1
fi
quiet docker compose start api xpra-relay

# Act inside the pipeline, right after grep matches: the pipeline as a whole
# only finishes once `logs -f` writes again and hits the closed pipe, which
# never happens when the container goes quiet after its ready line (i.e.
# without DEBUG=1). `logs -f` exits on its own when `down` removes the
# container.
docker compose logs -f browser 2>/dev/null | {
    grep -q 'Code Co-occurrence Graphs is ready' || exit 0
    if [ "$XPRA_CLIENT" = "1" ]; then
        quiet xpra attach tcp://127.0.0.1:10001/ \
            --speed=100 --min-speed=100 --opengl=no &
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$LINK_URL" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        open "$LINK_URL" >/dev/null 2>&1 &
    fi
} &

docker start -ai "$(docker compose ps -a -q browser)"
