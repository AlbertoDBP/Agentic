# Stage 1: builder
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --target /build/deps

# Stage 2: runtime
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --gecos "" --uid 1001 appuser
WORKDIR /app
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages/
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 8014
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8014/health || exit 1
CMD ["python3", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8014", "--workers", "1", \
     "--log-level", "info", "--no-access-log"]
