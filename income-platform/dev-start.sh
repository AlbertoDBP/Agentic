#!/usr/bin/env bash
# dev-start.sh — Start backend services locally for frontend live-data testing
# Usage: ./dev-start.sh [stop|status]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/venv/bin"
UVICORN="$VENV/uvicorn"
LOG_DIR="$ROOT/logs/dev"
PID_DIR="$ROOT/logs/dev/pids"
ENV_FILE="$ROOT/.env"

mkdir -p "$LOG_DIR" "$PID_DIR"

# Load .env safely (handles special chars, URLs with @, etc.)
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and blank lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    export "$line" 2>/dev/null || true
  done < "$ENV_FILE"
fi

# Override Docker hostnames → localhost for local dev
export AGENT04_URL="http://localhost:8004"
export AGENT05_URL="http://localhost:8005"
export AGENT06_URL="http://localhost:8006"
export AGENT07_URL="http://localhost:8007"
export INCOME_SCORING_URL="http://localhost:8003"
export ASSET_CLASSIFICATION_SERVICE_URL="http://localhost:8004"
export MARKET_DATA_SERVICE_URL="http://localhost:8001"

stop_services() {
  echo "Stopping services..."
  for pid_file in "$PID_DIR"/*.pid; do
    [ -f "$pid_file" ] || continue
    pid=$(cat "$pid_file")
    name=$(basename "$pid_file" .pid)
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "  Stopped $name (pid $pid)"
    fi
    rm -f "$pid_file"
  done
  echo "Done."
  exit 0
}

status_services() {
  echo "Service status:"
  for spec in "market-data:8001" "income-scoring:8003" "classification:8004" "tax:8005" "scenario:8006" "scanner:8007" "admin-panel:8100" "frontend:3000"; do
    name="${spec%%:*}"
    port="${spec##*:}"
    pid_file="$PID_DIR/${name}.pid"
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" 2>/dev/null || echo "---")
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "  RUNNING  $name (:$port) HTTP $http_code"
    else
      echo "  STOPPED  $name (:$port)"
    fi
  done
  exit 0
}

start_service() {
  local name="$1"
  local dir="$2"
  local module="$3"
  local port="$4"
  local extra_pythonpath="${5:-}"

  local pid_file="$PID_DIR/${name}.pid"
  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "  $name already running (pid $(cat "$pid_file"))"
    return
  fi

  local pypath="$ROOT/$dir"
  [ -n "$extra_pythonpath" ] && pypath="$pypath:$ROOT/$extra_pythonpath"

  pushd "$ROOT/$dir" > /dev/null
  PYTHONPATH="$pypath" "$UVICORN" "$module" --host 0.0.0.0 --port "$port" \
    > "$LOG_DIR/${name}.log" 2>&1 &
  local pid=$!
  echo $pid > "$pid_file"
  popd > /dev/null
  echo "  Started $name on :$port (pid $pid)"
}

[ "${1:-}" = "stop" ]   && stop_services
[ "${1:-}" = "status" ] && status_services

echo "Starting Income Platform backend services for local dev..."
echo ""

# Market Data (8001)
start_service "market-data"    "src/market-data-service"           "main:app"      8001

# Income Scoring (8003)
start_service "income-scoring" "src/income-scoring-service"        "app.main:app"  8003

# Asset Classification (8004) — needs shared/ in PYTHONPATH
start_service "classification" "src/asset-classification-service"  "app.main:app"  8004 "src"

# Tax Optimization (8005)
start_service "tax"            "src/tax-optimization-service"      "app.main:app"  8005

# Scenario Simulation (8006)
start_service "scenario"       "src/scenario-simulation-service"   "app.main:app"  8006

# Opportunity Scanner (8007)
start_service "scanner"        "src/opportunity-scanner-service"   "app.main:app"  8007

# Admin Panel (8100)
start_service "admin-panel"    "src/admin-panel"                   "app.main:app"  8100

echo ""
echo "Waiting for services to boot..."
sleep 4

echo ""
echo "Health checks:"
for spec in "market-data:8001" "income-scoring:8003" "classification:8004" "tax:8005" "scenario:8006" "scanner:8007" "admin-panel:8100"; do
  name="${spec%%:*}"
  port="${spec##*:}"
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" 2>/dev/null || echo "ERR")
  if [ "$http_code" = "200" ]; then
    echo "  OK  $name (:$port)"
  else
    echo "  ERR $name (:$port) HTTP $http_code — check logs/dev/${name}.log"
  fi
done

echo ""
echo "Logs:   tail -f logs/dev/<service>.log"
echo "Stop:   ./dev-start.sh stop"
echo "Status: ./dev-start.sh status"
echo ""
echo "Frontend: cd src/frontend && npm run dev"
echo "          open http://localhost:3000"
