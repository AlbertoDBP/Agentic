# Natural Language LLM Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude-powered conversational assistant with query, insight, and action capabilities — floating widget on every page + dedicated `/assistant` page — with persistent thread history, explicit memory, and user-defined skills.

**Architecture:** Next.js–first. The `/api/chat` route assembles live portfolio context from the admin-panel, calls Claude claude-sonnet-4-6 with streaming and tool use, and saves conversation history to Postgres via new admin-panel CRUD endpoints. No new microservice.

**Tech Stack:** `@anthropic-ai/sdk` (Node.js), Next.js 15 ReadableStream/SSE, FastAPI, SQLAlchemy raw SQL, React 19, Tailwind CSS

---

## File Structure

**New files:**
- `src/admin-panel/app/routes/api_chat.py` — CRUD for threads, messages, memories, skills + table migration
- `src/frontend/src/app/api/chat/route.ts` — Streaming LLM endpoint with multi-turn tool loop
- `src/frontend/src/lib/chat-context.ts` — Assembles system prompt from live platform APIs
- `src/frontend/src/lib/chat-tools.ts` — Tool definitions (Anthropic schema) + execution logic
- `src/frontend/src/lib/chat-system-prompt.ts` — Static system prompt constant
- `src/frontend/src/hooks/useChat.ts` — Chat state: thread list, messages, streaming
- `src/frontend/src/components/chat/ChatMessage.tsx` — Renders one message (markdown + tool cards)
- `src/frontend/src/components/chat/ToolCard.tsx` — Collapsible tool result card
- `src/frontend/src/components/chat/ChatPanel.tsx` — Shared message list + input bar
- `src/frontend/src/components/chat/ChatWidget.tsx` — Floating bottom-right widget
- `src/frontend/src/app/assistant/page.tsx` — Full-page assistant with thread sidebar
- `src/frontend/src/__tests__/chat-context.test.ts` — Context assembly unit tests
- `src/frontend/src/__tests__/chat-tools.test.ts` — Tool execution unit tests
- `src/admin-panel/tests/test_chat_api.py` — Admin-panel CRUD tests

**Modified files:**
- `src/admin-panel/app/main.py` — Register api_chat router + startup table migration
- `src/frontend/src/app/layout.tsx` — Add `<ChatWidget />` inside `<TooltipProvider>`
- `src/frontend/package.json` — Add `@anthropic-ai/sdk`
- `docker-compose.yml` — Add `ANTHROPIC_API_KEY` + `AGENT03_URL` to frontend env

---

## Task 1: DB Tables + Admin-Panel Router Scaffolding

**Files:**
- Create: `src/admin-panel/app/routes/api_chat.py`
- Modify: `src/admin-panel/app/main.py`
- Create: `src/admin-panel/tests/test_chat_api.py`

Context: The admin-panel uses raw SQLAlchemy (`text()`) with `with _db().connect() as conn:`. Follow the same pattern as `api_portfolio.py`. Tables live in `platform_shared` schema.

- [ ] **Step 1: Write the failing tests for thread CRUD**

```python
# src/admin-panel/tests/test_chat_api.py
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# These tests require a real DB. Skip with SKIP_DB_TESTS=1.
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1",
    reason="requires database"
)

from app.main import app
client = TestClient(app)

SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "dev-token")
HEADERS = {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def test_create_thread():
    r = client.post("/api/chat/threads", json={"title": "Test thread"}, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["title"] == "Test thread"


def test_list_threads():
    r = client.get("/api/chat/threads", headers=HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_append_and_fetch_messages():
    # Create thread
    thread = client.post("/api/chat/threads", json={"title": "msg test"}, headers=HEADERS).json()
    tid = thread["id"]

    # Append two messages
    msgs = [
        {"role": "user", "raw": {"role": "user", "content": "hello"}},
        {"role": "assistant", "raw": {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]}},
    ]
    r = client.post(f"/api/chat/threads/{tid}/messages", json=msgs, headers=HEADERS)
    assert r.status_code == 200

    # Fetch
    r = client.get(f"/api/chat/threads/{tid}/messages", headers=HEADERS)
    assert r.status_code == 200
    result = r.json()
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_memory_crud():
    r = client.post("/api/chat/memories",
        json={"content": "MAIN is anchor", "category": "constraint"},
        headers=HEADERS)
    assert r.status_code == 200
    mem = r.json()
    assert "id" in mem

    r = client.get("/api/chat/memories", headers=HEADERS)
    assert any(m["id"] == mem["id"] for m in r.json())

    r = client.delete(f"/api/chat/memories/{mem['id']}", headers=HEADERS)
    assert r.status_code == 200


def test_skill_crud():
    r = client.post("/api/chat/skills", json={
        "name": "BDC Check",
        "trigger_phrase": "bdc check",
        "procedure": "Fetch BDC positions, rank by durability."
    }, headers=HEADERS)
    assert r.status_code == 200
    skill = r.json()
    assert "id" in skill

    r = client.get("/api/chat/skills", headers=HEADERS)
    assert any(s["id"] == skill["id"] for s in r.json())

    r = client.delete(f"/api/chat/skills/{skill['id']}", headers=HEADERS)
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd src/admin-panel
pip install -r requirements.txt 2>/dev/null
SKIP_DB_TESTS=1 python -m pytest tests/test_chat_api.py -v 2>&1 | head -20
```

Expected: tests skipped (SKIP_DB_TESTS=1). Without the flag they'll fail with import error.

- [ ] **Step 3: Create `api_chat.py`**

