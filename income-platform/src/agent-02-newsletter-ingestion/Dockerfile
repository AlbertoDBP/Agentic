# ── Stage 1: Builder ──────────────────────────────────────────────────────────
# Compile Python deps in a separate stage to keep final image lean
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --target /build/deps


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# Runtime system deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN adduser --disabled-password --gecos "" --uid 1001 appuser

WORKDIR /app

# Copy compiled deps from builder
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages/

# Copy application code
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8002

# Health check — /health returns 200 when DB + cache connected
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Production: 2 workers, structured JSON logging
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8002", \
     "--workers", "2", \
     "--log-level", "info", \
     "--no-access-log"]
