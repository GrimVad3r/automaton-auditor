# Multi-stage Dockerfile for production deployment

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (pinned)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv==0.10.0

# Copy lock and metadata first for deterministic dependency layer caching
COPY pyproject.toml uv.lock README.md ./

# Install only locked runtime dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 auditor && \
    mkdir -p /app/logs /app/audit && \
    chown -R auditor:auditor /app

# Copy locked virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=auditor:auditor . .

# Ensure runtime uses the locked environment
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER auditor

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src; print('OK')" || exit 1

# Default command
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]

# Example usage:
# docker build -t automaton-auditor .
# docker run -v $(pwd)/.env:/app/.env automaton-auditor audit <repo-url> <pdf-path>
