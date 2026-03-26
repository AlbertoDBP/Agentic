# Opportunity Scanner v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing scanner page with a full portfolio-aware scanner featuring entry/exit limit prices, three portfolio lenses, and a proposal handoff to Agent 12.

**Architecture:** Four slices built bottom-up: entry/exit engine → portfolio context annotator → API extension → frontend replacement. Each slice is independently testable and commits green.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, asyncpg, pytest (backend); Next.js 14 App Router, React, TypeScript, Tailwind CSS, shadcn/ui (frontend).

**Spec:** `docs/superpowers/specs/2026-03-26-opportunity-scanner-v2-design.md`

---

## File Map

### Agent 07 — New Files

| File | Responsibility |
| --- | --- |
| `src/opportunity-scanner-service/app/scanner/entry_exit.py` | Compute entry/exit limit prices and zone status from cached market data |
| `src/opportunity-scanner-service/app/scanner/portfolio_context.py` | Annotate scan results with portfolio weights, held status, underperformer flags, lens filtering |
| `src/opportunity-scanner-service/scripts/migrate_proposal_drafts.py` | Create `platform_shared.proposal_drafts` table |
| `src/opportunity-scanner-service/tests/test_entry_exit.py` | Unit tests for entry/exit engine |
| `src/opportunity-scanner-service/tests/test_portfolio_context.py` | Unit tests for portfolio annotator |
| `src/opportunity-scanner-service/tests/test_propose_api.py` | Integration tests for POST /scan/{scan_id}/propose |

### Agent 07 — Modified Files

| File | Change |
| --- | --- |
| `src/opportunity-scanner-service/app/config.py` | Add `class_overweight_pct`, `sector_overweight_pct` settings |
| `src/opportunity-scanner-service/app/models.py` | Add `ProposalDraft` ORM model |
| `src/opportunity-scanner-service/app/scanner/engine.py` | Add `entry_exit` and `portfolio_context` fields to `ScanItem`; call both modules |
| `src/opportunity-scanner-service/app/api/scanner.py` | Add `portfolio_id`, `portfolio_lens` to `ScanRequest`; add `entry_exit`/`portfolio_context` to `ScanItemResponse`; add `POST /scan/{scan_id}/propose` endpoint |

### Frontend — New Files

| File | Responsibility |
| --- | --- |
| `src/frontend/src/components/scanner/input-panel.tsx` | Tab control: Manual / Portfolio / Universe input modes |
| `src/frontend/src/components/scanner/filter-panel.tsx` | Collapsible Group 1 + Group 2 filter controls |
| `src/frontend/src/components/scanner/lens-picker.tsx` | Gap / Replacement / Concentration tab switcher (shown when portfolio selected) |
| `src/frontend/src/components/scanner/results-table.tsx` | Full results table: score badge, entry/exit columns, portfolio badges, selection |
| `src/frontend/src/components/scanner/entry-exit-badge.tsx` | Per-row zone status badge + dollar price display |
| `src/frontend/src/components/scanner/portfolio-badges.tsx` | Held / Class ⚠ / Sector ⚠ / Replacing / Income / Durable badges |
| `src/frontend/src/components/scanner/proposal-modal.tsx` | Confirmation modal: selected tickers + target portfolio dropdown + submit |
| `src/frontend/src/app/api/scanner/propose/route.ts` | Route handler: POST /api/scanner/propose → ADMIN_PANEL proxy (15 s timeout — fast DB write) |

### Frontend — Modified Files

| File | Change |
| --- | --- |
| `src/frontend/src/app/scanner/page.tsx` | Full replacement with new ScannerPage assembly |
| `src/frontend/src/lib/types.ts` | Add `ScanItem`, `ScanResult`, `EntryExit`, `PortfolioContext`, `ProposalDraft` types |

---

## Task 1: Entry/Exit Engine

**Files:**

- Create: `src/opportunity-scanner-service/app/scanner/entry_exit.py`
- Create: `src/opportunity-scanner-service/tests/test_entry_exit.py`

### Background

The engine reads market data already in `platform_shared.market_data_cache` and computes three signals each for entry and exit. Entry limit = `min(applicable signals)`. Exit limit = `min(applicable signals)`. Zone status is based on current price vs. entry limit.

NAV-eligible asset classes: `{"BDC", "MORTGAGE_REIT"}` — these two classes have `nav_value` tracked in `market_data_cache`. All other classes (DIVIDEND_STOCK, BOND, EQUITY_REIT, COVERED_CALL_ETF, PREFERRED_STOCK) use technical and yield signals only. The spec uses the shorthand "CEF/BDC" to refer to these two classes.

- [ ] **Step 1: Write failing tests**

```python
# src/opportunity-scanner-service/tests/test_entry_exit.py
"""Tests for the entry/exit price engine."""
import pytest
from app.scanner.entry_exit import (
    compute_entry_exit,
    ZoneStatus,
    EntryExitResult,
    NAV_ELIGIBLE_CLASSES,
)


# ── compute_entry_exit ────────────────────────────────────────────────────────

class TestTechnicalEntrySignal:
    def test_uses_support_level_when_available(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=44.0,
            sma_200=43.0,
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=6.0,
            nav_value=None,
        )
        # technical entry = max(support_level=44.0, sma_200×1.01=43.43) = 44.0
        assert result.signals["technical_entry"] == pytest.approx(44.0)

    def test_uses_sma200_when_support_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=43.0,
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=6.0,
            nav_value=None,
        )
        assert result.signals["technical_entry"] == pytest.approx(43.43)

    def test_technical_entry_none_when_both_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=6.0,
            nav_value=None,
        )
        assert result.signals["technical_entry"] is None


class TestYieldEntrySignal:
    def test_yield_entry_computed_from_price_and_yield(self):
        # annual_dividend = 50 × 0.06 = 3.0
        # yield_entry_target = 6.0 × 1.15 = 6.9
        # yield_entry = 3.0 / 0.069 = 43.48
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=6.0,
            nav_value=None,
        )
        assert result.signals["yield_entry"] == pytest.approx(43.478, rel=1e-3)

    def test_yield_entry_none_when_yield_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.signals["yield_entry"] is None

    def test_yield_entry_none_when_price_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=None,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=6.0,
            nav_value=None,
        )
        assert result.signals["yield_entry"] is None


class TestNavSignal:
    def test_nav_entry_for_bdc(self):
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=48.0,
        )
        assert result.signals["nav_entry"] == pytest.approx(45.6)  # 48 × 0.95

    def test_nav_entry_none_for_non_nav_class(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=48.0,
        )
        assert result.signals["nav_entry"] is None

    def test_nav_exit_for_mortgage_reit(self):
        result = compute_entry_exit(
            asset_class="MORTGAGE_REIT",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=48.0,
        )
        assert result.signals["nav_exit"] == pytest.approx(50.4)  # 48 × 1.05


class TestEntryLimit:
    def test_entry_limit_is_min_of_applicable_signals(self):
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=44.0,
            sma_200=43.0,
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=6.0,
            nav_value=48.0,
        )
        # technical = 44.0, yield = ~43.48, nav = 45.6
        assert result.entry_limit == pytest.approx(43.478, rel=1e-3)

    def test_entry_limit_null_when_no_signals(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=None,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.entry_limit is None


class TestZoneStatus:
    def test_below_entry(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=42.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.BELOW_ENTRY

    def test_in_zone(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=44.5,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.IN_ZONE

    def test_near_entry(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=46.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.NEAR_ENTRY

    def test_above_entry(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.ABOVE_ENTRY

    def test_unknown_when_no_entry_limit(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=None,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.UNKNOWN

    def test_pct_from_entry_computed(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=46.2,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.pct_from_entry == pytest.approx(5.0, rel=1e-2)

    def test_pct_from_entry_null_when_price_none(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=None,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.pct_from_entry is None
        assert result.zone_status == ZoneStatus.UNKNOWN

    def test_in_zone_exact_boundary_at_1_03(self):
        """Price exactly at entry_limit × 1.03 is IN_ZONE."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=44.0 * 1.03,  # exactly 45.32
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.IN_ZONE

    def test_near_entry_just_above_1_03(self):
        """Price at entry_limit × 1.031 crosses into NEAR_ENTRY."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=44.0 * 1.031,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.NEAR_ENTRY

    def test_near_entry_exact_boundary_at_1_05(self):
        """Price exactly at entry_limit × 1.05 is NEAR_ENTRY."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=44.0 * 1.05,  # exactly 46.2
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.NEAR_ENTRY

    def test_above_entry_just_above_1_05(self):
        """Price just above entry_limit × 1.05 is ABOVE_ENTRY."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=44.0 * 1.051,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.zone_status == ZoneStatus.ABOVE_ENTRY


class TestTechnicalExitSignal:
    def test_uses_resistance_level_when_available(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=None,
            nav_value=None,
        )
        # technical_exit = min(resistance=60.0, week_52_high×0.95=58.9) = 58.9
        assert result.signals["technical_exit"] == pytest.approx(58.9)

    def test_uses_week_52_high_when_resistance_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=62.0,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.signals["technical_exit"] == pytest.approx(58.9)

    def test_technical_exit_none_when_both_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.signals["technical_exit"] is None

    def test_resistance_lower_than_week_52_signal_wins(self):
        """When resistance < week_52_high × 0.95, resistance governs (conservative)."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=55.0,
            week_52_high=62.0,   # × 0.95 = 58.9
            dividend_yield=None,
            nav_value=None,
        )
        assert result.signals["technical_exit"] == pytest.approx(55.0)


class TestYieldExitSignal:
    def test_yield_exit_computed(self):
        # annual_dividend = 50 × 0.06 = 3.0
        # yield_exit_target = 6.0 × 0.85 = 5.1
        # yield_exit = 3.0 / 0.051 = 58.82
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=6.0,
            nav_value=None,
        )
        assert result.signals["yield_exit"] == pytest.approx(58.82, rel=1e-3)

    def test_yield_exit_none_when_yield_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.signals["yield_exit"] is None

    def test_yield_exit_none_when_price_missing(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=None,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=6.0,
            nav_value=None,
        )
        assert result.signals["yield_exit"] is None


class TestNavExitSignal:
    def test_nav_exit_for_bdc(self):
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=48.0,
        )
        assert result.signals["nav_exit"] == pytest.approx(50.4)  # 48 × 1.05

    def test_nav_exit_none_for_non_nav_class(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=48.0,
        )
        assert result.signals["nav_exit"] is None

    def test_nav_exit_none_when_nav_value_missing(self):
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.signals["nav_exit"] is None


class TestExitLimit:
    def test_exit_limit_is_min_of_applicable_signals(self):
        # technical = 58.9, yield = 58.82, nav = 50.4 → exit_limit = 50.4
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=6.0,
            nav_value=48.0,
        )
        assert result.exit_limit == pytest.approx(50.4)

    def test_exit_limit_null_when_no_signals(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.exit_limit is None


class TestToDictShape:
    def test_to_dict_has_all_required_keys(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=60.0,
            week_52_high=None,
            dividend_yield=6.0,
            nav_value=None,
        )
        d = result.to_dict()
        assert set(d.keys()) == {"entry_limit", "exit_limit", "current_price", "pct_from_entry", "zone_status", "signals"}
        assert set(d["signals"].keys()) == {
            "technical_entry", "yield_entry", "nav_entry",
            "technical_exit", "yield_exit", "nav_exit",
        }

    def test_to_dict_zone_status_is_string(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        d = result.to_dict()
        assert isinstance(d["zone_status"], str)
        assert d["zone_status"] == "ABOVE_ENTRY"


class TestFullScenarios:
    """Integration-style tests: all signals present, various asset classes."""

    def test_fully_populated_bdc_entry_chooses_lowest_signal(self):
        """BDC with all three entry signals: technical, yield, NAV — entry = min."""
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=46.0,
            sma_200=44.0,       # technical = max(46, 44.44) = 46.0
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=8.0, # annual_div = 50×0.08=4.0; yield_entry = 8×1.15=9.2%; 4/0.092=43.48
            nav_value=50.0,     # nav_entry = 50×0.95=47.5
        )
        # technical=46.0, yield=43.48, nav=47.5 → entry_limit=43.48
        assert result.entry_limit == pytest.approx(43.478, rel=1e-3)
        assert result.zone_status == ZoneStatus.ABOVE_ENTRY

    def test_fully_populated_bdc_exit_chooses_lowest_signal(self):
        """BDC exit: technical=58.9, yield=58.82, nav=52.5 → exit=52.5."""
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=62.0,
            week_52_high=62.0,  # 62×0.95=58.9; min(62, 58.9)=58.9
            dividend_yield=8.0, # yield_exit=8×0.85=6.8%; 4/0.068=58.82
            nav_value=50.0,     # nav_exit=50×1.05=52.5
        )
        # technical=58.9, yield=58.82, nav=52.5 → exit_limit=52.5
        assert result.exit_limit == pytest.approx(52.5)

    def test_dividend_stock_no_nav_signals(self):
        """DIVIDEND_STOCK should never produce nav_entry or nav_exit."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=40.0,
            support_level=38.0,
            sma_200=37.0,
            resistance_level=48.0,
            week_52_high=50.0,
            dividend_yield=5.0,
            nav_value=39.0,  # should be ignored
        )
        assert result.signals["nav_entry"] is None
        assert result.signals["nav_exit"] is None

    def test_rsi_field_not_included_in_signals(self):
        """RSI is not an input to entry/exit — signals dict should not contain it."""
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert "rsi_14d" not in result.signals

    def test_entry_limit_rounded_to_two_decimals(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=43.0,       # technical = 43.0 × 1.01 = 43.43
            resistance_level=None,
            week_52_high=None,
            dividend_yield=None,
            nav_value=None,
        )
        assert result.entry_limit == 43.43

    def test_exit_limit_rounded_to_two_decimals(self):
        result = compute_entry_exit(
            asset_class="DIVIDEND_STOCK",
            price=50.0,
            support_level=None,
            sma_200=None,
            resistance_level=None,
            week_52_high=63.0,  # 63 × 0.95 = 59.85
            dividend_yield=None,
            nav_value=None,
        )
        assert result.exit_limit == 59.85
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd src/opportunity-scanner-service
python3 -m pytest tests/test_entry_exit.py -v 2>&1 | head -20
```

