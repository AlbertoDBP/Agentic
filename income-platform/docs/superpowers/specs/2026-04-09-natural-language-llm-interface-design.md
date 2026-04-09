# Natural Language & LLM Interface Design

**Date:** 2026-04-09
**Status:** Approved
**Scope:** Conversational AI assistant with query, insight, and action capabilities — floating widget + dedicated page, persistent thread history, explicit memory and user-defined skills

---

## Overview

An LLM-powered assistant embedded in the Income Fortress Platform that lets the user query portfolio data in plain English, receive AI-generated insights, and create ProposalDrafts via natural language commands. Built entirely within the existing Next.js frontend — no new microservice.

Three capabilities unified in one interface:
1. **Query** — "What are my worst-performing holdings?" / "Which positions are flagged UNSAFE?"
2. **Insight** — LLM synthesizes portfolio data into narrative analysis on demand
3. **Action** — Natural language commands create ProposalDrafts in the existing proposals workflow

---

## Architecture

### Option Selected: Next.js–first

Claude API calls live in a new `/api/chat` Next.js route. Context is assembled server-side by calling the platform's existing API routes in parallel. Conversation history is stored in Postgres via new admin-panel endpoints. No new microservice.

**Data flow:**
```
User types message
      ↓
POST /api/chat (Next.js streaming route)
      ↓
Context Assembly — parallel calls (all server-side, no Next.js proxy needed):
  - ADMIN_PANEL_URL/api/portfolios              → portfolio KPIs + targets
  - ADMIN_PANEL_URL/api/portfolios/[id]/positions → positions + HHS/IES scores
    (if portfolio_id absent: load all portfolios, then positions for largest by value only)
  - ADMIN_PANEL_URL/api/proposals               → pending proposals
  - ADMIN_PANEL_URL/api/alerts                  → recent alerts (last 7 days)
  - ADMIN_PANEL_URL/api/scanner/results         → latest cached scan results
  - ADMIN_PANEL_URL/api/chat/memories           → user memories
  - ADMIN_PANEL_URL/api/chat/skills             → user skills
      ↓
Claude claude-sonnet-4-6 API call (streaming, with tool use)
      ↓
Streamed tokens → ReadableStream → client (SSE)
      ↓
Admin-panel saves thread + messages to Postgres
```

**Note on `portfolio_id`:** The widget reads the current page URL and passes the active portfolio ID when on any `/portfolios/[id]` page. On other pages (dashboard, /assistant), it omits portfolio_id — context assembly then loads all portfolios from the list endpoint and fetches positions for the highest-value portfolio only. The system prompt notes which portfolio positions are shown.

**Model:** `claude-sonnet-4-6` — balances quality and cost. Already in use on the platform.

**Streaming:** Next.js `ReadableStream` with `text/event-stream` content type. Tokens appear in the UI as they arrive.

---

## Data Layer

### New Postgres Tables (via admin-panel migration)

