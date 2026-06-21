# API container for the cloud deployment (Render).
# Torch-free: production uses the hosted OpenAI embedder, so `--no-dev` skips
# sentence-transformers. Result is a small (~150-200MB) image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PORT=8000
EXPOSE 8000

# Render (and most PaaS) inject $PORT.
CMD ["sh", "-c", "uv run --no-dev uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
