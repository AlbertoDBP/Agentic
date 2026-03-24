# Portfolio HHS/IES Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HHS/IES computed fields to Agent 03's ScoreResponse, expose portfolio aggregate endpoints in the broker-service, and rebuild the frontend portfolio section as a Grand Dashboard + 5-tab per-portfolio view powered by those scores.

**Architecture:** Three sequential phases with explicit dependency gates — (1) Agent 03 gains HHS/IES fields via DB migration + new helpers + updated endpoint; (2) broker-service gains `GET /portfolios` and `GET /portfolios/{id}/summary` aggregating from Agent 03; (3) frontend is rebuilt with Grand Dashboard (`/dashboard`) and per-portfolio tabs (`/portfolios/[id]`). Each phase ships independently deployable code with tests before the next begins.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy / asyncpg / pytest (backend) · Next.js 16 / React 19 / TypeScript / TanStack Query v5 / TanStack Table v8 (frontend) · PostgreSQL `platform_shared` schema · Docker Compose on remote server legato.

**Spec:** `docs/superpowers/specs/2026-03-24-portfolio-frontend-redesign.md`
**Depends on:** `docs/superpowers/specs/2026-03-24-holding-health-score-framework-design.md` (read before implementing Phase 1)

---

## File Map

### Phase 1 — Agent 03 HHS/IES Backend

| Action | Path | Responsibility |
| ------ | ---- | -------------- |
| Create | `src/portfolio-positions-schema/scripts/migrate_v3_hhs_ies.py` | ADD COLUMN IF NOT EXISTS for all 15 new HHS/IES columns |
| Modify | `src/income-scoring-service/app/models.py` | Add HHS/IES columns to `IncomeScore` ORM model |
| Modify | `src/income-scoring-service/app/api/scores.py` | `ScoreResponse` additions, `_compute_hhs()`, `_compute_ies_gate()`, `_generate_hhs_commentary()`, `evaluate_score` integration, `_orm_to_response()` update |
| Create | `src/income-scoring-service/tests/test_hhs_ies.py` | Unit tests for all three new helpers |

### Phase 2 — Broker-Service Portfolio Endpoints

| Action | Path | Responsibility |
| ------ | ---- | -------------- |
| Create | `src/broker-service/app/services/__init__.py` | Package init |
| Create | `src/broker-service/app/services/portfolio_aggregator.py` | Fetch scores from Agent 03, compute aggregates |
| Modify | `src/broker-service/app/api/broker.py` | Add `GET /broker/portfolios` and `GET /broker/portfolios/{id}/summary` |
| Create | `src/broker-service/tests/__init__.py` | pytest package |
| Create | `src/broker-service/tests/test_portfolio_aggregator.py` | Aggregator + endpoint tests |

### Phase 3 — Frontend Redesign

| Action | Path | Responsibility |
| ------ | ---- | -------------- |
| Modify | `src/frontend/src/lib/types.ts` | HHS/IES fields on `ScoreResponse`, new `PortfolioSummary` type |
| Modify | `src/frontend/src/lib/help-content.ts` | HHS/IES help strings for all new fields |
| Modify | `src/frontend/src/lib/config.ts` | Design token CSS vars, asset-class color palette |
| Create | `src/frontend/src/lib/hooks/use-portfolios.ts` | TanStack Query hooks: `usePortfolios`, `usePortfolioSummary`, `usePortfolioScores` |
| Create | `src/frontend/src/components/portfolio/hhs-badge.tsx` | Color-coded HHS status badge |
| Create | `src/frontend/src/components/portfolio/kpi-strip.tsx` | Responsive 8-col KPI grid |
| Create | `src/frontend/src/components/portfolio/concentration-bar.tsx` | Stacked horizontal bar for asset-class/sector distribution |
| Create | `src/frontend/src/components/portfolio/portfolio-card.tsx` | 300px portfolio summary card |
| Create | `src/frontend/src/app/dashboard/page.tsx` | Grand Dashboard (aggregate strip + card scroll row) |
| Create | `src/frontend/src/app/portfolios/[id]/page.tsx` | Per-portfolio shell: identity header + KPI strip + collapsible summary + tab bar |
| Create | `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx` | Holdings table + position detail pane |
| Create | `src/frontend/src/app/portfolios/[id]/tabs/market-tab.tsx` | Market data table + ticker detail pane |
| Create | `src/frontend/src/app/portfolios/[id]/tabs/health-tab.tsx` | HHS/IES table + factor breakdown detail pane |
| Modify | `src/frontend/src/app/income-projection/page.tsx` | Add named `ProjectionContent` export |
| Modify | `src/frontend/src/app/portfolio/page.tsx` | Replace with `redirect('/dashboard')` |

---

## Phase 1 — Agent 03 HHS/IES Backend

### Task 1: DB Migration — Add HHS/IES Columns

**Files:**
- Create: `src/portfolio-positions-schema/scripts/migrate_v3_hhs_ies.py`

- [ ] **Step 1: Write the migration script**

```python
"""
Migration v3: Add HHS/IES computed columns to income_scores.

Run with:
  DATABASE_URL=postgresql://... python3 scripts/migrate_v3_hhs_ies.py

Safe to re-run: all statements use ADD COLUMN IF NOT EXISTS.
"""
import asyncio
import os
import sys
import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=require")[0]


async def run_migration():
    conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    print("✓ Connected to database")
    try:
        print("\n[income_scores] Adding HHS/IES columns...")
        cols = [
            # HHS pillars
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS hhs_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS income_pillar_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS durability_pillar_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS income_weight NUMERIC(6,4)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS durability_weight NUMERIC(6,4)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS unsafe_flag BOOLEAN",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS unsafe_threshold INTEGER DEFAULT 20",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS hhs_status TEXT",
            # IES
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS ies_score NUMERIC(6,2)",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS ies_calculated BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS ies_blocked_reason TEXT",
            # Quality gate
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS quality_gate_status TEXT DEFAULT 'PASS'",
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS quality_gate_reasons JSONB",
            # Commentary
            "ALTER TABLE platform_shared.income_scores ADD COLUMN IF NOT EXISTS hhs_commentary TEXT",
            # valid_until already exists — expose in API only
        ]
        for ddl in cols:
            await conn.execute(ddl)
            col = ddl.split("ADD COLUMN IF NOT EXISTS")[1].strip().split()[0]
            print(f"  ✓ income_scores.{col}")
        print("\n✓ Migration complete")
    finally:
        await conn.close()


if __name__ == "__main__":
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run_migration())
```

- [ ] **Step 2: Run migration against local/remote DB**

```bash
# From project root (or SSH into legato for production):
DATABASE_URL=$(grep DATABASE_URL .env | cut -d= -f2-) \
  python3 src/portfolio-positions-schema/scripts/migrate_v3_hhs_ies.py
```

Expected output: `✓ Migration complete` with 14 column lines.

- [ ] **Step 3: Verify columns exist**

```bash
psql "$DATABASE_URL" -c "\d platform_shared.income_scores" | grep -E "hhs|ies|quality_gate|unsafe"
```

Expected: 14 new column names printed.

- [ ] **Step 4: Commit**

```bash
git add src/portfolio-positions-schema/scripts/migrate_v3_hhs_ies.py
git commit -m "feat(db): add HHS/IES columns to income_scores (migrate_v3)"
```

---

### Task 2: IncomeScore ORM Model — Add HHS/IES Columns

**Files:**
- Modify: `src/income-scoring-service/app/models.py`

- [ ] **Step 1: Add columns to IncomeScore after the existing `signal_penalty_details` column**

```python
# Add this block after signal_penalty_details in the IncomeScore class:

# ── HHS / IES fields (v3.0) ───────────────────────────────────────────────
hhs_score = Column(Float, nullable=True)
income_pillar_score = Column(Float, nullable=True)
durability_pillar_score = Column(Float, nullable=True)
income_weight = Column(Float, nullable=True)
durability_weight = Column(Float, nullable=True)
unsafe_flag = Column(Boolean, nullable=True)           # None = not evaluated
unsafe_threshold = Column(Integer, nullable=True, default=20)
hhs_status = Column(String(20), nullable=True)         # STRONG|GOOD|WATCH|CONCERN|UNSAFE|INSUFFICIENT

ies_score = Column(Float, nullable=True)
ies_calculated = Column(Boolean, nullable=False, default=False)
ies_blocked_reason = Column(String(30), nullable=True) # UNSAFE_FLAG|HHS_BELOW_THRESHOLD|INSUFFICIENT_DATA

quality_gate_status = Column(String(20), nullable=True, default="PASS")
quality_gate_reasons = Column(JSONB, nullable=True)
hhs_commentary = Column(Text, nullable=True)           # persisted at score time
```

Make sure `Text` is imported: `from sqlalchemy import Column, Float, String, Boolean, Integer, Text, JSON, DateTime, Index, UUID, ForeignKey`.

- [ ] **Step 2: Verify the ORM loads without error**

```bash
cd src/income-scoring-service
python3 -c "from app.models import IncomeScore; print('OK', IncomeScore.__table__.columns.keys())"
```

Expected: prints column list including `hhs_score`, `ies_score`, etc.

- [ ] **Step 3: Commit**

```bash
git add src/income-scoring-service/app/models.py
git commit -m "feat(agent03): add HHS/IES ORM columns to IncomeScore model"
```

---

### Task 3: ScoreResponse Additions + HHS/IES Helpers

**Files:**
- Modify: `src/income-scoring-service/app/api/scores.py`

- [ ] **Step 1: Add new fields to ScoreResponse** (after existing `score_commentary` field)

```python
# Add to ScoreResponse class in scores.py:

# ── HHS pillars (v3.0) ────────────────────────────────────────────────────
hhs_score: Optional[float] = None
income_pillar_score: Optional[float] = None
durability_pillar_score: Optional[float] = None
income_weight: Optional[float] = None
durability_weight: Optional[float] = None
unsafe_flag: Optional[bool] = None               # None = not evaluated
unsafe_threshold: int = 20                        # snapshot of threshold at score time
hhs_status: Optional[str] = None                 # STRONG|GOOD|WATCH|CONCERN|UNSAFE|INSUFFICIENT

# ── IES ──────────────────────────────────────────────────────────────────
ies_score: Optional[float] = None
ies_calculated: bool = False
ies_blocked_reason: Optional[str] = None         # UNSAFE_FLAG|HHS_BELOW_THRESHOLD|INSUFFICIENT_DATA

# ── Quality gate surface ──────────────────────────────────────────────────
quality_gate_status: str = "PASS"
quality_gate_reasons: Optional[list] = None

# ── HHS commentary ────────────────────────────────────────────────────────
hhs_commentary: Optional[str] = None
valid_until: Optional[datetime] = None            # expose for broker-service staleness check
```

- [ ] **Step 2: Add `_HHS_UNSAFE_THRESHOLD` constant and import `_compute_ceilings`**

At the top of `scores.py`, update the import line (currently line 32):