```sql
-- Conversation threads (one per session, global per user)
CREATE TABLE platform_shared.chat_threads (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     TEXT NOT NULL DEFAULT 'default',
  title       TEXT,          -- auto-generated from first user message (first 60 chars)
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON platform_shared.chat_threads (user_id, updated_at DESC);

-- Messages within a thread
-- Each row stores one complete Messages API turn verbatim as JSONB.
-- The `role` column is a denormalized copy for quick filtering.
-- `raw` preserves the exact structure for round-tripping back to the API.
CREATE TABLE platform_shared.chat_messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id   UUID REFERENCES platform_shared.chat_threads(id) ON DELETE CASCADE,
  role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  raw         JSONB NOT NULL,   -- full Messages API message object: {role, content: [...]}
  created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON platform_shared.chat_messages (thread_id, created_at ASC);

-- Example `raw` values:
-- user turn:      {"role": "user", "content": "What are my UNSAFE holdings?"}
-- assistant turn: {"role": "assistant", "content": [{"type": "text", "text": "..."}, {"type": "tool_use", "id": "...", "name": "get_position_details", "input": {...}}]}
-- tool result:    stored as next user turn: {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]}
-- On thread load, rows are fetched ordered by created_at and passed directly to the Messages API as the `messages` array.

-- Explicit user memories (facts + preferences)
CREATE TABLE platform_shared.user_memories (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     TEXT NOT NULL DEFAULT 'default',
  content     TEXT NOT NULL,   -- e.g. "MAIN is an anchor position — do not suggest selling"
  category    TEXT,            -- e.g. "preference", "rule", "constraint"
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- User-defined skills (named analytical procedures)
CREATE TABLE platform_shared.user_skills (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         TEXT NOT NULL DEFAULT 'default',
  name            TEXT NOT NULL,            -- display name: "BDC Health Check"
  trigger_phrase  TEXT NOT NULL,            -- what the user types: "bdc health check"
  procedure       TEXT NOT NULL,            -- natural language description of steps
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

### Admin-Panel Endpoints

New router at `src/admin-panel/app/routes/api_chat.py`, mounted at `/api/chat`:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat/threads` | Create new thread |
| `GET` | `/api/chat/threads` | List threads (most recent first) |
| `GET` | `/api/chat/threads/{id}/messages` | Fetch full thread messages |
| `POST` | `/api/chat/threads/{id}/messages` | Append messages (batch) |
| `GET` | `/api/chat/memories` | List user memories |
| `POST` | `/api/chat/memories` | Create memory |
| `DELETE` | `/api/chat/memories/{id}` | Delete memory |
| `GET` | `/api/chat/skills` | List user skills |
| `POST` | `/api/chat/skills` | Create skill |
| `DELETE` | `/api/chat/skills/{id}` | Delete skill |

---

## System Prompt & Context Assembly

Each Claude call receives a fresh system prompt assembled from live data. Target size: ≤ 8,000 tokens for typical portfolios.

### Static Section (fixed)

```
You are the Income Fortress Platform Assistant — an expert income
investment analyst with full access to the user's portfolio, scoring
engine, market intelligence, and analyst signals.

Your role:
- Answer questions about portfolio health, HHS/IES scores, positions, and proposals
- Draft ProposalDrafts when the user asks to buy, sell, or rebalance
- Run analysis workflows using your available tools
- Surface risks and opportunities proactively

Response style: concise, data-driven. Always cite numbers. Never invent
data — use your tools to fetch what you don't have in context.

When the user asks you to "remember" something, call save_memory.
When the user defines a new analytical workflow, call save_skill.
When the user triggers a skill by its phrase, follow the stored procedure exactly.
```

### Dynamic Section (assembled per-request)

```
## User Memories
{memories list, or "None stored yet"}

## User Skills
{skills list with trigger phrases and procedures, or "None defined yet"}

## Portfolio Snapshot
{for each portfolio: name, total value, yield, position count, monthly
 target vs actual, income gap, UNSAFE count, pending proposal count}

## Position Summary
{abbreviated list: symbol | asset_type | HHS status | score | IES}
{Full details available via get_position_details tool}

## Active Alerts (last 7 days)
{alert type | symbol | description}

## Pending Proposals
{action | symbol | rationale summary}

## Recent Scanner Results
{top ADD candidates with IES score}
```

**Context size management:** Position summary uses one line per position (symbol + key scores only). Full position detail, factor breakdowns, and market data are fetched on-demand via tools. Analyst intelligence from Agent 02 is not in the default context but accessible via the `get_analyst_signals` tool (defined below).

---

## Claude Tools

Seven tools available to the assistant:

### `create_proposal_draft`
Routes through the existing `POST /api/proposals/generate` endpoint (Agent 12). The proposal engine derives action, quantity, and rationale from live scoring data — the LLM does not invent these values.

**Input:**
```json
{
  "ticker": "OXLC",
  "portfolio_id": "abc-123",
  "trigger_mode": "on_demand"
}
```
**What happens:** Agent 12 fetches the latest score for the ticker, applies portfolio rules, and creates a ProposalDraft row. Returns the proposal's integer ID (not UUID) and a link to the Proposals page.

**Returns:** `{ "proposal_id": 42, "action": "SELL", "rationale": "...", "link": "/proposals" }`

**Note:** If the user says "sell OXLC" or "buy more ARCC", Claude extracts the ticker and passes it to this tool. The engine determines whether a SELL/BUY/TRIM is appropriate based on current scores. If the engine's decision differs from the user's intent, Claude explains the discrepancy.

---

