#!/usr/bin/env bash
# ────────────────────────────────────────────────────────
# Income Platform — Production Smoke Test
# Generates a JWT via PyJWT inside a running container
# ────────────────────────────────────────────────────────
set -euo pipefail

BASE="${BASE_URL:-http://localhost}"

# ── Generate JWT using PyJWT inside a running container ──
# (containers have PyJWT + JWT_SECRET in their environment)
TOKEN=$(docker exec agent-03-income-scoring python3 -c "
import jwt, time, os
t = jwt.encode({'sub':'smoke-test','iat':int(time.time()),'exp':int(time.time())+3600}, os.environ['JWT_SECRET'], algorithm='HS256')
print(t)
")

if [ -z "$TOKEN" ]; then
  echo "ERROR: Could not generate JWT. Is agent-03-income-scoring running?"
  exit 1
fi

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
# Route: @app.get("/stocks/{symbol}/price")
echo "── Agent 01: Market Data ──"
test_endpoint "GET /stocks/O/price" "$BASE:8001/stocks/O/price"
echo ""

# ── Agent 02: Newsletter Ingestion ──
# Route: prefix="/signal" → GET /{ticker}
echo "── Agent 02: Newsletter Ingestion ──"
test_endpoint "GET /signal/O" "$BASE:8002/signal/O"
echo ""

# ── Agent 03: Income Scoring ──
# Route: prefix="/scores" → POST /evaluate
echo "── Agent 03: Income Scoring ──"
test_endpoint "POST /scores/evaluate (O)" "$BASE:8003/scores/evaluate" "POST" '{"ticker":"O","asset_class":"CommonStock"}'
test_endpoint "GET /scores/O" "$BASE:8003/scores/O"
echo ""

# ── Agent 04: Asset Classification ──
# Route: no prefix → POST /classify, POST /entry-price/{ticker}
echo "── Agent 04: Asset Classification ──"
test_endpoint "POST /classify (O)" "$BASE:8004/classify" "POST" '{"ticker":"O"}'
test_endpoint "POST /entry-price/O" "$BASE:8004/entry-price/O" "POST"
echo ""

# ── Agent 05: Tax Optimization ──
# Route: prefix="" → GET /tax/profile/{symbol}
echo "── Agent 05: Tax Optimization ──"
test_endpoint "GET /tax/profile/O" "$BASE:8005/tax/profile/O"
echo ""

# ── Agent 06: Scenario Simulation ──
# Route: no prefix → POST /scenarios/stress-test
echo "── Agent 06: Scenario Simulation ──"
test_endpoint "GET /scenarios/library" "$BASE:8006/scenarios/library"
echo ""

# ── Agent 07: Opportunity Scanner ──
# Route: no prefix → GET /universe
echo "── Agent 07: Opportunity Scanner ──"
test_endpoint "GET /universe" "$BASE:8007/universe"
echo ""

# ── Agent 08: Rebalancing ──
# Route: no prefix → GET /rebalance/portfolio/{id}/history
DUMMY_UUID="00000000-0000-0000-0000-000000000001"

echo "── Agent 08: Rebalancing ──"
test_endpoint "GET /rebalance/portfolio/history" "$BASE:8008/rebalance/portfolio/$DUMMY_UUID/history"
echo ""

# ── Agent 09: Income Projection ──
# Route: prefix="/projection" → GET /{portfolio_id}/latest
echo "── Agent 09: Income Projection ──"
test_endpoint "GET /projection/{id}/latest" "$BASE:8009/projection/$DUMMY_UUID/latest"
echo ""

# ── Agent 10: NAV Monitor ──
# Route: prefix="/monitor" → GET /alerts
echo "── Agent 10: NAV Monitor ──"
test_endpoint "GET /monitor/alerts" "$BASE:8010/monitor/alerts"
echo ""

# ── Agent 11: Smart Alert ──
# Route: prefix="/alerts" → GET ""
echo "── Agent 11: Smart Alert ──"
test_endpoint "GET /alerts" "$BASE:8011/alerts"
echo ""

# ── Agent 12: Proposal Engine ──
# Route: prefix="/proposals" → GET ""
echo "── Agent 12: Proposal Engine ──"
test_endpoint "GET /proposals" "$BASE:8012/proposals"
echo ""

# ── Summary ──
echo "═══════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════"

rm -f /tmp/smoke_resp
exit $FAIL
