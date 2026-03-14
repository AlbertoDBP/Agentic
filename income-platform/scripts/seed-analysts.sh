#!/usr/bin/env bash
# ────────────────────────────────────────────────────────
# Register analysts and trigger newsletter harvesting
# Run from: /opt/agentic/income-platform
# ────────────────────────────────────────────────────────
set -euo pipefail

BASE="${BASE_URL:-http://localhost}"
AGENT02="$BASE:8002"

# ── Get JWT token ──
TOKEN=$(docker exec agent-03-income-scoring python3 -c "
import jwt, time, os
t = jwt.encode({'sub':'admin','iat':int(time.time()),'exp':int(time.time())+3600}, os.environ['JWT_SECRET'], algorithm='HS256')
print(t)
")
AUTH="Authorization: Bearer $TOKEN"

echo "═══════════════════════════════════════════"
echo "  Analyst Registration & Harvesting"
echo "═══════════════════════════════════════════"
echo ""

# ── Register Analyst 1: Roberts Berzins ──
echo "── Registering Roberts Berzins, CFA ──"
curl -s -X POST "$AGENT02/analysts" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "sa_publishing_id": "104956",
    "display_name": "Roberts Berzins, CFA",
    "config": {"fetch_limit": 20}
  }' | python3 -m json.tool
echo ""

# ── Register Analyst 2: Rida Morwa ──
echo "── Registering Rida Morwa ──"
curl -s -X POST "$AGENT02/analysts" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "sa_publishing_id": "96726",
    "display_name": "Rida Morwa",
    "config": {"fetch_limit": 20}
  }' | python3 -m json.tool
echo ""

# ── Verify registration ──
echo "── Registered Analysts ──"
curl -s "$AGENT02/analysts" \
  -H "$AUTH" | python3 -m json.tool
echo ""

# ── Trigger harvesting ──
echo "── Triggering Harvester Flow ──"
echo "(This will fetch recent articles from Seeking Alpha for both analysts)"
echo ""
curl -s -X POST "$AGENT02/flows/harvester/trigger" \
  -H "$AUTH" \
  -H "Content-Type: application/json" | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════"
echo "  Done. Check logs: docker compose logs -f agent-02-newsletter-ingestion"
echo "═══════════════════════════════════════════"
