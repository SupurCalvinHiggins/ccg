FROM debian:bookworm-slim
ARG DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates wget \
    && rm -rf /var/lib/apt/lists/* \
    && wget -O /usr/share/keyrings/xpra.asc https://xpra.org/xpra.asc \
    && wget -O /etc/apt/sources.list.d/xpra.sources \
        https://raw.githubusercontent.com/Xpra-org/xpra/master/packaging/repos/bookworm/xpra.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium gocryptfs fuse3 \
        xvfb xpra xpra-x11 xpra-html5 libjs-jquery libjs-jquery-ui \
        xauth dbus-x11 python3-dbus python3-pil python3-xdg \
        netcat-openbsd fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /usr/sbin/nologin chromium

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod 755 /entrypoint.sh

USER 1000:1000
ENTRYPOINT ["/entrypoint.sh"]