```python
from app.scoring.income_scorer import IncomeScorer, ScoreResult, _compute_ceilings
```

Then add the constant near the top of the file (after imports):

```python
_HHS_UNSAFE_THRESHOLD = 20  # durability pillar ≤ this → UNSAFE flag
```

- [ ] **Step 3: Add `_compute_hhs()` helper** (add after `_generate_commentary()` function)

```python
def _compute_hhs(result: ScoreResult, profile: dict, gate_status: str) -> dict:
    """Compute HHS score, pillar normalizations, and UNSAFE flag.

    gate_status: "PASS" (normal) or "INSUFFICIENT_DATA" (provisional pass —
    scoring proceeded but gate lacked data to fully evaluate).
    Hard-fail gates never reach this function (vetoed with HTTP 422 in evaluate_score).
    """
    if gate_status == "INSUFFICIENT_DATA":
        return {
            "hhs_score": None,
            "income_pillar_score": None,
            "durability_pillar_score": None,
            "unsafe_flag": None,
            "hhs_status": "INSUFFICIENT",
            "income_weight": None,
            "durability_weight": None,
            "unsafe_threshold": _HHS_UNSAFE_THRESHOLD,
        }

    wy = float(profile["weight_yield"])
    wd = float(profile["weight_durability"])

    # Normalize each pillar to 0–100 using its budget as the max; clamp to [0, 100]
    # valuation_yield_score includes yield_vs_market + payout_sustainability + fcf_coverage
    # financial_durability_score includes debt_safety + dividend_consistency + volatility_score
    inc_norm = max(0.0, min(100.0, round((result.valuation_yield_score / wy) * 100, 2))) if wy > 0 else 0.0
    dur_norm = max(0.0, min(100.0, round((result.financial_durability_score / wd) * 100, 2))) if wd > 0 else 0.0

    total_hhs_budget = wy + wd
    income_w = round(wy / total_hhs_budget, 4) if total_hhs_budget > 0 else 0.5
    dur_w = round(1.0 - income_w, 4)

    hhs = round((inc_norm * income_w) + (dur_norm * dur_w), 2)
    unsafe = dur_norm <= _HHS_UNSAFE_THRESHOLD

    if unsafe:
        hhs_status = "UNSAFE"
    elif hhs >= 85:
        hhs_status = "STRONG"
    elif hhs >= 70:
        hhs_status = "GOOD"
    elif hhs >= 50:
        hhs_status = "WATCH"
    else:
        hhs_status = "CONCERN"

    return {
        "hhs_score": hhs,
        "income_pillar_score": inc_norm,
        "durability_pillar_score": dur_norm,
        "income_weight": income_w,
        "durability_weight": dur_w,
        "unsafe_flag": unsafe,
        "unsafe_threshold": _HHS_UNSAFE_THRESHOLD,
        "hhs_status": hhs_status,
    }
```

- [ ] **Step 4: Add `_compute_ies_gate()` helper** (add immediately after `_compute_hhs()`)

```python
def _compute_ies_gate(result: ScoreResult, profile: dict, hhs_fields: dict) -> dict:
    """Compute IES (Income Entry Score) if HHS gate allows.

    IES = Valuation 60% + Technical 40% (fixed weights per HHS spec §4.2).
    Gate: hhs_score > 50 AND unsafe_flag is explicitly False (not None).
    """
    hhs_score = hhs_fields["hhs_score"]
    unsafe_flag = hhs_fields["unsafe_flag"]

    if hhs_score is not None and hhs_score > 50 and unsafe_flag is False:
        wy = float(profile["weight_yield"])
        wt = float(profile["weight_technical"])
        raw = result.valuation_yield_score * 0.60 + result.technical_entry_score * 0.40
        mx = wy * 0.60 + wt * 0.40
        ies = max(0.0, min(100.0, round((raw / mx) * 100, 2))) if mx > 0 else 0.0
        return {"ies_score": ies, "ies_calculated": True, "ies_blocked_reason": None}

    if hhs_score is None:
        reason = "INSUFFICIENT_DATA"
    elif unsafe_flag is True:
        reason = "UNSAFE_FLAG"
    else:
        reason = "HHS_BELOW_THRESHOLD"

    return {"ies_score": None, "ies_calculated": False, "ies_blocked_reason": reason}
```

- [ ] **Step 5: Add `_generate_hhs_commentary()` helper** (add after `_compute_ies_gate()`)

```python
def _generate_hhs_commentary(hhs_fields: dict, factor_details: dict, asset_class: str) -> Optional[str]:
    """Generate a plain-English HHS commentary referencing only INC/DUR pillars."""
    hhs_score = hhs_fields.get("hhs_score")
    if hhs_score is None:
        return None

    hhs_status = hhs_fields.get("hhs_status", "")
    inc = hhs_fields.get("income_pillar_score", 0)
    dur = hhs_fields.get("durability_pillar_score", 0)
    unsafe = hhs_fields.get("unsafe_flag", False)

    parts = []
    if unsafe:
        parts.append(f"UNSAFE: Durability pillar {dur:.0f}/100 is at or below the safety threshold.")
    else:
        parts.append(f"HHS {hhs_score:.0f} ({hhs_status}): Income {inc:.0f}/100 · Durability {dur:.0f}/100.")

    # Highlight weakest sub-component
    fd = factor_details or {}
    dur_factors = {k: v for k, v in fd.items() if k in ("debt_safety", "dividend_consistency", "volatility_score")}
    if dur_factors:
        weakest = min(dur_factors, key=lambda k: (dur_factors[k] or {}).get("score", 99))
        w_score = (dur_factors[weakest] or {}).get("score", 0)
        w_max = (dur_factors[weakest] or {}).get("max", 1)
        if w_max and (w_score / w_max) < 0.5:
            parts.append(f"Weakest durability factor: {weakest.replace('_', ' ')} ({w_score:.0f}/{w_max:.0f} pts).")

    return " ".join(parts)
```

- [ ] **Step 6: Commit**

```bash
git add src/income-scoring-service/app/api/scores.py
git commit -m "feat(agent03): add ScoreResponse HHS/IES fields and compute helpers"
```

---

### Task 4: Unit Tests for HHS/IES Helpers

**Files:**
- Create: `src/income-scoring-service/tests/test_hhs_ies.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for _compute_hhs(), _compute_ies_gate(), _generate_hhs_commentary()."""
import pytest
from dataclasses import dataclass, field
from typing import Optional

# Import the helpers directly
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.api.scores import _compute_hhs, _compute_ies_gate, _generate_hhs_commentary, _HHS_UNSAFE_THRESHOLD


@dataclass
class FakeResult:
    valuation_yield_score: float = 30.0
    financial_durability_score: float = 30.0
    technical_entry_score: float = 15.0
    factor_details: dict = field(default_factory=dict)


DEFAULT_PROFILE = {
    "weight_yield": 40,
    "weight_durability": 40,
    "weight_technical": 20,
    "yield_sub_weights": {"payout_sustainability": 40, "yield_vs_market": 35, "fcf_coverage": 25},
    "durability_sub_weights": {"debt_safety": 40, "dividend_consistency": 35, "volatility_score": 25},
    "technical_sub_weights": {"price_momentum": 60, "price_range_position": 40},
}


class TestComputeHhs:
    def test_pass_gate_returns_hhs_score(self):
        r = FakeResult(valuation_yield_score=30.0, financial_durability_score=30.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["hhs_score"] == 75.0          # (75 * 0.5) + (75 * 0.5) = 75
        assert out["income_pillar_score"] == 75.0  # 30/40 * 100
        assert out["durability_pillar_score"] == 75.0

    def test_insufficient_data_returns_none_hhs(self):
        r = FakeResult()
        out = _compute_hhs(r, DEFAULT_PROFILE, "INSUFFICIENT_DATA")
        assert out["hhs_score"] is None
        assert out["unsafe_flag"] is None
        assert out["hhs_status"] == "INSUFFICIENT"

    def test_unsafe_flag_when_durability_at_threshold(self):
        dur_score = ((_HHS_UNSAFE_THRESHOLD / 100) * 40)  # 8.0 pts → 20/100 normalized
        r = FakeResult(financial_durability_score=dur_score)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["unsafe_flag"] is True
        assert out["hhs_status"] == "UNSAFE"

    def test_unsafe_flag_false_above_threshold(self):
        r = FakeResult(financial_durability_score=30.0)  # 75 normalized
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["unsafe_flag"] is False

    def test_status_strong_at_85(self):
        r = FakeResult(valuation_yield_score=34.0, financial_durability_score=34.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["hhs_score"] >= 85
        assert out["hhs_status"] == "STRONG"

    def test_status_watch_between_50_and_70(self):
        r = FakeResult(valuation_yield_score=22.0, financial_durability_score=22.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert 50 <= out["hhs_score"] < 70
        assert out["hhs_status"] in ("WATCH", "GOOD")

    def test_scores_clamped_at_100(self):
        r = FakeResult(valuation_yield_score=50.0, financial_durability_score=50.0)  # exceeds budget
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["income_pillar_score"] == 100.0
        assert out["durability_pillar_score"] == 100.0

    def test_scores_clamped_at_0(self):
        r = FakeResult(valuation_yield_score=-5.0, financial_durability_score=-5.0)
        out = _compute_hhs(r, DEFAULT_PROFILE, "PASS")
        assert out["income_pillar_score"] == 0.0
        assert out["durability_pillar_score"] == 0.0


class TestComputeIesGate:
    def test_ies_computed_when_hhs_above_50_and_not_unsafe(self):
        hhs_fields = {"hhs_score": 75.0, "unsafe_flag": False}
        r = FakeResult(valuation_yield_score=30.0, technical_entry_score=15.0)
        out = _compute_ies_gate(r, DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is True
        assert out["ies_score"] is not None
        assert 0.0 <= out["ies_score"] <= 100.0
        assert out["ies_blocked_reason"] is None

    def test_ies_blocked_when_unsafe(self):
        hhs_fields = {"hhs_score": 80.0, "unsafe_flag": True}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False
        assert out["ies_blocked_reason"] == "UNSAFE_FLAG"

    def test_ies_blocked_when_hhs_below_50(self):
        hhs_fields = {"hhs_score": 45.0, "unsafe_flag": False}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False
        assert out["ies_blocked_reason"] == "HHS_BELOW_THRESHOLD"

    def test_ies_blocked_when_hhs_none(self):
        hhs_fields = {"hhs_score": None, "unsafe_flag": None}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False
        assert out["ies_blocked_reason"] == "INSUFFICIENT_DATA"

    def test_ies_blocked_when_unsafe_flag_is_none(self):
        # unsafe_flag=None means gate-failed — must NOT allow IES even if hhs > 50
        hhs_fields = {"hhs_score": 60.0, "unsafe_flag": None}
        out = _compute_ies_gate(FakeResult(), DEFAULT_PROFILE, hhs_fields)
        assert out["ies_calculated"] is False


class TestGenerateHhsCommentary:
    def test_returns_none_when_hhs_none(self):
        assert _generate_hhs_commentary({"hhs_score": None}, {}, "DIVIDEND_STOCK") is None

    def test_returns_string_with_hhs_score(self):
        hhs_fields = {
            "hhs_score": 75.0, "hhs_status": "GOOD",
            "income_pillar_score": 80.0, "durability_pillar_score": 70.0,
            "unsafe_flag": False,
        }
        result = _generate_hhs_commentary(hhs_fields, {}, "DIVIDEND_STOCK")
        assert result is not None
        assert "75" in result
        assert "GOOD" in result

    def test_unsafe_commentary_mentions_threshold(self):
        hhs_fields = {
            "hhs_score": 30.0, "hhs_status": "UNSAFE",
            "income_pillar_score": 60.0, "durability_pillar_score": 15.0,
            "unsafe_flag": True,
        }
        result = _generate_hhs_commentary(hhs_fields, {}, "DIVIDEND_STOCK")
        assert "UNSAFE" in result
```

