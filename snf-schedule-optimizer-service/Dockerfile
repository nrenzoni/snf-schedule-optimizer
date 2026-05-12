FROM node:24-bookworm-slim AS buf-builder

WORKDIR /workspace/proto

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    && rm -rf /var/lib/apt/lists/*

COPY proto/package.json /workspace/proto/package.json
COPY proto/buf.gen.yaml /workspace/proto/buf.gen.yaml
COPY proto/buf.yaml /workspace/proto/buf.yaml
COPY proto/post_generate_fix_imports.py /workspace/proto/post_generate_fix_imports.py
COPY proto/scheduling /workspace/proto/scheduling

RUN mkdir -p /workspace/snf-schedule-optimizer-service/src/snf_schedule_optimizer/generated /workspace/snf-schedule-optimizer-ui/gen

RUN corepack enable && npm install
RUN npx buf generate && python3 post_generate_fix_imports.py

FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=buf-builder /workspace /workspace

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gcc \
    git \
    libpq-dev \
    python3 \
    && rm -rf /var/lib/apt/lists/*

COPY snf-schedule-optimizer-service/pyproject.toml ./pyproject.toml
COPY snf-schedule-optimizer-service/uv.lock ./uv.lock
RUN uv sync --frozen --no-install-project --no-dev

COPY snf-schedule-optimizer-service/src ./src

RUN rm -rf src/snf_schedule_optimizer/generated/* && \
    cp -r /workspace/snf-schedule-optimizer-service/src/snf_schedule_optimizer/generated/. /app/src/snf_schedule_optimizer/generated/

FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    coinor-cbc \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8000

CMD ["python", "-m", "snf_schedule_optimizer.api.main"]
