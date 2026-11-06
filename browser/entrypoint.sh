#!/bin/sh
set -eu

# /volume is the host-mounted encrypted directory (ciphertext). /data is the
# decrypted view, created fresh in this container's own mount namespace. The
# passphrase is read interactively by gocryptfs itself, straight from this
# container's tty (stdin_open/tty must be set, and this container must be
# started with `docker start -ai`, not a detached `docker compose up -d`) --
# it never passes through this script, an env var, or a log.
mkdir -p /data
[ -f /volume/gocryptfs.conf ] || gocryptfs -init -q -scryptn 18 /volume
gocryptfs -nosyslog /volume /data
trap 'fusermount3 -u /data' EXIT

if [ "${DISPLAY_MODE:-x11}" = "vnc" ]; then
    export DISPLAY=:99
    mkdir -p -m 1777 /tmp/.X11-unix
    Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
    sleep 2
    fluxbox &
    sleep 1
    x11vnc -display :99 -forever -shared -nopw -localhost -xrandr -threads -wait 5 -defer 5 -quiet &
    websockify --web /usr/share/novnc 6080 localhost:5900 &
    sleep 1
fi

exec chromium --no-sandbox --disable-dev-shm-usage --disable-gpu \
    --user-data-dir=/tmp/chromium-profile \
    --app="${API_URL:-http://api:8080}"