- [ ] **Step 2: Run tests and verify they fail** (helpers not yet integrated — functions exist but tests import them)

```bash
cd src/income-scoring-service
python3 -m pytest tests/test_hhs_ies.py -v
```

Expected: tests pass (helpers were added in Task 3 — tests validate the implementations written there).

- [ ] **Step 3: Commit**

```bash
git add src/income-scoring-service/tests/test_hhs_ies.py
git commit -m "test(agent03): unit tests for _compute_hhs, _compute_ies_gate, _generate_hhs_commentary"
```

---

### Task 5: Wire Helpers into `evaluate_score` + Update `_orm_to_response()`

**Files:**
- Modify: `src/income-scoring-service/app/api/scores.py`

- [ ] **Step 1: Add the call site in `evaluate_score`** after step 5b (signal penalty block) and before step 6 (DB persist)

Find the comment `# 6. Persist to DB` in `evaluate_score` and insert before it:

```python
    # 5c. HHS / IES computation
    from app.scoring.quality_gate import GateStatus
    _inline_status = getattr(gate_proxy, "status", None)
    _gate_status = (
        "INSUFFICIENT_DATA"
        if _inline_status == GateStatus.INSUFFICIENT_DATA
        else "PASS"
    )
    hhs_fields = _compute_hhs(result, weight_profile, _gate_status)
    ies_fields = _compute_ies_gate(result, weight_profile, hhs_fields)
    quality_gate_status_str = _gate_status
    quality_gate_reasons_list = getattr(gate_proxy, "fail_reasons", None) or []
    hhs_commentary_str = _generate_hhs_commentary(
        hhs_fields=hhs_fields,
        factor_details=result.factor_details or {},
        asset_class=asset_class,
    )
```

- [ ] **Step 2: Add HHS/IES fields to the `IncomeScore(...)` DB persist block**

In the `IncomeScore(...)` constructor call inside step 6, add after `signal_penalty_details=signal_penalty_details`:

```python
            hhs_score=hhs_fields["hhs_score"],
            income_pillar_score=hhs_fields["income_pillar_score"],
            durability_pillar_score=hhs_fields["durability_pillar_score"],
            income_weight=hhs_fields["income_weight"],
            durability_weight=hhs_fields["durability_weight"],
            unsafe_flag=hhs_fields["unsafe_flag"],
            unsafe_threshold=hhs_fields["unsafe_threshold"],
            hhs_status=hhs_fields["hhs_status"],
            ies_score=ies_fields["ies_score"],
            ies_calculated=ies_fields["ies_calculated"],
            ies_blocked_reason=ies_fields["ies_blocked_reason"],
            quality_gate_status=quality_gate_status_str,
            quality_gate_reasons=quality_gate_reasons_list or None,
            hhs_commentary=hhs_commentary_str,
```

- [ ] **Step 3: Update `_orm_to_response()`** — add new kwargs to the `ScoreResponse(...)` constructor:

```python
            # HHS/IES fields (v3.0)
            hhs_score=score.hhs_score,
            income_pillar_score=score.income_pillar_score,
            durability_pillar_score=score.durability_pillar_score,
            income_weight=score.income_weight,
            durability_weight=score.durability_weight,
            unsafe_flag=score.unsafe_flag,
            unsafe_threshold=score.unsafe_threshold or 20,
            hhs_status=score.hhs_status,
            ies_score=score.ies_score,
            ies_calculated=score.ies_calculated or False,
            ies_blocked_reason=score.ies_blocked_reason,
            quality_gate_status=score.quality_gate_status or "PASS",
            quality_gate_reasons=score.quality_gate_reasons,
            hhs_commentary=score.hhs_commentary,
            valid_until=score.valid_until,
```

- [ ] **Step 4: Run all existing tests + new HHS tests**

```bash
cd src/income-scoring-service
python3 -m pytest tests/ -v --tb=short
```

Expected: all existing tests pass; `test_hhs_ies.py` passes.

- [ ] **Step 5: Rebuild and test Agent 03 manually**

```bash
# From project root:
docker-compose build agent-03-income-scoring
docker-compose up -d agent-03-income-scoring
# Wait ~10s then score a ticker:
curl -s -X POST http://localhost:8003/scores/evaluate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_TOKEN" \
  -d '{"ticker":"MAIN","asset_class":"BDC"}' | python3 -m json.tool | grep -E "hhs|ies|unsafe"
```

Expected: response includes `hhs_score`, `income_pillar_score`, `unsafe_flag`, `ies_score` fields.

- [ ] **Step 6: Commit**

```bash
git add src/income-scoring-service/app/api/scores.py
git commit -m "feat(agent03): wire HHS/IES into evaluate_score + _orm_to_response"
```

---

## Phase 2 — Broker-Service Portfolio Endpoints

### Task 6: Portfolio Aggregator Service

**Files:**
- Create: `src/broker-service/app/services/__init__.py`
- Create: `src/broker-service/app/services/portfolio_aggregator.py`

- [ ] **Step 1: Create `services/__init__.py`** (empty)

```bash
touch src/broker-service/app/services/__init__.py
```

- [ ] **Step 2: Create `portfolio_aggregator.py`**

```python
"""
Portfolio aggregator — fetches HHS/IES scores from Agent 03 and computes
portfolio-level aggregates: Agg HHS, NAA Yield, HHI, concentration, etc.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


async def fetch_score(ticker: str, scoring_service_url: str, service_token: str) -> Optional[dict]:
    """GET /scores/{ticker} from Agent 03. Returns None on error."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{scoring_service_url}/scores/{ticker}",
                headers={"Authorization": f"Bearer {service_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning("Score fetch failed for %s: %s", ticker, e)
    return None


def _is_stale(score: dict) -> bool:
    """True if valid_until is in the past."""
    vu = score.get("valid_until")
    if not vu:
        return False
    try:
        exp = datetime.fromisoformat(vu.replace("Z", "+00:00"))
        return exp < datetime.now(timezone.utc)
    except Exception:
        return False


def compute_hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman Index = sum of squared position weights."""
    return round(sum(w ** 2 for w in weights), 4)


def aggregate_portfolio(positions: list[dict], scores: dict[str, dict]) -> dict:
    """Compute portfolio-level aggregates from positions + score map.

    positions: list of dicts with keys: symbol, current_value, annual_income
    scores: ticker → ScoreResponse dict
    """
    if not positions:
        return _empty_aggregate()

    total_value = sum(p.get("current_value") or 0 for p in positions)
    total_income = sum(p.get("annual_income") or 0 for p in positions)

    hhs_values, hhs_weights = [], []
    unsafe_count = 0
    gate_fail_count = 0
    asset_class_totals: dict[str, float] = {}
    sector_totals: dict[str, float] = {}

    for p in positions:
        ticker = p.get("symbol", "")
        val = p.get("current_value") or 0
        score = scores.get(ticker)

        # Asset class concentration
        ac = (score or {}).get("asset_class") or p.get("asset_type") or "UNKNOWN"
        asset_class_totals[ac] = asset_class_totals.get(ac, 0) + val

        # Sector concentration (from position data)
        sector = p.get("sector") or "Other"
        sector_totals[sector] = sector_totals.get(sector, 0) + val

        if not score or _is_stale(score):
            continue

        hhs = score.get("hhs_score")
        if hhs is not None and score.get("quality_gate_status", "PASS") == "PASS":
            weight = val / total_value if total_value > 0 else 0
            hhs_values.append(hhs * weight)
            hhs_weights.append(weight)

        if score.get("unsafe_flag") is True:
            unsafe_count += 1
        if score.get("quality_gate_status") in ("FAIL", "INSUFFICIENT_DATA"):
            gate_fail_count += 1

    # Weighted average HHS
    agg_hhs = round(sum(hhs_values), 2) if hhs_values else None

    # NAA Yield (use gross yield as proxy; full NAA requires tax service)
    naa_yield = round(total_income / total_value, 4) if total_value > 0 else None

    # HHI on position weights
    weights = [p.get("current_value", 0) / total_value for p in positions if total_value > 0]
    hhi = compute_hhi(weights)

    # Concentration breakdowns
    concentration_by_class = [
        {"class": k, "value": round(v, 2), "pct": round(v / total_value * 100, 1) if total_value > 0 else 0}
        for k, v in sorted(asset_class_totals.items(), key=lambda x: -x[1])
    ]
    concentration_by_sector = [
        {"sector": k, "value": round(v, 2), "pct": round(v / total_value * 100, 1) if total_value > 0 else 0}
        for k, v in sorted(sector_totals.items(), key=lambda x: -x[1])
    ]

    # Top 5 income holders
    positions_with_income = sorted(
        [p for p in positions if (p.get("annual_income") or 0) > 0],
        key=lambda p: p.get("annual_income", 0),
        reverse=True,
    )[:5]
    top_income = [
        {
            "ticker": p.get("symbol"),
            "asset_class": (scores.get(p.get("symbol") or "") or {}).get("asset_class") or p.get("asset_type"),
            "annual_income": round(p.get("annual_income", 0), 2),
            "income_pct": round(p.get("annual_income", 0) / total_income * 100, 1) if total_income > 0 else 0,
            "unsafe": (scores.get(p.get("symbol") or "") or {}).get("unsafe_flag") is True,
        }
        for p in positions_with_income
    ]

    return {
        "agg_hhs": agg_hhs,
        "naa_yield": naa_yield,
        "naa_yield_pre_tax": True,   # flag: using gross yield until tax service integrated
        "total_value": round(total_value, 2),
        "annual_income": round(total_income, 2),
        "hhi": hhi,
        "unsafe_count": unsafe_count,
        "gate_fail_count": gate_fail_count,
        "holding_count": len(positions),
        "concentration_by_class": concentration_by_class,
        "concentration_by_sector": concentration_by_sector,
        "top_income_holdings": top_income,
    }


def _empty_aggregate() -> dict:
    return {
        "agg_hhs": None, "naa_yield": None, "naa_yield_pre_tax": True,
        "total_value": 0.0, "annual_income": 0.0, "hhi": 0.0,
        "unsafe_count": 0, "gate_fail_count": 0, "holding_count": 0,
        "concentration_by_class": [], "concentration_by_sector": [],
        "top_income_holdings": [],
    }
```