Expected: `ImportError` (module does not exist yet).

- [ ] **Step 3: Implement entry_exit.py**

```python
# src/opportunity-scanner-service/app/scanner/entry_exit.py
"""
Agent 07 — Entry/Exit Price Engine

Computes concrete dollar entry and exit limit prices from cached market data.
All inputs come from platform_shared.market_data_cache — no new FMP calls.

Entry limit = min(technical_entry, yield_entry, nav_entry) — applicable signals only.
Exit limit  = min(technical_exit, yield_exit, nav_exit)   — applicable signals only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

NAV_ELIGIBLE_CLASSES = {"BDC", "MORTGAGE_REIT"}


class ZoneStatus(str, Enum):
    BELOW_ENTRY = "BELOW_ENTRY"   # price < entry_limit
    IN_ZONE     = "IN_ZONE"       # entry_limit ≤ price ≤ entry_limit × 1.03
    NEAR_ENTRY  = "NEAR_ENTRY"    # price ≤ entry_limit × 1.05
    ABOVE_ENTRY = "ABOVE_ENTRY"   # price > entry_limit × 1.05
    UNKNOWN     = "UNKNOWN"       # entry_limit is None


@dataclass
class EntryExitResult:
    entry_limit: Optional[float]
    exit_limit: Optional[float]
    current_price: Optional[float]
    pct_from_entry: Optional[float]
    zone_status: ZoneStatus
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_limit": self.entry_limit,
            "exit_limit": self.exit_limit,
            "current_price": self.current_price,
            "pct_from_entry": self.pct_from_entry,
            "zone_status": self.zone_status.value,
            "signals": self.signals,
        }


def _safe(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def compute_entry_exit(
    asset_class: str,
    price: Optional[float],
    support_level: Optional[float],
    sma_200: Optional[float],
    resistance_level: Optional[float],
    week_52_high: Optional[float],
    dividend_yield: Optional[float],   # percent, e.g. 6.5 = 6.5%
    nav_value: Optional[float],
) -> EntryExitResult:
    """Compute entry/exit limit prices and zone status for one ticker."""

    price = _safe(price)
    nav_eligible = asset_class in NAV_ELIGIBLE_CLASSES

    # ── Derived yield values ─────────────────────────────────────────────────
    annual_dividend: Optional[float] = None
    yield_entry_target: Optional[float] = None
    yield_exit_target: Optional[float] = None

    if price is not None and dividend_yield is not None:
        annual_dividend = price * (dividend_yield / 100.0)
        yield_entry_target = dividend_yield * 1.15   # proxy for historical high yield
        yield_exit_target  = dividend_yield * 0.85   # proxy for historical low yield

    # ── Entry signals ────────────────────────────────────────────────────────
    technical_entry: Optional[float] = None
    if support_level is not None or sma_200 is not None:
        candidates = []
        if support_level is not None:
            candidates.append(support_level)
        if sma_200 is not None:
            candidates.append(sma_200 * 1.01)
        technical_entry = max(candidates)

    yield_entry: Optional[float] = None
    if annual_dividend is not None and yield_entry_target is not None and yield_entry_target > 0:
        yield_entry = annual_dividend / (yield_entry_target / 100.0)

    nav_entry: Optional[float] = None
    if nav_eligible and nav_value is not None:
        nav_entry = nav_value * 0.95

    entry_signals = [s for s in [technical_entry, yield_entry, nav_entry] if s is not None]
    entry_limit = min(entry_signals) if entry_signals else None

    # ── Exit signals ─────────────────────────────────────────────────────────
    technical_exit: Optional[float] = None
    if resistance_level is not None or week_52_high is not None:
        candidates = []
        if resistance_level is not None:
            candidates.append(resistance_level)
        if week_52_high is not None:
            candidates.append(week_52_high * 0.95)
        technical_exit = min(candidates)

    yield_exit: Optional[float] = None
    if annual_dividend is not None and yield_exit_target is not None and yield_exit_target > 0:
        yield_exit = annual_dividend / (yield_exit_target / 100.0)

    nav_exit: Optional[float] = None
    if nav_eligible and nav_value is not None:
        nav_exit = nav_value * 1.05

    exit_signals = [s for s in [technical_exit, yield_exit, nav_exit] if s is not None]
    exit_limit = min(exit_signals) if exit_signals else None

    # ── Zone status ──────────────────────────────────────────────────────────
    pct_from_entry: Optional[float] = None
    if entry_limit is None:
        zone_status = ZoneStatus.UNKNOWN
    elif price is None:
        zone_status = ZoneStatus.UNKNOWN
    else:
        pct_from_entry = round((price - entry_limit) / entry_limit * 100.0, 2)
        if price < entry_limit:
            zone_status = ZoneStatus.BELOW_ENTRY
        elif price <= entry_limit * 1.03:
            zone_status = ZoneStatus.IN_ZONE
        elif price <= entry_limit * 1.05:
            zone_status = ZoneStatus.NEAR_ENTRY
        else:
            zone_status = ZoneStatus.ABOVE_ENTRY

    return EntryExitResult(
        entry_limit=round(entry_limit, 2) if entry_limit is not None else None,
        exit_limit=round(exit_limit, 2) if exit_limit is not None else None,
        current_price=price,
        pct_from_entry=pct_from_entry,
        zone_status=zone_status,
        signals={
            "technical_entry": round(technical_entry, 2) if technical_entry is not None else None,
            "yield_entry":     round(yield_entry, 2)     if yield_entry is not None else None,
            "nav_entry":       round(nav_entry, 2)       if nav_entry is not None else None,
            "technical_exit":  round(technical_exit, 2)  if technical_exit is not None else None,
            "yield_exit":      round(yield_exit, 2)      if yield_exit is not None else None,
            "nav_exit":        round(nav_exit, 2)        if nav_exit is not None else None,
        },
    )
```

- [ ] **Step 4: Run tests — expect green**

```bash
cd src/opportunity-scanner-service
python3 -m pytest tests/test_entry_exit.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/opportunity-scanner-service/app/scanner/entry_exit.py \
        src/opportunity-scanner-service/tests/test_entry_exit.py
git commit -m "feat(scanner): add entry/exit price engine with zone status"
```

---

## Task 2: Portfolio Context Annotator

**Files:**

- Create: `src/opportunity-scanner-service/app/scanner/portfolio_context.py`
- Create: `src/opportunity-scanner-service/tests/test_portfolio_context.py`

### Background — Portfolio Context

Given a list of `ScanItem`s and a portfolio's positions (held shares, asset class, sector, scores), this module:

1. Computes market-value-weighted class/sector weights across the portfolio
2. Annotates each scan item with `already_held`, weight percentages, overweight flags, underperformer status
3. Filters/re-ranks by `portfolio_lens`

Input positions come as dicts (fetched from DB before calling this module). The module is pure Python — no DB calls inside.

- [ ] **Step 1: Write failing tests**

