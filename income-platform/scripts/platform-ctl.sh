#!/usr/bin/env bash
# ────────────────────────────────────────────────────────
# Income Platform — Management CLI
# Usage: bash scripts/platform-ctl.sh <command> [args]
# ────────────────────────────────────────────────────────
set -euo pipefail

BASE="${BASE_URL:-http://localhost}"

# ── Service Registry ──
# Format: "num:port:container:label"
SERVICES=(
  "01:8001:market-data-service:Market Data"
  "02:8002:agent-02-newsletter-ingestion:Newsletter"
  "03:8003:agent-03-income-scoring:Income Scoring"
  "04:8004:agent-04-asset-classification:Classification"
  "05:8005:tax-optimization-service:Tax Optimization"
  "06:8006:agent-06-scenario-simulation:Simulation"
  "07:8007:agent-07-opportunity-scanner:Scanner"
  "08:8008:agent-08-rebalancing:Rebalancing"
  "09:8009:agent-09-income-projection:Projection"
  "10:8010:agent-10-nav-monitor:NAV Monitor"
  "11:8011:agent-11-smart-alert:Smart Alert"
  "12:8012:agent-12-proposal:Proposal"
  "99:8099:scheduler:Scheduler"
  "00:8100:admin-panel:Admin Panel"
)

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── JWT Token ──
_token() {
  docker exec agent-03-income-scoring python3 -c "
import jwt, time, os
print(jwt.encode({'sub':'admin','iat':int(time.time()),'exp':int(time.time())+3600}, os.environ['JWT_SECRET'], algorithm='HS256'))
" 2>/dev/null
}

_auth_header() {
  echo "Authorization: Bearer $(_token)"
}

# ── Lookup helpers ──
_find_service() {
  local num="$1"
  for svc in "${SERVICES[@]}"; do
    IFS=: read -r snum sport scontainer slabel <<< "$svc"
    if [ "$snum" = "$num" ]; then
      echo "$sport:$scontainer:$slabel"
      return 0
    fi
  done
  echo ""
  return 1
}

# ═══════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════

cmd_status() {
  echo -e "${BOLD}═══════════════════════════════════════════${NC}"
  echo -e "${BOLD}  Income Platform — Service Status${NC}"
  echo -e "${BOLD}═══════════════════════════════════════════${NC}"
  echo ""
  printf "  %-4s %-22s %-6s %-10s %s\n" "NUM" "SERVICE" "PORT" "STATUS" "TIME"
  printf "  %-4s %-22s %-6s %-10s %s\n" "───" "─────────────────────" "────" "────────" "────"

  for svc in "${SERVICES[@]}"; do
    IFS=: read -r snum sport scontainer slabel <<< "$svc"
    START=$(date +%s%N 2>/dev/null || python3 -c "import time; print(int(time.time()*1e9))")
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$BASE:$sport/health" 2>/dev/null || echo "000")
    END=$(date +%s%N 2>/dev/null || python3 -c "import time; print(int(time.time()*1e9))")
    MS=$(( (END - START) / 1000000 ))

    if [ "$HTTP_CODE" = "200" ]; then
      printf "  %-4s %-22s %-6s ${GREEN}%-10s${NC} %sms\n" "$snum" "$slabel" "$sport" "healthy" "$MS"
    else
      printf "  %-4s %-22s %-6s ${RED}%-10s${NC} %sms\n" "$snum" "$slabel" "$sport" "DOWN($HTTP_CODE)" "$MS"
    fi
  done
  echo ""
}

cmd_logs() {
  local num="${1:-}"
  local lines="${2:-100}"
  if [ -z "$num" ]; then
    echo "Usage: platform-ctl.sh logs <agent-num> [lines]"
    echo "  Example: platform-ctl.sh logs 02 50"
    exit 1
  fi
  num=$(printf '%02d' "$num" 2>/dev/null || echo "$num")
  local info
  info=$(_find_service "$num") || { echo "Unknown agent: $num"; exit 1; }
  IFS=: read -r port container label <<< "$info"
  echo -e "${CYAN}Logs for $label ($container) — last $lines lines${NC}"
  echo "────────────────────────────────────────"
  docker logs --tail "$lines" "$container" 2>&1
}

