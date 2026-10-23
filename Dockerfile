# syntax=docker/dockerfile:1.7
# Multi-stage build. Runtime image contains no build tools, no cloud credentials and no client data.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Install dependencies first (cache layer), then the project.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra gcp --extra anthropic
COPY src ./src
COPY config ./config
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra gcp --extra anthropic

FROM python:3.12-slim-bookworm AS runtime
RUN groupadd -r app && useradd -r -g app -d /app app \
    && apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    READINESS_CONFIG_DIR=/app/config \
    READINESS_WORKSPACE_DIR=/tmp/readiness-workspace \
    PORT=8080
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"
CMD ["sh", "-c", "uvicorn readiness.api.app:app --host 0.0.0.0 --port ${PORT}"]
