FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependencies first (cached unless the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code
COPY . .
RUN uv sync --frozen --no-dev

# Runtime: same base Python, no uv, no build tooling
FROM python:3.13-slim
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=build --chown=65534:65534 /app /app
ENV NUMBA_CACHE_DIR=/numba-cache
USER 65534:65534
EXPOSE 8080
CMD ["python", "-m", "ccg.server", "--host", "0.0.0.0", "--port", "8080"]