### `get_position_details`
Fetches **full** position data for one symbol: market data, cost basis, income metrics, HHS/IES scores, factor breakdown. The context assembly already loads positions but truncates to abbreviated one-liners in the system prompt. This tool bypasses the truncation and returns the complete position object.

Calls: `ADMIN_PANEL_URL/api/portfolios/{portfolio_id}/positions` (same endpoint as context assembly), then filters the array to the requested symbol server-side.

`portfolio_id` is always a UUID string (same type used throughout the platform — portfolios use UUID PKs).
```json
{ "symbol": "MAIN", "portfolio_id": "abc-123-uuid" }
```

---

### `get_score_breakdown`
Returns `factor_details` (8 scoring factors with score/max/value) for a symbol.
Calls: `AGENT03_URL/scores/{ticker}` — the existing `GET /{ticker}` endpoint in the income-scoring service (Agent 03, port 8003). This endpoint already exists and returns the full `ScoreResponse` including `factor_details`.
```json
{ "symbol": "ARCC" }
```

---

### `get_scanner_results`
Returns the latest **cached** scanner results for a portfolio. Does NOT trigger a new scan (scans take up to 120 seconds and run on a schedule via Agent 07).
Calls: `ADMIN_PANEL_URL/api/scanner/results?portfolio_id={id}`.
```json
{ "portfolio_id": "abc-123" }
```
**Returns:** Top ADD/TRIM candidates with IES score, estimated income contribution, and rationale from the most recent scan run.

---

### `get_analyst_signals`
Returns analyst signals and frameworks ingested by Agent 02 for a specific ticker.
Calls: `ADMIN_PANEL_URL/api/newsletters/signals?ticker={symbol}` (existing Agent 02 endpoint).
```json
{ "symbol": "MAIN" }
```
**Returns:** Recent income signals, analyst philosophy summary, and framework keywords for the ticker.

---

### `save_memory`
Stores a fact or preference in `user_memories`.
```json
{
  "content": "MAIN is an anchor position — do not suggest selling",
  "category": "constraint"
}
```

---

### `save_skill`
Stores a named analytical procedure in `user_skills`.
```json
{
  "name": "BDC Health Check",
  "trigger_phrase": "bdc health check",
  "procedure": "Fetch all BDC positions. Check debt_safety and dividend_consistency factors for each. Rank by durability pillar score descending. Flag any with Critical directionality on debt_safety. Show ranked table with recommendation."
}
```

---

## Frontend Components

### 1. Floating Chat Widget
**Location:** Fixed bottom-right corner, all pages. Component: `ChatWidget.tsx`

- **Collapsed state:** Round button with chat icon, notification dot if new assistant message
- **Open state:** Panel (380px wide, 520px tall) with message list + input
- **Context-aware:** Reads `usePathname()` to detect active portfolio page. Passes `portfolio_id` extracted from `/portfolios/[id]` URL segments. On other pages, `portfolio_id` is omitted.
- **Thread continuity:** Resumes the most recent thread by default. "New chat" button starts a fresh thread.
- **Thread title:** Generated by the route handler when creating a new thread — first 60 characters of the user's opening message, truncated at a word boundary. No LLM call needed.

### 2. `/assistant` Page
**Full-page layout** with two panels:

**Left sidebar (280px):**
- "New Chat" button
- Thread list grouped by date (Today / Yesterday / This Week / Older)
- Thread title = first 60 chars of first user message
- Active thread highlighted

**Right panel (flex-1):**
- Message history with markdown rendering
- Tool use shown as collapsible cards ("Created ProposalDraft for OXLC ↗")
- Streaming response with cursor indicator
- Input bar pinned to bottom

**Memory & Skills panel:** Accessible via settings icon in header. Shows all stored memories and skills with delete buttons.

### 3. `ChatMessage` Component
Renders a single message. Handles:
- Markdown (bold, lists, tables, code blocks)
- Tool use cards (collapsible, shows tool name + key result)
- ProposalDraft links (inline card with "View in Proposals →")
- Streaming state (animated cursor during generation)

### 4. Next.js API Route: `/api/chat`