cmd_restart() {
  local num="${1:-}"
  if [ -z "$num" ]; then
    echo "Usage: platform-ctl.sh restart <agent-num>"
    exit 1
  fi
  num=$(printf '%02d' "$num" 2>/dev/null || echo "$num")
  local info
  info=$(_find_service "$num") || { echo "Unknown agent: $num"; exit 1; }
  IFS=: read -r port container label <<< "$info"
  echo -e "${YELLOW}Restarting $label ($container)...${NC}"
  docker restart "$container"
  echo -e "${GREEN}Done.${NC}"
}

cmd_jobs() {
  echo -e "${BOLD}Scheduler Jobs${NC}"
  echo "────────────────────────────────────────"
  curl -s "$BASE:8099/jobs" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for j in data.get('jobs', []):
    nxt = j.get('next_run', 'N/A')
    if nxt and nxt != 'N/A':
        nxt = nxt[:19].replace('T', ' ')
    print(f\"  {j['id']:<25s} next: {nxt}\")
    print(f\"    {j.get('name', '')}\")
print(f\"\n  Total: {data.get('count', 0)} jobs\")
" 2>/dev/null || echo "  Scheduler not responding"
}

cmd_trigger() {
  local job_id="${1:-}"
  if [ -z "$job_id" ]; then
    echo "Usage: platform-ctl.sh trigger <job-id>"
    echo "  Available: market-data-refresh, newsletter-harvest, score-portfolio,"
    echo "             classify-new, opportunity-scan, nav-monitor-scan, smart-alert-scan"
    exit 1
  fi
  echo -e "${YELLOW}Triggering job: $job_id${NC}"
  curl -s -X POST "$BASE:8099/jobs/$job_id/run" 2>/dev/null | python3 -m json.tool
}

cmd_db_stats() {
  echo -e "${BOLD}Database Table Stats (platform_shared)${NC}"
  echo "────────────────────────────────────────"
  docker exec agent-03-income-scoring python3 -c "
import os, asyncio, asyncpg
async def stats():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'].split('?')[0], ssl='require')
    rows = await conn.fetch('''
        SELECT relname AS table_name, n_live_tup AS row_count
        FROM pg_stat_user_tables
        WHERE schemaname = 'platform_shared'
        ORDER BY n_live_tup DESC
    ''')
    for r in rows:
        print(f\"  {r['table_name']:<35s} {r['row_count']:>8,d} rows\")
    if not rows:
        print('  No tables found')
    await conn.close()
asyncio.run(stats())
" 2>/dev/null || echo "  Could not connect to database"
}

cmd_portfolio() {
  echo -e "${BOLD}Portfolio Summary${NC}"
  echo "────────────────────────────────────────"
  docker exec agent-03-income-scoring python3 -c "
import os, asyncio, asyncpg
async def summary():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'].split('?')[0], ssl='require')
    row = await conn.fetchrow('''
        SELECT
            COUNT(*) as positions,
            COALESCE(SUM(current_value), 0) as total_value,
            COALESCE(SUM(annual_income), 0) as annual_income,
            COALESCE(AVG(yield_on_cost), 0) as avg_yoc
        FROM platform_shared.positions
        WHERE status = 'ACTIVE'
    ''')
    print(f\"  Positions:     {row['positions']}\")
    print(f\"  Total Value:   \${row['total_value']:,.2f}\")
    print(f\"  Annual Income: \${row['annual_income']:,.2f}\")
    print(f\"  Avg YoC:       {row['avg_yoc']:.2%}\")
    print()
    # Asset allocation
    rows = await conn.fetch('''
        SELECT COALESCE(s.asset_type, 'Unknown') as asset_type,
               COUNT(*) as count,
               COALESCE(SUM(p.current_value), 0) as value
        FROM platform_shared.positions p
        LEFT JOIN platform_shared.securities s ON p.symbol = s.symbol
        WHERE p.status = 'ACTIVE'
        GROUP BY s.asset_type
        ORDER BY value DESC
    ''')
    if rows:
        print('  Asset Allocation:')
        for r in rows:
            print(f\"    {r['asset_type'] or 'Unknown':<20s} {r['count']:>3d} positions  \${r['value']:>12,.2f}\")
    await conn.close()
asyncio.run(summary())
" 2>/dev/null || echo "  Could not connect to database"
}

cmd_analysts() {
  echo -e "${BOLD}Registered Analysts${NC}"
  echo "────────────────────────────────────────"
  AUTH=$(_auth_header)
  curl -s -H "$AUTH" "$BASE:8002/analysts" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
analysts = data if isinstance(data, list) else data.get('analysts', [])
for a in analysts:
    name = a.get('display_name', 'Unknown')
    articles = a.get('article_count', 0)
    last = a.get('last_article_fetched_at', 'never')
    if last and last != 'never':
        last = last[:19].replace('T', ' ')
    active = 'active' if a.get('is_active', True) else 'inactive'
    print(f\"  {name:<30s} {articles:>4d} articles  last: {last}  [{active}]\")
if not analysts:
    print('  No analysts registered')
" 2>/dev/null || echo "  Agent 02 not responding"
}

cmd_alerts() {
  AUTH=$(_auth_header)

  echo -e "${BOLD}NAV Alerts (Agent 10)${NC}"
  echo "────────────────────────────────────────"
  curl -s -H "$AUTH" "$BASE:8010/monitor/alerts" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
alerts = data if isinstance(data, list) else data.get('alerts', [])
for a in alerts:
    sym = a.get('symbol', '?')
    sev = a.get('severity', '?')
    typ = a.get('alert_type', '?')
    status = a.get('status', '?')
    print(f\"  {sym:<10s} {sev:<10s} {typ:<25s} [{status}]\")
if not alerts:
    print('  No NAV alerts')
" 2>/dev/null || echo "  Agent 10 not responding"

  echo ""
  echo -e "${BOLD}Unified Alerts (Agent 11)${NC}"
  echo "────────────────────────────────────────"
  curl -s -H "$AUTH" "$BASE:8011/alerts" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
alerts = data if isinstance(data, list) else data.get('alerts', [])
for a in alerts:
    sym = a.get('symbol', '?')
    typ = a.get('alert_type', '?')
    status = a.get('status', '?')
    created = a.get('created_at', '')[:19].replace('T', ' ') if a.get('created_at') else ''
    print(f\"  {sym:<10s} {typ:<30s} [{status}]  {created}\")
if not alerts:
    print('  No unified alerts')
" 2>/dev/null || echo "  Agent 11 not responding"
}

cmd_help() {
  echo -e "${BOLD}Income Platform — Management CLI${NC}"
  echo ""
  echo "Usage: platform-ctl.sh <command> [args]"
  echo ""
  echo "Commands:"
  echo "  status              Health check all services"
  echo "  logs <num> [lines]  Tail logs for agent N (default 100 lines)"
  echo "  restart <num>       Restart agent N container"
  echo "  jobs                List scheduler jobs + next run times"
  echo "  trigger <job-id>    Trigger a scheduler job on demand"
  echo "  db-stats            Show table row counts"
  echo "  portfolio           Portfolio summary"
  echo "  analysts            List registered analysts"
  echo "  alerts              Show active alerts"
  echo "  help                Show this help"
  echo ""
  echo "Examples:"
  echo "  platform-ctl.sh status"
  echo "  platform-ctl.sh logs 02 50"
  echo "  platform-ctl.sh restart 07"
  echo "  platform-ctl.sh trigger market-data-refresh"
}

# ── Dispatch ──
CMD="${1:-help}"
shift || true

case "$CMD" in
  status)    cmd_status ;;
  logs)      cmd_logs "$@" ;;
  restart)   cmd_restart "$@" ;;
  jobs)      cmd_jobs ;;
  trigger)   cmd_trigger "$@" ;;
  db-stats)  cmd_db_stats ;;
  portfolio) cmd_portfolio ;;
  analysts)  cmd_analysts ;;
  alerts)    cmd_alerts ;;
  help|--help|-h) cmd_help ;;
  *) echo "Unknown command: $CMD"; cmd_help; exit 1 ;;
esac
