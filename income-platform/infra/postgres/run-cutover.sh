#!/usr/bin/env bash
#
# run-cutover.sh — one guided run of the DO -> legato cutover:
#   pre-flight -> stand up postgres+valkey -> restore DB -> flip services -> health-check
#
# Usage:
#   infra/postgres/run-cutover.sh [BUNDLE.tgz] [--dry-run] [--yes]
#     BUNDLE      bundle from export-bundle.sh; defaults to newest in /opt/backups
#     --dry-run   print every action, mutate nothing (pre-flight checks still run)
#     --yes       skip the final "proceed?" confirmation
#
# IMPORTANT
# - Edit .env to the self-hosted values BEFORE running (PG_HOST=postgres, PG_PORT=5432,
#   new PG_PASSWORD, PGBOUNCER_URL=...@pgbouncer..., REDIS_URL=redis://valkey:6379/0).
#   This script VALIDATES that and refuses if .env still points at DO. It does NOT edit
#   .env for you (it won't invent your rotated password).
# - It restores ONLY the database from the bundle — never the bundle's .env (that's the
#   OLD DO config). Your edited .env is left untouched.
# - DO is read-only throughout. Rollback = revert .env to the DO values and `compose up -d`.
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/Agentic/income-platform}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"
COMPOSE="docker compose -f ${REPO_DIR}/docker-compose.yml"
# Host ports to health-check after the flip (service -> port)
HEALTH_PORTS="${HEALTH_PORTS:-8001 8002 8003 8004 8013 8014 8100}"

DRY=0; ASSUME_YES=0; BUNDLE=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --yes)     ASSUME_YES=1 ;;
    *.tgz)     BUNDLE="$a" ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

c_ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
c_no(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
hdr(){ printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
# run: execute, or just print in dry-run
run(){ if [ "$DRY" = 1 ]; then printf '  [dry-run] %s\n' "$*"; else echo "  + $*"; "$@"; fi; }
envget(){ grep -E "^$1=" "${REPO_DIR}/.env" 2>/dev/null | head -1 | cut -d= -f2-; }
die(){ c_no "$1"; echo; echo "Aborted — nothing was changed." >&2; exit 1; }

cd "$REPO_DIR"

# ── Phase 0: pre-flight (read-only; runs in dry-run too) ─────────────────────
hdr "Phase 0 — pre-flight"
command -v docker >/dev/null || die "docker not found"
$COMPOSE version >/dev/null 2>&1 || die "'docker compose' not available"
c_ok "docker + compose present"

[ -f "${REPO_DIR}/.env" ] || die ".env not found in ${REPO_DIR}"
$COMPOSE config --services 2>/dev/null | grep -qx postgres || die "compose has no 'postgres' service — git pull the infra branch first"
$COMPOSE config --services 2>/dev/null | grep -qx valkey   || die "compose has no 'valkey' service — git pull the infra branch first"
c_ok "compose defines postgres + valkey"

# Validate .env was flipped to self-hosted (refuse if still DO)
PG_HOST_V="$(envget PG_HOST)"; PG_PORT_V="$(envget PG_PORT)"
PGB_V="$(envget PGBOUNCER_URL)"; REDIS_V="$(envget REDIS_URL)"
PG_USER="$(envget PG_USER)"; PG_DATABASE="$(envget PG_DATABASE)"; PG_PW="$(envget PG_PASSWORD)"
: "${PG_USER:=dbpmanager}"; : "${PG_DATABASE:=income_platform}"

case "$PG_HOST_V" in
  postgres) c_ok "PG_HOST=postgres" ;;
  *ondigitalocean.com|"") die "PG_HOST is '${PG_HOST_V:-<empty>}' — edit .env to PG_HOST=postgres before cutover" ;;
  *) c_no "PG_HOST='$PG_HOST_V' (expected 'postgres') — continuing, but verify"; ;;
esac
[ "${PG_PORT_V:-}" = "5432" ] || c_no "PG_PORT='${PG_PORT_V:-<empty>}' (expected 5432) — verify"
echo "$PGB_V"  | grep -q '@pgbouncer' || die "PGBOUNCER_URL must point at @pgbouncer (got: ${PGB_V:-<empty>})"
echo "$REDIS_V"| grep -Eq '//valkey|@valkey' || die "REDIS_URL must point at valkey (got: ${REDIS_V:-<empty>})"
c_ok "PGBOUNCER_URL -> pgbouncer, REDIS_URL -> valkey"
case "$PG_PW" in
  ""|CHANGE_ME|CHANGE_ME_ROTATED) die "PG_PASSWORD is unset/placeholder — set the NEW rotated password in .env" ;;
  *) c_ok "PG_PASSWORD is set (rotated)" ;;
esac

# Resolve bundle
[ -n "$BUNDLE" ] || BUNDLE="$(ls -t "${BACKUP_DIR}"/income_platform_export_*.tgz 2>/dev/null | head -1 || true)"
[ -n "$BUNDLE" ] && [ -f "$BUNDLE" ] || die "no bundle found (pass one, or place it in ${BACKUP_DIR})"
tar tzf "$BUNDLE" | grep -q '\.dump$' || die "bundle has no .dump member: $BUNDLE"
c_ok "bundle: $BUNDLE"