```python
# src/opportunity-scanner-service/tests/test_portfolio_context.py
"""Tests for portfolio context annotator."""
import pytest
from app.scanner.portfolio_context import (
    annotate_with_portfolio,
    apply_lens,
    PortfolioPosition,
    PortfolioContext,
)


def _pos(symbol, asset_class, sector, shares, price, val_score=35.0, dur_score=35.0):
    return PortfolioPosition(
        symbol=symbol,
        asset_class=asset_class,
        sector=sector,
        shares=shares,
        price=price,
        valuation_yield_score=val_score,
        financial_durability_score=dur_score,
    )


def _item(ticker, asset_class, score=80.0):
    """Minimal scan item dict for testing."""
    return {
        "ticker": ticker,
        "asset_class": asset_class,
        "score": score,
        "grade": "A",
        "recommendation": "AGGRESSIVE_BUY",
        "chowder_signal": None,
        "chowder_number": None,
        "signal_penalty": 0.0,
        "rank": 1,
        "passed_quality_gate": True,
        "veto_flag": False,
        "score_details": {},
        "portfolio_context": None,
        "entry_exit": None,
    }


class TestAnnotation:
    def test_already_held_flagged(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        assert result[0]["portfolio_context"]["already_held"] is True

    def test_not_held_flagged(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0)]
        items = [_item("ARCC", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        assert result[0]["portfolio_context"]["already_held"] is False

    def test_asset_class_weight_computed(self):
        # Portfolio: MAIN (BDC) 4000, ARCC (BDC) 4000, O (EQUITY_REIT) 2000 — total 10000
        # BDC weight = 80%
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
            _pos("ARCC", "BDC", "Financials", 100, 40.0),
            _pos("O", "EQUITY_REIT", "Real Estate", 100, 20.0),
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        ctx = result[0]["portfolio_context"]
        assert ctx["asset_class_weight_pct"] == pytest.approx(80.0)

    def test_sector_weight_computed(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
            _pos("O", "EQUITY_REIT", "Real Estate", 100, 60.0),
        ]
        items = [_item("O", "EQUITY_REIT")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        ctx = result[0]["portfolio_context"]
        assert ctx["sector_weight_pct"] == pytest.approx(60.0)

    def test_class_overweight_flag(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
            _pos("ARCC", "BDC", "Financials", 100, 40.0),
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        assert result[0]["portfolio_context"]["class_overweight"] is True

    def test_underperformer_income_pillar(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=20.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        ctx = result[0]["portfolio_context"]
        assert ctx["is_underperformer"] is True
        assert ctx["underperformer_reason"] == "income_pillar"

    def test_underperformer_durability_pillar(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, dur_score=20.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        ctx = result[0]["portfolio_context"]
        assert ctx["is_underperformer"] is True
        assert ctx["underperformer_reason"] == "durability_pillar"

    def test_position_excluded_from_denominator_when_price_missing(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
            _pos("ARCC", "BDC", "Financials", 100, None),  # price missing
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)
        # Only MAIN counts: BDC weight = 100%
        assert result[0]["portfolio_context"]["asset_class_weight_pct"] == pytest.approx(100.0)


class TestLens:
    def _make_scan_items_with_context(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=20.0),  # underperformer
        ]
        items = [
            _item("MAIN", "BDC", score=65.0),   # held, underperformer
            _item("ARCC", "BDC", score=82.0),   # not held, BDC
            _item("O", "EQUITY_REIT", score=78.0),  # not held, different class
        ]
        return annotate_with_portfolio(items, positions, class_overweight_pct=20, sector_overweight_pct=30)

    def test_gap_lens_excludes_held(self):
        items = self._make_scan_items_with_context()
        result = apply_lens(items, lens="gap")
        tickers = [i["ticker"] for i in result]
        assert "MAIN" not in tickers

    def test_replacement_lens_includes_same_class_as_underperformer(self):
        items = self._make_scan_items_with_context()
        result = apply_lens(items, lens="replacement")
        tickers = [i["ticker"] for i in result]
        assert "ARCC" in tickers
        assert "O" not in tickers

    def test_replacement_sets_replacing_ticker(self):
        items = self._make_scan_items_with_context()
        result = apply_lens(items, lens="replacement")
        arcc = next(i for i in result if i["ticker"] == "ARCC")
        assert arcc["portfolio_context"]["replacing_ticker"] == "MAIN"

    def test_concentration_lens_includes_all(self):
        items = self._make_scan_items_with_context()
        result = apply_lens(items, lens="concentration")
        assert len(result) == 3

    def test_null_lens_annotates_only(self):
        items = self._make_scan_items_with_context()
        result = apply_lens(items, lens=None)
        assert len(result) == 3

    def test_gap_lens_sorted_by_score_descending(self):
        positions = []
        items = [
            _item("ARCC", "BDC", score=70.0),
            _item("MAIN", "BDC", score=90.0),
            _item("O", "EQUITY_REIT", score=80.0),
        ]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens="gap")
        scores = [i["score"] for i in result]
        assert scores == sorted(scores, reverse=True)

    def test_replacement_lens_sorted_by_score_delta(self):
        positions = [
            _pos("HELD", "BDC", "Financials", 100, 40.0, val_score=20.0),
        ]
        held_item = _item("HELD", "BDC", score=55.0)
        candidate_high = _item("ARCC", "BDC", score=88.0)   # delta = 33
        candidate_low = _item("MAIN", "BDC", score=72.0)    # delta = 17
        items = [held_item, candidate_high, candidate_low]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens="replacement")
        tickers = [i["ticker"] for i in result]
        assert tickers.index("ARCC") < tickers.index("MAIN")

    def test_multiple_underperformers_lowest_score_chosen(self):
        """When two held positions underperform in same class, lowest scorer is replacing_ticker."""
        positions = [
            _pos("WEAK1", "BDC", "Financials", 100, 40.0, val_score=20.0),
            _pos("WEAK2", "BDC", "Financials", 100, 40.0, val_score=20.0),
        ]
        weak1 = _item("WEAK1", "BDC", score=65.0)
        weak2 = _item("WEAK2", "BDC", score=55.0)
        candidate = _item("ARCC", "BDC", score=85.0)
        annotated = annotate_with_portfolio([weak1, weak2, candidate], positions)
        result = apply_lens(annotated, lens="replacement")
        arcc_row = next(i for i in result if i["ticker"] == "ARCC")
        assert arcc_row["portfolio_context"]["replacing_ticker"] == "WEAK2"

    def test_sector_overweight_flag(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 200, 50.0),
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, sector_overweight_pct=30)
        assert result[0]["portfolio_context"]["sector_overweight"] is True

    def test_held_weight_pct_value(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),    # MV=4000
            _pos("O", "EQUITY_REIT", "Real Estate", 100, 60.0),  # MV=6000
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions)
        assert result[0]["portfolio_context"]["held_weight_pct"] == pytest.approx(40.0, rel=1e-2)

    def test_zero_shares_excluded_from_denominator(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
            _pos("ARCC", "BDC", "Financials", 0, 50.0),   # zero shares → MV=0
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20)
        ctx = result[0]["portfolio_context"]
        assert ctx["asset_class_weight_pct"] == pytest.approx(100.0)
        assert ctx["class_overweight"] is True

    def test_empty_portfolio_weights_are_zero(self):
        items = [_item("ARCC", "BDC")]
        result = annotate_with_portfolio(items, positions=[])
        ctx = result[0]["portfolio_context"]
        assert ctx["asset_class_weight_pct"] == 0.0
        assert ctx["sector_weight_pct"] == 0.0
        assert ctx["class_overweight"] is False
        assert ctx["already_held"] is False

    def test_concentration_lens_rank_by_diversification_score(self):
        positions = [
            _pos("BDC_HEAVY", "BDC", "Financials", 500, 40.0),   # BDC MV=20000
            _pos("REIT_LIGHT", "EQUITY_REIT", "Real Estate", 100, 30.0),  # MV=3000
        ]
        bdc_candidate = _item("ARCC", "BDC", score=90.0)
        reit_candidate = _item("O", "EQUITY_REIT", score=80.0)
        annotated = annotate_with_portfolio([bdc_candidate, reit_candidate], positions)
        result = apply_lens(annotated, lens="concentration")
        # BDC is ~87% of portfolio → BDC candidate score×0.13=11.7; REIT ~13% → 80×0.87=69.6 → REIT ranks first
        assert result[0]["ticker"] == "O"

    def test_multiple_candidates_same_replacing_ticker(self):
        positions = [
            _pos("WEAK", "BDC", "Financials", 100, 40.0, val_score=20.0),
        ]
        weak_item = _item("WEAK", "BDC", score=60.0)
        c1 = _item("ARCC", "BDC", score=88.0)
        c2 = _item("MAIN", "BDC", score=82.0)
        annotated = annotate_with_portfolio([weak_item, c1, c2], positions)
        result = apply_lens(annotated, lens="replacement")
        for row in result:
            assert row["portfolio_context"]["replacing_ticker"] == "WEAK"

    def test_env_driven_thresholds_respected(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=150.0)
        assert result[0]["portfolio_context"]["class_overweight"] is False
        result2 = annotate_with_portfolio(items, positions, class_overweight_pct=80.0)
        assert result2[0]["portfolio_context"]["class_overweight"] is True


class TestAnnotationExtra:
    """Additional annotation coverage to meet ≥40 test requirement."""

    def test_not_held_already_held_false(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0)]
        items = [_item("ARCC", "BDC")]
        result = annotate_with_portfolio(items, positions)
        assert result[0]["portfolio_context"]["already_held"] is False
        assert result[0]["portfolio_context"]["held_shares"] is None

    def test_held_shares_count_correct(self):
        positions = [_pos("MAIN", "BDC", "Financials", 250, 40.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions)
        assert result[0]["portfolio_context"]["held_shares"] == 250

    def test_replacing_ticker_null_in_null_lens(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=20.0)]
        items = [_item("MAIN", "BDC"), _item("ARCC", "BDC")]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens=None)
        for row in result:
            assert row["portfolio_context"]["replacing_ticker"] is None

    def test_class_weight_not_overweight_below_threshold(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 10.0),   # BDC MV=1000
            _pos("O", "EQUITY_REIT", "Real Estate", 100, 90.0),  # REIT MV=9000
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, class_overweight_pct=20.0)
        # BDC = 10% < 20 → not overweight
        assert result[0]["portfolio_context"]["class_overweight"] is False
        assert result[0]["portfolio_context"]["asset_class_weight_pct"] == pytest.approx(10.0)

    def test_sector_weight_not_overweight_below_threshold(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 20.0),   # Financials MV=2000
            _pos("O", "EQUITY_REIT", "Real Estate", 100, 80.0),  # Real Estate MV=8000
        ]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions, sector_overweight_pct=30.0)
        # Financials = 20% < 30 → not overweight
        assert result[0]["portfolio_context"]["sector_overweight"] is False

    def test_underperformer_both_pillars_reason_income_wins(self):
        """When both pillars fail, income_pillar reason takes precedence."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=20.0, dur_score=20.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions)
        ctx = result[0]["portfolio_context"]
        assert ctx["is_underperformer"] is True
        assert ctx["underperformer_reason"] == "income_pillar"

    def test_not_underperformer_when_both_pillars_pass(self):
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=30.0, dur_score=30.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions)
        ctx = result[0]["portfolio_context"]
        assert ctx["is_underperformer"] is False
        assert ctx["underperformer_reason"] is None

    def test_gap_lens_empty_when_all_held(self):
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
            _pos("ARCC", "BDC", "Financials", 100, 40.0),
        ]
        items = [_item("MAIN", "BDC"), _item("ARCC", "BDC")]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens="gap")
        assert result == []

    def test_replacement_lens_empty_when_no_underperformers(self):
        """No underperforming positions → replacement lens returns nothing."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=35.0, dur_score=35.0)]
        items = [_item("MAIN", "BDC"), _item("ARCC", "BDC", score=85.0)]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens="replacement")
        assert result == []

    def test_replacement_lens_excludes_different_class(self):
        """Replacement candidates must be same asset class as underperformer."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=20.0)]
        items = [_item("MAIN", "BDC", score=60.0), _item("O", "EQUITY_REIT", score=85.0)]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens="replacement")
        tickers = [i["ticker"] for i in result]
        assert "O" not in tickers

    def test_multiple_items_no_portfolio(self):
        """No portfolio → all items pass through with null portfolio_context."""
        items = [_item("ARCC", "BDC"), _item("O", "EQUITY_REIT"), _item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions=[])
        assert len(result) == 3
        for row in result:
            assert row["portfolio_context"]["already_held"] is False

    def test_annotate_preserves_all_item_fields(self):
        """Annotation does not strip existing fields from scan items."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0)]
        item = _item("MAIN", "BDC", score=82.5)
        result = annotate_with_portfolio([item], positions)
        row = result[0]
        assert row["ticker"] == "MAIN"
        assert row["score"] == 82.5
        assert row["asset_class"] == "BDC"
        assert "portfolio_context" in row

    def test_concentration_all_same_class_scores_by_diversification(self):
        """Concentration lens: equal class weight → ranks pure by score."""
        positions = [
            _pos("MAIN", "BDC", "Financials", 100, 40.0),
        ]
        c1 = _item("ARCC", "BDC", score=90.0)
        c2 = _item("HTGC", "BDC", score=75.0)
        annotated = annotate_with_portfolio([c1, c2], positions)
        result = apply_lens(annotated, lens="concentration")
        # Both BDC; same class weight → higher score wins
        assert result[0]["ticker"] == "ARCC"

    def test_null_lens_order_unchanged(self):
        """Null lens preserves original item order."""
        positions = []
        items = [_item("O", "EQUITY_REIT", score=70.0), _item("MAIN", "BDC", score=90.0)]
        annotated = annotate_with_portfolio(items, positions)
        result = apply_lens(annotated, lens=None)
        assert [r["ticker"] for r in result] == ["O", "MAIN"]

    def test_held_weight_pct_null_when_price_missing(self):
        """held_weight_pct is None when position price is missing."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, None)]  # no price
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions)
        assert result[0]["portfolio_context"]["held_weight_pct"] is None

    def test_replacement_assigns_ticker_case_insensitive(self):
        """MAIN and main resolve to same ticker."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=20.0)]
        held_item = _item("main", "BDC", score=60.0)  # lowercase
        candidate = _item("ARCC", "BDC", score=85.0)
        annotated = annotate_with_portfolio([held_item, candidate], positions)
        result = apply_lens(annotated, lens="replacement")
        assert len(result) > 0
        assert result[0]["portfolio_context"]["replacing_ticker"].upper() == "MAIN"

    def test_underperformer_threshold_boundary_at_28(self):
        """val_score == 28 is NOT underperformer (condition is strictly < 28)."""
        positions = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=28.0, dur_score=28.0)]
        items = [_item("MAIN", "BDC")]
        result = annotate_with_portfolio(items, positions)
        ctx = result[0]["portfolio_context"]
        assert ctx["is_underperformer"] is False
        # Also verify: val_score=27.9 → IS underperformer
        positions2 = [_pos("MAIN", "BDC", "Financials", 100, 40.0, val_score=27.9)]
        result2 = annotate_with_portfolio(items, positions2)
        assert result2[0]["portfolio_context"]["is_underperformer"] is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd src/opportunity-scanner-service
python3 -m pytest tests/test_portfolio_context.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement portfolio_context.py**

```python
# src/opportunity-scanner-service/app/scanner/portfolio_context.py
"""
Agent 07 — Portfolio Context Annotator

Pure Python module — no DB calls. Receives pre-fetched positions and scan items,
computes market-value weights, annotates each item, and applies lens filtering.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

UNDERPERFORMER_SCORE_THRESHOLD = 28.0  # below 70% of max 40 pillar score


@dataclass
class PortfolioPosition:
    symbol: str
    asset_class: str
    sector: str
    shares: float
    price: Optional[float]             # from market_data_cache; None = excluded from denominator
    valuation_yield_score: Optional[float] = None
    financial_durability_score: Optional[float] = None


def _market_value(pos: PortfolioPosition) -> Optional[float]:
    if pos.price is None or pos.shares is None:
        return None
    return pos.shares * pos.price


def annotate_with_portfolio(
    items: list[dict[str, Any]],
    positions: list[PortfolioPosition],
    class_overweight_pct: float = 20.0,
    sector_overweight_pct: float = 30.0,
) -> list[dict[str, Any]]:
    """Annotate each scan item with portfolio context."""
    # Build lookup: symbol → position
    pos_by_symbol = {p.symbol.upper(): p for p in positions}

    # Compute portfolio total market value (exclude positions with no price)
    total_mv = sum(mv for p in positions if (mv := _market_value(p)) is not None)

    # Compute asset-class and sector weights from portfolio
    class_mv: dict[str, float] = {}
    sector_mv: dict[str, float] = {}
    for p in positions:
        mv = _market_value(p)
        if mv is None:
            continue
        class_mv[p.asset_class] = class_mv.get(p.asset_class, 0.0) + mv
        sector_mv[p.sector] = sector_mv.get(p.sector, 0.0) + mv

    def _weight_pct(mv_dict: dict, key: str) -> float:
        if total_mv == 0:
            return 0.0
        return round(mv_dict.get(key, 0.0) / total_mv * 100.0, 1)

    # Identify underperformers: held positions failing income or durability pillar
    underperformers: dict[str, str] = {}   # symbol → reason
    for p in positions:
        if p.valuation_yield_score is not None and p.valuation_yield_score < UNDERPERFORMER_SCORE_THRESHOLD:
            underperformers[p.symbol.upper()] = "income_pillar"
        elif p.financial_durability_score is not None and p.financial_durability_score < UNDERPERFORMER_SCORE_THRESHOLD:
            underperformers[p.symbol.upper()] = "durability_pillar"

    # For each scan item, determine context from the HELD position in that asset class
    # (for the item itself, use the portfolio's aggregate class/sector weights)
    result = []
    for item in items:
        ticker = item["ticker"].upper()
        held_pos = pos_by_symbol.get(ticker)
        asset_class = item.get("asset_class", "")

        already_held = held_pos is not None
        class_weight = _weight_pct(class_mv, asset_class)
        # sector comes from the scan item's market data (not available here — use held pos sector or None)
        sector = held_pos.sector if held_pos else ""
        sector_weight = _weight_pct(sector_mv, sector) if sector else 0.0

        is_underperformer = ticker in underperformers
        underperformer_reason = underperformers.get(ticker)

        ctx = {
            "already_held": already_held,
            "held_shares": held_pos.shares if held_pos else None,
            "held_weight_pct": round(_market_value(held_pos) / total_mv * 100.0, 1)
                               if held_pos and total_mv > 0 and _market_value(held_pos) is not None else None,
            "asset_class_weight_pct": class_weight,
            "sector_weight_pct": sector_weight,
            "class_overweight": class_weight > class_overweight_pct,
            "sector_overweight": sector_weight > sector_overweight_pct,
            "is_underperformer": is_underperformer,
            "underperformer_reason": underperformer_reason,
            "replacing_ticker": None,  # set by apply_lens for replacement lens
        }

        annotated = dict(item)
        annotated["portfolio_context"] = ctx
        result.append(annotated)

    return result


def apply_lens(
    items: list[dict[str, Any]],
    lens: Optional[str],
) -> list[dict[str, Any]]:
    """Filter and re-rank items according to the selected lens."""
    if lens is None:
        return items

    if lens == "gap":
        return sorted(
            (i for i in items if not i["portfolio_context"]["already_held"]),
            key=lambda i: i["score"],
            reverse=True,
        )

    if lens == "replacement":
        # Find underperforming held tickers per asset class (lowest score wins as "replacing_ticker")
        underperformer_by_class: dict[str, str] = {}
        for item in items:
            ctx = item["portfolio_context"]
            if ctx["already_held"] and ctx["is_underperformer"]:
                ac = item["asset_class"]
                existing = underperformer_by_class.get(ac)
                if existing is None or item["score"] < next(
                    (i["score"] for i in items if i["ticker"] == existing), 999
                ):
                    underperformer_by_class[ac] = item["ticker"]

        result = []
        for item in items:
            if item["portfolio_context"]["already_held"]:
                continue
            ac = item["asset_class"]
            replacing = underperformer_by_class.get(ac)
            if replacing is None:
                continue
            annotated = dict(item)
            annotated["portfolio_context"] = dict(item["portfolio_context"])
            annotated["portfolio_context"]["replacing_ticker"] = replacing
            result.append(annotated)

        # Rank by score delta vs replacing_ticker score
        def _delta(i: dict) -> float:
            replacing = i["portfolio_context"]["replacing_ticker"]
            replaced_score = next(
                (x["score"] for x in items if x["ticker"] == replacing), 0.0
            )
            return i["score"] - replaced_score

        result.sort(key=_delta, reverse=True)
        return result

    if lens == "concentration":
        # Rank: score × (1 - class_weight_pct/100) to reward diversifying picks
        def _conc_score(i: dict) -> float:
            w = i["portfolio_context"].get("asset_class_weight_pct", 0.0)
            return i["score"] * (1 - w / 100.0)
        return sorted(items, key=_conc_score, reverse=True)

    return items
```

- [ ] **Step 4: Run tests — expect green**

```bash
cd src/opportunity-scanner-service
python3 -m pytest tests/test_portfolio_context.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full test suite — no regressions**

```bash
python3 -m pytest tests/ -v --tb=short
```

Expected: all 100 existing tests + new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/opportunity-scanner-service/app/scanner/portfolio_context.py \
        src/opportunity-scanner-service/tests/test_portfolio_context.py
git commit -m "feat(scanner): add portfolio context annotator with lens filtering"
```

---

## Task 3: Config — Overweight Thresholds

**Files:**

- Modify: `src/opportunity-scanner-service/app/config.py`

- [ ] **Step 1: Add settings**

Add these two lines inside the `Settings` class after `quality_gate_threshold`:

```python
class_overweight_pct: float = 20.0    # % weight above which class is flagged overweight
sector_overweight_pct: float = 30.0   # % weight above which sector is flagged overweight
```

- [ ] **Step 2: Verify settings load**

```bash
cd src/opportunity-scanner-service
python3 -c "from app.config import settings; print(settings.class_overweight_pct, settings.sector_overweight_pct)"
```

Expected: `20.0 30.0`

- [ ] **Step 3: Commit**

```bash
git add src/opportunity-scanner-service/app/config.py
git commit -m "feat(scanner): add class/sector overweight threshold settings"
```

---

## Task 4: ProposalDraft Model + Migration

**Files:**

- Modify: `src/opportunity-scanner-service/app/models.py`
- Create: `src/opportunity-scanner-service/scripts/migrate_proposal_drafts.py`

- [ ] **Step 1: Add ORM model**

In `src/opportunity-scanner-service/app/models.py`, append after the existing `ScanResult` class:

```python
class ProposalDraft(Base):
    """Proposal draft written by scanner before Agent 12 picks it up."""
    __tablename__ = "proposal_drafts"
    __table_args__ = (
        Index("ix_proposal_drafts_created_at", "created_at"),
        {"schema": "platform_shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_shared.scan_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_shared.portfolios.id"),
        nullable=False,
    )
    tickers: Mapped[list] = mapped_column(JSONB, nullable=False)       # [{ticker, entry_limit, exit_limit}]
    entry_limits: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {ticker: entry_limit}
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
```

Also ensure `ForeignKey` and `Index` are imported in models.py:

```python
from sqlalchemy import ForeignKey, Index, Integer, String, text
```

(Add `ForeignKey` if not present; `Index` is likely already there — verify before adding.)

- [ ] **Step 2: Create migration script**

```python
# src/opportunity-scanner-service/scripts/migrate_proposal_drafts.py
"""
Create platform_shared.proposal_drafts table.
Safe to run multiple times (uses IF NOT EXISTS).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlalchemy as sa
from app.config import settings