- [ ] **Step 3: Commit**

```bash
git add src/broker-service/app/services/
git commit -m "feat(broker): portfolio aggregator service (HHI, Agg HHS, concentration)"
```

---

### Task 7: Portfolio Endpoint Unit Tests

**Files:**
- Create: `src/broker-service/tests/__init__.py`
- Create: `src/broker-service/tests/test_portfolio_aggregator.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for portfolio_aggregator.py"""
import pytest
from app.services.portfolio_aggregator import aggregate_portfolio, compute_hhi, _is_stale


POSITIONS = [
    {"symbol": "MAIN", "current_value": 10000, "annual_income": 600, "asset_type": "BDC", "sector": "Financial"},
    {"symbol": "JEPI", "current_value": 5000, "annual_income": 300, "asset_type": "COVERED_CALL_ETF", "sector": "Financial"},
    {"symbol": "O",    "current_value": 5000, "annual_income": 200, "asset_type": "EQUITY_REIT",   "sector": "Real Estate"},
]

SCORES = {
    "MAIN": {"asset_class": "BDC", "hhs_score": 80.0, "unsafe_flag": False, "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
    "JEPI": {"asset_class": "COVERED_CALL_ETF", "hhs_score": 60.0, "unsafe_flag": False, "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
    "O":    {"asset_class": "EQUITY_REIT",  "hhs_score": 15.0, "unsafe_flag": True,  "quality_gate_status": "PASS", "valid_until": "2099-01-01T00:00:00+00:00"},
}


class TestComputeHhi:
    def test_equal_weights_three_positions(self):
        weights = [1/3, 1/3, 1/3]
        assert round(compute_hhi(weights), 4) == round(3 * (1/3)**2, 4)

    def test_single_position_is_one(self):
        assert compute_hhi([1.0]) == 1.0

    def test_empty_is_zero(self):
        assert compute_hhi([]) == 0.0


class TestAggregatePortfolio:
    def test_agg_hhs_is_value_weighted(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        # MAIN (10k): 80 * 0.5 = 40; JEPI (5k): 60 * 0.25 = 15; O (5k): excluded (unsafe — still counted but hhs is included)
        # O: hhs=15, unsafe=True, gate=PASS → hhs IS counted (unsafe doesn't exclude from avg, spec says gate-fail and stale excluded)
        assert result["agg_hhs"] is not None
        assert 30 < result["agg_hhs"] < 70

    def test_unsafe_count(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        assert result["unsafe_count"] == 1  # only O

    def test_total_value(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        assert result["total_value"] == 20000.0

    def test_annual_income(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        assert result["annual_income"] == 1100.0

    def test_concentration_by_class_sorted_desc(self):
        result = aggregate_portfolio(POSITIONS, SCORES)
        pcts = [c["pct"] for c in result["concentration_by_class"]]
        assert pcts == sorted(pcts, reverse=True)

    def test_empty_positions(self):
        result = aggregate_portfolio([], {})
        assert result["agg_hhs"] is None
        assert result["total_value"] == 0.0

    def test_stale_score_excluded_from_hhs(self):
        stale_scores = {k: {**v, "valid_until": "2000-01-01T00:00:00+00:00"} for k, v in SCORES.items()}
        result = aggregate_portfolio(POSITIONS, stale_scores)
        assert result["agg_hhs"] is None   # all stale → no HHS data
```

- [ ] **Step 2: Run tests**

```bash
cd src/broker-service
python3 -m pytest tests/test_portfolio_aggregator.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/broker-service/tests/
git commit -m "test(broker): portfolio aggregator unit tests"
```

---

### Task 8: Portfolio API Endpoints

**Files:**
- Modify: `src/broker-service/app/api/broker.py`
- Modify: `src/broker-service/app/config.py`

- [ ] **Step 1: Add `SCORING_SERVICE_URL` and `SERVICE_TOKEN` to broker config**

In `src/broker-service/app/config.py`, add:

```python
scoring_service_url: str = "http://agent-03-income-scoring:8003"
service_token: str = ""          # read from SERVICE_TOKEN env var
```

In `docker-compose.yml`, add to broker-service environment:

```yaml
- SCORING_SERVICE_URL=${SCORING_SERVICE_URL:-http://agent-03-income-scoring:8003}
- SERVICE_TOKEN=${SERVICE_TOKEN}
```

- [ ] **Step 2: Add portfolio endpoints to `broker.py`**

Add these imports at the top:

```python
import asyncio
import httpx
from app.services.portfolio_aggregator import aggregate_portfolio, fetch_score
```

Add endpoints after the existing routes:

```python
@router.get("/portfolios")
async def list_portfolios(db: Session = Depends(get_db)):
    """List all portfolios with aggregate KPIs."""
    rows = db.execute(text("""
        SELECT p.id, p.name, p.account_type AS tax_status, a.broker,
               COUNT(pos.id) AS holding_count, p.last_refreshed_at,
               SUM(pos.current_value) AS total_value,
               SUM(pos.annual_income) AS annual_income
        FROM platform_shared.portfolios p
        LEFT JOIN platform_shared.accounts a ON a.portfolio_id = p.id
        LEFT JOIN platform_shared.positions pos ON pos.portfolio_id = p.id
        GROUP BY p.id, p.name, p.account_type, a.broker, p.last_refreshed_at
        ORDER BY p.name
    """)).mappings().all()

    results = []
    for row in rows:
        # Fetch positions for this portfolio
        positions = _get_positions_for_portfolio(db, row["id"])
        # Fetch scores from Agent 03 (concurrent)
        scores = await _fetch_scores_for_positions(positions)
        agg = aggregate_portfolio(positions, scores)
        results.append({
            "id": str(row["id"]),
            "name": row["name"],
            "tax_status": row["tax_status"],
            "broker": row["broker"],
            "last_refresh": row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
            **agg,
        })
    return results


@router.get("/portfolios/{portfolio_id}/summary")
async def portfolio_summary(portfolio_id: str, db: Session = Depends(get_db)):
    """Full portfolio summary for the portfolio page."""
    row = db.execute(text("""
        SELECT p.id, p.name, p.account_type AS tax_status, a.broker,
               p.last_refreshed_at
        FROM platform_shared.portfolios p
        LEFT JOIN platform_shared.accounts a ON a.portfolio_id = p.id
        WHERE p.id = :id
        LIMIT 1
    """), {"id": portfolio_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    positions = _get_positions_for_portfolio(db, portfolio_id)
    scores = await _fetch_scores_for_positions(positions)
    agg = aggregate_portfolio(positions, scores)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "tax_status": row["tax_status"],
        "broker": row["broker"],
        "last_refresh": row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
        **agg,
        "scores_unavailable": not scores,
    }


def _get_positions_for_portfolio(db: Session, portfolio_id: str) -> list[dict]:
    rows = db.execute(text("""
        SELECT pos.symbol, pos.current_value, pos.annual_income,
               pos.asset_type, pos.sector, pos.industry
        FROM platform_shared.positions pos
        WHERE pos.portfolio_id = :pid
    """), {"pid": portfolio_id}).mappings().all()
    return [dict(r) for r in rows]


async def _fetch_scores_for_positions(positions: list[dict]) -> dict[str, dict]:
    """Fetch scores concurrently from Agent 03 for all unique tickers."""
    from app.config import settings
    tickers = list({p["symbol"] for p in positions if p.get("symbol")})
    if not tickers:
        return {}
    tasks = [fetch_score(t, settings.scoring_service_url, settings.service_token) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {t: r for t, r in zip(tickers, results) if isinstance(r, dict)}
```

- [ ] **Step 3: Rebuild and test broker-service**

```bash
docker-compose build broker-service
docker-compose up -d broker-service
# Test endpoint (sync a portfolio first if needed):
curl -s http://localhost:8013/broker/portfolios \
  -H "Authorization: Bearer $SERVICE_TOKEN" | python3 -m json.tool
```

Expected: JSON array of portfolio objects with `agg_hhs`, `hhi`, etc.

- [ ] **Step 4: Commit**

```bash
git add src/broker-service/
git commit -m "feat(broker): GET /broker/portfolios and /broker/portfolios/{id}/summary"
```

---

## Phase 3 — Frontend Redesign

### Task 9: Types, Help Content, Design Tokens

**Files:**
- Modify: `src/frontend/src/lib/types.ts`
- Modify: `src/frontend/src/lib/help-content.ts`
- Modify: `src/frontend/src/lib/config.ts`

- [ ] **Step 1: Add HHS/IES fields to types.ts**

Add after the existing score fields in the `Position` interface (after `signal_penalty`):

```typescript
// HHS/IES v3.0
hhs_score?: number | null;
income_pillar_score?: number | null;
durability_pillar_score?: number | null;
income_weight?: number | null;
durability_weight?: number | null;
unsafe_flag?: boolean | null;
unsafe_threshold?: number;
hhs_status?: string | null;
ies_score?: number | null;
ies_calculated?: boolean;
ies_blocked_reason?: string | null;
quality_gate_status?: string;
quality_gate_reasons?: string[] | null;
hhs_commentary?: string | null;
valid_until?: string | null;
```

Add new `PortfolioSummary` and `PortfolioListItem` interfaces after the `Position` interface:

```typescript
export interface PortfolioListItem {
  id: string;
  name: string;
  tax_status?: string;
  broker?: string;
  last_refresh?: string | null;
  holding_count: number;
  total_value: number;
  annual_income: number;
  naa_yield?: number | null;
  naa_yield_pre_tax?: boolean;
  agg_hhs?: number | null;
  hhi?: number;
  unsafe_count: number;
  gate_fail_count: number;
  concentration_by_class: Array<{ class: string; value: number; pct: number }>;
}

export interface PortfolioSummary extends PortfolioListItem {
  concentration_by_sector: Array<{ sector: string; value: number; pct: number }>;
  top_income_holdings: Array<{
    ticker: string;
    asset_class?: string;
    annual_income: number;
    income_pct: number;
    unsafe: boolean;
  }>;
  scores_unavailable?: boolean;
}
```

- [ ] **Step 2: Add HHS/IES entries to help-content.ts**

Add a new `HHS_HELP` export object at the end of the file:

