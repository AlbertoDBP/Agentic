#!/usr/bin/env bash
#
# Nightly backup of the self-hosted Postgres (income_platform) running in the
# `postgres` compose container on legato. Replaces DO managed-Postgres backups.
#
# Install via cron (see documentation/deployment/migrate-do-postgres-to-self-hosted.md §9):
#   15 3 * * * /opt/Agentic/income-platform/infra/postgres/backup.sh >> /var/log/pg_backup.log 2>&1
#
set -euo pipefail

COMPOSE_DIR="/opt/Agentic/income-platform"
BACKUP_DIR="/opt/backups"
DB_USER="dbpmanager"
DB_NAME="income_platform"
RETENTION_DAYS=14

# Off-box target — UNCOMMENT and configure one. A backup on the same droplet does
# NOT survive a droplet loss, so this step is what actually protects the data.
#   OFFSITE_CMD=(rclone copy "$OUT" "spaces:income-platform-backups/postgres/")
#   OFFSITE_CMD=(aws s3 cp "$OUT" "s3://income-platform-backups/postgres/")
OFFSITE_CMD=()

mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/income_platform_${TS}.dump"

echo "[$(date -Is)] Starting pg_dump -> ${OUT}"
docker compose -f "${COMPOSE_DIR}/docker-compose.yml" exec -T postgres \
  pg_dump --no-owner --no-privileges -Fc -U "${DB_USER}" "${DB_NAME}" > "${OUT}"

# Fail loudly if the dump is suspiciously small (e.g. auth failure produced an empty file)
SIZE="$(stat -c%s "${OUT}" 2>/dev/null || stat -f%z "${OUT}")"
if [ "${SIZE}" -lt 100000 ]; then
  echo "[$(date -Is)] ERROR: dump is only ${SIZE} bytes — aborting, NOT pruning old backups." >&2
  exit 1
fi
echo "[$(date -Is)] Dump OK (${SIZE} bytes)"

# Off-box copy (if configured)
if [ "${#OFFSITE_CMD[@]}" -gt 0 ]; then
  echo "[$(date -Is)] Copying off-box: ${OFFSITE_CMD[*]}"
  "${OFFSITE_CMD[@]}"
else
  echo "[$(date -Is)] WARNING: no OFFSITE_CMD configured — backup is local-only." >&2
fi

# Prune local copies older than retention window (only after a verified-good dump)
find "${BACKUP_DIR}" -name 'income_platform_*.dump' -mtime "+${RETENTION_DAYS}" -delete
echo "[$(date -Is)] Done. Local retention: ${RETENTION_DAYS} days."