DDL = """
CREATE TABLE IF NOT EXISTS platform_shared.proposal_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID REFERENCES platform_shared.scan_results(id),
    target_portfolio_id UUID NOT NULL REFERENCES platform_shared.portfolios(id),
    tickers             JSONB NOT NULL,
    entry_limits        JSONB NOT NULL,
    status              TEXT NOT NULL DEFAULT 'DRAFT',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_proposal_drafts_created_at
    ON platform_shared.proposal_drafts (created_at);
"""

engine = sa.create_engine(settings.database_url)
with engine.connect() as conn:
    conn.execute(sa.text(DDL))
    conn.commit()
    print("proposal_drafts table ready.")
```

- [ ] **Step 3: Run migration on remote server**

```bash
ssh legato "cd /opt/income-platform/src/opportunity-scanner-service && python3 scripts/migrate_proposal_drafts.py"
```

Expected: `proposal_drafts table ready.`

- [ ] **Step 4: Verify**

```bash
ssh legato "psql \$DATABASE_URL -c '\d platform_shared.proposal_drafts'"
```

- [ ] **Step 5: Commit**

```bash
git add src/opportunity-scanner-service/app/models.py \
        src/opportunity-scanner-service/scripts/migrate_proposal_drafts.py
git commit -m "feat(scanner): add ProposalDraft model and migration"
```

---

## Task 5: Extend POST /scan + Add Propose Endpoint

**Files:**

- Modify: `src/opportunity-scanner-service/app/api/scanner.py`
- Modify: `src/opportunity-scanner-service/app/scanner/engine.py`
- Create: `src/opportunity-scanner-service/tests/test_propose_api.py`

### Background — API Extension

`POST /scan` already accepts a rich filter set. We add:

- `portfolio_id` — optional UUID; triggers portfolio annotation
- `portfolio_lens` — optional string; triggers lens filtering after annotation

The engine gains `entry_exit` (always computed) and `portfolio_context` (computed when portfolio_id provided) fields on `ScanItem`.

The new `POST /scan/{scan_id}/propose` endpoint writes a `ProposalDraft` row and returns the draft.

- [ ] **Step 1: Write failing tests for propose endpoint**

```python
# src/opportunity-scanner-service/tests/test_propose_api.py
"""Tests for POST /scan/{scan_id}/propose endpoint."""
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.auth import create_access_token

