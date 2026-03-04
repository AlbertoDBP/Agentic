FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY src/asset-classification-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/asset-classification-service/ .
COPY src/shared/ ./shared/

ENV PYTHONPATH=/app

EXPOSE 8004

CMD ["sh", "-c", "python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8004"]
