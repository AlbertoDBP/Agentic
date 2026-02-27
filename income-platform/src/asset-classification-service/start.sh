#!/bin/bash
# Start Agent 04 locally (development)
# Run from: src/asset-classification-service/

SERVICE_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$(cd "$SERVICE_DIR/.." && pwd)"

export PYTHONPATH="$SRC_DIR:$SERVICE_DIR"

echo "PYTHONPATH=$PYTHONPATH"
echo "Starting Agent 04 on port 8004..."

uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
