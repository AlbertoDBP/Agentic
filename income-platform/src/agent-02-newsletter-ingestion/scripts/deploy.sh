#!/bin/bash
# Agent 02 — Newsletter Ingestion Service
# DigitalOcean Deployment Script
#
# Usage (run from DO droplet):
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --skip-migrate    # skip DB migration (re-deploys only)
#   ./scripts/deploy.sh --skip-nginx      # skip nginx reload
#
# Prerequisites on droplet:
#   - Docker installed
#   - Git repo cloned at ~/Agentic
#   - .env file present in service directory
#   - Nginx configured with agent-02.conf location block

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SERVICE_NAME="agent-02-newsletter-ingestion"
SERVICE_DIR="$HOME/Agentic/income-platform/src/agent-02-newsletter-ingestion"
CONTAINER_NAME="agent-02-newsletter-ingestion"
PORT=8002
SKIP_MIGRATE=false
SKIP_NGINX=false

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case $arg in
    --skip-migrate) SKIP_MIGRATE=true ;;
    --skip-nginx)   SKIP_NGINX=true ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
log "=== Agent 02 Deployment ==="
log "Service dir: $SERVICE_DIR"

[ -d "$SERVICE_DIR" ]     || fail "Service directory not found: $SERVICE_DIR"
[ -f "$SERVICE_DIR/.env" ] || fail ".env file missing — copy from .env.production.example and fill in values"

cd "$SERVICE_DIR"

# ── Pull latest code ──────────────────────────────────────────────────────────
log "Pulling latest from GitHub..."
cd "$HOME/Agentic"
git pull origin main
cd "$SERVICE_DIR"
log "✅ Code up to date"

# ── Build Docker image ────────────────────────────────────────────────────────
log "Building Docker image..."
docker build -t "$SERVICE_NAME:latest" . || fail "Docker build failed"
log "✅ Image built: $SERVICE_NAME:latest"

# ── Run DB migration ──────────────────────────────────────────────────────────
if [ "$SKIP_MIGRATE" = false ]; then
  log "Running database migration..."
  docker run --rm \
    --env-file "$SERVICE_DIR/.env" \
    "$SERVICE_NAME:latest" \
    python scripts/migrate.py \
    || fail "Migration failed"
  log "✅ Migration complete"
else
  log "⏭  Skipping migration (--skip-migrate)"
fi

# ── Stop existing container ───────────────────────────────────────────────────
if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
  log "Stopping existing container..."
  docker stop "$CONTAINER_NAME"
  docker rm "$CONTAINER_NAME"
  log "✅ Old container removed"
fi

# ── Start new container ───────────────────────────────────────────────────────
log "Starting container on port $PORT..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --env-file "$SERVICE_DIR/.env" \
  -p "127.0.0.1:$PORT:$PORT" \
  "$SERVICE_NAME:latest" \
  || fail "Container start failed"

log "✅ Container started: $CONTAINER_NAME"

# ── Wait for health check ─────────────────────────────────────────────────────
log "Waiting for service to become healthy..."
RETRIES=12
until curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ $RETRIES -eq 0 ]; then
    log "Health check failed — showing container logs:"
    docker logs --tail 30 "$CONTAINER_NAME"
    fail "Service failed to become healthy"
  fi
  sleep 5
done
log "✅ Service healthy at http://localhost:$PORT/health"

# ── Reload Nginx ──────────────────────────────────────────────────────────────
if [ "$SKIP_NGINX" = false ]; then
  log "Reloading Nginx..."
  sudo nginx -t && sudo systemctl reload nginx \
    || fail "Nginx reload failed — check config"
  log "✅ Nginx reloaded"
else
  log "⏭  Skipping Nginx reload (--skip-nginx)"
fi

# ── Register Prefect schedules ────────────────────────────────────────────────
log "Registering Prefect flow schedules..."
docker exec "$CONTAINER_NAME" python scripts/prefect_schedule.py \
  || log "⚠️  Prefect schedule registration failed — run manually if needed"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
log "=== Deployment Complete ==="
log "Service:   $SERVICE_NAME"
log "Container: $CONTAINER_NAME"
log "Port:      $PORT"
log "Health:    http://localhost:$PORT/health"
log "Docs:      http://localhost:$PORT/docs"
echo ""
log "Useful commands:"
log "  docker logs -f $CONTAINER_NAME"
log "  docker exec -it $CONTAINER_NAME /bin/bash"
log "  curl http://localhost:$PORT/health"