```python
# src/admin-panel/app/routes/api_chat.py
"""
Chat assistant CRUD — threads, messages, memories, skills.
Tables are created on startup via ensure_chat_tables().
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from app.database import engine

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Table migration ────────────────────────────────────────────────────────────

def ensure_chat_tables():
    """Create chat tables if they don't exist. Called once at startup."""
    ddl = """
    CREATE TABLE IF NOT EXISTS platform_shared.chat_threads (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    TEXT NOT NULL DEFAULT 'default',
        title      TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS chat_threads_user_updated
        ON platform_shared.chat_threads (user_id, updated_at DESC);

    CREATE TABLE IF NOT EXISTS platform_shared.chat_messages (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        thread_id  UUID REFERENCES platform_shared.chat_threads(id) ON DELETE CASCADE,
        role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        raw        JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS chat_messages_thread_created
        ON platform_shared.chat_messages (thread_id, created_at ASC);

    CREATE TABLE IF NOT EXISTS platform_shared.user_memories (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    TEXT NOT NULL DEFAULT 'default',
        content    TEXT NOT NULL,
        category   TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS platform_shared.user_skills (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         TEXT NOT NULL DEFAULT 'default',
        name            TEXT NOT NULL,
        trigger_phrase  TEXT NOT NULL,
        procedure       TEXT NOT NULL,
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()
        logger.info("chat tables ready")
    except Exception as exc:
        logger.error("ensure_chat_tables failed: %s", exc)


# ── Pydantic models ────────────────────────────────────────────────────────────

class ThreadCreate(BaseModel):
    title: Optional[str] = None

class MessageItem(BaseModel):
    role: str
    raw: dict

class MemoryCreate(BaseModel):
    content: str
    category: Optional[str] = None

class SkillCreate(BaseModel):
    name: str
    trigger_phrase: str
    procedure: str


# ── Threads ────────────────────────────────────────────────────────────────────

@router.post("/api/chat/threads")
def create_thread(body: ThreadCreate):
    with engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO platform_shared.chat_threads (title) VALUES (:title) RETURNING id, title, created_at"
        ), {"title": body.title}).fetchone()
        conn.commit()
    return {"id": str(row.id), "title": row.title, "created_at": row.created_at.isoformat()}


@router.get("/api/chat/threads")
def list_threads():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, title, created_at, updated_at FROM platform_shared.chat_threads "
            "WHERE user_id = 'default' ORDER BY updated_at DESC LIMIT 100"
        )).fetchall()
    return [{"id": str(r.id), "title": r.title, "created_at": r.created_at.isoformat(),
             "updated_at": r.updated_at.isoformat()} for r in rows]


# ── Messages ───────────────────────────────────────────────────────────────────

@router.post("/api/chat/threads/{thread_id}/messages")
def append_messages(thread_id: str, messages: list[MessageItem]):
    import json
    with engine.connect() as conn:
        for msg in messages:
            conn.execute(text(
                "INSERT INTO platform_shared.chat_messages (thread_id, role, raw) "
                "VALUES (:tid, :role, :raw::jsonb)"
            ), {"tid": thread_id, "role": msg.role, "raw": json.dumps(msg.raw)})
        conn.execute(text(
            "UPDATE platform_shared.chat_threads SET updated_at = now() WHERE id = :id"
        ), {"id": thread_id})
        conn.commit()
    return {"saved": len(messages)}


@router.get("/api/chat/threads/{thread_id}/messages")
def get_messages(thread_id: str):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, role, raw, created_at FROM platform_shared.chat_messages "
            "WHERE thread_id = :tid ORDER BY created_at ASC"
        ), {"tid": thread_id}).fetchall()
    return [{"id": str(r.id), "role": r.role, "raw": r.raw,
             "created_at": r.created_at.isoformat()} for r in rows]


# ── Memories ───────────────────────────────────────────────────────────────────

@router.post("/api/chat/memories")
def create_memory(body: MemoryCreate):
    with engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO platform_shared.user_memories (content, category) "
            "VALUES (:content, :category) RETURNING id, content, category, created_at"
        ), {"content": body.content, "category": body.category}).fetchone()
        conn.commit()
    return {"id": str(row.id), "content": row.content, "category": row.category,
            "created_at": row.created_at.isoformat()}


@router.get("/api/chat/memories")
def list_memories():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, content, category, created_at FROM platform_shared.user_memories "
            "WHERE user_id = 'default' ORDER BY created_at DESC"
        )).fetchall()
    return [{"id": str(r.id), "content": r.content, "category": r.category,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.delete("/api/chat/memories/{memory_id}")
def delete_memory(memory_id: str):
    with engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM platform_shared.user_memories WHERE id = :id"
        ), {"id": memory_id})
        conn.commit()
    return {"deleted": memory_id}


# ── Skills ─────────────────────────────────────────────────────────────────────

@router.post("/api/chat/skills")
def create_skill(body: SkillCreate):
    with engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO platform_shared.user_skills (name, trigger_phrase, procedure) "
            "VALUES (:name, :trigger, :procedure) RETURNING id, name, trigger_phrase, procedure, created_at"
        ), {"name": body.name, "trigger": body.trigger_phrase, "procedure": body.procedure}).fetchone()
        conn.commit()
    return {"id": str(row.id), "name": row.name, "trigger_phrase": row.trigger_phrase,
            "procedure": row.procedure, "created_at": row.created_at.isoformat()}


@router.get("/api/chat/skills")
def list_skills():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, trigger_phrase, procedure, created_at FROM platform_shared.user_skills "
            "WHERE user_id = 'default' ORDER BY created_at DESC"
        )).fetchall()
    return [{"id": str(r.id), "name": r.name, "trigger_phrase": r.trigger_phrase,
             "procedure": r.procedure, "created_at": r.created_at.isoformat()} for r in rows]


@router.delete("/api/chat/skills/{skill_id}")
def delete_skill(skill_id: str):
    with engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM platform_shared.user_skills WHERE id = :id"
        ), {"id": skill_id})
        conn.commit()
    return {"deleted": skill_id}
```

- [ ] **Step 4: Register router and startup migration in `main.py`**

Open `src/admin-panel/app/main.py`. Add after the existing imports:

```python
from app.routes.api_chat import router as chat_router, ensure_chat_tables
```

Add the router registration alongside the others (before `proxy.router` to avoid catch-all):

```python
app.include_router(chat_router)
```

Add a startup event at the end of the file (after `app = FastAPI(...)` instantiation):

```python
@app.on_event("startup")
async def startup():
    ensure_chat_tables()
```

- [ ] **Step 5: Run tests locally (requires DB)**

```bash
cd src/admin-panel
python -m pytest tests/test_chat_api.py -v
```

Expected: 5 tests PASS. If DB unavailable, run with `SKIP_DB_TESTS=1` and confirm they skip cleanly.

- [ ] **Step 6: Commit**

```bash
git add src/admin-panel/app/routes/api_chat.py \
        src/admin-panel/app/main.py \
        src/admin-panel/tests/test_chat_api.py
git commit -m "feat(admin-panel): add chat CRUD endpoints and DB tables for assistant feature"
```

---

## Task 2: Install Anthropic SDK + Context Assembly

**Files:**
- Modify: `src/frontend/package.json`
- Create: `src/frontend/src/lib/chat-context.ts`
- Create: `src/frontend/src/lib/chat-system-prompt.ts`
- Create: `src/frontend/src/__tests__/chat-context.test.ts`

Context: The frontend has no `@anthropic-ai/sdk` yet. Context assembly calls `ADMIN_PANEL_URL` directly from the server-side route (not via Next.js proxy routes). Falls back gracefully if any API is unavailable.

- [ ] **Step 1: Install `@anthropic-ai/sdk`**

```bash
cd src/frontend
npm install @anthropic-ai/sdk
```

Expected: `package.json` now includes `"@anthropic-ai/sdk": "^0.x.x"`.

- [ ] **Step 2: Write failing context assembly tests**

```typescript
// src/frontend/src/__tests__/chat-context.test.ts
import { buildPositionSummary, buildPortfolioSnapshot, truncateTitle } from "@/lib/chat-context";

describe("truncateTitle", () => {
  it("truncates at word boundary within 60 chars", () => {
    const long = "What are the highest yielding positions in my portfolio right now";
    const result = truncateTitle(long);
    expect(result.length).toBeLessThanOrEqual(63); // "..." adds 3
    expect(result).toContain("...");
  });

  it("returns as-is when under 60 chars", () => {
    expect(truncateTitle("Short title")).toBe("Short title");
  });
});

describe("buildPositionSummary", () => {
  const positions = [
    { symbol: "MAIN", asset_type: "BDC", hhs_status: "GOOD", score: 82, ies_calculated: true, ies_score: 76 },
    { symbol: "OXLC", asset_type: "CEF", hhs_status: "UNSAFE", score: 41, ies_calculated: false, ies_blocked_reason: "UNSAFE_FLAG" },
  ];

  it("formats position table with symbol, type, HHS, score, IES", () => {
    const result = buildPositionSummary(positions as any[]);
    expect(result).toContain("MAIN");
    expect(result).toContain("GOOD");
    expect(result).toContain("82");
    expect(result).toContain("UNSAFE");
    expect(result).toContain("blocked");
  });
});

describe("buildPortfolioSnapshot", () => {
  it("handles missing optional fields gracefully", () => {
    const portfolio = { id: "abc", name: "Test", total_value: null, blended_yield: null, position_count: 0 };
    const result = buildPortfolioSnapshot(portfolio as any, true);
    expect(result).toContain("Test");
    expect(result).not.toThrow;
  });
});
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd src/frontend
npm test -- --testPathPattern=chat-context --passWithNoTests 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 4: Create `chat-system-prompt.ts`**

```typescript
// src/frontend/src/lib/chat-system-prompt.ts
export const SYSTEM_PROMPT = `You are the Income Fortress Platform Assistant — an expert income investment analyst with full access to the user's portfolio data, scoring engine, market intelligence, and analyst signals.

Your role:
- Answer questions about portfolio health, HHS/IES scores, positions, and proposals
- Draft ProposalDrafts when the user asks to buy, sell, or rebalance
- Run analysis workflows using your available tools
- Surface risks and opportunities proactively

Response style: concise, data-driven. Always cite numbers. Never invent data — use your tools to fetch what you don't have in context.

When the user asks you to "remember" something or states a preference, call save_memory.
When the user defines a new analytical workflow, call save_skill with the name, trigger phrase, and procedure.
When the user types a trigger phrase matching a stored skill, follow that skill's procedure step by step.

Format responses in markdown. Use tables for ranked lists. Keep responses under 400 words unless the user asks for a deep dive.`;
```

- [ ] **Step 5: Create `chat-context.ts`**

```typescript
// src/frontend/src/lib/chat-context.ts

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const AGENT03_URL = process.env.AGENT03_URL ?? "http://localhost:8003";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