client = TestClient(app)


def _auth_headers():
    token = create_access_token({"sub": "test"})
    return {"Authorization": f"Bearer {token}"}


class TestProposeEndpoint:
    def _make_scan_id(self, db_mock):
        """Return a UUID that the mock DB will recognise as a valid scan."""
        scan_id = str(uuid.uuid4())
        mock_row = MagicMock()
        mock_row.id = uuid.UUID(scan_id)
        db_mock.get.return_value = mock_row
        return scan_id

    @patch("app.api.scanner.get_db")
    def test_missing_scan_id_returns_404(self, mock_get_db):
        db = MagicMock()
        db.get.return_value = None
        mock_get_db.return_value = iter([db])
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/scan/{fake_id}/propose",
            json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404

    @patch("app.api.scanner.get_db")
    def test_missing_portfolio_id_returns_422(self, mock_get_db):
        db = MagicMock()
        mock_get_db.return_value = iter([db])
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"selected_tickers": ["MAIN"]},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    @patch("app.api.scanner.get_db")
    def test_happy_path_returns_draft(self, mock_get_db):
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.80, "exit_limit": 52.80, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
        ]

        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": 44.80, "exit_limit": 52.80, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": 44.80}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)  # portfolio exists
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["MAIN"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "proposal_id" in data
        assert data["status"] == "DRAFT"
        assert data["target_portfolio_id"] == portfolio_id

    @patch("app.api.scanner.get_db")
    def test_response_shape_has_all_required_fields(self, mock_get_db):
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "ARCC", "entry_exit": {"entry_limit": 18.0, "exit_limit": 22.0, "zone_status": "IN_ZONE"}, "score": 75.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "ARCC", "entry_limit": 18.0, "exit_limit": 22.0, "zone_status": "IN_ZONE", "score": 75.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"ARCC": 18.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["ARCC"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        required_keys = {"proposal_id", "status", "tickers", "entry_limits", "target_portfolio_id", "created_at"}
        assert required_keys.issubset(set(data.keys()))

    @patch("app.api.scanner.get_db")
    def test_portfolio_not_found_returns_422(self, mock_get_db):
        scan_id = str(uuid.uuid4())
        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [{"ticker": "MAIN", "entry_exit": {}, "score": 80.0, "asset_class": "BDC"}]

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = None  # portfolio NOT found
        mock_get_db.return_value = iter([db])

        resp = client.post(
            f"/scan/{scan_id}/propose",
            json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_empty_selected_tickers_returns_422(self):
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"selected_tickers": [], "target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_missing_selected_tickers_returns_422(self):
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    @patch("app.api.scanner.get_db")
    def test_ticker_not_in_scan_items_excluded_from_payload(self, mock_get_db):
        """Tickers requested but not in scan results are silently skipped."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "IN_ZONE"}, "score": 82.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "IN_ZONE", "score": 82.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": 44.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["MAIN", "NOTHERE"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        tickers_in_payload = [t["ticker"] for t in data["tickers"]]
        assert "MAIN" in tickers_in_payload
        assert "NOTHERE" not in tickers_in_payload

    @patch("app.api.scanner.get_db")
    def test_agent12_unavailable_still_writes_draft(self, mock_get_db):
        """If Agent 12 is not reachable, proposal_drafts row is still written locally."""
        # The stub endpoint writes directly to DB without calling Agent 12.
        # This test confirms a DRAFT row is returned even without Agent 12.
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "O", "entry_exit": {"entry_limit": 55.0, "exit_limit": 65.0, "zone_status": "NEAR_ENTRY"}, "score": 79.0, "asset_class": "EQUITY_REIT"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "O", "entry_limit": 55.0, "exit_limit": 65.0, "zone_status": "NEAR_ENTRY", "score": 79.0, "asset_class": "EQUITY_REIT"}]
        draft_row.entry_limits = {"O": 55.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["O"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        # Status is DRAFT (not forwarded to Agent 12 yet)
        assert resp.status_code == 200
        assert resp.json()["status"] == "DRAFT"

    def test_invalid_scan_id_format_returns_422(self):
        """Non-UUID scan_id path param returns 422 from FastAPI validation."""
        resp = client.post(
            "/scan/not-a-uuid/propose",
            json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_unauthenticated_request_returns_401(self):
        resp = client.post(
            f"/scan/{uuid.uuid4()}/propose",
            json={"selected_tickers": ["MAIN"], "target_portfolio_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @patch("app.api.scanner.get_db")
    def test_entry_limits_keyed_by_ticker(self, mock_get_db):
        """entry_limits in response is dict keyed by ticker."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_exit": {"entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE"}, "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [
            {"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE", "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row.entry_limits = {"MAIN": 44.0, "ARCC": 18.5}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["MAIN", "ARCC"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "MAIN" in data["entry_limits"]
        assert "ARCC" in data["entry_limits"]

    @patch("app.api.scanner.get_db")
    def test_ticker_matching_is_case_insensitive(self, mock_get_db):
        """'main' in selected_tickers matches 'MAIN' in scan items."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": 44.0}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["main"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200

    @patch("app.api.scanner.get_db")
    def test_scan_with_null_entry_exit_produces_null_entry_limit(self, mock_get_db):
        """When entry_exit block is missing from scan item, entry_limit is null in draft."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": None, "score": 80.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [{"ticker": "MAIN", "entry_limit": None, "exit_limit": None, "zone_status": None, "score": 80.0, "asset_class": "BDC"}]
        draft_row.entry_limits = {"MAIN": None}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["MAIN"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        assert resp.json()["entry_limits"]["MAIN"] is None

    @patch("app.api.scanner.get_db")
    def test_multiple_valid_tickers_all_included_in_draft(self, mock_get_db):
        """When two valid tickers are selected and both in scan, both appear in tickers list."""
        scan_id = str(uuid.uuid4())
        portfolio_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())

        scan_row = MagicMock()
        scan_row.id = uuid.UUID(scan_id)
        scan_row.items = [
            {"ticker": "MAIN", "entry_exit": {"entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY"}, "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_exit": {"entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE"}, "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row = MagicMock()
        draft_row.id = uuid.UUID(draft_id)
        draft_row.status = "DRAFT"
        draft_row.tickers = [
            {"ticker": "MAIN", "entry_limit": 44.0, "exit_limit": 52.0, "zone_status": "NEAR_ENTRY", "score": 82.0, "asset_class": "BDC"},
            {"ticker": "ARCC", "entry_limit": 18.5, "exit_limit": 22.0, "zone_status": "IN_ZONE", "score": 78.0, "asset_class": "BDC"},
        ]
        draft_row.entry_limits = {"MAIN": 44.0, "ARCC": 18.5}
        draft_row.target_portfolio_id = uuid.UUID(portfolio_id)
        draft_row.created_at = "2026-03-26T10:00:00+00:00"

        db = MagicMock()
        db.get.return_value = scan_row
        db.execute.return_value.fetchone.return_value = (portfolio_id,)
        db.refresh.side_effect = lambda obj: None
        mock_get_db.return_value = iter([db])

        with patch("app.api.scanner.ProposalDraft", return_value=draft_row):
            resp = client.post(
                f"/scan/{scan_id}/propose",
                json={"selected_tickers": ["MAIN", "ARCC"], "target_portfolio_id": portfolio_id},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        tickers_in_payload = [t["ticker"] for t in resp.json()["tickers"]]
        assert "MAIN" in tickers_in_payload
        assert "ARCC" in tickers_in_payload
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd src/opportunity-scanner-service
python3 -m pytest tests/test_propose_api.py -v 2>&1 | head -15
```

Expected: failure (endpoint does not exist).

- [ ] **Step 3: Extend engine.py — add entry_exit + portfolio_context fields**

In `src/opportunity-scanner-service/app/scanner/engine.py`:

Add to imports at top:

```python
from app.scanner.entry_exit import compute_entry_exit
```

In the `ScanItem` dataclass, add after `score_details`:

```python
entry_exit: Optional[dict] = None
portfolio_context: Optional[dict] = None
```

In `run_scan()`, after building the `ScanItem`, add entry_exit computation. The cache data needs to be passed in. Add a new parameter `market_cache: dict[str, dict]` to `run_scan()` (defaults to `{}`):

```python
async def run_scan(
    tickers: list[str],
    min_score: float = 0.0,
    min_yield: float = 0.0,
    asset_classes: Optional[list[str]] = None,
    quality_gate_only: bool = False,
    market_cache: dict[str, dict] = None,   # {ticker: cache_row_dict}
) -> ScanEngineResult:
```

After building `ScanItem`, add:

```python
# Compute entry/exit if market data available
cache_row = (market_cache or {}).get(ticker, {})
ee = compute_entry_exit(
    asset_class=item.asset_class,
    price=cache_row.get("price"),
    support_level=cache_row.get("support_level"),
    sma_200=cache_row.get("sma_200"),
    resistance_level=cache_row.get("resistance_level"),
    week_52_high=cache_row.get("week_52_high"),
    dividend_yield=cache_row.get("dividend_yield"),
    nav_value=cache_row.get("nav_value"),
)
item.entry_exit = ee.to_dict()
```

- [ ] **Step 4: Extend scanner.py — new request fields, response fields, propose endpoint**

In `src/opportunity-scanner-service/app/api/scanner.py`:

**Add to imports:**

```python
import uuid as uuid_mod
from app.models import ProposalDraft
from app.scanner.portfolio_context import (
    PortfolioPosition,
    annotate_with_portfolio,
    apply_lens,
)
```

**Add to `ScanRequest`:**

```python
portfolio_id: Optional[str] = Field(None, description="Portfolio UUID to scan against")
portfolio_lens: Optional[str] = Field(None, description="gap | replacement | concentration | null")
```

**Add to `ScanItemResponse`:**

```python
entry_exit: Optional[dict[str, Any]] = None
portfolio_context: Optional[dict[str, Any]] = None
```

**In `post_scan()`, after `result = await run_scan(...)`, add portfolio context if portfolio_id provided:**

```python
items_json = [
    {
        ...existing fields...,
        "entry_exit": it.entry_exit,
        "portfolio_context": it.portfolio_context,
    }
    for it in result.items
]

if request.portfolio_id:
    # Fetch positions for portfolio
    pos_rows = db.execute(
        text("""
            SELECT p.symbol, p.shares, p.asset_type,
                   s.sector, m.price,
                   sc.valuation_yield_score, sc.financial_durability_score
            FROM platform_shared.positions p
            LEFT JOIN platform_shared.securities s ON s.symbol = p.symbol
            LEFT JOIN platform_shared.market_data_cache m ON m.symbol = p.symbol
            LEFT JOIN LATERAL (
                SELECT valuation_yield_score, financial_durability_score
                FROM platform_shared.income_scores
                WHERE ticker = p.symbol
                ORDER BY created_at DESC LIMIT 1
            ) sc ON true
            WHERE p.portfolio_id = :pid
        """),
        {"pid": request.portfolio_id},
    ).fetchall()

    positions = [
        PortfolioPosition(
            symbol=r[0], shares=float(r[1] or 0), asset_class=r[2] or "",
            sector=r[3] or "", price=float(r[4]) if r[4] else None,
            valuation_yield_score=float(r[5]) if r[5] else None,
            financial_durability_score=float(r[6]) if r[6] else None,
        )
        for r in pos_rows
    ]

    items_json = annotate_with_portfolio(
        items_json, positions,
        class_overweight_pct=settings.class_overweight_pct,
        sector_overweight_pct=settings.sector_overweight_pct,
    )
    if request.portfolio_lens:
        items_json = apply_lens(items_json, lens=request.portfolio_lens)
        # Re-rank after lens
        for rank, item in enumerate(items_json, start=1):
            item["rank"] = rank
```

**Add propose endpoint after the `/universe` endpoint:**

```python
class ProposeRequest(BaseModel):
    selected_tickers: list[str] = Field(..., min_length=1)
    target_portfolio_id: str = Field(..., description="UUID of target portfolio")


class ProposeDraftResponse(BaseModel):
    proposal_id: str
    status: str
    tickers: list[dict[str, Any]]
    entry_limits: dict[str, Any]
    target_portfolio_id: str
    created_at: str


@router.post("/scan/{scan_id}/propose", response_model=ProposeDraftResponse)
def post_propose(scan_id: UUID, request: ProposeRequest, db: Session = Depends(get_db)):
    """
    Create a proposal draft from selected scan results.
    Writes to proposal_drafts; Agent 12 will pick it up when available.
    """
    scan_row = db.get(ScanResult, scan_id)
    if scan_row is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found.")

    # Validate portfolio exists
    port_check = db.execute(
        text("SELECT id FROM platform_shared.portfolios WHERE id = :pid"),
        {"pid": request.target_portfolio_id},
    ).fetchone()
    if port_check is None:
        raise HTTPException(status_code=422, detail=f"Portfolio {request.target_portfolio_id} not found.")

    # Build tickers payload from scan items
    selected = {t.upper() for t in request.selected_tickers}
    tickers_payload = []
    entry_limits: dict[str, Any] = {}
    for item in scan_row.items:
        if item["ticker"].upper() not in selected:
            continue
        ee = item.get("entry_exit") or {}
        tickers_payload.append({
            "ticker": item["ticker"],
            "entry_limit": ee.get("entry_limit"),
            "exit_limit": ee.get("exit_limit"),
            "zone_status": ee.get("zone_status"),
            "score": item.get("score"),
            "asset_class": item.get("asset_class"),
        })
        entry_limits[item["ticker"]] = ee.get("entry_limit")

    draft = ProposalDraft(
        scan_id=scan_id,
        target_portfolio_id=uuid_mod.UUID(request.target_portfolio_id),
        tickers=tickers_payload,
        entry_limits=entry_limits,
        status="DRAFT",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return ProposeDraftResponse(
        proposal_id=str(draft.id),
        status=draft.status,
        tickers=draft.tickers,
        entry_limits=draft.entry_limits,
        target_portfolio_id=str(draft.target_portfolio_id),
        created_at=str(draft.created_at),
    )
```

- [ ] **Step 5: Run propose tests**

```bash
cd src/opportunity-scanner-service
python3 -m pytest tests/test_propose_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run full test suite — no regressions**

```bash
python3 -m pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/opportunity-scanner-service/app/scanner/engine.py \
        src/opportunity-scanner-service/app/api/scanner.py \
        src/opportunity-scanner-service/tests/test_propose_api.py
git commit -m "feat(scanner): extend POST /scan with entry_exit + portfolio context; add propose endpoint"
```

---

## Task 6: Frontend Types + Route Handler

**Files:**

- Modify: `src/frontend/src/lib/types.ts`
- Create: `src/frontend/src/app/api/scanner/propose/route.ts`

- [ ] **Step 1: Add scanner types to types.ts**

> **Note:** `PortfolioListItem` already exists in `src/frontend/src/lib/types.ts` (line ~293) — do NOT re-add it. `usePortfolios()` from `use-portfolios.ts` returns a React Query result; destructure as `const { data: portfolios = [] } = usePortfolios()`.

Append to `src/frontend/src/lib/types.ts`:

```typescript
// ── Scanner v2 types ──────────────────────────────────────────────────────────

export interface EntryExit {
  entry_limit: number | null;
  exit_limit: number | null;
  current_price: number | null;
  pct_from_entry: number | null;
  zone_status: "BELOW_ENTRY" | "IN_ZONE" | "NEAR_ENTRY" | "ABOVE_ENTRY" | "UNKNOWN";
  signals: {
    technical_entry: number | null;
    yield_entry: number | null;
    nav_entry: number | null;
    technical_exit: number | null;
    yield_exit: number | null;
    nav_exit: number | null;
  };
}

export interface PortfolioContext {
  already_held: boolean;
  held_shares: number | null;
  held_weight_pct: number | null;
  asset_class_weight_pct: number;
  sector_weight_pct: number;
  class_overweight: boolean;
  sector_overweight: boolean;
  is_underperformer: boolean;
  underperformer_reason: "income_pillar" | "durability_pillar" | null;
  replacing_ticker: string | null;
}

export interface ScanItem {
  rank: number;
  ticker: string;
  asset_class: string;
  score: number;
  grade: string;
  recommendation: string;
  chowder_number: number | null;
  chowder_signal: string | null;
  signal_penalty: number;
  passed_quality_gate: boolean;
  veto_flag: boolean;
  score_details: {
    valuation_yield_score?: number;
    financial_durability_score?: number;
    technical_entry_score?: number;
    nav_erosion_penalty?: number;
  };
  entry_exit?: EntryExit | null;
  portfolio_context?: PortfolioContext | null;
}

export interface ScanResult {
  scan_id: string;
  total_scanned: number;
  total_passed: number;
  total_vetoed: number;
  items: ScanItem[];
  filters_applied: Record<string, unknown>;
  created_at: string;
}

export interface ProposalDraft {
  proposal_id: string;
  status: string;
  tickers: Array<{
    ticker: string;
    entry_limit: number | null;
    exit_limit: number | null;
    zone_status: string;
    score: number;
    asset_class: string;
  }>;
  entry_limits: Record<string, number | null>;
  target_portfolio_id: string;
  created_at: string;
}
```

- [ ] **Step 2: Create propose route handler**

```typescript
// src/frontend/src/app/api/scanner/propose/route.ts
/**
 * Route Handler for POST /api/scanner/propose
 * Proxies to ADMIN_PANEL/api/scanner/scan/{scan_id}/propose
 * Quick operation — uses 15 s timeout.
 */
import { NextRequest, NextResponse } from "next/server";

const ADMIN_PANEL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

export async function POST(req: NextRequest) {
  const { scan_id, selected_tickers, target_portfolio_id } = await req.json();

  if (!scan_id || !target_portfolio_id || !selected_tickers?.length) {
    return NextResponse.json({ detail: "scan_id, target_portfolio_id and selected_tickers are required" }, { status: 422 });
  }

  try {
    const upstream = await fetch(`${ADMIN_PANEL}/api/scanner/scan/${scan_id}/propose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_tickers, target_portfolio_id }),
      signal: AbortSignal.timeout(15_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/lib/types.ts \
        src/frontend/src/app/api/scanner/propose/route.ts
git commit -m "feat(scanner-ui): add scanner v2 types and propose route handler"
```

---

## Task 7: InputPanel + FilterPanel Components

**Files:**

- Create: `src/frontend/src/components/scanner/input-panel.tsx`
- Create: `src/frontend/src/components/scanner/filter-panel.tsx`

- [ ] **Step 1: Create InputPanel**

```tsx
// src/frontend/src/components/scanner/input-panel.tsx
"use client";

import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { PortfolioListItem } from "@/lib/types";

export type InputMode = "manual" | "portfolio" | "universe";

interface InputPanelProps {
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
  manualTickers: string;
  onManualTickersChange: (v: string) => void;
  selectedPortfolioId: string | null;
  onPortfolioChange: (id: string) => void;
  portfolios: PortfolioListItem[];
}

const TABS: { value: InputMode; label: string }[] = [
  { value: "manual", label: "Manual List" },
  { value: "portfolio", label: "Portfolio" },
  { value: "universe", label: "Full Universe" },
];

export function InputPanel({
  mode,
  onModeChange,
  manualTickers,
  onManualTickersChange,
  selectedPortfolioId,
  onPortfolioChange,
  portfolios,
}: InputPanelProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      {/* Mode tabs */}
      <div className="flex gap-1 rounded-md bg-muted p-1 w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => onModeChange(tab.value)}
            className={cn(
              "px-3 py-1.5 rounded text-sm font-medium transition-colors",
              mode === tab.value
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Input area */}
      {mode === "manual" && (
        <Textarea
          value={manualTickers}
          onChange={(e) => onManualTickersChange(e.target.value)}
          placeholder={"Enter tickers (comma or newline separated)\nMAIN, ARCC, O, JEPI, ..."}
          rows={4}
          className="font-mono text-sm resize-none"
        />
      )}

      {mode === "portfolio" && (
        <Select value={selectedPortfolioId ?? ""} onValueChange={onPortfolioChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select a portfolio to scan..." />
          </SelectTrigger>
          <SelectContent>
            {portfolios.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
                <span className="ml-2 text-muted-foreground text-xs">
                  ({p.holding_count} positions)
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {mode === "universe" && (
        <p className="text-sm text-muted-foreground">
          Scans all active securities in the tracked universe. May take up to 2 minutes on a cold cache.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create FilterPanel**

```tsx
// src/frontend/src/components/scanner/filter-panel.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const ASSET_CLASSES = [
  "DIVIDEND_STOCK", "COVERED_CALL_ETF", "BOND",
  "EQUITY_REIT", "MORTGAGE_REIT", "BDC", "PREFERRED_STOCK",
];

export interface ScanFilters {
  // Group 1
  min_score: number;
  quality_gate_only: boolean;
  asset_classes: string[];
  // Group 2
  min_yield: number;
  max_payout_ratio: string;
  min_volume: string;
  min_market_cap_m: string;
  max_market_cap_m: string;
  min_price: string;
  max_price: string;
  max_pe: string;
  min_nav_discount_pct: string;
}

export const DEFAULT_FILTERS: ScanFilters = {
  min_score: 0,
  quality_gate_only: false,
  asset_classes: [],
  min_yield: 0,
  max_payout_ratio: "",
  min_volume: "",
  min_market_cap_m: "",
  max_market_cap_m: "",
  min_price: "",
  max_price: "",
  max_pe: "",
  min_nav_discount_pct: "",
};

interface FilterPanelProps {
  filters: ScanFilters;
  onChange: (f: ScanFilters) => void;
}

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false);

  const set = (patch: Partial<ScanFilters>) => onChange({ ...filters, ...patch });

  const toggleClass = (cls: string) => {
    const current = filters.asset_classes;
    set({
      asset_classes: current.includes(cls)
        ? current.filter((c) => c !== cls)
        : [...current, cls],
    });
  };

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50"
      >
        <span>Filters</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-5 border-t border-border pt-4">
          {/* Group 1 */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Scoring</p>
            <div className="flex items-center gap-4">
              <Label className="text-sm w-24 shrink-0">Min Score: {filters.min_score}</Label>
              <Slider
                min={0} max={100} step={5}
                value={[filters.min_score]}
                onValueChange={([v]) => set({ min_score: v })}
                className="flex-1"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch
                id="quality-gate"
                checked={filters.quality_gate_only}
                onCheckedChange={(v) => set({ quality_gate_only: v })}
              />
              <Label htmlFor="quality-gate" className="text-sm">Quality gate only (≥70)</Label>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ASSET_CLASSES.map((cls) => (
                <Badge
                  key={cls}
                  variant={filters.asset_classes.includes(cls) ? "default" : "outline"}
                  className="cursor-pointer select-none text-xs"
                  onClick={() => toggleClass(cls)}
                >
                  {cls.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          </div>

          {/* Group 2 */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Market Data</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                { label: "Min Yield %", key: "min_yield", type: "number" },
                { label: "Max Payout %", key: "max_payout_ratio" },
                { label: "Min Volume", key: "min_volume" },
                { label: "Min Cap $M", key: "min_market_cap_m" },
                { label: "Max Cap $M", key: "max_market_cap_m" },
                { label: "Min Price $", key: "min_price" },
                { label: "Max Price $", key: "max_price" },
                { label: "Max P/E", key: "max_pe" },
                { label: "NAV Discount %", key: "min_nav_discount_pct" },
              ].map(({ label, key }) => (
                <div key={key} className="space-y-1">
                  <Label className="text-xs text-muted-foreground">{label}</Label>
                  <Input
                    type="number"
                    value={(filters as Record<string, unknown>)[key] as string}
                    onChange={(e) => set({ [key]: e.target.value } as Partial<ScanFilters>)}
                    className="h-8 text-sm"
                    placeholder="—"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Check the project uses shadcn/ui Slider and Switch**

```bash
ls src/frontend/src/components/ui/ | grep -E "slider|switch"
```

If missing, add them:

```bash
cd src/frontend
npx shadcn@latest add slider switch label select textarea
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/scanner/
git commit -m "feat(scanner-ui): add InputPanel and FilterPanel components"
```

---

## Task 8: EntryExitBadge + PortfolioBadges + ResultsTable

**Files:**

- Create: `src/frontend/src/components/scanner/entry-exit-badge.tsx`
- Create: `src/frontend/src/components/scanner/portfolio-badges.tsx`
- Create: `src/frontend/src/components/scanner/results-table.tsx`

- [ ] **Step 1: Create EntryExitBadge**

```tsx
// src/frontend/src/components/scanner/entry-exit-badge.tsx
import { cn } from "@/lib/utils";
import type { EntryExit } from "@/lib/types";

const ZONE_CONFIG = {
  BELOW_ENTRY: { label: "Below Entry", dot: "bg-emerald-500", text: "text-emerald-600" },
  IN_ZONE:     { label: "In Zone",     dot: "bg-emerald-500", text: "text-emerald-600" },
  NEAR_ENTRY:  { label: "Near Entry",  dot: "bg-amber-500",   text: "text-amber-600" },
  ABOVE_ENTRY: { label: "Above Entry", dot: "bg-red-500",     text: "text-red-600" },
  UNKNOWN:     { label: "No Data",     dot: "bg-gray-400",    text: "text-gray-500" },
} as const;

interface EntryExitBadgeProps {
  entryExit: EntryExit | null | undefined;
  className?: string;
}

function fmt(v: number | null | undefined): string {
  if (v == null) return "—";
  return `$${v.toFixed(2)}`;
}

export function EntryExitBadge({ entryExit, className }: EntryExitBadgeProps) {
  if (!entryExit || entryExit.zone_status === "UNKNOWN") {
    return <span className="text-muted-foreground text-xs">—</span>;
  }

  const cfg = ZONE_CONFIG[entryExit.zone_status] ?? ZONE_CONFIG.UNKNOWN;
  const pct = entryExit.pct_from_entry;
  const sign = pct != null && pct >= 0 ? "+" : "";

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <span className={cn("text-sm font-medium tabular-nums", cfg.text)}>
        {fmt(entryExit.entry_limit)}
      </span>
      <span className={cn("inline-flex items-center gap-1 text-xs rounded-full px-1.5 py-0.5", cfg.text)}>
        <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", cfg.dot)} />
        {pct != null ? `${sign}${pct.toFixed(1)}%` : cfg.label}
      </span>
    </div>
  );
}

export function EntryExitExpandedRow({ entryExit }: { entryExit: EntryExit }) {
  const rows = [
    { label: "Technical entry", value: fmt(entryExit.signals.technical_entry) },
    { label: "Yield entry",     value: fmt(entryExit.signals.yield_entry) },
    { label: "NAV entry",       value: fmt(entryExit.signals.nav_entry) },
    { label: "Technical exit",  value: fmt(entryExit.signals.technical_exit) },
    { label: "Yield exit",      value: fmt(entryExit.signals.yield_exit) },
    { label: "NAV exit",        value: fmt(entryExit.signals.nav_exit) },
  ];

  return (
    <div className="grid grid-cols-3 gap-2 text-xs p-2">
      {rows.map(({ label, value }) => (
        <div key={label} className="flex justify-between gap-2">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-mono font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create PortfolioBadges**

```tsx
// src/frontend/src/components/scanner/portfolio-badges.tsx
import { Badge } from "@/components/ui/badge";
import type { PortfolioContext, ScanItem } from "@/lib/types";

interface PortfolioBadgesProps {
  item: ScanItem;
}

export function PortfolioBadges({ item }: PortfolioBadgesProps) {
  const ctx = item.portfolio_context;
  if (!ctx) return null;

  const income_ok = (item.score_details.valuation_yield_score ?? 40) >= 28;
  const durable_ok = (item.score_details.financial_durability_score ?? 40) >= 28;

  return (
    <div className="flex flex-wrap gap-1 mt-0.5">
      {ctx.already_held && (
        <Badge variant="secondary" className="text-xs px-1.5 py-0">Already Held</Badge>
      )}
      {ctx.class_overweight && (
        <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-500 text-amber-600">
          Class ⚠ {ctx.asset_class_weight_pct.toFixed(0)}%
        </Badge>
      )}
      {ctx.sector_overweight && (
        <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-500 text-amber-600">
          Sector ⚠ {ctx.sector_weight_pct.toFixed(0)}%
        </Badge>
      )}
      {ctx.replacing_ticker && (
        <Badge className="text-xs px-1.5 py-0 bg-blue-500 hover:bg-blue-500">
          Replacing: {ctx.replacing_ticker}
        </Badge>
      )}
      <Badge
        variant="outline"
        className={`text-xs px-1.5 py-0 ${income_ok ? "border-emerald-500 text-emerald-600" : "border-amber-500 text-amber-600"}`}
      >
        Income {income_ok ? "✓" : "⚠"}
      </Badge>
      <Badge
        variant="outline"
        className={`text-xs px-1.5 py-0 ${durable_ok ? "border-emerald-500 text-emerald-600" : "border-amber-500 text-amber-600"}`}
      >
        Durable {durable_ok ? "✓" : "⚠"}
      </Badge>
    </div>
  );
}
```

- [ ] **Step 3: Create ResultsTable**

```tsx
// src/frontend/src/components/scanner/results-table.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ShieldAlert } from "lucide-react";
import { ScorePill } from "@/components/score-pill";
import { TickerBadge } from "@/components/ticker-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn, formatPercent } from "@/lib/utils";
import { EntryExitBadge, EntryExitExpandedRow } from "./entry-exit-badge";
import { PortfolioBadges } from "./portfolio-badges";
import type { ScanItem, ScanResult } from "@/lib/types";

interface ResultsTableProps {
  result: ScanResult | null;
  selectedTickers: Set<string>;
  onToggleTicker: (ticker: string) => void;
  loading?: boolean;
}

export function ResultsTable({ result, selectedTickers, onToggleTicker, loading }: ResultsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [showVetoed, setShowVetoed] = useState(false);

  const toggleExpand = (ticker: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
        Scanning…
      </div>
    );
  }

  if (!result) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
        Run a scan to see results.
      </div>
    );
  }

  const passed = result.items.filter((i) => !i.veto_flag);
  const vetoed = result.items.filter((i) => i.veto_flag);

  const renderRow = (item: ScanItem) => {
    const expanded = expandedRows.has(item.ticker);
    const selected = selectedTickers.has(item.ticker);

    return (
      <>
        <tr
          key={item.ticker}
          className={cn("border-b border-border hover:bg-muted/30 transition-colors", selected && "bg-primary/5")}
        >
          <td className="px-3 py-2.5 w-8">
            <Checkbox
              checked={selected}
              onCheckedChange={() => onToggleTicker(item.ticker)}
              disabled={item.veto_flag}
            />
          </td>
          <td className="px-3 py-2.5 text-xs text-muted-foreground tabular-nums">{item.rank || "—"}</td>
          <td className="px-3 py-2.5">
            <div>
              <TickerBadge ticker={item.ticker} />
              {item.portfolio_context && <PortfolioBadges item={item} />}
            </div>
          </td>
          <td className="px-3 py-2.5 text-xs text-muted-foreground">{item.asset_class.replace(/_/g, " ")}</td>
          <td className="px-3 py-2.5">
            <ScorePill score={item.score} grade={item.grade} />
          </td>
          <td className="px-3 py-2.5 text-xs">{item.recommendation.replace(/_/g, " ")}</td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.entry_exit ? (
              <EntryExitBadge entryExit={item.entry_exit} />
            ) : "—"}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums font-medium">
            {item.entry_exit?.current_price != null ? `$${item.entry_exit.current_price.toFixed(2)}` : "—"}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.entry_exit?.exit_limit != null ? `$${item.entry_exit.exit_limit.toFixed(2)}` : "—"}
          </td>
          <td className="px-3 py-2.5 text-xs tabular-nums">
            {item.chowder_number != null ? item.chowder_number.toFixed(1) : "—"}
          </td>
          <td className="px-3 py-2.5">
            {item.veto_flag && <ShieldAlert className="h-4 w-4 text-red-500" />}
          </td>
          <td className="px-3 py-2.5 w-6">
            {item.entry_exit && (
              <button onClick={() => toggleExpand(item.ticker)} className="text-muted-foreground hover:text-foreground">
                {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
            )}
          </td>
        </tr>
        {expanded && item.entry_exit && (
          <tr className="bg-muted/20 border-b border-border">
            <td colSpan={12} className="px-6 py-2">
              <EntryExitExpandedRow entryExit={item.entry_exit} />
            </td>
          </tr>
        )}
      </>
    );
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Stats bar */}
      <div className="px-4 py-2 border-b border-border bg-muted/30 flex gap-4 text-xs text-muted-foreground">
        <span>{result.total_scanned} scanned</span>
        <span className="text-emerald-600 font-medium">{result.total_passed} passed</span>
        <span className="text-red-500">{result.total_vetoed} vetoed</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/20 text-xs text-muted-foreground">
              <th className="px-3 py-2 text-left w-8" />
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Ticker</th>
              <th className="px-3 py-2 text-left">Class</th>
              <th className="px-3 py-2 text-left">Score</th>
              <th className="px-3 py-2 text-left">Rec</th>
              <th className="px-3 py-2 text-left">Entry $</th>
              <th className="px-3 py-2 text-left">Current $</th>
              <th className="px-3 py-2 text-left">Exit $</th>
              <th className="px-3 py-2 text-left">Chowder</th>
              <th className="px-3 py-2 text-left" />
              <th className="px-3 py-2 w-6" />
            </tr>
          </thead>
          <tbody>
            {passed.map(renderRow)}
            {vetoed.length > 0 && (
              <>
                <tr className="border-b border-border bg-muted/10">
                  <td colSpan={12} className="px-4 py-2">
                    <button
                      onClick={() => setShowVetoed(!showVetoed)}
                      className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                    >
                      {showVetoed ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      Show vetoed ({vetoed.length})
                    </button>
                  </td>
                </tr>
                {showVetoed && vetoed.map(renderRow)}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/components/scanner/
git commit -m "feat(scanner-ui): add ResultsTable, EntryExitBadge, PortfolioBadges components"
```

---

## Task 9: LensPicker + ProposalModal

**Files:**

- Create: `src/frontend/src/components/scanner/lens-picker.tsx`
- Create: `src/frontend/src/components/scanner/proposal-modal.tsx`

- [ ] **Step 1: Create LensPicker**

```tsx
// src/frontend/src/components/scanner/lens-picker.tsx
import { cn } from "@/lib/utils";

export type ScannerLens = "gap" | "replacement" | "concentration" | null;

const LENSES: { value: ScannerLens; label: string; description: string }[] = [
  { value: "gap", label: "Gap Finder", description: "New opportunities not in portfolio" },
  { value: "replacement", label: "Replacement", description: "Better alternatives to underperformers" },
  { value: "concentration", label: "Concentration", description: "Picks that improve diversification" },
];

interface LensPickerProps {
  lens: ScannerLens;
  onChange: (lens: ScannerLens) => void;
}

export function LensPicker({ lens, onChange }: LensPickerProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {LENSES.map((l) => (
        <button
          key={l.value}
          onClick={() => onChange(lens === l.value ? null : l.value)}
          title={l.description}
          className={cn(
            "px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
            lens === l.value
              ? "bg-primary text-primary-foreground border-primary"
              : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create ProposalModal**

```tsx
// src/frontend/src/components/scanner/proposal-modal.tsx
"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { ScanItem, ScanResult, PortfolioListItem } from "@/lib/types";

interface ProposalModalProps {
  open: boolean;
  onClose: () => void;
  selectedTickers: Set<string>;
  scanResult: ScanResult | null;
  portfolios: PortfolioListItem[];
  defaultPortfolioId?: string | null;
  onSuccess: (proposalId: string) => void;
}

export function ProposalModal({
  open,
  onClose,
  selectedTickers,
  scanResult,
  portfolios,
  defaultPortfolioId,
  onSuccess,
}: ProposalModalProps) {
  const [targetPortfolioId, setTargetPortfolioId] = useState<string>(defaultPortfolioId ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedItems: ScanItem[] = (scanResult?.items ?? []).filter(
    (i) => selectedTickers.has(i.ticker)
  );

  const handleSubmit = async () => {
    if (!targetPortfolioId || !scanResult) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/scanner/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scan_id: scanResult.scan_id,
          selected_tickers: [...selectedTickers],
          target_portfolio_id: targetPortfolioId,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Failed to create proposal");
      onSuccess(data.proposal_id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Generate Proposal</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Selected tickers summary */}
          <div className="space-y-1">
            <p className="text-sm font-medium">Selected ({selectedItems.length})</p>
            <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1.5 max-h-40 overflow-y-auto">
              {selectedItems.map((item) => (
                <div key={item.ticker} className="flex justify-between text-sm">
                  <span className="font-mono font-medium">{item.ticker}</span>
                  <span className="text-muted-foreground">
                    Entry:{" "}
                    {item.entry_exit?.entry_limit != null
                      ? `$${item.entry_exit.entry_limit.toFixed(2)}`
                      : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Target portfolio */}
          <div className="space-y-2">
            <Label className="text-sm">Target Portfolio <span className="text-red-500">*</span></Label>
            <Select value={targetPortfolioId} onValueChange={setTargetPortfolioId}>
              <SelectTrigger>
                <SelectValue placeholder="Select target portfolio..." />
              </SelectTrigger>
              <SelectContent>
                {portfolios.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={loading || !targetPortfolioId}
          >
            {loading ? "Generating…" : "Generate Proposal →"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/components/scanner/lens-picker.tsx \
        src/frontend/src/components/scanner/proposal-modal.tsx
git commit -m "feat(scanner-ui): add LensPicker and ProposalModal components"
```

---

## Task 10: Assemble New Scanner Page

**Files:**

- Modify: `src/frontend/src/app/scanner/page.tsx` (full replacement)

- [ ] **Step 1: Replace scanner page**

```tsx
// src/frontend/src/app/scanner/page.tsx
"use client";

import { useState, useCallback } from "react";
import { ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InputPanel, type InputMode } from "@/components/scanner/input-panel";
import { FilterPanel, DEFAULT_FILTERS, type ScanFilters } from "@/components/scanner/filter-panel";
import { LensPicker, type ScannerLens } from "@/components/scanner/lens-picker";
import { ResultsTable } from "@/components/scanner/results-table";
import { ProposalModal } from "@/components/scanner/proposal-modal";
import { usePortfolios } from "@/lib/hooks/use-portfolios";
import type { ScanResult } from "@/lib/types";

export default function ScannerPage() {
  // Input mode
  const [mode, setMode] = useState<InputMode>("manual");
  const [manualTickers, setManualTickers] = useState("");
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<ScanFilters>(DEFAULT_FILTERS);

  // Portfolio lens (only active when portfolio mode)
  const [lens, setLens] = useState<ScannerLens>(null);

  // Scan state
  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection + proposal
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(new Set());
  const [proposalOpen, setProposalOpen] = useState(false);

  const { data: portfolios = [] } = usePortfolios();

  const handleToggleTicker = useCallback((ticker: string) => {
    setSelectedTickers((prev) => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      return next;
    });
  }, []);

  const buildPayload = () => {
    const payload: Record<string, unknown> = {
      tickers: [],
      use_universe: mode === "universe",
      min_score: filters.min_score,
      quality_gate_only: filters.quality_gate_only,
      asset_classes: filters.asset_classes.length ? filters.asset_classes : null,
      min_yield: filters.min_yield,
      max_payout_ratio: filters.max_payout_ratio ? Number(filters.max_payout_ratio) : null,
      min_volume: filters.min_volume ? Number(filters.min_volume) : null,
      min_market_cap_m: filters.min_market_cap_m ? Number(filters.min_market_cap_m) : null,
      max_market_cap_m: filters.max_market_cap_m ? Number(filters.max_market_cap_m) : null,
      min_price: filters.min_price ? Number(filters.min_price) : null,
      max_price: filters.max_price ? Number(filters.max_price) : null,
      max_pe: filters.max_pe ? Number(filters.max_pe) : null,
      min_nav_discount_pct: filters.min_nav_discount_pct ? Number(filters.min_nav_discount_pct) : null,
    };

    if (mode === "manual") {
      payload.tickers = manualTickers
        .split(/[\n,]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
    }

    if (mode === "portfolio" && selectedPortfolioId) {
      payload.portfolio_id = selectedPortfolioId;
      if (lens) payload.portfolio_lens = lens;
      // Scan portfolio positions: set use_universe=false, tickers=[]
      // The backend fetches positions when portfolio_id is set
      payload.use_universe = false;
      payload.tickers = [];
    }

    return payload;
  };

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedTickers(new Set());

    try {
      const resp = await fetch("/api/scanner/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Scan failed");
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleProposalSuccess = (proposalId: string) => {
    // TODO: redirect to /proposals when page exists
    alert(`Proposal created: ${proposalId}`);
    setSelectedTickers(new Set());
  };

  return (
    <div className="space-y-4 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScanLine className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">Scanner</h1>
        </div>
        <div className="flex items-center gap-2">
          {selectedTickers.size > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setProposalOpen(true)}
            >
              Generate Proposal → ({selectedTickers.size})
            </Button>
          )}
          <Button onClick={handleScan} disabled={loading} size="sm">
            {loading ? "Scanning…" : "Run Scan"}
          </Button>
        </div>
      </div>

      {/* Input */}
      <InputPanel
        mode={mode}
        onModeChange={setMode}
        manualTickers={manualTickers}
        onManualTickersChange={setManualTickers}
        selectedPortfolioId={selectedPortfolioId}
        onPortfolioChange={setSelectedPortfolioId}
        portfolios={portfolios}
      />

      {/* Filters */}
      <FilterPanel filters={filters} onChange={setFilters} />

      {/* Lens picker — only when portfolio mode active */}
      {mode === "portfolio" && selectedPortfolioId && (
        <LensPicker lens={lens} onChange={setLens} />
      )}

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      <ResultsTable
        result={result}
        selectedTickers={selectedTickers}
        onToggleTicker={handleToggleTicker}
        loading={loading}
      />

      {/* Proposal modal */}
      <ProposalModal
        open={proposalOpen}
        onClose={() => setProposalOpen(false)}
        selectedTickers={selectedTickers}
        scanResult={result}
        portfolios={portfolios}
        defaultPortfolioId={mode === "portfolio" ? selectedPortfolioId : null}
        onSuccess={handleProposalSuccess}
      />
    </div>
  );
}
```

- [ ] **Step 2: Confirm hook and scan route exist**

`src/frontend/src/lib/hooks/use-portfolios.ts` and `src/frontend/src/app/api/scanner/scan/route.ts` both exist in the repo — no creation needed. Verify the hook exports a `portfolios` array:

```bash
grep -n "portfolios" src/frontend/src/lib/hooks/use-portfolios.ts
```

If the export shape differs (e.g. `data` instead of `portfolios`), update the destructure in the `ScannerPage` import accordingly before committing.

- [ ] **Step 3: Build check**

```bash
cd src/frontend
npm run build 2>&1 | tail -30
```

Fix any TypeScript errors before committing.

- [ ] **Step 4: Manual smoke test**

Start the dev server:

```bash
cd src/frontend
npm run dev
```

Open `http://localhost:3000/scanner`. Verify:

- Manual / Portfolio / Universe tabs switch correctly
- Filter panel expands/collapses
- "Run Scan" with a few tickers returns results
- Entry $ / Current $ / Exit $ columns show dollar values
- Row expand shows signal breakdown
- Checkbox selection enables "Generate Proposal →" button
- Proposal modal opens, requires portfolio selection, submits

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/scanner/page.tsx
git commit -m "feat(scanner-ui): replace scanner page with v2 — portfolio lenses, entry/exit prices, proposal handoff"
```

---

## Task 11: Deploy to Production

- [ ] **Step 1: Push branch and deploy backend**

```bash
git push origin main
ssh legato "cd /opt/income-platform && git pull && docker compose restart opportunity-scanner-service"
```

- [ ] **Step 2: Verify backend health**

```bash
curl http://legato:8007/health
```

Expected: `{"status": "healthy", ...}`

- [ ] **Step 3: Deploy frontend**

```bash
ssh legato "cd /opt/income-platform/src/frontend && npm run build && pm2 restart frontend"
```

- [ ] **Step 4: End-to-end smoke test on production**

- Open scanner page in browser
- Run a 5-ticker manual scan
- Confirm entry/exit prices appear
- Run a portfolio scan with Gap Finder lens
- Select 2 results, open proposal modal, select target portfolio, submit
- Verify `proposal_drafts` row exists in DB:

```bash
ssh legato "psql \$DATABASE_URL -c 'SELECT id, status, created_at FROM platform_shared.proposal_drafts ORDER BY created_at DESC LIMIT 3'"
```

- [ ] **Step 5: Final commit**

```bash
git tag v2.1-scanner-v2
git push origin --tags
```
