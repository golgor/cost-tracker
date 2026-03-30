# syntax=docker/dockerfile:1

# ============================================================
# Stage 1: Builder
# ============================================================
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Build-time optimizations
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install Python dependencies (layer-cached separately from app source)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# Install the project itself
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

# Download Tailwind CSS v4 standalone CLI and compile CSS
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) TAILWIND_BIN="tailwindcss-linux-x64" ;; \
        arm64) TAILWIND_BIN="tailwindcss-linux-arm64" ;; \
        *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/${TAILWIND_BIN}" \
        -o /usr/local/bin/tailwindcss && \
    chmod +x /usr/local/bin/tailwindcss && \
    tailwindcss \
        --input app/static/src/input.css \
        --output app/static/css/output.css \
        --minify

# ============================================================
# Stage 2: Production
# ============================================================
FROM python:3.14-slim-bookworm AS production

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Copy compiled CSS (no Node.js or Tailwind at runtime)
COPY --from=builder /app/app/static/css/output.css /app/app/static/css/output.css

RUN adduser --system --no-create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
