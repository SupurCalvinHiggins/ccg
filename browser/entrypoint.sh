#!/bin/sh
set -eu

BAR='\033[1;36m'
TITLE='\033[1;97m'
LINK='\033[4;38;5;30m'
RESET='\033[0m'
LINK_URL='http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=remote'
WINDOW_TITLE='^Code Co-occurrence Graph$'

printf "\n${BAR}┃${RESET}  ${TITLE}ccg sandboxed browser${RESET}\n"
printf "${BAR}┃${RESET}\n"

STEP=1
if [ ! -f /volume/gocryptfs.conf ]; then
    printf "${BAR}┃${RESET}  ${STEP}. Create your password below. Write it down: it cannot be recovered.\n"
    STEP=$((STEP + 1))
fi

printf "${BAR}┃${RESET}  ${STEP}. Enter your password below to unlock your data.\n"
STEP=$((STEP + 1))

if [ "${DISPLAY_MODE:-x11}" = "vnc" ]; then
    printf "${BAR}┃${RESET}  ${STEP}. A link will appear below once ready. Open it in your browser.\n"
else
    printf "${BAR}┃${RESET}  ${STEP}. Your browser window will open automatically.\n"
fi
STEP=$((STEP + 1))

printf "${BAR}┃${RESET}  ${STEP}. To stop, close the browser window.\n"
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

if command -v xdotool >/dev/null 2>&1; then
    (
        i=0
        while [ $i -lt 30 ]; do
            if xdotool search --name "$WINDOW_TITLE" >/dev/null 2>&1; then
                if [ "${DISPLAY_MODE:-x11}" = "vnc" ]; then
                    printf "\n${BAR}┃${RESET}  ${TITLE}ccg is ready${RESET}\n"
                    printf "${BAR}┃${RESET}\n"
                    printf "${BAR}┃${RESET}  Open this link:\n"
                    printf "${BAR}┃${RESET}     ${LINK}${LINK_URL}${RESET}\n\n"
                else
                    printf "\n${BAR}┃${RESET}  ${TITLE}ccg is ready${RESET}\n\n"
                fi
                break
            fi
            sleep 1
            i=$((i + 1))
        done
    ) &
elif [ "${DISPLAY_MODE:-x11}" = "vnc" ]; then
    printf "\n${BAR}┃${RESET}  Open this link:\n"
    printf "${BAR}┃${RESET}     ${LINK}${LINK_URL}${RESET}\n\n"
fi

exec chromium --no-sandbox --disable-dev-shm-usage --disable-gpu \
    --user-data-dir=/tmp/chromium-profile \
    --app="${API_URL:-http://api:8080}"
