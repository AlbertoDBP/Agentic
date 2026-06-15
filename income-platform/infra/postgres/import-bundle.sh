#!/usr/bin/env bash
#
# Import a bundle produced by export-bundle.sh into the local `postgres` container:
#   restores .env (backing up any existing one) and pg_restores the database.
#
# Usage:
#   infra/postgres/import-bundle.sh income_platform_export_<ts>.tgz [--force-env]
#
#   --force-env   overwrite an existing .env (a timestamped backup is always made first).
#                 Without it, an existing .env is left in place and the bundled copy is
#                 written to .env.imported for you to diff/merge manually.
#
# Prerequisites: the `postgres` container is up and healthy, and the target database
# (POSTGRES_DB) exists (the official image creates it on first boot).
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/Agentic/income-platform}"
DB_USER="${DB_USER:-dbpmanager}"
DB_NAME="${DB_NAME:-income_platform}"

BUNDLE="${1:-}"
FORCE_ENV="${2:-}"
if [ -z "$BUNDLE" ] || [ ! -f "$BUNDLE" ]; then
  echo "Usage: $0 <bundle.tgz> [--force-env]" >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
echo "[$(date -Is)] Extracting $(basename "$BUNDLE")"
tar -C "$WORK" -xzf "$BUNDLE"
[ -f "$WORK/MANIFEST.txt" ] && { echo "--- MANIFEST ---"; cat "$WORK/MANIFEST.txt"; echo "----------------"; }

DUMP="$WORK/${DB_NAME}.dump"
if [ ! -f "$DUMP" ]; then
  echo "[$(date -Is)] ERROR: ${DB_NAME}.dump not found in bundle." >&2
  exit 1
fi

# --- Restore .env -----------------------------------------------------------
if [ -f "$WORK/.env" ]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  if [ -f "${REPO_DIR}/.env" ]; then
    cp "${REPO_DIR}/.env" "${REPO_DIR}/.env.bak.${TS}"
    echo "[$(date -Is)] Backed up existing .env -> .env.bak.${TS}"
    if [ "$FORCE_ENV" = "--force-env" ]; then
      cp "$WORK/.env" "${REPO_DIR}/.env"
      echo "[$(date -Is)] Overwrote .env from bundle (--force-env)"
    else
      cp "$WORK/.env" "${REPO_DIR}/.env.imported"
      echo "[$(date -Is)] Existing .env kept. Bundled copy written to .env.imported — diff & merge manually."
    fi
  else
    cp "$WORK/.env" "${REPO_DIR}/.env"
    echo "[$(date -Is)] Installed .env from bundle"
  fi
else
  echo "[$(date -Is)] NOTE: bundle has no .env — leaving existing config untouched."
fi

# --- Restore database -------------------------------------------------------
echo "[$(date -Is)] Restoring database '${DB_NAME}' (pg_restore --clean --if-exists)"
docker compose -f "${REPO_DIR}/docker-compose.yml" exec -T postgres \
  pg_restore --no-owner --no-privileges --clean --if-exists \
  -U "$DB_USER" -d "$DB_NAME" < "$DUMP"

# --- Verify -----------------------------------------------------------------
echo "[$(date -Is)] Post-restore checks:"
docker compose -f "${REPO_DIR}/docker-compose.yml" exec -T postgres \
  psql -U "$DB_USER" -d "$DB_NAME" -c '\dx' \
  -c "SELECT count(*) AS tables FROM information_schema.tables WHERE table_schema='platform_shared';"

echo "[$(date -Is)] Import complete. Recreate services to pick up any .env changes:"
echo "  docker compose -f ${REPO_DIR}/docker-compose.yml up -d"
