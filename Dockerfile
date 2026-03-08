# --- Build with uv ---
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies via uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

# App files
COPY main.py models.py ./
COPY static/ ./static/

# Default data dir (Fly.io'da volume mount eder, lokalde boş kalır)
RUN mkdir -p /data

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