echo
echo "Plan:"
echo "  1) compose up -d postgres valkey   (stand up data services)"
echo "  2) restore DB-only from bundle into 'postgres' (.env untouched)"
echo "  3) verify restored table count"
echo "  4) compose up -d                   (flip all services onto new infra)"
echo "  5) health-check ports: $HEALTH_PORTS"
if [ "$DRY" = 1 ]; then echo; echo "(dry-run — stopping before any change)"; fi

if [ "$DRY" != 1 ] && [ "$ASSUME_YES" != 1 ]; then
  echo; read -r -p "Proceed with the cutover? [y/N] " ans
  case "$ans" in y|Y|yes) ;; *) die "user declined"; esac
fi

# ── Phase 1: stand up data services ─────────────────────────────────────────
hdr "Phase 1 — stand up postgres + valkey"
run $COMPOSE up -d postgres valkey
if [ "$DRY" != 1 ]; then
  echo -n "  waiting for postgres healthy "
  for i in $(seq 1 30); do
    s="$(docker inspect -f '{{.State.Health.Status}}' postgres 2>/dev/null || echo starting)"
    [ "$s" = healthy ] && { echo " ok"; break; }
    echo -n "."; sleep 3
    [ "$i" = 30 ] && die "postgres did not become healthy in time"
  done
  v="$(docker inspect -f '{{.State.Health.Status}}' valkey 2>/dev/null || echo none)"
  [ "$v" = healthy ] && c_ok "valkey healthy" || c_no "valkey health: $v (cache is optional; continuing)"
fi

# ── Phase 2: restore DB only (docker cp + pg_restore from file path) ─────────
hdr "Phase 2 — restore database (DB only; .env left as-is)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
if [ "$DRY" = 1 ]; then
  echo "  [dry-run] tar -xzf $(basename "$BUNDLE") -> dump; docker cp into postgres; pg_restore --clean --if-exists"
else
  tar -C "$WORK" -xzf "$BUNDLE"
  DUMP="$(find "$WORK" -name '*.dump' | head -1)"
  [ -n "$DUMP" ] || die "no .dump after extracting bundle"
  echo "  + extensions (idempotent)"
  docker exec -i postgres psql -U "$PG_USER" -d "$PG_DATABASE" \
    -c 'CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; CREATE EXTENSION IF NOT EXISTS pg_trgm;' >/dev/null
  echo "  + copy dump into container"
  docker cp "$DUMP" postgres:/tmp/cutover.dump
  echo "  + pg_restore"
  docker exec -i postgres pg_restore --no-owner --no-privileges --clean --if-exists \
    -U "$PG_USER" -d "$PG_DATABASE" /tmp/cutover.dump 2> "$WORK/restore.err" || true
  docker exec -i postgres rm -f /tmp/cutover.dump || true
  ERRS="$(grep -ci error "$WORK/restore.err" || true)"
  [ "${ERRS:-0}" -gt 0 ] && { echo "  pg_restore reported ${ERRS} error line(s):"; grep -i error "$WORK/restore.err" | head -10; }
fi

# ── Phase 3: verify restore ──────────────────────────────────────────────────
hdr "Phase 3 — verify restored data"
if [ "$DRY" = 1 ]; then
  echo "  [dry-run] count tables in postgres; require a healthy table count"
else
  TBLS="$(docker exec -i postgres psql -U "$PG_USER" -d "$PG_DATABASE" -At -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('platform_shared','public') AND table_type='BASE TABLE';" 2>/dev/null || echo 0)"
  echo "  restored base tables: ${TBLS:-0}"
  [ "${TBLS:-0}" -ge 50 ] && c_ok "restore looks complete" || die "only ${TBLS:-0} tables restored — review pg_restore errors above; DO is untouched, safe to retry"
fi

# ── Phase 4: flip all services ───────────────────────────────────────────────
hdr "Phase 4 — flip services onto new infra"
run $COMPOSE up -d

# ── Phase 5: health-check ────────────────────────────────────────────────────
hdr "Phase 5 — health checks"
if [ "$DRY" = 1 ]; then
  echo "  [dry-run] curl localhost:{$HEALTH_PORTS}/health"
else
  sleep 8
  fail=0
  for p in $HEALTH_PORTS; do
    if curl -fsS --max-time 5 "http://localhost:$p/health" >/dev/null 2>&1; then c_ok "port $p /health"; else c_no "port $p /health"; fail=1; fi
  done
  echo
  if [ "$fail" = 0 ]; then
    printf '\033[1;32mCutover complete.\033[0m All checked services healthy on self-hosted Postgres + Valkey.\n'
    echo "Keep the DO databases alive ~7 days, then destroy. Verify a real pgvector read before then."
  else
    printf '\033[1;33mCutover applied, but some health checks failed.\033[0m Inspect: %s logs <service>\n' "$COMPOSE"
    echo "Rollback if needed: revert .env to the DO values, then '$COMPOSE up -d'. DO data is intact."
  fi
fi