```typescript
export const HHS_HELP: Record<string, string> = {
  hhs_score: "Holding Health Score (0–100): Income pillar × income weight + Durability pillar × durability weight. Gate-failed holdings show — until rescored.",
  income_pillar: "Income Pillar (0–100): Yield attractiveness, payout sustainability, and FCF coverage — normalized to 0–100 from the raw yield score.",
  durability_pillar: "Durability Pillar (0–100): Debt safety, dividend consistency, and volatility — normalized to 0–100. Values ≤ 20 trigger the UNSAFE flag.",
  unsafe_flag: "UNSAFE: Durability pillar is at or below the safety threshold (default 20). Immediate review recommended regardless of overall HHS.",
  hhs_status: "HHS status band: STRONG ≥ 85 · GOOD ≥ 70 · WATCH ≥ 50 · CONCERN < 50 · UNSAFE when Durability ≤ threshold.",
  ies_score: "Income Entry Score (0–100): Valuation 60% + Technical 40%. Only calculated when HHS > 50 and no UNSAFE flag.",
  ies_blocked: "IES could not be calculated. Reason: UNSAFE_FLAG means Durability is critical; HHS_BELOW_THRESHOLD means overall health is too low; INSUFFICIENT_DATA means gate lacked data.",
  quality_gate: "Quality Gate status: PASS = all required criteria met; INSUFFICIENT_DATA = gate ran but lacked data (score is provisional).",
  agg_hhs: "Aggregate HHS: position-weighted average HHS across all holdings. Gate-failed and stale (expired) holdings are excluded.",
  naa_yield: "Net After-All Yield: (Gross Dividend − Fee Drag − Tax Drag) / Total Invested. Holdings without tax data shown pre-tax (marked *).",
  hhi: "Herfindahl-Hirschman Index: sum of squared position weights. Higher = more concentrated. Flag at > 0.10 (moderate profile).",
  chowder_number: "Chowder Number = TTM dividend yield + 5-year dividend growth CAGR. ≥ 12 STRONG · 8–12 MODERATE · < 8 WEAK. Informational only.",
};
```

- [ ] **Step 3: Add design tokens to config.ts**

Add or update the CSS variable map in `config.ts`:

```typescript
export const DESIGN_TOKENS = {
  // HHS status colors (maps hhs_status → CSS class prefix)
  HHS_STATUS_COLORS: {
    STRONG:       "text-green-400",
    GOOD:         "text-green-400",
    WATCH:        "text-amber-400",
    CONCERN:      "text-orange-400",
    UNSAFE:       "text-red-400",
    INSUFFICIENT: "text-slate-500",
  } as Record<string, string>,

  // Asset-class colors for concentration bars (matches spec §6.1)
  ASSET_CLASS_COLORS: {
    BDC:                "bg-purple-400",
    EQUITY_REIT:        "bg-blue-500",
    MORTGAGE_REIT:      "bg-blue-400",
    COVERED_CALL_ETF:   "bg-amber-400",
    MLP:                "bg-teal-400",
    DIVIDEND_STOCK:     "bg-green-500",
    BOND:               "bg-yellow-200",
    PREFERRED_STOCK:    "bg-pink-400",
    UNKNOWN:            "bg-slate-600",
  } as Record<string, string>,
} as const;
```

- [ ] **Step 4: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/lib/types.ts src/frontend/src/lib/help-content.ts src/frontend/src/lib/config.ts
git commit -m "feat(frontend): HHS/IES types, help-content entries, design tokens"
```

---

### Task 10: TanStack Query Hooks

**Files:**
- Create: `src/frontend/src/lib/hooks/use-portfolios.ts`

- [ ] **Step 1: Create the hooks file**

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/lib/config";
import type { PortfolioListItem, PortfolioSummary } from "@/lib/types";

const authHeader = () => ({
  Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : ""}`,
});

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeader() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

/** All portfolios with aggregate KPIs. */
export function usePortfolios() {
  return useQuery<PortfolioListItem[]>({
    queryKey: ["portfolios"],
    queryFn: () => apiFetch("/broker/portfolios"),
    staleTime: 30_000,
  });
}

