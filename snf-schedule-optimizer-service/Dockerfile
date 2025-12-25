FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


# Set environment variables
# Ensure uv doesn't try to create a venv inside the container
# Optimization: Don't cache downloaded packages in the image layers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1


WORKDIR /app

# Install system dependencies for psycopg2 and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    build-essential \
    git \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 4. Install python dependencies
# Using uv sync if you have pyproject.toml/uv.lock,
# or uv pip install if you are still using requirements.txt
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and scripts
COPY src ./src
#COPY scripts ./scripts
#RUN chmod +x scripts/*.sh

# Default port for the API
EXPOSE 8000

# While Docker Compose usually overrides this, having a default CMD is best practice.
# Direct python calls are preferred for production-like images since 'uv sync'
# Direct python calls are preferred for production-like images since 'uv sync'
# has already populated the system site-packages.
#  python located in /app/.venv/bin (from PATH)
CMD ["python", "src/snf_schedule_optimizer/api/main.py"]