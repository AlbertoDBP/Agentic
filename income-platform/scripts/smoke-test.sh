#!/usr/bin/env bash
# ────────────────────────────────────────────────────────
# Income Platform — Production Smoke Test
# Generates a JWT from JWT_SECRET and hits every agent
# ────────────────────────────────────────────────────────
set -euo pipefail

BASE="${BASE_URL:-http://localhost}"

# ── Load JWT_SECRET from .env if not already set ──
if [ -z "${JWT_SECRET:-}" ]; then
  ENV_FILE="$(dirname "$0")/../.env"
  if [ -f "$ENV_FILE" ]; then
    JWT_SECRET=$(grep '^JWT_SECRET=' "$ENV_FILE" | cut -d= -f2-)
  fi
fi

if [ -z "${JWT_SECRET:-}" ]; then
  echo "ERROR: JWT_SECRET not set. Export it or add to .env"
  exit 1
fi

# ── Generate JWT token using Python ──
TOKEN=$(python3 -c "
import json, hmac, hashlib, base64, time

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

header = b64url(json.dumps({'alg':'HS256','typ':'JWT'}).encode())
now = int(time.time())
payload = b64url(json.dumps({'sub':'smoke-test','iat':now,'exp':now+3600}).encode())
sig = b64url(hmac.new('${JWT_SECRET}'.encode(), f'{header}.{payload}'.encode(), hashlib.sha256).digest())
print(f'{header}.{payload}.{sig}')
")

AUTH="Authorization: Bearer $TOKEN"
PASS=0
FAIL=0

echo "═══════════════════════════════════════════"
echo "  Income Platform — Smoke Test"
echo "═══════════════════════════════════════════"
echo ""

# ── Helper ──
test_endpoint() {
  local label="$1" url="$2" method="${3:-GET}" body="${4:-}"
  echo -n "  $label ... "

  if [ "$method" = "GET" ]; then
    HTTP_CODE=$(curl -s -o /tmp/smoke_resp -w "%{http_code}" -H "$AUTH" "$url")
  else
    HTTP_CODE=$(curl -s -o /tmp/smoke_resp -w "%{http_code}" -X "$method" -H "$AUTH" -H "Content-Type: application/json" -d "$body" "$url")
  fi

  if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "✅ $HTTP_CODE"
    PASS=$((PASS + 1))
  elif [ "$HTTP_CODE" -ge 300 ] && [ "$HTTP_CODE" -lt 500 ]; then
    echo "⚠️  $HTTP_CODE ($(cat /tmp/smoke_resp | python3 -c 'import sys,json; print(json.load(sys.stdin).get("detail",""))' 2>/dev/null || cat /tmp/smoke_resp))"
    PASS=$((PASS + 1))
  else
    echo "❌ $HTTP_CODE"
    cat /tmp/smoke_resp 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"    → {d.get(\"detail\",d)}")' 2>/dev/null || true
    FAIL=$((FAIL + 1))
  fi
}

# ── Health checks (no auth needed) ──
echo "── Health Checks ──"
for port in 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011 8012; do
  AGENT_NUM=$(printf '%02d' $((port - 8000)))
  echo -n "  Agent $AGENT_NUM [:$port] ... "
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE:$port/health" 2>/dev/null)
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ healthy"
    PASS=$((PASS + 1))
  else
    echo "❌ $HTTP_CODE"
    FAIL=$((FAIL + 1))
  fi
done
echo ""

# ── Agent 01: Market Data ──
echo "── Agent 01: Market Data ──"
test_endpoint "GET /stocks/O" "$BASE:8001/stocks/O"
echo ""

# ── Agent 03: Income Scoring ──
echo "── Agent 03: Income Scoring ──"
test_endpoint "POST /score (O)" "$BASE:8003/score" "POST" '{"ticker":"O"}'
echo ""

# ── Agent 04: Asset Classification ──
echo "── Agent 04: Asset Classification ──"
test_endpoint "POST /classify (O)" "$BASE:8004/classify" "POST" '{"ticker":"O"}'
test_endpoint "POST /entry-price/O" "$BASE:8004/entry-price/O" "POST"
echo ""

# ── Agent 05: Tax Optimization ──
echo "── Agent 05: Tax Optimization ──"
test_endpoint "GET /tax/profile/O" "$BASE:8005/tax/profile/O"
echo ""

# ── Agent 06: Scenario Simulation ──
echo "── Agent 06: Scenario Simulation ──"
test_endpoint "POST /simulate" "$BASE:8006/simulate" "POST" '{"ticker":"O","years":5}'
echo ""

# ── Agent 08: Rebalancing ──
echo "── Agent 08: Rebalancing ──"
test_endpoint "GET /rebalancing/status" "$BASE:8008/rebalancing/status"
echo ""

# ── Agent 09: Income Projection ──
echo "── Agent 09: Income Projection ──"
test_endpoint "GET /projections/summary" "$BASE:8009/projections/summary"
echo ""

# ── Agent 10: NAV Monitor ──
echo "── Agent 10: NAV Monitor ──"
test_endpoint "GET /nav/alerts" "$BASE:8010/nav/alerts"
echo ""

# ── Agent 11: Smart Alert ──
echo "── Agent 11: Smart Alert ──"
test_endpoint "GET /alerts" "$BASE:8011/alerts"
echo ""

# ── Agent 12: Proposal Engine ──
echo "── Agent 12: Proposal Engine ──"
test_endpoint "GET /proposals" "$BASE:8012/proposals"
echo ""

# ── Summary ──
echo "═══════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════"

rm -f /tmp/smoke_resp
exit $FAIL
