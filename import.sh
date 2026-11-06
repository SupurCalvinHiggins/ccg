#!/bin/sh
# Copy one or more files into the sandboxed browser's encrypted data volume,
# then (after confirming) securely delete the originals from this machine.
# The browser must already be running (./start.sh).
#
#   ./import.sh interview_alice.csv interview_bob.csv
#
set -eu
cd "$(dirname "$0")"

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <file> [file...]" >&2
    exit 1
fi

for f in "$@"; do
    [ -f "$f" ] || { echo "not a file: $f" >&2; exit 1; }
done

ID="$(docker ps --filter "name=browser" --format '{{.ID}}' | head -n1)"
if [ -z "$ID" ]; then
    echo "no running 'browser' container found -- start it with ./start.sh first" >&2
    exit 1
fi

echo "Copying into the sandboxed browser's encrypted volume:"
for f in "$@"; do
    name=$(basename "$f")
    echo "  $f -> browser:/data/$name"
    # Not `docker cp`: some Docker versions refuse to copy into a container
    # with read_only:true regardless of the destination being on a writable
    # mount. `docker exec` isn't subject to that check.
    docker exec -i "$ID" sh -c "cat > '/data/$name'" < "$f"
done

echo
printf "Delete the original file(s) from this machine now? [y/N] "
read -r REPLY
case "$REPLY" in
    [yY] | [yY][eE][sS]) ;;
    *)
        echo "Leaving original files in place."
        exit 0
        ;;
esac

if command -v shred >/dev/null 2>&1; then
    for f in "$@"; do
        shred -u -z -n 3 "$f"
        echo "  securely deleted $f"
    done
else
    echo "warning: 'shred' isn't available here -- falling back to a plain delete" >&2
    echo "(no overwrite guarantee; note shred itself gives no strong guarantee on" >&2
    echo "SSDs or journaled/copy-on-write filesystems either)." >&2
    for f in "$@"; do
        rm -f "$f"
        echo "  deleted $f"
    done
fi
