#!/bin/sh
set -eu

BAR='\033[1;36m'
TITLE='\033[1;97m'
LINK='\033[4;38;5;30m'
RESET='\033[0m'
LINK_URL='http://127.0.0.1:10001/'

quiet() {
    if [ "${DEBUG:-0}" = "1" ]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi
}

printf "\n${BAR}┃${RESET}  ${TITLE}Code Co-occurrence Graphs${RESET}\n"
printf "${BAR}┃${RESET}\n"

STEP=1
if [ ! -f /volume/gocryptfs.conf ]; then
    printf "${BAR}┃${RESET}  ${STEP}. Create your password below. Write it down: it cannot be recovered.\n"
    STEP=$((STEP + 1))
fi

printf "${BAR}┃${RESET}  ${STEP}. Enter your password below to unlock your data.\n"
STEP=$((STEP + 1))

printf "${BAR}┃${RESET}  ${STEP}. Once ready, the application will open automatically.\n"
STEP=$((STEP + 1))

printf "${BAR}┃${RESET}  ${STEP}. To stop, close the application.\n"
printf "${BAR}┃${RESET}\n\n"

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

export XDG_RUNTIME_DIR=/tmp/xdg
mkdir -m 700 -p "$XDG_RUNTIME_DIR"

# start.sh / start.ps1 watch this container's log for the "Code Co-occurrence Graphs is ready"
# line -- keep the text in sync with them.
(
    i=0
    while [ $i -lt 60 ]; do
        if nc -z 127.0.0.1 10000 2>/dev/null; then
            printf "\n${BAR}┃${RESET}  ${TITLE}Code Co-occurrence Graphs is ready${RESET}\n"
            if [ "${XPRA_CLIENT:-0}" != "1" ]; then
                printf "${BAR}┃${RESET}\n"
                printf "${BAR}┃${RESET}  Native xpra client not found - recommended for best performance.\n"
                printf "${BAR}┃${RESET}  ${LINK}${LINK_URL}${RESET}\n"
            fi
            printf "\n"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
) &

quiet xpra start :100 \
    --start-child="chromium --no-sandbox --disable-dev-shm-usage --disable-gpu --disable-frame-rate-limit --user-data-dir=/tmp/chromium-profile --app=${API_URL:-http://api:8080}" \
    --bind-tcp=0.0.0.0:10000 \
    --html=on \
    --daemon=no \
    --exit-with-children=yes \
    --clipboard=yes \
    --dpi=96 \
    --speaker=off \
    --microphone=off \
    --file-transfer=no \
    --open-url=no \
    --printing=no \
    --pulseaudio=no \
    --webcam=no \
    --notifications=no \
    --system-tray=no \
    --bell=no \
    --mdns=no \
    --refresh-rate=144 \
    --video-encoders=none \
    --encodings=jpeg,rgb \
    || true
