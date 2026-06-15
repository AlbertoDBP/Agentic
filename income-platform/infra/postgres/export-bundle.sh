#!/usr/bin/env bash
#
# Export the platform's portable state into ONE file:
#   income_platform_export_<ts>.tgz  =  Postgres dump (-Fc)  +  .env
#
# Code is already in git, and Valkey is ephemeral cache (nothing to back up), so the
# database dump + .env is the complete data+secrets bundle. Rebuild anywhere with:
#   git clone … && infra/postgres/import-bundle.sh income_platform_export_<ts>.tgz
#
# Two source modes:
#   (default) dump from the local `postgres` compose container
#   (SOURCE_DSN set) dump from a remote DB — used for the initial DO -> legato move, e.g.
#     SOURCE_DSN="postgresql://dbpmanager:<DO_PASS>@income-platform-db-...ondigitalocean.com:25060/income_platform?sslmode=require" \
#       infra/postgres/export-bundle.sh
#
# ⚠️ The output contains BOTH the full database AND .env secrets — treat it like a password.
#    It is written chmod 600. For off-box storage, encrypt it (see ENCRYPT note at the end).
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/Agentic/income-platform}"
OUT_DIR="${OUT_DIR:-/opt/backups}"
DB_USER="${DB_USER:-dbpmanager}"
DB_NAME="${DB_NAME:-income_platform}"
PG_IMAGE="${PG_IMAGE:-pgvector/pgvector:pg16}"
SOURCE_DSN="${SOURCE_DSN:-}"          # empty = dump from local `postgres` container

TS="$(date +%Y%m%d_%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DUMP="$WORK/${DB_NAME}.dump"
BUNDLE="${OUT_DIR}/income_platform_export_${TS}.tgz"

mkdir -p "$OUT_DIR"
cd "$REPO_DIR"

echo "[$(date -Is)] Dumping database -> ${DUMP}"
if [ -n "$SOURCE_DSN" ]; then
  echo "  source: remote DSN (one-off ${PG_IMAGE} container)"
  docker run --rm -v "$WORK:/work" "$PG_IMAGE" \
    pg_dump --no-owner --no-privileges -Fc "$SOURCE_DSN" -f "/work/${DB_NAME}.dump"
else
  echo "  source: local 'postgres' compose container"
  docker compose -f "${REPO_DIR}/docker-compose.yml" exec -T postgres \
    pg_dump --no-owner --no-privileges -Fc -U "$DB_USER" "$DB_NAME" > "$DUMP"
fi

# Guard against an empty/failed dump (e.g. auth failure)
SIZE="$(stat -c%s "$DUMP" 2>/dev/null || stat -f%z "$DUMP")"
if [ "${SIZE}" -lt 100000 ]; then
  echo "[$(date -Is)] ERROR: dump is only ${SIZE} bytes — aborting." >&2
  exit 1
fi
echo "[$(date -Is)] Dump OK (${SIZE} bytes)"

# Stage .env alongside the dump (it is NOT in git, so it must travel in the bundle)
if [ -f "${REPO_DIR}/.env" ]; then
  cp "${REPO_DIR}/.env" "$WORK/.env"
  echo "[$(date -Is)] Included .env"
else
  echo "[$(date -Is)] WARNING: ${REPO_DIR}/.env not found — bundle will contain DB only." >&2
fi

# A manifest so the importer knows what it's looking at
cat > "$WORK/MANIFEST.txt" <<EOF
income-platform export bundle
created:   ${TS}
db_name:   ${DB_NAME}
db_user:   ${DB_USER}
dump_fmt:  pg_dump -Fc (custom; restore with pg_restore)
contains:  ${DB_NAME}.dump, .env, MANIFEST.txt
EOF

echo "[$(date -Is)] Packing -> ${BUNDLE}"
tar -C "$WORK" -czf "$BUNDLE" .
chmod 600 "$BUNDLE"

SHA="$(sha256sum "$BUNDLE" 2>/dev/null | awk '{print $1}' || shasum -a 256 "$BUNDLE" | awk '{print $1}')"
echo "[$(date -Is)] Done."
echo "  bundle: ${BUNDLE}"
echo "  size:   $(du -h "$BUNDLE" | awk '{print $1}')"
echo "  sha256: ${SHA}"
echo
echo "Off-box + encrypt (recommended — it contains secrets):"
echo "  gpg --symmetric --cipher-algo AES256 \"${BUNDLE}\"   # -> ${BUNDLE}.gpg"
echo "  rclone copy \"${BUNDLE}.gpg\" spaces:income-platform-backups/   # or aws s3 cp ..."