function serviceHeaders() {
  return { Authorization: `Bearer ${serviceToken()}` };
}

// ── Exported helpers (also used by tests) ─────────────────────────────────────

export function truncateTitle(text: string): string {
  if (text.length <= 60) return text;
  const cut = text.slice(0, 60).lastIndexOf(" ");
  return text.slice(0, cut > 0 ? cut : 60) + "...";
}

export function buildPositionSummary(positions: any[]): string {
  if (!positions.length) return "_No positions found._\n";
  let out = "Symbol | Type | HHS | Score | IES\n---|---|---|---|---\n";
  for (const p of positions) {
    const ies = p.ies_calculated
      ? (p.ies_score?.toFixed(0) ?? "—")
      : `blocked(${p.ies_blocked_reason ?? "—"})`;
    out += `${p.symbol} | ${p.asset_type ?? "—"} | ${p.hhs_status ?? "—"} | ${p.score?.toFixed(0) ?? "—"} | ${ies}\n`;
  }
  return out;
}

export function buildPortfolioSnapshot(portfolio: any, isActive: boolean): string {
  let out = `### ${portfolio.name}${isActive ? " *(active)*" : ""}\n`;
  out += `- Value: $${(portfolio.total_value ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  out += `, Yield: ${portfolio.blended_yield?.toFixed(1) ?? "—"}%`;
  out += `, Positions: ${portfolio.position_count ?? 0}\n`;
  if (portfolio.monthly_income_target) {
    out += `- Monthly target: $${portfolio.monthly_income_target}\n`;
  }
  return out;
}

// ── Main context assembly ──────────────────────────────────────────────────────

export interface AssembleContextOptions {
  portfolioId?: string;
  userAuthHeader: string; // forwarded from the user's request
}

export async function assembleContext(opts: AssembleContextOptions): Promise<string> {
  const userHeaders = { Authorization: opts.userAuthHeader };
  const svcHeaders = serviceHeaders();

  // Parallel fetch — failures fall back to empty arrays/nulls
  const [portfolios, memories, skills] = await Promise.all([
    fetch(`${ADMIN_PANEL_URL}/api/portfolios`, { headers: userHeaders })
      .then((r) => r.ok ? r.json() : []).catch(() => []),
    fetch(`${ADMIN_PANEL_URL}/api/chat/memories`, { headers: svcHeaders })
      .then((r) => r.ok ? r.json() : []).catch(() => []),
    fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, { headers: svcHeaders })
      .then((r) => r.ok ? r.json() : []).catch(() => []),
  ]);

  const activePortfolioId = opts.portfolioId ?? portfolios[0]?.id;

  let positions: any[] = [];
  let alerts: any[] = [];
  let proposals: any[] = [];
  let scannerResults: any[] = [];

  if (activePortfolioId) {
    [positions, alerts, proposals, scannerResults] = await Promise.all([
      fetch(`${ADMIN_PANEL_URL}/api/portfolios/${activePortfolioId}/positions`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${ADMIN_PANEL_URL}/api/alerts?limit=20`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${ADMIN_PANEL_URL}/api/proposals?status=pending&limit=20`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${ADMIN_PANEL_URL}/api/scanner/results?portfolio_id=${activePortfolioId}`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
    ]);
  }

  let ctx = "";

  // Memories
  ctx += "## User Memories\n";
  ctx += memories.length > 0
    ? memories.map((m: any) => `- [${m.category ?? "general"}] ${m.content}`).join("\n")
    : "None stored yet.";
  ctx += "\n\n";

  // Skills
  ctx += "## User Skills\n";
  ctx += skills.length > 0
    ? skills.map((s: any) => `- **${s.name}** (trigger: "${s.trigger_phrase}")\n  ${s.procedure}`).join("\n\n")
    : "None defined yet.";
  ctx += "\n\n";

  // Portfolio snapshot
  ctx += "## Portfolio Snapshot\n";
  for (const p of portfolios) {
    ctx += buildPortfolioSnapshot(p, p.id === activePortfolioId);
  }
  ctx += "\n";

  // Position summary
  if (positions.length > 0) {
    const activeName = portfolios.find((p: any) => p.id === activePortfolioId)?.name ?? "portfolio";
    ctx += `## Position Summary (${activeName})\n`;
    ctx += buildPositionSummary(positions);
    if (!opts.portfolioId && portfolios.length > 1) {
      const others = portfolios.filter((p: any) => p.id !== activePortfolioId).map((p: any) => p.name).join(", ");
      ctx += `\n_(Showing ${activeName}. Other portfolios: ${others}. Use get_position_details for any symbol.)_\n`;
    }
    ctx += "\n";
  }

  // Alerts
  if (Array.isArray(alerts) && alerts.length > 0) {
    ctx += "## Active Alerts\n";
    for (const a of alerts.slice(0, 10)) {
      ctx += `- ${a.alert_type ?? a.type ?? "ALERT"}: ${a.symbol ?? a.ticker ?? "?"} — ${a.message ?? a.description ?? ""}\n`;
    }
    ctx += "\n";
  }

  // Pending proposals
  if (Array.isArray(proposals) && proposals.length > 0) {
    ctx += "## Pending Proposals\n";
    for (const p of proposals.slice(0, 10)) {
      ctx += `- ${p.action ?? p.proposal_type ?? "?"}: ${p.ticker ?? p.symbol ?? "?"} — ${(p.rationale ?? "").slice(0, 100)}\n`;
    }
    ctx += "\n";
  }

  // Scanner results
  if (Array.isArray(scannerResults) && scannerResults.length > 0) {
    ctx += "## Recent Scanner Results\n";
    for (const r of scannerResults.slice(0, 8)) {
      ctx += `- ${r.ticker ?? r.symbol}: IES ${r.ies_score?.toFixed(0) ?? "—"} — ${(r.rationale ?? "").slice(0, 80)}\n`;
    }
    ctx += "\n";
  }

  return ctx;
}
```

- [ ] **Step 6: Run tests — confirm they pass**

```bash
cd src/frontend
npm test -- --testPathPattern=chat-context 2>&1 | tail -15
```

Expected: 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/frontend/package.json src/frontend/package-lock.json \
        src/frontend/src/lib/chat-context.ts \
        src/frontend/src/lib/chat-system-prompt.ts \
        src/frontend/src/__tests__/chat-context.test.ts
git commit -m "feat(frontend): add @anthropic-ai/sdk and chat context assembly"
```

---

## Task 3: Tool Definitions and Execution

**Files:**
- Create: `src/frontend/src/lib/chat-tools.ts`
- Create: `src/frontend/src/__tests__/chat-tools.test.ts`

Context: Tools are defined in Anthropic SDK format. Execution fetches from platform APIs. `AGENT03_URL` serves score breakdowns. Tool results are plain objects — serialized to JSON when returned to Claude.

- [ ] **Step 1: Write failing tool tests**