/** Full summary for a single portfolio. */
export function usePortfolioSummary(portfolioId: string | undefined) {
  return useQuery<PortfolioSummary>({
    queryKey: ["portfolio-summary", portfolioId],
    queryFn: () => apiFetch(`/broker/portfolios/${portfolioId}/summary`),
    enabled: !!portfolioId,
    staleTime: 30_000,
  });
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/lib/hooks/
git commit -m "feat(frontend): usePortfolios + usePortfolioSummary TanStack Query hooks"
```

---

### Task 11: Shared Portfolio Components

**Files:**
- Create: `src/frontend/src/components/portfolio/hhs-badge.tsx`
- Create: `src/frontend/src/components/portfolio/kpi-strip.tsx`
- Create: `src/frontend/src/components/portfolio/concentration-bar.tsx`

- [ ] **Step 1: Create `hhs-badge.tsx`**

```tsx
"use client";
import { cn } from "@/lib/utils";
import { DESIGN_TOKENS } from "@/lib/config";
import { HelpTooltip } from "@/components/help-tooltip";
import { HHS_HELP } from "@/lib/help-content";

interface HhsBadgeProps {
  status?: string | null;
  score?: number | null;
  showScore?: boolean;
  className?: string;
}

export function HhsBadge({ status, score, showScore = true, className }: HhsBadgeProps) {
  if (!status) return <span className="text-muted-foreground text-xs">—</span>;
  const colorClass = DESIGN_TOKENS.HHS_STATUS_COLORS[status] ?? "text-slate-400";
  return (
    <span className={cn("inline-flex items-center gap-1 font-semibold text-xs", colorClass, className)}>
      {status === "UNSAFE" && <span>⚠</span>}
      {status}
      {showScore && score != null && <span className="font-normal opacity-70">({score.toFixed(0)})</span>}
      <HelpTooltip text={HHS_HELP.hhs_status} />
    </span>
  );
}
```

- [ ] **Step 2: Create `kpi-strip.tsx`**

```tsx
"use client";
import { cn } from "@/lib/utils";
import { HelpTooltip } from "@/components/help-tooltip";

interface KpiItem {
  label: string;
  value: string | number | null | undefined;
  helpText?: string;
  colorClass?: string;
  alert?: boolean;
}

interface KpiStripProps {
  items: KpiItem[];
  className?: string;
}

export function KpiStrip({ items, className }: KpiStripProps) {
  return (
    <div className={cn(
      "grid gap-1.5 mb-3",
      "grid-cols-2 sm:grid-cols-4 lg:grid-cols-8",
      className
    )}>
      {items.map((item, i) => (
        <div
          key={i}
          className={cn(
            "bg-card border rounded-lg px-2.5 py-1.5",
            item.alert && "border-red-900/50 bg-red-950/30"
          )}
        >
          <div className="flex items-center gap-0.5 text-[0.625rem] font-bold uppercase text-muted-foreground tracking-wide">
            {item.label}
            {item.helpText && <HelpTooltip text={item.helpText} />}
          </div>
          <div className={cn("text-sm font-bold mt-0.5", item.colorClass ?? "text-foreground")}>
            {item.value ?? "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create `concentration-bar.tsx`**

```tsx
"use client";
import { cn } from "@/lib/utils";
import { DESIGN_TOKENS } from "@/lib/config";
import { HelpTooltip } from "@/components/help-tooltip";

interface ConcentrationItem {
  label: string;
  pct: number;
  colorClass?: string;
}

interface ConcentrationBarProps {
  items: ConcentrationItem[];
  label?: string;
  helpText?: string;
  className?: string;
}

export function ConcentrationBar({ items, label, helpText, className }: ConcentrationBarProps) {
  const withColors = items.map((item) => ({
    ...item,
    colorClass: item.colorClass ?? DESIGN_TOKENS.ASSET_CLASS_COLORS[item.label] ?? "bg-slate-600",
  }));

  return (
    <div className={cn("space-y-1.5", className)}>
      {label && (
        <div className="flex items-center gap-1 text-[0.625rem] font-bold uppercase text-muted-foreground tracking-wide">
          {label}
          {helpText && <HelpTooltip text={helpText} />}
        </div>
      )}
      {/* Stacked bar */}
      <div className="flex h-2.5 w-full rounded overflow-hidden gap-px">
        {withColors.map((item, i) => (
          <div
            key={i}
            className={cn("h-full", item.colorClass)}
            style={{ width: `${item.pct}%` }}
            title={`${item.label}: ${item.pct}%`}
          />
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {withColors.map((item, i) => (
          <div key={i} className="flex items-center gap-1 text-[0.6rem] text-muted-foreground">
            <div className={cn("w-2 h-2 rounded-sm flex-shrink-0", item.colorClass)} />
            {item.label} {item.pct.toFixed(0)}%
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/components/portfolio/
git commit -m "feat(frontend): HhsBadge, KpiStrip, ConcentrationBar shared components"
```

---

### Task 12: Portfolio Card + Grand Dashboard

**Files:**
- Create: `src/frontend/src/components/portfolio/portfolio-card.tsx`
- Create: `src/frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Create `portfolio-card.tsx`**

```tsx
"use client";
import { useRouter } from "next/navigation";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import type { PortfolioListItem } from "@/lib/types";
import { HhsBadge } from "./hhs-badge";
import { ConcentrationBar } from "./concentration-bar";
import { HelpTooltip } from "@/components/help-tooltip";
import { HHS_HELP } from "@/lib/help-content";
import { ArrowRight } from "lucide-react";

interface PortfolioCardProps {
  portfolio: PortfolioListItem;
}

export function PortfolioCard({ portfolio: p }: PortfolioCardProps) {
  const router = useRouter();
  const navigate = () => router.push(`/portfolios/${p.id}`);

  return (
    <div
      className="bg-card border border-border rounded-xl flex-shrink-0 w-[300px] overflow-hidden cursor-pointer hover:border-border/80 transition-colors"
      onClick={navigate}
      style={{ scrollSnapAlign: "start" }}
    >
      {/* Header */}
      <div className="flex items-start justify-between px-3.5 pt-3 pb-2 border-b border-border/50">
        <div>
          <div className="font-bold text-sm leading-tight">{p.name}</div>
          <div className="text-[0.6rem] text-muted-foreground mt-0.5 space-x-1.5">
            {p.tax_status && <span className="bg-muted rounded px-1 py-0.5">{p.tax_status}</span>}
            {p.broker && <span className="bg-muted rounded px-1 py-0.5">{p.broker}</span>}
            <span>{p.holding_count} holdings</span>
          </div>
        </div>
        <div className="text-right">
          <HhsBadge status={p.agg_hhs != null ? (p.agg_hhs >= 70 ? "GOOD" : p.agg_hhs >= 50 ? "WATCH" : "CONCERN") : undefined} score={p.agg_hhs} />
        </div>
      </div>

      {/* KPI grid 3×2 */}
      <div className="grid grid-cols-3 gap-px bg-border/30 border-b border-border/50">
        {[
          { label: "Value",    value: formatCurrency(p.total_value) },
          { label: "Income",   value: formatCurrency(p.annual_income) },
          { label: "Yield",    value: p.naa_yield != null ? `${(p.naa_yield * 100).toFixed(2)}%${p.naa_yield_pre_tax ? "*" : ""}` : "—" },
          { label: "HHI",      value: p.hhi?.toFixed(3) ?? "—" },
          { label: "Holdings", value: p.holding_count },
          { label: "⚠ UNSAFE", value: p.unsafe_count > 0 ? p.unsafe_count : "✓" },
        ].map((kpi, i) => (
          <div key={i} className="bg-card px-2.5 py-1.5">
            <div className="text-[0.55rem] font-bold uppercase text-muted-foreground">{kpi.label}</div>
            <div className={cn("text-xs font-bold mt-0.5", i === 5 && p.unsafe_count > 0 ? "text-red-400" : "text-foreground")}>
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {/* Concentration bar */}
      <div className="px-3.5 py-2.5">
        <ConcentrationBar
          items={(p.concentration_by_class ?? []).map(c => ({ label: c.class, pct: c.pct }))}
        />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3.5 pb-3">
        <div className="flex items-center gap-1.5 text-[0.6rem] text-muted-foreground">
          {p.unsafe_count > 0 && (
            <span className="bg-red-950 text-red-400 rounded px-1.5 py-0.5 font-bold">⚠ {p.unsafe_count} UNSAFE</span>
          )}
        </div>
        <button
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 font-medium"
          onClick={navigate}
        >
          Open <ArrowRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

export function AddPortfolioCard() {
  return (
    <div className="flex-shrink-0 w-[300px] border-2 border-dashed border-border rounded-xl flex items-center justify-center min-h-[200px] text-muted-foreground text-sm"
      style={{ scrollSnapAlign: "start" }}>
      <div className="text-center p-4">
        <div className="text-2xl mb-2">+</div>
        <div className="font-medium">Add Portfolio</div>
        <div className="text-xs text-muted-foreground/70 mt-1">Coming soon</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/page.tsx`**

```tsx
"use client";
import { useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { usePortfolios } from "@/lib/hooks/use-portfolios";
import { PortfolioCard, AddPortfolioCard } from "@/components/portfolio/portfolio-card";
import { KpiStrip } from "@/components/portfolio/kpi-strip";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { HHS_HELP } from "@/lib/help-content";

export default function DashboardPage() {
  const { data: portfolios, isLoading, error, refetch } = usePortfolios();
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: "left" | "right") => {
    scrollRef.current?.scrollBy({ left: dir === "left" ? -316 : 316, behavior: "smooth" });
  };

  // Aggregate strip computations
  const totalAum    = portfolios?.reduce((s, p) => s + (p.total_value ?? 0), 0) ?? 0;
  const totalIncome = portfolios?.reduce((s, p) => s + (p.annual_income ?? 0), 0) ?? 0;
  const unsafeTotal = portfolios?.reduce((s, p) => s + (p.unsafe_count ?? 0), 0) ?? 0;
  const avgHhs = (() => {
    if (!portfolios?.length) return null;
    const withHhs = portfolios.filter(p => p.agg_hhs != null && p.total_value);
    if (!withHhs.length) return null;
    const totalVal = withHhs.reduce((s, p) => s + p.total_value, 0);
    return withHhs.reduce((s, p) => s + (p.agg_hhs! * p.total_value / totalVal), 0);
  })();

  const kpis = [
    { label: "Total AUM",     value: formatCurrency(totalAum),            helpText: "Combined market value across all portfolios." },
    { label: "Ann. Income",   value: formatCurrency(totalIncome),          helpText: "Projected annual income based on current dividends." },
    { label: "Avg HHS",       value: avgHhs != null ? avgHhs.toFixed(1) : "—",
      colorClass: avgHhs != null ? (avgHhs >= 70 ? "text-green-400" : avgHhs >= 50 ? "text-amber-400" : "text-red-400") : undefined,
      helpText: HHS_HELP.agg_hhs },
    { label: "Portfolios",    value: portfolios?.length ?? 0 },
    { label: "⚠ UNSAFE",      value: unsafeTotal, colorClass: unsafeTotal > 0 ? "text-red-400" : undefined,
      alert: unsafeTotal > 0, helpText: HHS_HELP.unsafe_flag },
  ];

  return (
    <div className="p-4 max-w-screen-2xl mx-auto">
      <h1 className="text-lg font-bold mb-3">Dashboard</h1>

      {/* Aggregate KPI strip */}
      <KpiStrip items={kpis} />

      {/* Portfolio card scroll */}
      {isLoading && (
        <div className="flex gap-3 py-2">
          {[1,2,3].map(i => <div key={i} className="flex-shrink-0 w-[300px] h-[220px] bg-card rounded-xl animate-pulse border border-border" />)}
        </div>
      )}
      {error && (
        <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-sm text-red-400 flex items-center justify-between">
          Failed to load portfolios.
          <button className="underline text-xs" onClick={() => refetch()}>Retry</button>
        </div>
      )}
      {portfolios && (
        <div className="relative">
          <div
            ref={scrollRef}
            className="flex gap-3 overflow-x-auto pb-2 scroll-snap-x mandatory"
            style={{ scrollbarWidth: "thin" }}
          >
            {portfolios.map(p => <PortfolioCard key={p.id} portfolio={p} />)}
            <AddPortfolioCard />
          </div>
          {portfolios.length > 2 && (
            <div className="flex gap-2 justify-end mt-2">
              <button onClick={() => scroll("left")} className="p-1 rounded border border-border text-muted-foreground hover:text-foreground"><ChevronLeft className="h-4 w-4" /></button>
              <button onClick={() => scroll("right")} className="p-1 rounded border border-border text-muted-foreground hover:text-foreground"><ChevronRight className="h-4 w-4" /></button>
            </div>
          )}
          {portfolios.length === 0 && (
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm border border-dashed border-border rounded-xl">
              No portfolios yet. Create your first portfolio to get started.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check + dev server verification**

```bash
cd src/frontend && npx tsc --noEmit
# Then start dev server and navigate to http://localhost:3000/dashboard
npm run dev
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/portfolio/portfolio-card.tsx src/frontend/src/app/dashboard/
git commit -m "feat(frontend): Grand Dashboard with portfolio card scroll and aggregate KPIs"
```

---

### Task 13: Per-Portfolio Page Shell + Collapsible Summary

**Files:**
- Create: `src/frontend/src/app/portfolios/[id]/page.tsx`

- [ ] **Step 1: Create the portfolio page**

```tsx
"use client";
import { useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, ArrowLeft, RefreshCw } from "lucide-react";
import { usePortfolioSummary } from "@/lib/hooks/use-portfolios";
import { KpiStrip } from "@/components/portfolio/kpi-strip";
import { ConcentrationBar } from "@/components/portfolio/concentration-bar";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { HelpTooltip } from "@/components/help-tooltip";
import { HHS_HELP } from "@/lib/help-content";
import { cn, formatCurrency } from "@/lib/utils";
import { PortfolioTab }   from "./tabs/portfolio-tab";
import { MarketTab }      from "./tabs/market-tab";
import { HealthTab }      from "./tabs/health-tab";
import { SimulationContent } from "@/app/income-simulation/page";
import { ProjectionContent } from "@/app/income-projection/page";

type Tab = "portfolio" | "market" | "health" | "simulation" | "projection";
const TABS: { key: Tab; label: string }[] = [
  { key: "portfolio",  label: "Portfolio" },
  { key: "market",     label: "Market" },
  { key: "health",     label: "Health" },
  { key: "simulation", label: "Simulation" },
  { key: "projection", label: "Income Projection" },
];

export default function PortfolioPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeTab = (searchParams.get("tab") as Tab) ?? "portfolio";
  const [summaryOpen, setSummaryOpen] = useState(true);

  const { data: summary, isLoading, error, refetch } = usePortfolioSummary(id);

  const setTab = (tab: Tab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`/portfolios/${id}?${params.toString()}`);
  };

  const kpis = [
    { label: "Agg HHS",     value: summary?.agg_hhs?.toFixed(1) ?? "—",
      colorClass: summary?.agg_hhs != null ? (summary.agg_hhs >= 70 ? "text-green-400" : summary.agg_hhs >= 50 ? "text-amber-400" : "text-red-400") : undefined,
      helpText: HHS_HELP.agg_hhs },
    { label: "NAA Yield",   value: summary?.naa_yield != null ? `${(summary.naa_yield * 100).toFixed(2)}%` : "—", colorClass: "text-green-400", helpText: HHS_HELP.naa_yield },
    { label: "Value",       value: summary ? formatCurrency(summary.total_value) : "—" },
    { label: "Ann. Income", value: summary ? formatCurrency(summary.annual_income) : "—", colorClass: "text-blue-400" },
    { label: "HHI",         value: summary?.hhi?.toFixed(3) ?? "—",
      colorClass: (summary?.hhi ?? 0) > 0.10 ? "text-amber-400" : undefined, helpText: HHS_HELP.hhi },
    { label: "Holdings",    value: summary?.holding_count ?? "—" },
    { label: "⚠ UNSAFE",   value: summary?.unsafe_count ?? 0,
      colorClass: (summary?.unsafe_count ?? 0) > 0 ? "text-red-400" : undefined,
      alert: (summary?.unsafe_count ?? 0) > 0, helpText: HHS_HELP.unsafe_flag },
  ];

  if (isLoading) return <div className="p-4 text-muted-foreground text-sm animate-pulse">Loading portfolio…</div>;
  if (error) return (
    <div className="p-4">
      <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-sm text-red-400 flex items-center justify-between">
        Failed to load portfolio.
        <button className="underline text-xs" onClick={() => refetch()}>Retry</button>
      </div>
    </div>
  );

  return (
    <div className="p-4 max-w-screen-2xl mx-auto">
      {/* Identity header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <button onClick={() => router.push("/dashboard")} className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4" />
            </button>
            <h1 className="text-lg font-bold">{summary?.name ?? id}</h1>
            {(summary?.unsafe_count ?? 0) > 0 && (
              <span className="bg-red-950 text-red-400 text-[0.6rem] font-bold px-1.5 py-0.5 rounded">
                ⚠ {summary?.unsafe_count} UNSAFE
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 ml-6 mt-0.5 text-[0.6rem] text-muted-foreground">
            {summary?.tax_status && <span className="bg-muted rounded px-1.5 py-0.5">{summary.tax_status}</span>}
            {summary?.broker && <span className="bg-muted rounded px-1.5 py-0.5">{summary.broker}</span>}
            {summary?.holding_count != null && <span>{summary.holding_count} holdings</span>}
            {summary?.last_refresh && <span>Refreshed {new Date(summary.last_refresh).toLocaleDateString()}</span>}
          </div>
        </div>
        <button onClick={() => refetch()} className="p-1.5 text-muted-foreground hover:text-foreground" title="Refresh">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* KPI strip */}
      <KpiStrip items={kpis} />

      {/* Collapsible summary */}
      <div className="bg-card border border-border rounded-lg mb-3 overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-3.5 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
          onClick={() => setSummaryOpen(o => !o)}
        >
          <span>
            {!summaryOpen && summary && (
              <span className="text-foreground font-normal">
                {summary.concentration_by_class?.[0] && `${summary.concentration_by_class[0].class} ${summary.concentration_by_class[0].pct}%`}
                {(summary?.unsafe_count ?? 0) > 0 && ` · ⚠ ${summary.unsafe_count} UNSAFE`}
              </span>
            )}
            {summaryOpen && "Summary"}
          </span>
          {summaryOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
        {summaryOpen && summary && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 px-3.5 pb-3.5">
            <div>
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-1.5">Asset Class</div>
              <ConcentrationBar
                items={(summary.concentration_by_class ?? []).map(c => ({ label: c.class, pct: c.pct }))}
              />
            </div>
            <div>
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-1.5">Top Income</div>
              <div className="space-y-1">
                {(summary.top_income_holdings ?? []).map((h, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className={cn("font-medium", h.unsafe && "text-amber-400")}>
                      {h.unsafe && "⚠ "}{h.ticker}
                    </span>
                    <span className="text-muted-foreground">{formatCurrency(h.annual_income)} · {h.income_pct.toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-1.5">Sector</div>
              <ConcentrationBar
                items={(summary.concentration_by_sector ?? []).map(s => ({ label: s.sector, pct: s.pct, colorClass: "bg-slate-500" }))}
              />
            </div>
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 overflow-x-auto pb-1 mb-3 border-b border-border">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "px-3 py-1.5 text-xs font-medium rounded-t whitespace-nowrap transition-colors",
              activeTab === t.key
                ? "bg-card border border-border border-b-card text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "portfolio"  && <PortfolioTab portfolioId={id} />}
      {activeTab === "market"     && <MarketTab portfolioId={id} />}
      {activeTab === "health"     && <HealthTab portfolioId={id} />}
      {activeTab === "simulation" && <SimulationContent defaultPortfolioId={id} />}
      {activeTab === "projection" && <ProjectionContent defaultPortfolioId={id} />}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check** (will have import errors from missing tab files — OK at this stage)

```bash
cd src/frontend && npx tsc --noEmit 2>&1 | grep -v "Cannot find module.*tabs"
```

- [ ] **Step 3: Commit shell**

```bash
git add src/frontend/src/app/portfolios/
git commit -m "feat(frontend): /portfolios/[id] page shell with tab routing and collapsible summary"
```

---

### Task 14: Portfolio Tab + Market Tab

**Files:**
- Create: `src/frontend/src/app/portfolios/[id]/tabs/portfolio-tab.tsx`
- Create: `src/frontend/src/app/portfolios/[id]/tabs/market-tab.tsx`

- [ ] **Step 1: Create `portfolio-tab.tsx`**

```tsx
"use client";
import { useMemo, useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { usePortfolio } from "@/lib/portfolio-context";
import { HHS_HELP, HOLDINGS_HELP } from "@/lib/help-content";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import type { Position } from "@/lib/types";

interface PortfolioTabProps {
  portfolioId: string;
}

export function PortfolioTab({ portfolioId }: PortfolioTabProps) {
  const { activePortfolio } = usePortfolio();
  const positions = activePortfolio?.positions ?? [];
  const [selected, setSelected] = useState<Position | null>(null);

  // Filter to current portfolio
  const filtered = useMemo(
    () => positions.filter(p => p.portfolio_id === portfolioId),
    [positions, portfolioId]
  );

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="symbol" helpMap={HOLDINGS_HELP} />,
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
    },
    { accessorKey: "asset_type", header: "Class" },
    { accessorKey: "name", header: "Name" },
    { accessorKey: "shares", header: "Shares" },
    {
      accessorKey: "current_value",
      header: () => <ColHeader label="Mkt Value" helpKey="current_value" helpMap={HOLDINGS_HELP} />,
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "annual_income",
      header: () => <ColHeader label="Ann. Income" helpKey="annual_income" helpMap={HOLDINGS_HELP} />,
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "current_yield",
      header: () => <ColHeader label="Yield" helpKey="current_yield" helpMap={HOLDINGS_HELP} />,
      cell: ({ getValue }) => getValue() != null ? `${((getValue() as number) * 100).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "hhs_status",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => (
        <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />
      ),
    },
  ];

  return (
    <div className={cn("flex gap-3", selected && "lg:gap-3")}>
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={filtered}
          storageKey={`portfolio-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) => setSelected(s => s?.symbol === row.symbol ? null : row)}
          frozenColumns={1}
        />
      </div>

      {/* Detail pane */}
      {selected && (
        <div className="w-[360px] flex-shrink-0 bg-card border border-border rounded-lg p-4 text-sm space-y-4 overflow-y-auto max-h-[calc(100vh-200px)]">
          <div className="flex items-center justify-between">
            <span className="font-bold">{selected.symbol}</span>
            <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground text-xs">✕</button>
          </div>

          {/* Position section */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Position</div>
            <div className="grid grid-cols-2 gap-y-1.5 text-xs">
              {[
                ["Shares", selected.shares],
                ["Avg Cost", formatCurrency(selected.avg_cost ?? selected.cost_basis / (selected.shares || 1))],
                ["Mkt Price", formatCurrency(selected.market_price ?? 0)],
                ["Mkt Value", formatCurrency(selected.current_value)],
                ["Cost Basis", formatCurrency(selected.cost_basis)],
                ["Unrealized G/L", formatCurrency(selected.current_value - selected.cost_basis)],
              ].map(([k, v], i) => (
                <div key={i}>
                  <div className="text-muted-foreground text-[0.6rem] uppercase">{k}</div>
                  <div className="font-medium">{v}</div>
                </div>
              ))}
            </div>
          </section>

          {/* Income section */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Income</div>
            <div className="grid grid-cols-2 gap-y-1.5 text-xs">
              {[
                ["Annual Income", formatCurrency(selected.annual_income)],
                ["Gross Yield", selected.current_yield != null ? `${(selected.current_yield * 100).toFixed(2)}%` : "—"],
                ["Frequency", selected.dividend_frequency ?? "—"],
                ["Ex-Date", selected.ex_div_date ?? "—"],
              ].map(([k, v], i) => (
                <div key={i}>
                  <div className="text-muted-foreground text-[0.6rem] uppercase">{k}</div>
                  <div className="font-medium">{v}</div>
                </div>
              ))}
            </div>
          </section>

          {/* Health summary */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Health Summary</div>
            {selected.hhs_score != null ? (
              <div className="space-y-1.5">
                <HhsBadge status={selected.hhs_status} score={selected.hhs_score} />
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>Income: {selected.income_pillar_score?.toFixed(0) ?? "—"}/100</span>
                  <span>·</span>
                  <span>Durability: {selected.durability_pillar_score?.toFixed(0) ?? "—"}/100</span>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-xs italic">Rescore to see HHS</div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `market-tab.tsx`** (abbreviated — same pattern as portfolio-tab)

```tsx
"use client";
import { useMemo, useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { ColHeader } from "@/components/help-tooltip";
import { usePortfolio } from "@/lib/portfolio-context";
import { MARKET_HELP } from "@/lib/help-content";
import { formatCurrency } from "@/lib/utils";
import type { Position } from "@/lib/types";

interface MarketTabProps { portfolioId: string; }

export function MarketTab({ portfolioId }: MarketTabProps) {
  const { activePortfolio } = usePortfolio();
  const positions = activePortfolio?.positions ?? [];
  const [selected, setSelected] = useState<Position | null>(null);
  const filtered = useMemo(() => positions.filter(p => p.portfolio_id === portfolioId), [positions, portfolioId]);

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="symbol" helpMap={MARKET_HELP} />,
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
    },
    { accessorKey: "asset_type", header: "Class" },
    {
      accessorKey: "market_price",
      header: () => <ColHeader label="Price" helpKey="price" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => formatCurrency(getValue() as number),
    },
    {
      accessorKey: "week52_high",
      header: () => <ColHeader label="52w High" helpKey="week52_range" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "week52_low",
      header: () => <ColHeader label="52w Low" helpKey="week52_range" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
    {
      accessorKey: "current_yield",
      header: () => <ColHeader label="Div Yield" helpKey="dividend_yield" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => getValue() != null ? `${((getValue() as number) * 100).toFixed(2)}%` : "—",
    },
    {
      accessorKey: "beta",
      header: () => <ColHeader label="Beta" helpKey="beta" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => (getValue() as number)?.toFixed(2) ?? "—",
    },
    {
      accessorKey: "market_cap",
      header: () => <ColHeader label="Mkt Cap" helpKey="market_cap" helpMap={MARKET_HELP} />,
      cell: ({ getValue }) => getValue() != null ? formatCurrency(getValue() as number) : "—",
    },
  ];

  return (
    <div className="flex gap-3">
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={filtered}
          storageKey={`market-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) => setSelected(s => s?.symbol === row.symbol ? null : row)}
          frozenColumns={1}
        />
      </div>
      {selected && (
        <div className="w-[360px] flex-shrink-0 bg-card border border-border rounded-lg p-4 text-sm overflow-y-auto max-h-[calc(100vh-200px)]">
          <div className="flex items-center justify-between mb-3">
            <span className="font-bold">{selected.symbol}</span>
            <button onClick={() => setSelected(null)} className="text-muted-foreground text-xs">✕</button>
          </div>
          <div className="grid grid-cols-2 gap-y-1.5 text-xs">
            {[
              ["Price", formatCurrency(selected.market_price ?? 0)],
              ["52w High", formatCurrency(selected.week52_high ?? 0)],
              ["52w Low", formatCurrency(selected.week52_low ?? 0)],
              ["Div Yield", selected.current_yield != null ? `${(selected.current_yield * 100).toFixed(2)}%` : "—"],
              ["P/E", selected.pe_ratio?.toFixed(1) ?? "—"],
              ["Beta", selected.beta?.toFixed(2) ?? "—"],
              ["Market Cap", selected.market_cap != null ? formatCurrency(selected.market_cap) : "—"],
              ["Sector", selected.sector ?? "—"],
              ["Industry", selected.industry ?? "—"],
            ].map(([k, v], i) => (
              <div key={i}>
                <div className="text-muted-foreground text-[0.6rem] uppercase">{k}</div>
                <div className="font-medium">{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/tabs/
git commit -m "feat(frontend): Portfolio and Market tabs with DataTable + detail pane"
```

---

### Task 15: Health Tab

**Files:**
- Create: `src/frontend/src/app/portfolios/[id]/tabs/health-tab.tsx`

- [ ] **Step 1: Create `health-tab.tsx`**

```tsx
"use client";
import { useMemo, useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { HhsBadge } from "@/components/portfolio/hhs-badge";
import { ColHeader } from "@/components/help-tooltip";
import { usePortfolio } from "@/lib/portfolio-context";
import { HHS_HELP } from "@/lib/help-content";
import { cn } from "@/lib/utils";
import type { Position } from "@/lib/types";

// Factor pillar mapping (spec §1.3)
const FACTOR_PILLAR: Record<string, "INC" | "DUR" | "IES"> = {
  yield_vs_market: "INC", payout_sustainability: "INC", fcf_coverage: "INC",
  debt_safety: "DUR", dividend_consistency: "DUR", volatility_score: "DUR",
  price_momentum: "IES", price_range_position: "IES",
};
const PILLAR_COLOR: Record<string, string> = {
  INC: "text-green-400 bg-green-950/40",
  DUR: "text-blue-400 bg-blue-950/40",
  IES: "text-slate-400 bg-slate-800/40",
};

interface HealthTabProps { portfolioId: string; }

export function HealthTab({ portfolioId }: HealthTabProps) {
  const { activePortfolio } = usePortfolio();
  const positions = activePortfolio?.positions ?? [];
  const [selected, setSelected] = useState<Position | null>(null);
  const filtered = useMemo(() => positions.filter(p => p.portfolio_id === portfolioId), [positions, portfolioId]);

  const columns: ColumnDef<Position>[] = [
    {
      accessorKey: "symbol",
      header: () => <ColHeader label="Ticker" helpKey="hhs_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
    },
    { accessorKey: "asset_type", header: "Class" },
    {
      accessorKey: "hhs_score",
      header: () => <ColHeader label="HHS" helpKey="hhs_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => <HhsBadge status={row.original.hhs_status} score={row.original.hhs_score} />,
    },
    {
      accessorKey: "income_pillar_score",
      header: () => <ColHeader label="Income" helpKey="income_pillar" helpMap={HHS_HELP} />,
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(0)}/100` : "—",
    },
    {
      accessorKey: "durability_pillar_score",
      header: () => <ColHeader label="Durability" helpKey="durability_pillar" helpMap={HHS_HELP} />,
      cell: ({ getValue }) => getValue() != null ? `${(getValue() as number).toFixed(0)}/100` : "—",
    },
    {
      accessorKey: "ies_score",
      header: () => <ColHeader label="IES" helpKey="ies_score" helpMap={HHS_HELP} />,
      cell: ({ row }) => row.original.ies_calculated
        ? `${row.original.ies_score?.toFixed(0)}/100`
        : <span className="text-muted-foreground text-xs">{row.original.ies_blocked_reason ?? "—"}</span>,
    },
    {
      accessorKey: "quality_gate_status",
      header: "Gate",
      cell: ({ getValue }) => {
        const v = getValue() as string;
        return <span className={cn("text-xs font-medium", v === "PASS" ? "text-green-400" : "text-amber-400")}>{v ?? "—"}</span>;
      },
    },
    { accessorKey: "grade", header: "Grade" },
  ];

  return (
    <div className="flex gap-3">
      <div className="flex-1 min-w-0">
        <DataTable
          columns={columns}
          data={filtered}
          storageKey={`health-tab-${portfolioId}`}
          enableRowSelection
          onRowClick={(row) => setSelected(s => s?.symbol === row.symbol ? null : row)}
          frozenColumns={1}
        />
      </div>

      {selected && (
        <div className="w-[360px] flex-shrink-0 bg-card border border-border rounded-lg p-4 text-sm overflow-y-auto max-h-[calc(100vh-200px)] space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-bold">{selected.symbol}</span>
            <button onClick={() => setSelected(null)} className="text-muted-foreground text-xs">✕</button>
          </div>

          {/* HHS Breakdown */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">HHS Breakdown</div>
            {selected.hhs_score != null ? (
              <>
                <HhsBadge status={selected.hhs_status} score={selected.hhs_score} />
                <div className="text-[0.6rem] text-muted-foreground mt-1">
                  HHS = (Income × {((selected.income_weight ?? 0.5) * 100).toFixed(0)}%) + (Durability × {((selected.durability_weight ?? 0.5) * 100).toFixed(0)}%)
                </div>
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-green-400">Income</span>
                    <span>{selected.income_pillar_score?.toFixed(0) ?? "—"}/100</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-blue-400">Durability</span>
                    <span>{selected.durability_pillar_score?.toFixed(0) ?? "—"}/100</span>
                  </div>
                </div>
                {selected.unsafe_flag && (
                  <div className="mt-2 bg-red-950/40 border border-red-900/50 rounded p-2 text-xs text-red-400">
                    ⚠ UNSAFE — Durability at or below safety threshold ({selected.unsafe_threshold ?? 20})
                  </div>
                )}
              </>
            ) : (
              <div className="text-muted-foreground text-xs italic">
                Rescore to see HHS <button className="underline ml-1">Refresh</button>
              </div>
            )}
          </section>

          {/* Factor breakdown */}
          {selected.factor_details && Object.keys(selected.factor_details).length > 0 && (
            <section>
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Factor Breakdown</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground text-[0.6rem] uppercase border-b border-border">
                    <th className="text-left pb-1">Factor</th>
                    <th className="text-center pb-1">Pillar</th>
                    <th className="text-right pb-1">Score/Max</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(selected.factor_details)
                    .filter(([k]) => !["chowder_number", "chowder_signal"].includes(k))
                    .map(([key, val]) => {
                      const pillar = FACTOR_PILLAR[key] ?? "INC";
                      const v = val as { score?: number; max?: number; value?: number } | null;
                      return (
                        <tr key={key} className={cn("border-b border-border/30", pillar === "IES" && "opacity-60")}>
                          <td className="py-1 pr-2">{key.replace(/_/g, " ")}</td>
                          <td className="py-1 text-center">
                            <span className={cn("text-[0.55rem] font-bold px-1 rounded", PILLAR_COLOR[pillar])}>{pillar}</span>
                          </td>
                          <td className="py-1 text-right text-muted-foreground">
                            {v?.score?.toFixed(1) ?? "—"}{v?.max != null ? `/${v.max}` : ""}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </section>
          )}

          {/* IES */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">IES — Entry Score</div>
            {selected.ies_calculated ? (
              <div className="text-sm font-bold">{selected.ies_score?.toFixed(0)}/100</div>
            ) : (
              <div className="text-muted-foreground text-xs">
                Blocked: {selected.ies_blocked_reason ?? "—"}
              </div>
            )}
          </section>

          {/* Commentary */}
          {(selected.hhs_commentary || selected.score_commentary) && (
            <section>
              <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Commentary</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {selected.hhs_commentary ?? (
                  <><span className="text-amber-400 text-[0.6rem]">V6 commentary — HHS commentary not yet generated.</span>{" "}{(selected as any).score_commentary}</>
                )}
              </p>
            </section>
          )}

          {/* Quality gate */}
          <section>
            <div className="text-[0.6rem] font-bold uppercase text-blue-400 mb-2">Quality Gate</div>
            <div className={cn("text-xs font-medium", selected.quality_gate_status === "PASS" ? "text-green-400" : "text-amber-400")}>
              {selected.quality_gate_status ?? "PASS"}
            </div>
            {selected.quality_gate_reasons?.length ? (
              <ul className="mt-1 space-y-0.5">
                {selected.quality_gate_reasons.map((r, i) => <li key={i} className="text-xs text-muted-foreground">· {r}</li>)}
              </ul>
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd src/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/app/portfolios/[id]/tabs/health-tab.tsx
git commit -m "feat(frontend): Health tab with factor breakdown and IES detail pane"
```

---

### Task 16: ProjectionContent Export + Redirect + Final Wiring

**Files:**
- Modify: `src/frontend/src/app/income-projection/page.tsx`
- Modify: `src/frontend/src/app/portfolio/page.tsx`

- [ ] **Step 1: Add `ProjectionContent` named export to `income-projection/page.tsx`**

Find the existing default export `ProjectionPage` and add above it:

```tsx
/** Named export for embedding in the portfolio page Projection tab. */
export function ProjectionContent({ defaultPortfolioId }: { defaultPortfolioId?: string }) {
  // Wrap the existing ProjectionPage content scoped to defaultPortfolioId.
  // For now, render the page with the portfolio_id passed as a context/prop.
  // This is a thin wrapper — the full projection logic is unchanged.
  return <ProjectionPage portfolioId={defaultPortfolioId} />;
}
```

Also update the `ProjectionPage` signature to accept an optional `portfolioId` prop:

```tsx
export default function ProjectionPage({ portfolioId }: { portfolioId?: string } = {}) {
  // ... existing code unchanged, use portfolioId to pre-filter if provided
}
```

- [ ] **Step 2: Replace `portfolio/page.tsx` with redirect**

```tsx
import { redirect } from "next/navigation";

export default function PortfolioPage() {
  redirect("/dashboard");
}
```

- [ ] **Step 3: Final TypeScript check across all new files**

```bash
cd src/frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 4: Start dev server and do a full walkthrough**

```bash
cd src/frontend && npm run dev
```

Verify:
- `http://localhost:3000/` or `/dashboard` shows Grand Dashboard with portfolio cards
- Clicking a card navigates to `/portfolios/[id]?tab=portfolio`
- Tab switching updates URL and renders correct content
- Health tab shows HHS badge and factor breakdown when a scored position is selected
- `http://localhost:3000/portfolio` redirects to `/dashboard`

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/income-projection/page.tsx src/frontend/src/app/portfolio/page.tsx
git commit -m "feat(frontend): ProjectionContent export, /portfolio → /dashboard redirect"
```

---

### Task 17: Deploy to Production

- [ ] **Step 1: Push all commits**

```bash
git push origin main
```

- [ ] **Step 2: SSH to legato and deploy**

```bash
ssh root@138.197.78.238
cd /opt/Agentic

git pull origin main

# Run DB migration
DATABASE_URL=$(grep DATABASE_URL .env | cut -d= -f2-) \
  python3 income-platform/src/portfolio-positions-schema/scripts/migrate_v3_hhs_ies.py

# Rebuild affected services
docker-compose build agent-03-income-scoring broker-service frontend
docker-compose up -d agent-03-income-scoring broker-service frontend
```

- [ ] **Step 3: Verify production**

```bash
# Check Agent 03 scores MAIN and verify HHS fields appear:
curl -s -X POST https://your-domain/api/scores/evaluate \
  -H "Content-Type: application/json" \
  -d '{"ticker":"MAIN","asset_class":"BDC"}' | python3 -m json.tool | grep hhs

# Check broker portfolio endpoint:
curl -s https://your-domain/broker/portfolios | python3 -m json.tool | head -30
```

- [ ] **Step 4: Final commit if any hotfixes**

```bash
git add -A && git commit -m "fix: production hotfixes after deploy"
git push origin main
```

---

## Implementation Notes

### Testing Agent 03 locally (no Docker)

```bash
cd src/income-scoring-service
JWT_SECRET=test python3 -m pytest tests/ -v
```

### Checking broker-service alone

```bash
cd src/broker-service
python3 -m pytest tests/ -v
```

### Running the frontend dev server

```bash
cd src/frontend
npm install   # if needed
npm run dev   # http://localhost:3000
```

### Environment variables required for new features

```bash
# Add to .env on legato if not present:
SCORING_SERVICE_URL=http://agent-03-income-scoring:8003
SERVICE_TOKEN=<your-service-token>
```
