FROM debian:stable-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    gocryptfs \
    fuse3 \
    xvfb \
    fluxbox \
    x11vnc \
    websockify \
    novnc \
    fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 -s /usr/sbin/nologin chromium

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER 1000:1000
ENTRYPOINT ["/entrypoint.sh"]