```typescript
// src/frontend/src/__tests__/chat-tools.test.ts
import { buildToolDefinitions } from "@/lib/chat-tools";

describe("buildToolDefinitions", () => {
  it("returns 7 tools", () => {
    const tools = buildToolDefinitions();
    expect(tools).toHaveLength(7);
  });

  it("all tools have required Anthropic schema fields", () => {
    const tools = buildToolDefinitions();
    for (const tool of tools) {
      expect(tool.name).toBeDefined();
      expect(tool.description).toBeDefined();
      expect(tool.input_schema).toBeDefined();
      expect(tool.input_schema.type).toBe("object");
    }
  });

  it("create_proposal_draft requires ticker and portfolio_id", () => {
    const tools = buildToolDefinitions();
    const t = tools.find((t) => t.name === "create_proposal_draft")!;
    expect(t.input_schema.required).toContain("ticker");
    expect(t.input_schema.required).toContain("portfolio_id");
  });

  it("get_score_breakdown requires symbol", () => {
    const tools = buildToolDefinitions();
    const t = tools.find((t) => t.name === "get_score_breakdown")!;
    expect(t.input_schema.required).toContain("symbol");
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd src/frontend
npm test -- --testPathPattern=chat-tools 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `chat-tools.ts`**

```typescript
// src/frontend/src/lib/chat-tools.ts
import type Anthropic from "@anthropic-ai/sdk";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const AGENT03_URL = process.env.AGENT03_URL ?? "http://localhost:8003";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

function svcHeaders() {
  return { Authorization: `Bearer ${serviceToken()}` };
}

// ── Tool definitions (Anthropic schema) ───────────────────────────────────────

export function buildToolDefinitions(): Anthropic.Tool[] {
  return [
    {
      name: "create_proposal_draft",
      description:
        "Creates a ProposalDraft in the proposals workflow via Agent 12. The engine derives action, quantity, and rationale from live scoring — do not invent these values. Use when the user asks to buy, sell, or rebalance a specific holding.",
      input_schema: {
        type: "object" as const,
        properties: {
          ticker: { type: "string", description: "Stock ticker symbol (e.g. OXLC)" },
          portfolio_id: { type: "string", description: "UUID of the target portfolio" },
          trigger_mode: { type: "string", enum: ["on_demand"], description: "Always 'on_demand'" },
        },
        required: ["ticker", "portfolio_id"],
      },
    },
    {
      name: "get_position_details",
      description:
        "Fetches full position data for one symbol: market data, cost basis, income metrics, HHS/IES scores, and factor breakdown. Use when the user asks about a specific holding in detail.",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string" },
          portfolio_id: { type: "string" },
        },
        required: ["symbol", "portfolio_id"],
      },
    },
    {
      name: "get_score_breakdown",
      description:
        "Returns factor_details (8 scoring sub-components with score/max/value) for a symbol from Agent 03. Use when the user asks why a score is high or low.",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "get_scanner_results",
      description:
        "Returns the latest cached scanner results for a portfolio (ADD/TRIM candidates). Does NOT trigger a new scan — shows the most recent run by Agent 07.",
      input_schema: {
        type: "object" as const,
        properties: {
          portfolio_id: { type: "string" },
        },
        required: ["portfolio_id"],
      },
    },
    {
      name: "get_analyst_signals",
      description:
        "Returns analyst signals and frameworks for a specific ticker from Agent 02's newsletter ingestion (Seeking Alpha commentary, analyst philosophy).",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "save_memory",
      description:
        "Stores a fact, preference, or rule about the user or their portfolio in persistent memory. Call whenever the user says 'remember', 'always', or states a preference.",
      input_schema: {
        type: "object" as const,
        properties: {
          content: { type: "string", description: "The memory to store" },
          category: {
            type: "string",
            enum: ["constraint", "preference", "rule", "fact"],
            description: "Category of the memory",
          },
        },
        required: ["content"],
      },
    },
    {
      name: "save_skill",
      description:
        "Stores a named analytical workflow that can be triggered by a phrase in future conversations.",
      input_schema: {
        type: "object" as const,
        properties: {
          name: { type: "string", description: "Display name, e.g. 'BDC Health Check'" },
          trigger_phrase: { type: "string", description: "Phrase the user types to invoke this skill" },
          procedure: { type: "string", description: "Step-by-step procedure description" },
        },
        required: ["name", "trigger_phrase", "procedure"],
      },
    },
  ];
}

// ── Tool execution ─────────────────────────────────────────────────────────────

export async function executeTool(
  name: string,
  input: Record<string, unknown>
): Promise<Record<string, unknown>> {
  try {
    switch (name) {
      case "create_proposal_draft": {
        const body = {
          ticker: input.ticker,
          portfolio_id: input.portfolio_id,
          trigger_mode: "on_demand",
        };
        const r = await fetch(`${ADMIN_PANEL_URL}/api/proposals/generate`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) return { error: `Proposal generation failed: HTTP ${r.status}` };
        const data = await r.json();
        return {
          proposal_id: data.id ?? data.proposal_id,
          action: data.action ?? data.proposal_type,
          rationale: data.rationale ?? "",
          link: "/proposals",
          message: `ProposalDraft created for ${input.ticker}. View in /proposals.`,
        };
      }

      case "get_position_details": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/portfolios/${input.portfolio_id}/positions`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { error: `Positions fetch failed: HTTP ${r.status}` };
        const positions: any[] = await r.json();
        const pos = positions.find(
          (p) => p.symbol?.toUpperCase() === String(input.symbol).toUpperCase()
        );
        return pos ?? { error: `Symbol ${input.symbol} not found in portfolio` };
      }

      case "get_score_breakdown": {
        const r = await fetch(`${AGENT03_URL}/scores/${input.symbol}`, {
          headers: svcHeaders(),
        });
        if (!r.ok) return { error: `Score fetch failed: HTTP ${r.status}` };
        const data = await r.json();
        return {
          symbol: input.symbol,
          hhs_score: data.hhs_score,
          hhs_status: data.hhs_status,
          ies_score: data.ies_score,
          factor_details: data.factor_details ?? {},
        };
      }

      case "get_scanner_results": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/scanner/results?portfolio_id=${input.portfolio_id}`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { error: `Scanner results fetch failed: HTTP ${r.status}` };
        return { results: await r.json() };
      }

      case "get_analyst_signals": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/newsletters/signals?ticker=${input.symbol}`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { signals: [], message: "No analyst data available" };
        return { signals: await r.json() };
      }

      case "save_memory": {
        const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/memories`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ content: input.content, category: input.category }),
        });
        if (!r.ok) return { error: "Failed to save memory" };
        return { saved: true, content: input.content };
      }

      case "save_skill": {
        const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({
            name: input.name,
            trigger_phrase: input.trigger_phrase,
            procedure: input.procedure,
          }),
        });
        if (!r.ok) return { error: "Failed to save skill" };
        return { saved: true, name: input.name, trigger_phrase: input.trigger_phrase };
      }

      default:
        return { error: `Unknown tool: ${name}` };
    }
  } catch (err) {
    return { error: String(err) };
  }
}
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd src/frontend
npm test -- --testPathPattern=chat-tools 2>&1 | tail -10
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/lib/chat-tools.ts \
        src/frontend/src/__tests__/chat-tools.test.ts
git commit -m "feat(frontend): add LLM tool definitions and execution"
```

---

## Task 4: Streaming `/api/chat` Route

**Files:**
- Create: `src/frontend/src/app/api/chat/route.ts`

Context: This is the core route. It assembles context, runs the multi-turn tool loop with Claude streaming, emits SSE events, and saves the conversation. The `@anthropic-ai/sdk` streaming API emits typed events. Tool calls interrupt the stream, tools execute, then streaming resumes.

SSE event types emitted to client:
- `{ type: "thread_id", thread_id: "..." }` — first event, so client knows which thread to resume
- `{ type: "text", text: "..." }` — token by token
- `{ type: "tool_start", name: "...", id: "..." }` — tool call beginning
- `{ type: "tool_result", id: "...", name: "...", result: {...} }` — tool completed
- `{ type: "done" }` — stream complete
- `{ type: "error", message: "..." }` — on failure

- [ ] **Step 1: Create the route**

```typescript
// src/frontend/src/app/api/chat/route.ts
import { NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { assembleContext, truncateTitle } from "@/lib/chat-context";
import { buildToolDefinitions, executeTool } from "@/lib/chat-tools";
import { SYSTEM_PROMPT } from "@/lib/chat-system-prompt";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}
function svcHeaders() {
  return { Authorization: `Bearer ${serviceToken()}`, "Content-Type": "application/json" };
}