```
POST /api/chat
Body: { thread_id?, message: string, portfolio_id? }

1. Save user message immediately to thread (via admin-panel POST /api/chat/threads/{id}/messages)
   — ensures message is persisted before any side effects occur
2. Load or create thread (via admin-panel)
3. Assemble context (parallel API calls, see Architecture section)
4. Load memories + skills (via admin-panel)
5. Build system prompt
6. Multi-turn tool-use streaming loop (max 5 rounds):
   a. Call Claude claude-sonnet-4-6 with streaming
   b. Buffer stream tokens; emit each token to client via ReadableStream (SSE)
   c. If stop_reason = "tool_use":
      - Emit tool-card event to client (client renders collapsible tool card)
      - Execute all tool calls in the response
      - Append assistant message + tool results to messages array
      - Continue loop from step (a) with updated messages
   d. If stop_reason = "end_turn": exit loop
7. Save complete assistant turn to thread (via admin-panel)
   — saved after streaming completes; includes all tool_use + tool_result content blocks
```

**Client-side state during tool use:** When the client receives a tool-card SSE event, it shows a "thinking…" indicator with the tool name. When the next text tokens arrive, the thinking indicator is replaced by the tool card (collapsed by default) followed by the assistant's text.

**Auth:** Uses `SERVICE_JWT_TOKEN ?? SERVICE_TOKEN ?? "dev-token"` for internal service calls (same pattern as rebalance route).

**Error handling:**
- Claude API timeout (60s): return partial response + "Response interrupted — please retry"
- Platform API failures: continue with reduced context, note missing data in system prompt
- Tool execution failure: return error description as tool_result; Claude handles gracefully in response
- Client disconnect mid-stream: user message already saved; assistant message is lost — acceptable for v1

---

## Memory System

### Explicit Memory (v1)

User controls all memory. No implicit learning.

**Creating memories:** User says "remember that..." or "always..." → Claude calls `save_memory` → confirmation shown in chat.

**Using memories:** Loaded into every system prompt. Claude applies them automatically ("Since MAIN is your anchor position, I'll exclude it from the sell list...")

**Managing memories:** Via the Memory panel in `/assistant` page. List all, delete individual.

### User-Defined Skills (v1)

**Creating skills:** User describes a workflow in chat ("When I say 'income gap analysis', do X, Y, Z") → Claude extracts the procedure and trigger phrase, calls `save_skill`.

**Invoking skills:** User types a phrase → Claude checks the skill list in the system prompt and uses its own judgment to match it to a stored skill (fuzzy match acceptable — if the user types "run bdc health check" and the trigger is "bdc health check", Claude should recognize it). No deterministic string matching in code — this is intentionally left to the model.

**Managing skills:** Same panel as memories in `/assistant` page.

---

## Known v1 Limitations

- Skills have no edit endpoint — to change a skill's procedure, delete and recreate via the Memory & Skills panel. A `PUT /api/chat/skills/{id}` endpoint is deferred to v2.
- Assistant message lost on client disconnect mid-stream — the user message is saved immediately, but the assistant response is only saved after streaming completes.
- Skill invocation relies on model judgment, not deterministic matching — edge cases with ambiguous trigger phrases may not invoke the correct skill.

---

## Out of Scope (v1)

- Voice input/output
- Implicit learning (tracking proposal acceptance patterns)
- Multi-portfolio batch analysis in a single query
- LLM-generated insight cards surfaced automatically throughout the UI (outside of chat)
- Analyst intelligence from Agent 02 in default context (available via tool, not auto-loaded)
- Semantic/embedding-based memory retrieval (load all memories for now; add retrieval if volume grows)
- Per-portfolio thread scoping (global threads only)

---

## Testing Plan

### API Route
- Streams tokens correctly for a simple query
- Context assembly completes within 3s for a 20-position portfolio
- Tool call round-trip: `create_proposal_draft` creates a real ProposalDraft in DB
- Thread saved correctly after each exchange
- Handles Claude API timeout gracefully

### Memory & Skills
- `save_memory` persists and appears in next conversation's system prompt
- `save_skill` trigger phrase correctly invokes stored procedure
- Memory/skill deletion removes from system prompt on next call

### Frontend
- Floating widget opens/closes without layout shift
- Streaming renders tokens in real time
- Tool use card renders correctly with collapsible detail
- Thread list loads and resumes correctly
- Memory panel shows all stored memories with working delete
