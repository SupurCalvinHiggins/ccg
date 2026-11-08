# ccg

A (vibe-coded) tool to visualize code co-occurence graphs.

## Overview

If you want to understand your codebook's global structure and you have:
1. Dozens of coded interview transcripts
1. Thousands of coded quotes
1. Hundreds of codes
code co-occurence graphs (CCGs) may help.

In codebooks, transitive relationships like `A~B` and `B~C` so `A~C` are implict. Although code `A`'s description may mention code `B`, and code `B`'s description may mention code `C`, noticing the relationship between `A` and `C` through `B` requires additional effort. With large datasets, manually identifying higher-order relationships becomes intractable: if $$n$$ is the codebook size, the number of potential relationships is $$2^n$$. Even the number of potential second-order relationships -- $\frac{n^2}{2} - \frac{n}{2}$$ -- quickly becomes infeasible. CCGs solve this problem by visualizing "reasonable" higher-order relationships between codes. Researchers can then analyze this smaller set of candidate relationships.

## Installation

Do the following:
1. Install `git`.
1. Install `docker`.
1. Clone the repository with `git`.

## Usage

Do the following:
1. Export your codebook as a CSV file in this format:
```csv
participant,codes
<name>,<code1>|<code2>|...|<codeN>
```
1. Run `docker compose up -d --build` in the repository root to start the server.
1. Open `http://localhost:8080` in a web browser.
1. Upload your codebook CSV. **Your data will remain on your device. Your data will NOT be saved, copied or sent over the internet.**
1. When you are done, run `docker compose down` to stop the server.

TODO: bundle browser into container. lockdown network. preload JS libraries.

TODO: VNC path (compose.vnc.yaml) runs x11vnc with -nopw on loopback-only 127.0.0.1:6080 -- any other local account on a shared machine can connect with no credentials, add a VNC password.

TODO: X11 mode shares the host's real X11 session (no per-app isolation) -- a compromised sandboxed browser could snoop other windows' keystrokes/clipboard; VNC mode (private Xvfb) doesn't have this exposure.

TODO: tmpfs-backed paths (chromium profile, numba cache, gocryptfs's /data mountpoint) can still be paged to host swap under memory pressure if the host has swap enabled -- disable swap or use encrypted swap.

TODO: `docker cp <file> browser:/data/` puts the filename in the host shell's history -- use generic filenames if they might be participant-identifying.

## TODO: README updates needed for the Xpra swap

The remote-display stack changed from X11 socket passthrough / `Xvfb + fluxbox + x11vnc + websockify + noVNC` to a single `xpra` server, and `compose.vnc.yaml`/`compose.x11.yaml` were merged into `compose.yml`, used on every OS. The following needs updating above (left as-is for you to edit):

- Usage still says to run `docker compose up -d --build`, open `http://localhost:8080`, and `docker compose down`. That no longer works: the `proxy` service is gone, and the browser container needs an interactive tty for the passphrase. Use `./start.sh` (Linux/Mac) or `./start.ps1` (Windows) instead; closing the browser window stops everything.
- Document installing the native **Xpra client** (Linux/Mac/Windows) as the recommended way to connect: `start.sh`/`start.ps1` detect it and attach automatically. Without it, they open `http://127.0.0.1:10001/` (Xpra's HTML5 client) in the default browser.
- The VNC `-nopw` TODO and the X11-snooping TODO are obsolete (VNC and X11 passthrough are gone). Replace them with: Xpra's port on 127.0.0.1:10001 has no authentication by choice, so other local accounts on a shared machine could attach.
- Non-pixel channels left on: clipboard (both directions) and window titles. File transfer, open-url, printing and audio are off.
- The browser container always keeps a Docker log (json-file) so the start scripts can detect when it's ready. It holds only the banner/ready text, and it's deleted with the container on `down`.
- The `proxy` service (host `localhost:8080` → api) was removed, because it exposed api's last result (`/api/status`) to anything on the host.
- `DEBUG=1` shows the suppressed build/container logs (troubleshooting).
- Display tuning for speed over sharpness (blur while moving is expected): the server uses `--refresh-rate=144 --video-encoders=none --encodings=jpeg,rgb` and Chromium runs with `--disable-frame-rate-limit` (`browser/entrypoint.sh`). The start scripts attach the native client with `--speed=100 --min-speed=100`.
- Known limit: dragging the graph tops out around 60 fps. The Xpra client forwards mouse movement at roughly 85 events/s, and Chromium merges them into about one redraw per frame. Panning is limited by Xpra's encoding instead.
- With the frame-rate limit off, Chromium renders as fast as it can while the graph animates, so expect high CPU use during layout and dragging.