// ── Thread helpers ─────────────────────────────────────────────────────────────

async function createThread(title: string): Promise<string> {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads`, {
    method: "POST",
    headers: svcHeaders(),
    body: JSON.stringify({ title }),
  });
  const data = await r.json();
  return data.id as string;
}

async function saveMessages(threadId: string, messages: Array<{ role: string; raw: object }>) {
  await fetch(`${ADMIN_PANEL_URL}/api/chat/threads/${threadId}/messages`, {
    method: "POST",
    headers: svcHeaders(),
    body: JSON.stringify(messages),
  }).catch(() => {/* best effort */});
}

async function loadHistory(threadId: string): Promise<Anthropic.MessageParam[]> {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads/${threadId}/messages`, {
    headers: { Authorization: `Bearer ${serviceToken()}` },
  }).catch(() => null);
  if (!r?.ok) return [];
  const rows: Array<{ role: string; raw: Anthropic.MessageParam }> = await r.json();
  return rows.map((m) => m.raw);
}

// ── Main handler ───────────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const enc = new TextEncoder();
  const { message, thread_id, portfolio_id } = await req.json() as {
    message: string;
    thread_id?: string;
    portfolio_id?: string;
  };

  const userAuth = req.headers.get("authorization") ?? `Bearer ${serviceToken()}`;

  const stream = new ReadableStream({
    async start(controller) {
      const emit = (obj: object) =>
        controller.enqueue(enc.encode(`data: ${JSON.stringify(obj)}\n\n`));

      try {
        // 1. Create or resolve thread
        const threadId = thread_id ?? await createThread(truncateTitle(message));
        emit({ type: "thread_id", thread_id: threadId });

        // 2. Save user message immediately (before any side effects)
        await saveMessages(threadId, [{ role: "user", raw: { role: "user", content: message } }]);

        // 3. Assemble context
        const contextStr = await assembleContext({ portfolioId: portfolio_id, userAuthHeader: userAuth });

        // 4. Load thread history (excludes the message we just saved — it's appended below)
        const history = await loadHistory(threadId);

        // 5. Build messages array
        let messages: Anthropic.MessageParam[] = [
          ...history,
          { role: "user", content: message },
        ];

        const tools = buildToolDefinitions();

        // 6. Multi-turn streaming loop (max 5 rounds)
        let finalContentBlocks: Anthropic.ContentBlock[] = [];

        for (let round = 0; round < 5; round++) {
          const response = await anthropic.messages.create({
            model: "claude-sonnet-4-6",
            max_tokens: 4096,
            system: `${SYSTEM_PROMPT}\n\n${contextStr}`,
            messages,
            tools,
            stream: true,
          });

          const contentBlocks: Anthropic.ContentBlock[] = [];
          let currentBlock: any = null;
          let stopReason = "";

          for await (const event of response) {
            if (event.type === "content_block_start") {
              currentBlock = { ...event.content_block };
              if (event.content_block.type === "text") {
                (currentBlock as any).text = "";
              } else if (event.content_block.type === "tool_use") {
                (currentBlock as any)._inputStr = "";
                emit({ type: "tool_start", name: event.content_block.name, id: event.content_block.id });
              }
            } else if (event.type === "content_block_delta") {
              if (event.delta.type === "text_delta" && currentBlock?.type === "text") {
                currentBlock.text += event.delta.text;
                emit({ type: "text", text: event.delta.text });
              } else if (event.delta.type === "input_json_delta" && currentBlock?.type === "tool_use") {
                currentBlock._inputStr = (currentBlock._inputStr ?? "") + event.delta.partial_json;
              }
            } else if (event.type === "content_block_stop") {
              if (currentBlock) {
                if (currentBlock.type === "tool_use") {
                  try { currentBlock.input = JSON.parse(currentBlock._inputStr ?? "{}"); }
                  catch { currentBlock.input = {}; }
                  delete currentBlock._inputStr;
                }
                contentBlocks.push(currentBlock);
              }
            } else if (event.type === "message_delta") {
              stopReason = event.delta.stop_reason ?? "";
            }
          }

          finalContentBlocks = contentBlocks;

          if (stopReason !== "tool_use") break;

          // Execute tools
          const toolUseBlocks = contentBlocks.filter(
            (b): b is Anthropic.ToolUseBlock => b.type === "tool_use"
          );
          const toolResults: Anthropic.ToolResultBlockParam[] = [];

          for (const block of toolUseBlocks) {
            const result = await executeTool(block.name, block.input as Record<string, unknown>);
            emit({ type: "tool_result", id: block.id, name: block.name, result });
            toolResults.push({
              type: "tool_result",
              tool_use_id: block.id,
              content: JSON.stringify(result),
            });
          }

          messages = [
            ...messages,
            { role: "assistant", content: contentBlocks },
            { role: "user", content: toolResults },
          ];
        }

        // 7. Save assistant message
        await saveMessages(threadId, [{
          role: "assistant",
          raw: { role: "assistant", content: finalContentBlocks },
        }]);

        emit({ type: "done" });
      } catch (err) {
        emit({ type: "error", message: err instanceof Error ? err.message : String(err) });
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep "chat/route" | head -20
```

Expected: no errors on `chat/route.ts`.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/app/api/chat/route.ts
git commit -m "feat(frontend): add streaming /api/chat route with multi-turn tool loop"
```

---

## Task 5: ChatMessage and ToolCard Components

**Files:**
- Create: `src/frontend/src/components/chat/ToolCard.tsx`
- Create: `src/frontend/src/components/chat/ChatMessage.tsx`

Context: Messages render markdown (bold, lists, tables). Tool results appear as collapsible cards. The `cn()` utility is in `@/lib/utils`. Use `lucide-react` for icons (already installed).

- [ ] **Step 1: Create `ToolCard.tsx`**

```tsx
// src/frontend/src/components/chat/ToolCard.tsx
"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolCardProps {
  name: string;
  result?: Record<string, unknown>;
  pending?: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  create_proposal_draft: "Created ProposalDraft",
  get_position_details: "Position Details",
  get_score_breakdown: "Score Breakdown",
  get_scanner_results: "Scanner Results",
  get_analyst_signals: "Analyst Signals",
  save_memory: "Memory Saved",
  save_skill: "Skill Saved",
};

export function ToolCard({ name, result, pending = false }: ToolCardProps) {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABELS[name] ?? name;

  return (
    <div className="my-1.5 rounded border border-border/40 bg-muted/20 text-xs overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left text-muted-foreground hover:text-foreground transition-colors"
      >
        <Wrench className="w-3 h-3 shrink-0 text-blue-400" />
        <span className="flex-1 font-medium">{label}</span>
        {pending ? (
          <span className="text-[10px] text-muted-foreground animate-pulse">thinking…</span>
        ) : open ? (
          <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronRight className="w-3 h-3" />
        )}
      </button>
      {open && result && (
        <pre className="px-2.5 pb-2 text-[10px] text-muted-foreground whitespace-pre-wrap break-words border-t border-border/40 pt-1.5">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      {result?.link && (
        <div className="px-2.5 pb-1.5">
          <a href={result.link as string} className="text-blue-400 hover:underline text-[10px]">
            View in Proposals →
          </a>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `ChatMessage.tsx`**

```tsx
// src/frontend/src/components/chat/ChatMessage.tsx
import { cn } from "@/lib/utils";
import { ToolCard } from "./ToolCard";

export interface ChatMessageData {
  id?: string;
  role: "user" | "assistant";
  text?: string;
  toolCards?: Array<{ id: string; name: string; result?: Record<string, unknown>; pending?: boolean }>;
  streaming?: boolean;
}

interface ChatMessageProps {
  message: ChatMessageData;
}

// Minimal markdown renderer — bold, inline code, links
function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, '<code class="bg-muted/40 px-0.5 rounded text-[11px]">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-400 hover:underline">$1</a>');
}

function renderText(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Table detection
    if (line.includes("|") && lines[i + 1]?.match(/^\|[-| ]+\|$/)) {
      const headers = line.split("|").filter(Boolean).map((s) => s.trim());
      i += 2; // skip separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|")) {
        rows.push(lines[i].split("|").filter(Boolean).map((s) => s.trim()));
        i++;
      }
      elements.push(
        <div key={i} className="overflow-x-auto my-2">
          <table className="text-xs w-full border-collapse">
            <thead>
              <tr className="border-b border-border/50">
                {headers.map((h, j) => (
                  <th key={j} className="text-left px-2 py-1 text-muted-foreground font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/20">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-2 py-1"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(cell) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // List items
    if (line.match(/^[-*] /)) {
      const items: string[] = [];
      while (i < lines.length && lines[i].match(/^[-*] /)) {
        items.push(lines[i].slice(2));
        i++;
      }
      elements.push(
        <ul key={i} className="list-disc list-inside space-y-0.5 my-1.5 pl-1 text-sm">
          {items.map((item, j) => (
            <li key={j} dangerouslySetInnerHTML={{ __html: renderMarkdown(item) }} />
          ))}
        </ul>
      );
      continue;
    }

    // Regular paragraph
    if (line.trim()) {
      elements.push(
        <p key={i} className="text-sm leading-relaxed"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(line) }} />
      );
    } else {
      elements.push(<div key={i} className="h-1.5" />);
    }
    i++;
  }

  return elements;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-2.5", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-[9px] font-bold text-blue-400">AI</span>
        </div>
      )}
      <div className={cn("max-w-[85%] space-y-1", isUser ? "items-end" : "items-start")}>
        {/* Tool cards (before text for assistant) */}
        {!isUser && message.toolCards?.map((tc) => (
          <ToolCard key={tc.id} name={tc.name} result={tc.result} pending={tc.pending} />
        ))}

        {/* Text bubble */}
        {message.text && (
          <div className={cn(
            "rounded-lg px-3 py-2 text-sm",
            isUser
              ? "bg-blue-600/20 border border-blue-500/30 text-foreground"
              : "bg-muted/30 border border-border/30 text-foreground"
          )}>
            {isUser ? (
              <p className="text-sm whitespace-pre-wrap">{message.text}</p>
            ) : (
              <div className="space-y-1">{renderText(message.text)}</div>
            )}
            {message.streaming && (
              <span className="inline-block w-1.5 h-3.5 bg-blue-400 ml-0.5 animate-pulse rounded-sm" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep "chat/" | head -20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/chat/ToolCard.tsx \
        src/frontend/src/components/chat/ChatMessage.tsx
git commit -m "feat(frontend): add ChatMessage and ToolCard components"
```

---

## Task 6: `useChat` Hook

**Files:**
- Create: `src/frontend/src/hooks/useChat.ts`

Context: Manages thread state, SSE stream parsing, and message accumulation. Uses `fetch` with `ReadableStream`. Exports all state needed by both the widget and the full page.

- [ ] **Step 1: Create `useChat.ts`**

```typescript
// src/frontend/src/hooks/useChat.ts
"use client";
import { useState, useCallback, useRef } from "react";
import type { ChatMessageData } from "@/components/chat/ChatMessage";

interface Thread {
  id: string;
  title: string;
  updated_at: string;
}

interface UseChatOptions {
  portfolioId?: string;
}

export function useChat(opts: UseChatOptions = {}) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>();
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // ── Thread list ──────────────────────────────────────────────────────────────

  const fetchThreads = useCallback(async () => {
    setThreadsLoading(true);
    try {
      const r = await fetch("/api/chat/threads");
      if (r.ok) setThreads(await r.json());
    } finally {
      setThreadsLoading(false);
    }
  }, []);

  const loadThread = useCallback(async (threadId: string) => {
    setActiveThreadId(threadId);
    const r = await fetch(`/api/chat/threads/${threadId}/messages`);
    if (!r.ok) return;
    const rows: Array<{ role: string; raw: { role: string; content: any } }> = await r.json();

    const msgs: ChatMessageData[] = rows.map((row, i) => {
      if (row.role === "user") {
        const content = typeof row.raw.content === "string" ? row.raw.content : "";
        return { id: `${threadId}-${i}`, role: "user" as const, text: content };
      }
      // assistant: extract text from content blocks
      const blocks = Array.isArray(row.raw.content) ? row.raw.content : [];
      const text = blocks
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text)
        .join("");
      const toolCards = blocks
        .filter((b: any) => b.type === "tool_use")
        .map((b: any) => ({ id: b.id, name: b.name }));
      return { id: `${threadId}-${i}`, role: "assistant" as const, text, toolCards };
    });

    setMessages(msgs);
  }, []);

  const startNewThread = useCallback(() => {
    setActiveThreadId(undefined);
    setMessages([]);
  }, []);

  // ── Send message ─────────────────────────────────────────────────────────────

  const send = useCallback(async (text?: string) => {
    const msg = text ?? input;
    if (!msg.trim() || loading) return;
    setInput("");
    setLoading(true);

    // Optimistic user message
    const userMsg: ChatMessageData = { id: `user-${Date.now()}`, role: "user", text: msg };
    setMessages((prev) => [...prev, userMsg]);

    // Placeholder assistant message
    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", text: "", streaming: true, toolCards: [] },
    ]);

    abortRef.current = new AbortController();

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          thread_id: activeThreadId,
          portfolio_id: opts.portfolioId,
        }),
        signal: abortRef.current.signal,
      });

      if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);

      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += dec.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const evt of events) {
          if (!evt.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(evt.slice(6));

            if (payload.type === "thread_id" && !activeThreadId) {
              setActiveThreadId(payload.thread_id);
              // Refresh thread list to show new thread
              fetchThreads();
            } else if (payload.type === "text") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, text: (m.text ?? "") + payload.text }
                    : m
                )
              );
            } else if (payload.type === "tool_start") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCards: [
                          ...(m.toolCards ?? []),
                          { id: payload.id, name: payload.name, pending: true },
                        ],
                      }
                    : m
                )
              );
            } else if (payload.type === "tool_result") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCards: (m.toolCards ?? []).map((tc) =>
                          tc.id === payload.id
                            ? { ...tc, result: payload.result, pending: false }
                            : tc
                        ),
                      }
                    : m
                )
              );
            } else if (payload.type === "done") {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
              );
            } else if (payload.type === "error") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, text: `Error: ${payload.message}`, streaming: false }
                    : m
                )
              );
            }
          } catch {
            // malformed JSON line — skip
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: "Request failed. Please try again.", streaming: false }
              : m
          )
        );
      }
    } finally {
      setLoading(false);
    }
  }, [input, loading, activeThreadId, opts.portfolioId, fetchThreads]);

  return {
    threads,
    activeThreadId,
    messages,
    input,
    setInput,
    loading,
    threadsLoading,
    fetchThreads,
    loadThread,
    startNewThread,
    send,
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep "useChat\|hooks" | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/hooks/useChat.ts
git commit -m "feat(frontend): add useChat hook for streaming state management"
```

---

## Task 7: ChatPanel — Shared Panel Component

**Files:**
- Create: `src/frontend/src/components/chat/ChatPanel.tsx`

Context: Shared by both `ChatWidget` (in a floating panel) and the `/assistant` page (in a right-column container). Receives `useChat()` return values as props and renders the message list + input bar.

- [ ] **Step 1: Create `ChatPanel.tsx`**

```tsx
// src/frontend/src/components/chat/ChatPanel.tsx
"use client";
import { useEffect, useRef, KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessageData } from "./ChatMessage";

interface ChatPanelProps {
  messages: ChatMessageData[];
  input: string;
  loading: boolean;
  onInputChange: (v: string) => void;
  onSend: () => void;
  className?: string;
  placeholder?: string;
}

export function ChatPanel({
  messages,
  input,
  loading,
  onInputChange,
  onSend,
  className,
  placeholder = "Ask anything about your portfolio…",
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground text-xs pt-8">
            Ask about your portfolio, holdings, or scores.
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-border/50 px-3 py-2 flex gap-2 items-end shrink-0">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={1}
          disabled={loading}
          className={cn(
            "flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60",
            "focus:outline-none min-h-[32px] max-h-[120px] py-1.5",
            "disabled:opacity-50"
          )}
          style={{ height: "auto" }}
          onInput={(e) => {
            const t = e.target as HTMLTextAreaElement;
            t.style.height = "auto";
            t.style.height = `${Math.min(t.scrollHeight, 120)}px`;
          }}
        />
        <button
          onClick={onSend}
          disabled={loading || !input.trim()}
          className={cn(
            "w-7 h-7 rounded-md flex items-center justify-center shrink-0 transition-colors",
            "bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          )}
        >
          <Send className="w-3.5 h-3.5 text-white" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep "ChatPanel" | head -10
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/chat/ChatPanel.tsx
git commit -m "feat(frontend): add shared ChatPanel component"
```

---

## Task 8: Floating `ChatWidget`

**Files:**
- Create: `src/frontend/src/components/chat/ChatWidget.tsx`

Context: Fixed bottom-right button + panel. Reads current URL via `usePathname()` to extract portfolio ID. Resumes the most recent thread on open.

- [ ] **Step 1: Create `ChatWidget.tsx`**

```tsx
// src/frontend/src/components/chat/ChatWidget.tsx
"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { MessageCircle, X, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
import { ChatPanel } from "./ChatPanel";

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Extract portfolio ID from /portfolios/[id] URLs
  const portfolioId = pathname.match(/\/portfolios\/([^/]+)/)?.[1];

  const { messages, input, loading, setInput, send, threads, fetchThreads, loadThread } =
    useChat({ portfolioId });

  // Load most recent thread when widget opens
  useEffect(() => {
    if (!open) return;
    fetchThreads().then(() => {
      // threads state is updated asynchronously — load in next render via effect below
    });
  }, [open, fetchThreads]);

  // When threads load for the first time and widget is open, load the most recent
  const [didLoad, setDidLoad] = useState(false);
  useEffect(() => {
    if (!open || didLoad || threads.length === 0) return;
    setDidLoad(true);
    loadThread(threads[0].id);
  }, [open, threads, didLoad, loadThread]);

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "fixed bottom-5 right-5 z-50 w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all",
          "bg-blue-600 hover:bg-blue-500 text-white",
          open && "hidden"
        )}
        aria-label="Open assistant"
      >
        <MessageCircle className="w-5 h-5" />
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-5 right-5 z-50 w-[380px] h-[520px] rounded-xl shadow-2xl border border-border/60 bg-card flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/50 bg-card/80 shrink-0">
            <span className="text-sm font-semibold text-foreground">Platform Assistant</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground p-0.5 rounded"
                aria-label="Minimize"
              >
                <Minus className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground p-0.5 rounded"
                aria-label="Close"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <ChatPanel
            messages={messages}
            input={input}
            loading={loading}
            onInputChange={setInput}
            onSend={send}
            className="flex-1 min-h-0"
          />
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep "ChatWidget" | head -10
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/chat/ChatWidget.tsx
git commit -m "feat(frontend): add floating ChatWidget component"
```

---

## Task 9: `/assistant` Full Page

**Files:**
- Create: `src/frontend/src/app/assistant/page.tsx`

Context: Full-page layout. Left sidebar (280px) shows thread list grouped by date + "New Chat" button + Memory/Skills management. Right panel shows `ChatPanel`.

- [ ] **Step 1: Create `assistant/page.tsx`**

```tsx
// src/frontend/src/app/assistant/page.tsx
"use client";
import { useEffect, useState } from "react";
import { Plus, Trash2, Brain, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
import { ChatPanel } from "@/components/chat/ChatPanel";

interface Memory { id: string; content: string; category: string | null; created_at: string; }
interface Skill { id: string; name: string; trigger_phrase: string; procedure: string; }

function groupByDate(threads: Array<{ id: string; title: string; updated_at: string }>) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, typeof threads> = {
    Today: [],
    Yesterday: [],
    "This Week": [],
    Older: [],
  };

  for (const t of threads) {
    const d = new Date(t.updated_at);
    if (d >= today) groups["Today"].push(t);
    else if (d >= yesterday) groups["Yesterday"].push(t);
    else if (d >= weekAgo) groups["This Week"].push(t);
    else groups["Older"].push(t);
  }

  return groups;
}

export default function AssistantPage() {
  const { threads, activeThreadId, messages, input, loading, threadsLoading,
    setInput, send, fetchThreads, loadThread, startNewThread } = useChat();

  const [showMemoryPanel, setShowMemoryPanel] = useState(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);

  useEffect(() => { fetchThreads(); }, [fetchThreads]);

  const loadMemoriesAndSkills = async () => {
    const [mRes, sRes] = await Promise.all([
      fetch("/api/chat/memories"),
      fetch("/api/chat/skills"),
    ]);
    if (mRes.ok) setMemories(await mRes.json());
    if (sRes.ok) setSkills(await sRes.json());
  };

  const deleteMemory = async (id: string) => {
    await fetch(`/api/chat/memories/${id}`, { method: "DELETE" });
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const deleteSkill = async (id: string) => {
    await fetch(`/api/chat/skills/${id}`, { method: "DELETE" });
    setSkills((prev) => prev.filter((s) => s.id !== id));
  };

  const grouped = groupByDate(threads);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left sidebar */}
      <div className="w-72 shrink-0 border-r border-border/50 bg-card/30 flex flex-col">
        <div className="p-3 border-b border-border/40 flex items-center gap-2 shrink-0">
          <button
            onClick={startNewThread}
            className="flex-1 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-md hover:bg-muted/30 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Chat
          </button>
          <button
            onClick={() => { setShowMemoryPanel((o) => !o); loadMemoriesAndSkills(); }}
            className={cn(
              "p-1.5 rounded-md transition-colors",
              showMemoryPanel
                ? "bg-blue-600/20 text-blue-400"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
            )}
            title="Memory & Skills"
          >
            <Brain className="w-4 h-4" />
          </button>
        </div>

        {showMemoryPanel ? (
          /* Memory & Skills panel */
          <div className="flex-1 overflow-y-auto p-3 space-y-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-blue-400 mb-2 flex items-center gap-1">
                <Brain className="w-3 h-3" /> Memories
              </div>
              {memories.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No memories yet. Tell the assistant to "remember" something.</p>
              ) : (
                <div className="space-y-1.5">
                  {memories.map((m) => (
                    <div key={m.id} className="flex gap-1.5 group">
                      <p className="flex-1 text-xs text-foreground/80">{m.content}</p>
                      <button onClick={() => deleteMemory(m.id)}
                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-400">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-blue-400 mb-2 flex items-center gap-1">
                <Zap className="w-3 h-3" /> Skills
              </div>
              {skills.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No skills yet. Describe a workflow and ask the assistant to save it as a skill.</p>
              ) : (
                <div className="space-y-2">
                  {skills.map((s) => (
                    <div key={s.id} className="group border border-border/30 rounded p-2">
                      <div className="flex justify-between items-start">
                        <span className="text-xs font-medium">{s.name}</span>
                        <button onClick={() => deleteSkill(s.id)}
                          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-400">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-[10px] text-blue-400 mt-0.5">trigger: "{s.trigger_phrase}"</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Thread list */
          <div className="flex-1 overflow-y-auto">
            {threadsLoading && (
              <p className="text-xs text-muted-foreground p-3">Loading…</p>
            )}
            {Object.entries(grouped).map(([label, group]) =>
              group.length > 0 ? (
                <div key={label}>
                  <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground/60 px-3 pt-3 pb-1">
                    {label}
                  </p>
                  {group.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => loadThread(t.id)}
                      className={cn(
                        "w-full text-left px-3 py-2 text-xs truncate hover:bg-muted/30 transition-colors",
                        activeThreadId === t.id ? "bg-muted/40 text-foreground" : "text-muted-foreground"
                      )}
                    >
                      {t.title ?? "Untitled"}
                    </button>
                  ))}
                </div>
              ) : null
            )}
          </div>
        )}
      </div>

      {/* Right panel */}
      <ChatPanel
        messages={messages}
        input={input}
        loading={loading}
        onInputChange={setInput}
        onSend={send}
        className="flex-1 min-w-0"
        placeholder="Ask about your portfolio, run an analysis, or define a new skill…"
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | grep "assistant" | head -10
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/app/assistant/page.tsx
git commit -m "feat(frontend): add /assistant full-page chat with thread sidebar and memory panel"
```

---

## Task 10: Wire-Up, Env Vars, and Deploy

**Files:**
- Modify: `src/frontend/src/app/layout.tsx`
- Modify: `docker-compose.yml`
- Add nav link to sidebar (find the sidebar component)

Context: ChatWidget must be added inside the existing providers in `layout.tsx`. `docker-compose.yml` needs `ANTHROPIC_API_KEY` and `AGENT03_URL` for the frontend service. The `/assistant` route also needs a sidebar nav link.

- [ ] **Step 1: Add ChatWidget to layout**

Open `src/frontend/src/app/layout.tsx`. Add the import:

```typescript
import { ChatWidget } from "@/components/chat/ChatWidget";
```

Inside the JSX, add `<ChatWidget />` just before the closing `</TooltipProvider>` tag:

```tsx
<TooltipProvider>
  <div className="flex min-h-screen">
    <Sidebar />
    <MainContent>{children}</MainContent>
  </div>
  <ChatWidget />   {/* ← add this */}
</TooltipProvider>
```

- [ ] **Step 2: Add nav link to Sidebar**

Find the sidebar component:

```bash
grep -r "proposals\|scanner\|Sidebar" src/frontend/src/components --include="*.tsx" -l | head -5
```

Open the sidebar file and add an `/assistant` nav link following the same pattern as the other nav items. Look for where `/proposals` or `/scanner` links are defined and add:

```tsx
{ href: "/assistant", label: "Assistant", icon: MessageCircle }
```

Import `MessageCircle` from `lucide-react` if not already present.

- [ ] **Step 3: Add proxy routes for chat history (thread list, messages, memories, skills)**

The `/assistant` page calls `/api/chat/threads`, `/api/chat/memories`, and `/api/chat/skills` as Next.js API routes (not directly to admin-panel). Create lightweight proxy routes:

```typescript
// src/frontend/src/app/api/chat/threads/route.ts
import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }

export async function GET() {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads`,
    { headers: { Authorization: `Bearer ${svcToken()}` } });
  return NextResponse.json(await r.json(), { status: r.status });
}
export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads`, {
    method: "POST",
    headers: { Authorization: `Bearer ${svcToken()}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

```typescript
// src/frontend/src/app/api/chat/threads/[id]/messages/route.ts
import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }
const hdrs = () => ({ Authorization: `Bearer ${svcToken()}`, "Content-Type": "application/json" });

export async function GET(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads/${id}/messages`, { headers: hdrs() });
  return NextResponse.json(await r.json(), { status: r.status });
}
export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.json();
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads/${id}/messages`, {
    method: "POST", headers: hdrs(), body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

```typescript
// src/frontend/src/app/api/chat/memories/route.ts
import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }
const hdrs = () => ({ Authorization: `Bearer ${svcToken()}`, "Content-Type": "application/json" });

export async function GET() {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/memories`, { headers: hdrs() });
  return NextResponse.json(await r.json(), { status: r.status });
}
export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/memories`, {
    method: "POST", headers: hdrs(), body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

```typescript
// src/frontend/src/app/api/chat/memories/[id]/route.ts
import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }

export async function DELETE(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/memories/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${svcToken()}` },
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

```typescript
// src/frontend/src/app/api/chat/skills/route.ts  (same pattern as memories)
import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }
const hdrs = () => ({ Authorization: `Bearer ${svcToken()}`, "Content-Type": "application/json" });

export async function GET() {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, { headers: hdrs() });
  return NextResponse.json(await r.json(), { status: r.status });
}
export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, {
    method: "POST", headers: hdrs(), body: JSON.stringify(body),
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

```typescript
// src/frontend/src/app/api/chat/skills/[id]/route.ts
import { NextRequest, NextResponse } from "next/server";
const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
function svcToken() { return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token"; }

export async function DELETE(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${svcToken()}` },
  });
  return NextResponse.json(await r.json(), { status: r.status });
}
```

- [ ] **Step 4: Update `docker-compose.yml` — add env vars to frontend service**

Open `docker-compose.yml`. In the `frontend` service's `environment:` block, add after `AGENT08_URL`:

```yaml
    - AGENT03_URL=http://agent-03-income-scoring:8003
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

Verify `ANTHROPIC_API_KEY` is already in `.env` on the server (it's used by the newsletter agent). If not, it must be added.

- [ ] **Step 5: Final TypeScript check**

```bash
cd src/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 0 errors.

- [ ] **Step 6: Run all frontend tests**

```bash
cd src/frontend
npm test 2>&1 | tail -20
```

Expected: all tests pass including chat-context and chat-tools.

- [ ] **Step 7: Commit**

```bash
git add src/frontend/src/app/layout.tsx \
        src/frontend/src/app/api/chat/ \
        src/frontend/src/app/assistant/ \
        docker-compose.yml
git commit -m "feat: wire up ChatWidget, assistant page, proxy routes, and deploy env vars"
```

- [ ] **Step 8: Deploy to production**

```bash
# Push to remote
git push origin main

# On server
ssh root@138.197.78.238
cd /opt/Agentic && git pull origin main
cd income-platform

# Rebuild frontend (has new dependencies) and admin-panel (new router)
docker compose build --no-cache frontend admin-panel

# Restart both
docker compose up -d frontend admin-panel
```

- [ ] **Step 9: Smoke test**

From a browser:
1. Open the platform — verify the floating chat button appears bottom-right
2. Click it — verify the widget opens with a blank chat
3. Type "What portfolios do I have?" — verify streaming response with portfolio names
4. Type "remember that MAIN is my anchor position" — verify assistant calls `save_memory` tool card appears
5. Navigate to `/assistant` — verify thread from step 3 appears in the sidebar
6. Click the Brain icon — verify the memory from step 4 appears

---

## Summary

| Task | What it builds | Tests |
|------|----------------|-------|
| 1 | DB tables + admin-panel CRUD | pytest (5 tests) |
| 2 | @anthropic-ai/sdk + context assembly | Jest (4 tests) |
| 3 | Tool definitions + execution | Jest (4 tests) |
| 4 | Streaming `/api/chat` route | TypeScript compile |
| 5 | ChatMessage + ToolCard components | TypeScript compile |
| 6 | `useChat` hook | TypeScript compile |
| 7 | ChatPanel component | TypeScript compile |
| 8 | Floating ChatWidget | TypeScript compile |
| 9 | `/assistant` full page | TypeScript compile |
| 10 | Wire-up + deploy | Manual smoke test |
