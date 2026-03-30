# Holding Health Score Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Holding Health Score (HHS) wrapper layer to the income-scoring-service that remaps existing Agent-03 pillar outputs into Income + Durability pillars, adds an UNSAFE flag, introduces an on-demand Income Entry Score (IES), computes NAA Yield per holding, and aggregates into a two-output Portfolio Health panel.

**Architecture:** Wrapper approach — no changes to Agent-03 internals (`income_scorer.py`, `quality_gate.py`, pillar scoring curves). New modules in `app/scoring/` read `ScoreResult` outputs and remap them. New API endpoints added to `app/api/`. A new `HHSWeightProfile` DB table (separate from `ScoringWeightProfile` — see Task 1 rationale) stores class-specific Income/Durability weights. Phase 1: weights loaded from in-code defaults with DB table seeded for Phase 3 DB-backed loader.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, asyncpg, Pydantic v2, pytest. All inside `src/income-scoring-service/`.

---

## File Map

**New files:**
- `src/income-scoring-service/app/scoring/hhs_weights.py` — default HHS weight table + UNSAFE threshold defaults
- `src/income-scoring-service/app/scoring/hhs_wrapper.py` — HHS computation (normalizer + pillar mapping + UNSAFE flag)
- `src/income-scoring-service/app/scoring/ies_calculator.py` — IES prerequisite gate + structure
- `src/income-scoring-service/app/scoring/naa_yield.py` — NAA Yield per holding
- `src/income-scoring-service/app/scoring/portfolio_health.py` — portfolio health aggregation
- `src/income-scoring-service/app/api/hhs.py` — HHS API endpoints
- `src/income-scoring-service/app/api/portfolio_health.py` — Portfolio Health API endpoints
- `src/income-scoring-service/tests/test_hhs_weights.py`
- `src/income-scoring-service/tests/test_hhs_wrapper.py`
- `src/income-scoring-service/tests/test_ies_calculator.py`
- `src/income-scoring-service/tests/test_naa_yield.py`
- `src/income-scoring-service/tests/test_portfolio_health.py`
- `src/income-scoring-service/scripts/seed_hhs_weights.py`

**Modified files:**
- `src/income-scoring-service/app/models.py` — add `HHSWeightProfile` model
- `src/income-scoring-service/app/main.py` — register new routers (line 19 import + include_router calls)
- `src/income-scoring-service/scripts/migrate.py` — add HHS tables migration

---

## Task 1: HHS Weight Profiles — DB Model + Defaults

**Purpose:** Store class-specific Income/Durability pillar weights and UNSAFE threshold.

**Rationale for separate table:** `HHSWeightProfile` is kept separate from `ScoringWeightProfile` to enforce the wrapper contract — Agent-03 internal weights (40/40/20) are never modified. Merging into `ScoringWeightProfile` would couple the HHS layer to Agent-03 internals. Phase 1 reads weights from in-code defaults; `HHSWeightProfile` table is seeded now for the Phase 3 DB-backed loader.

**Files:**
- Create: `src/income-scoring-service/tests/test_hhs_weights.py`
- Create: `src/income-scoring-service/app/scoring/hhs_weights.py`
- Modify: `src/income-scoring-service/app/models.py`
- Modify: `src/income-scoring-service/scripts/migrate.py`
- Create: `src/income-scoring-service/scripts/seed_hhs_weights.py`

- [ ] **Step 1: Write failing tests for HHS weight defaults**

```python
# tests/test_hhs_weights.py
from app.scoring.hhs_weights import HHSWeightDefaults, RiskProfile

ALL_CLASSES = ["DIVIDEND_STOCK", "COVERED_CALL_ETF", "MREIT", "BDC",
               "BOND", "PREFERRED", "REIT"]

def test_all_spec_asset_classes_present():
    """All 7 asset classes from spec §3.4 must have defaults."""
    for ac in ALL_CLASSES:
        weights = HHSWeightDefaults.get(ac, RiskProfile.MODERATE)
        assert weights is not None, f"Missing default for {ac}"

def test_default_weights_sum_to_100():
    for ac in ALL_CLASSES:
        weights = HHSWeightDefaults.get(ac, RiskProfile.MODERATE)
        assert weights.income_weight + weights.durability_weight == 100, \
            f"{ac}: income={weights.income_weight} + durability={weights.durability_weight} != 100"

def test_unsafe_threshold_defaults():
    assert HHSWeightDefaults.unsafe_threshold(RiskProfile.CONSERVATIVE) == 20
    assert HHSWeightDefaults.unsafe_threshold(RiskProfile.MODERATE) == 20
    assert HHSWeightDefaults.unsafe_threshold(RiskProfile.AGGRESSIVE) == 20

def test_unknown_asset_class_falls_back_to_default():
    weights = HHSWeightDefaults.get("UNKNOWN_CLASS", RiskProfile.MODERATE)
    assert weights.income_weight == 40
    assert weights.durability_weight == 60

def test_durability_weight_is_complement_of_income():
    for ac in ALL_CLASSES:
        w = HHSWeightDefaults.get(ac, RiskProfile.MODERATE)
        assert w.durability_weight == 100 - w.income_weight
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/income-scoring-service
pytest tests/test_hhs_weights.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'app.scoring.hhs_weights'`

- [ ] **Step 3: Create `hhs_weights.py`**

```python
# app/scoring/hhs_weights.py
"""
HHS pillar weight defaults and UNSAFE threshold defaults.

Phase 1: weights read from these in-code defaults (DB lookup deferred to Phase 3).
Phase 3: HHSWeightProfile DB table (seeded in scripts/seed_hhs_weights.py) replaces
         these defaults via a DB-backed loader.

Income + Durability weights always sum to 100.
durability_weight is always derived as 100 - income_weight.

unsafe_threshold: Durability score (0–100) at or below which UNSAFE flag fires.
Default: 20. Phase 3 learning loop: ±1 pt/quarter, floor 10, ceiling 35.
"""
from dataclasses import dataclass
from enum import Enum


class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class HHSWeights:
    asset_class: str
    income_weight: int   # 0–100
    unsafe_threshold: int

    @property
    def durability_weight(self) -> int:
        return 100 - self.income_weight


# Spec §3.4 — income_weight per asset class. durability_weight = 100 - income_weight.
_DEFAULTS: dict[str, int] = {
    "DIVIDEND_STOCK":    45,
    "COVERED_CALL_ETF":  40,
    "MREIT":             35,
    "BDC":               35,
    "BOND":              35,
    "PREFERRED":         40,
    "REIT":              40,
}
_DEFAULT_INCOME_WEIGHT = 40  # fallback for unknown classes
_DEFAULT_UNSAFE_THRESHOLD = 20


class HHSWeightDefaults:
    @staticmethod
    def get(asset_class: str, risk_profile: RiskProfile = RiskProfile.MODERATE) -> HHSWeights:
        """Return HHS weight config for an asset class.
        risk_profile reserved for Phase 3 per-profile differentiation.
        """
        income_w = _DEFAULTS.get(asset_class.upper(), _DEFAULT_INCOME_WEIGHT)
        return HHSWeights(
            asset_class=asset_class,
            income_weight=income_w,
            unsafe_threshold=_DEFAULT_UNSAFE_THRESHOLD,
        )

    @staticmethod
    def unsafe_threshold(risk_profile: RiskProfile = RiskProfile.MODERATE) -> int:
        return _DEFAULT_UNSAFE_THRESHOLD
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_hhs_weights.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Add `HHSWeightProfile` model to `models.py`**

Add after the `ScoringWeightProfile` class (~line 262). Note: `{"schema": "platform_shared"}` is required — all tables in this service use this schema. Missing it causes the table to land in `public` schema and be invisible to the rest of the platform.

```python
class HHSWeightProfile(Base):
    """
    HHS pillar weight profiles — Income vs Durability split per asset class.

    Separate from ScoringWeightProfile (which owns Agent-03 40/40/20 weights)
    to preserve the wrapper-only contract. See architecture doc.

    income_weight + durability_weight must always equal 100.
    durability_weight stored for query convenience; always = 100 - income_weight.

    Phase 1: read from hhs_weights.py defaults. Phase 3: DB-backed loader added.
    """
    __tablename__ = "hhs_weight_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class = Column(String(50), nullable=False, index=True)
    risk_profile = Column(String(20), nullable=False, default="moderate")
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    income_weight = Column(SmallInteger, nullable=False)
    durability_weight = Column(SmallInteger, nullable=False)  # = 100 - income_weight
    unsafe_threshold = Column(SmallInteger, nullable=False, default=20)

    source = Column(String(30), nullable=False, default="MANUAL")
    change_reason = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime, nullable=True)
    superseded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_hhs_wp_asset_class", "asset_class", "risk_profile", "is_active"),
        {"schema": "platform_shared"},  # REQUIRED — all tables use platform_shared schema
    )
```

- [ ] **Step 6: Add migration**

In `scripts/migrate.py`, add after the existing migration steps:

```python
# HHS Weight Profiles — always schema-qualified as platform_shared
await conn.execute("""
    CREATE TABLE IF NOT EXISTS platform_shared.hhs_weight_profiles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        asset_class VARCHAR(50) NOT NULL,
        risk_profile VARCHAR(20) NOT NULL DEFAULT 'moderate',
        version INTEGER NOT NULL DEFAULT 1,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        income_weight SMALLINT NOT NULL,
        durability_weight SMALLINT NOT NULL,
        unsafe_threshold SMALLINT NOT NULL DEFAULT 20,
        source VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
        change_reason TEXT,
        created_by VARCHAR(100),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        activated_at TIMESTAMPTZ,
        superseded_at TIMESTAMPTZ
    )
""")
await conn.execute("""
    CREATE INDEX IF NOT EXISTS ix_hhs_wp_asset_class
    ON platform_shared.hhs_weight_profiles (asset_class, risk_profile, is_active)
""")
```

- [ ] **Step 7: Create seed script**

```python
# scripts/seed_hhs_weights.py
"""Seed default HHS weight profiles. Run once after migration."""
import asyncio
import asyncpg
from app.scoring.hhs_weights import _DEFAULTS, _DEFAULT_UNSAFE_THRESHOLD
from app.config import settings

async def seed():
    conn = await asyncpg.connect(settings.database_url)
    for ac, income_w in _DEFAULTS.items():
        for rp in ["conservative", "moderate", "aggressive"]:
            await conn.execute("""
                INSERT INTO platform_shared.hhs_weight_profiles
                    (asset_class, risk_profile, income_weight, durability_weight,
                     unsafe_threshold, source, created_by, activated_at)
                VALUES ($1, $2, $3, $4, $5, 'INITIAL_SEED', 'seed_script', NOW())
                ON CONFLICT DO NOTHING
            """, ac, rp, income_w, 100 - income_w, _DEFAULT_UNSAFE_THRESHOLD)
    await conn.close()
    print("HHS weight profiles seeded.")

if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 8: Commit**

```bash
git add tests/test_hhs_weights.py app/scoring/hhs_weights.py app/models.py \
        scripts/migrate.py scripts/seed_hhs_weights.py
git commit -m "feat: add HHS weight profiles — model, defaults, migration, seed"
```

---

## Task 2: HHS Wrapper — Normalizer + Pillar Computation + UNSAFE Flag

**Purpose:** Core HHS logic. Takes a `ScoreResult` from `IncomeScorer`, remaps Valuation & Yield → Income pillar, Financial Durability → Durability pillar (both re-normalized to 0–100), applies class-specific weights, and sets the UNSAFE flag.

**Files:**
- Create: `src/income-scoring-service/app/scoring/hhs_wrapper.py`
- Create: `src/income-scoring-service/tests/test_hhs_wrapper.py`

**Key normalization rule (spec §3.2):**
- `income_pillar = (score_result.valuation_yield_score / weight_yield) * 100`
- `durability_pillar = (score_result.financial_durability_score / weight_durability) * 100`
- `technical_entry_score` is discarded

**Phase 1 simplification:** Agent-03's Valuation & Yield pillar sub-components (`payout_sustainability`, `yield_vs_market`, `fcf_coverage`) are all yield-quality metrics — none are price valuation (P/E, NAV premium). Price valuation is NOT computed by Agent-03 at all; it lives in IES. Therefore using the full `valuation_yield_score` as the Income pillar proxy is correct for Phase 1 with no data loss. A comment in the code records this.

**CB CAUTION interface:** The `compute()` method accepts `cb_caution_modifier: float = 0.0` (defaulting to 0) to reserve the interface for Phase 3 CB CAUTION integration (−5pt Durability modifier). This is a non-breaking addition now; adding it later would be a breaking change.

**`HHSStatus` enum:** Defined in `hhs_wrapper.py` alongside the wrapper class, consistent with `GateStatus` defined in `quality_gate.py`. API response models use `use_enum_values=True` to serialize as strings.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hhs_wrapper.py
from app.scoring.hhs_wrapper import HHSWrapper, HHSResult, HHSStatus
from app.scoring.hhs_weights import HHSWeights
from app.scoring.income_scorer import ScoreResult
from app.scoring.quality_gate import GateResult, GateStatus


def _score(vy=32.0, fd=30.0, te=15.0, wy=40, wd=40) -> ScoreResult:
    """Build a minimal ScoreResult for testing."""
    r = ScoreResult()
    r.asset_class = "DIVIDEND_STOCK"
    r.ticker = "O"
    r.valuation_yield_score = vy
    r.financial_durability_score = fd
    r.technical_entry_score = te
    r.total_score_raw = vy + fd + te
    r.total_score = vy + fd + te
    r.weight_profile = {"weight_yield": wy, "weight_durability": wd, "weight_technical": 20}
    return r


def _weights(income_w=45, threshold=20) -> HHSWeights:
    return HHSWeights(asset_class="DIVIDEND_STOCK", income_weight=income_w, unsafe_threshold=threshold)


def test_income_pillar_normalized_correctly():
    # 32 / 40 * 100 = 80.0
    result = HHSWrapper().compute(_score(vy=32.0), _weights())
    assert abs(result.income_pillar - 80.0) < 0.01

def test_durability_pillar_normalized_correctly():
    # 30 / 40 * 100 = 75.0
    result = HHSWrapper().compute(_score(fd=30.0), _weights())
    assert abs(result.durability_pillar - 75.0) < 0.01

def test_technical_entry_discarded():
    # Changing technical score must not affect HHS
    r1 = HHSWrapper().compute(_score(te=20.0), _weights())
    r2 = HHSWrapper().compute(_score(te=0.0), _weights())
    assert abs(r1.hhs_score - r2.hhs_score) < 0.01

def test_hhs_composite_uses_pillar_weights():
    # income=80 * 0.45 + durability=75 * 0.55 = 36 + 41.25 = 77.25
    result = HHSWrapper().compute(_score(vy=32.0, fd=30.0), _weights(income_w=45))
    assert abs(result.hhs_score - 77.25) < 0.01

def test_unsafe_flag_at_threshold():
    # 8/40 * 100 = 20.0 <= threshold 20 → UNSAFE
    result = HHSWrapper().compute(_score(fd=8.0), _weights(threshold=20))
    assert result.unsafe is True

def test_unsafe_flag_not_triggered_above_threshold():
    # 9/40 * 100 = 22.5 > threshold 20 → not UNSAFE
    result = HHSWrapper().compute(_score(fd=9.0), _weights(threshold=20))
    assert result.unsafe is False

def test_cb_caution_modifier_reduces_durability():
    # Without modifier: durability = 30/40*100 = 75
    # With −5pt: durability = 70
    w = _weights(threshold=20)
    r_no_mod = HHSWrapper().compute(_score(fd=30.0), w, cb_caution_modifier=0.0)
    r_with_mod = HHSWrapper().compute(_score(fd=30.0), w, cb_caution_modifier=-5.0)
    assert abs(r_no_mod.durability_pillar - 75.0) < 0.01
    assert abs(r_with_mod.durability_pillar - 70.0) < 0.01

def test_gate_fail_status():
    gate = GateResult(status=GateStatus.FAIL, passed=False,
                      fail_reasons=["Dividend history < 10 years"])
    result = HHSWrapper().from_gate_result(gate, asset_class="DIVIDEND_STOCK", ticker="O")
    assert result.status == HHSStatus.QUALITY_GATE_FAIL
    assert result.hhs_score is None
    assert "Dividend history" in result.gate_fail_reasons[0]

def test_insufficient_data_status():
    gate = GateResult(status=GateStatus.INSUFFICIENT_DATA, passed=False, fail_reasons=[])
    result = HHSWrapper().from_gate_result(gate, asset_class="DIVIDEND_STOCK", ticker="O")
    assert result.status == HHSStatus.INSUFFICIENT_DATA
    assert result.hhs_score is None

def test_scored_status_set_on_success():
    result = HHSWrapper().compute(_score(), _weights())
    assert result.status == HHSStatus.SCORED
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/income-scoring-service
pytest tests/test_hhs_wrapper.py -v 2>&1 | head -20
```
Expected: `ImportError` — `hhs_wrapper` does not exist yet

- [ ] **Step 3: Verify `ScoreResult` has required fields**

```bash
grep -n "class ScoreResult\|asset_class\|ticker\|weight_profile" \
    app/scoring/income_scorer.py | head -15
```

If `ticker` or `weight_profile` fields are absent from `ScoreResult`, add them as optional fields with defaults (`ticker: str = ""`, `weight_profile: dict = field(default_factory=dict)`). Do not change any existing fields.

- [ ] **Step 4: Create `hhs_wrapper.py`**

```python
# app/scoring/hhs_wrapper.py
"""
HHS Wrapper — Holding Health Score computation.

Reads ScoreResult from IncomeScorer, remaps to two pillars:
  Income pillar    = valuation_yield_score re-normalized to 0–100
  Durability pillar = financial_durability_score re-normalized to 0–100
  Technical Entry  = DISCARDED

Phase 1 note: Agent-03's Valuation & Yield pillar sub-components
(payout_sustainability, yield_vs_market, fcf_coverage) are all yield-quality
metrics. Price valuation (P/E, NAV premium) is not computed by Agent-03 —
it lives in IES. Using full valuation_yield_score as Income pillar proxy
is correct for Phase 1 with no data loss.

CB CAUTION interface: cb_caution_modifier parameter (default 0.0) reserved
for Phase 3 CB CAUTION −5pt Durability integration.

HHSStatus is defined here alongside HHSWrapper, consistent with the pattern
of GateStatus defined alongside QualityGateEngine in quality_gate.py.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.scoring.hhs_weights import HHSWeights
from app.scoring.income_scorer import ScoreResult
from app.scoring.quality_gate import GateResult, GateStatus


class HHSStatus(str, Enum):
    SCORED = "SCORED"
    QUALITY_GATE_FAIL = "QUALITY_GATE_FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE = "STALE"


@dataclass
class HHSResult:
    ticker: str = ""
    asset_class: str = ""
    status: HHSStatus = HHSStatus.SCORED
    income_pillar: Optional[float] = None
    durability_pillar: Optional[float] = None
    hhs_score: Optional[float] = None
    unsafe: bool = False
    unsafe_threshold_used: int = 20
    income_weight_used: int = 0
    durability_weight_used: int = 0
    gate_fail_reasons: list[str] = field(default_factory=list)


class HHSWrapper:

    def compute(
        self,
        score: ScoreResult,
        hhs_weights: HHSWeights,
        cb_caution_modifier: float = 0.0,
    ) -> HHSResult:
        """
        Map ScoreResult pillars to HHS Income + Durability pillars.

        cb_caution_modifier: applied to durability_pillar after normalization.
        Default 0.0. Phase 3: pass −5.0 when CB CAUTION is active.
        """
        wp = score.weight_profile or {}
        weight_yield = float(wp.get("weight_yield", 40))
        weight_durability = float(wp.get("weight_durability", 40))

        income_pillar = (score.valuation_yield_score / weight_yield * 100) if weight_yield > 0 else 0.0
        durability_pillar = (score.financial_durability_score / weight_durability * 100) if weight_durability > 0 else 0.0

        # Apply CB CAUTION modifier (Phase 3: −5.0 when CAUTION active)
        durability_pillar += cb_caution_modifier

        # Clamp to 0–100
        income_pillar = max(0.0, min(100.0, income_pillar))
        durability_pillar = max(0.0, min(100.0, durability_pillar))

        iw = hhs_weights.income_weight / 100.0
        dw = hhs_weights.durability_weight / 100.0
        hhs_score = round(income_pillar * iw + durability_pillar * dw, 2)

        unsafe = durability_pillar <= hhs_weights.unsafe_threshold

        return HHSResult(
            ticker=getattr(score, "ticker", ""),
            asset_class=score.asset_class,
            status=HHSStatus.SCORED,
            income_pillar=round(income_pillar, 2),
            durability_pillar=round(durability_pillar, 2),
            hhs_score=hhs_score,
            unsafe=unsafe,
            unsafe_threshold_used=hhs_weights.unsafe_threshold,
            income_weight_used=hhs_weights.income_weight,
            durability_weight_used=hhs_weights.durability_weight,
        )

    def from_gate_result(
        self, gate: GateResult, asset_class: str = "", ticker: str = ""
    ) -> HHSResult:
        if gate.status == GateStatus.FAIL:
            status = HHSStatus.QUALITY_GATE_FAIL
        elif gate.status == GateStatus.INSUFFICIENT_DATA:
            status = HHSStatus.INSUFFICIENT_DATA
        else:
            raise ValueError(f"Unexpected gate status: {gate.status}")
        return HHSResult(
            ticker=ticker, asset_class=asset_class, status=status,
            hhs_score=None, unsafe=False, gate_fail_reasons=gate.fail_reasons or [],
        )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_hhs_wrapper.py -v
```
Expected: all 10 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/scoring/hhs_wrapper.py tests/test_hhs_wrapper.py
git commit -m "feat: add HHS wrapper — pillar normalization, UNSAFE flag, CB modifier interface"
```

---

## Task 3: IES Calculator — Prerequisite Gate + Structure

**Purpose:** Income Entry Score gate and formula. Sub-metric computations (P/E, RSI, DMA) depend on Agent-01 market data and are deferred to Phase 3. Gate logic and IES formula are fully implemented.

**Files:**
- Create: `src/income-scoring-service/tests/test_ies_calculator.py`
- Create: `src/income-scoring-service/app/scoring/ies_calculator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ies_calculator.py
from app.scoring.ies_calculator import IESCalculator, IESResult, IESStatus
from app.scoring.hhs_wrapper import HHSResult, HHSStatus


def _hhs(score=75.0, unsafe=False) -> HHSResult:
    return HHSResult(ticker="O", asset_class="REIT", status=HHSStatus.SCORED,
                     hhs_score=score, unsafe=unsafe,
                     income_pillar=80.0, durability_pillar=70.0)


def test_blocked_when_hhs_below_threshold():
    result = IESCalculator().evaluate(_hhs(score=45.0), None, None)
    assert result.status == IESStatus.GATE_BLOCKED
    assert result.reason == "HHS_BELOW_THRESHOLD"
    assert result.ies_score is None
    assert result.action == "NO_ACTION"

def test_blocked_when_unsafe():
    result = IESCalculator().evaluate(_hhs(score=75.0, unsafe=True), None, None)
    assert result.status == IESStatus.GATE_BLOCKED
    assert result.reason == "UNSAFE_FLAG"
    assert result.action == "NO_ACTION"

def test_full_position_at_85_plus():
    # 90*0.60 + 78*0.40 = 54 + 31.2 = 85.2
    result = IESCalculator().evaluate(_hhs(), valuation_score=90.0, technical_score=78.0)
    assert result.status == IESStatus.SCORED
    assert abs(result.ies_score - 85.2) < 0.01
    assert result.action == "FULL_POSITION"

def test_partial_position_at_70_to_84():
    # 80*0.60 + 60*0.40 = 48 + 24 = 72.0
    result = IESCalculator().evaluate(_hhs(), valuation_score=80.0, technical_score=60.0)
    assert abs(result.ies_score - 72.0) < 0.01
    assert result.action == "PARTIAL_POSITION"

def test_wait_below_70():
    # 60*0.60 + 55*0.40 = 36 + 22 = 58.0
    result = IESCalculator().evaluate(_hhs(), valuation_score=60.0, technical_score=55.0)
    assert abs(result.ies_score - 58.0) < 0.01
    assert result.action == "WAIT_OR_DCA"

def test_gate_blocked_response_is_machine_readable():
    result = IESCalculator().evaluate(_hhs(score=30.0), None, None)
    # Must be a structured IESResult, not an exception
    assert isinstance(result, IESResult)
    assert result.ies_score is None
    assert result.hhs_score_at_evaluation == 30.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ies_calculator.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `ies_calculator.py`**

```python
# app/scoring/ies_calculator.py
"""
IES — Income Entry Score. On-demand only.

Formula: IES = (valuation_score × 0.60) + (technical_score × 0.40)
Output: 0–100.

Prerequisite gate: HHS > 50 AND no UNSAFE flag.
Gate-blocked response is machine-readable (consumed by Agent-12 and rebalancer).

Valuation sub-metrics (P/E vs 5yr avg, NAV premium/discount, yield vs benchmark)
and Technical sub-metrics (RSI, 200-DMA, 52wk high %) are computed externally
and passed in as pre-scored 0–100 values.
TODO Phase 3: implement sub-metric scoring using Agent-01 market data.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.scoring.hhs_wrapper import HHSResult, HHSStatus

HHS_GATE_THRESHOLD = 50


class IESStatus(str, Enum):
    SCORED = "SCORED"
    GATE_BLOCKED = "GATE_BLOCKED"


@dataclass
class IESResult:
    ticker: str = ""
    status: IESStatus = IESStatus.SCORED
    reason: Optional[str] = None
    ies_score: Optional[float] = None
    valuation_score: Optional[float] = None
    technical_score: Optional[float] = None
    action: str = "NO_ACTION"
    hhs_score_at_evaluation: Optional[float] = None


class IESCalculator:

    def evaluate(
        self,
        hhs: HHSResult,
        valuation_score: Optional[float],
        technical_score: Optional[float],
    ) -> IESResult:
        if hhs.unsafe:
            return IESResult(ticker=hhs.ticker, status=IESStatus.GATE_BLOCKED,
                             reason="UNSAFE_FLAG", action="NO_ACTION",
                             hhs_score_at_evaluation=hhs.hhs_score)

        if hhs.hhs_score is None or hhs.hhs_score <= HHS_GATE_THRESHOLD:
            return IESResult(ticker=hhs.ticker, status=IESStatus.GATE_BLOCKED,
                             reason="HHS_BELOW_THRESHOLD", action="NO_ACTION",
                             hhs_score_at_evaluation=hhs.hhs_score)

        ies_score = round(
            (valuation_score or 0.0) * 0.60 + (technical_score or 0.0) * 0.40, 2
        )
        return IESResult(
            ticker=hhs.ticker, status=IESStatus.SCORED,
            ies_score=ies_score, valuation_score=valuation_score,
            technical_score=technical_score,
            action=self._action(ies_score),
            hhs_score_at_evaluation=hhs.hhs_score,
        )

    @staticmethod
    def _action(score: float) -> str:
        if score >= 85:
            return "FULL_POSITION"
        elif score >= 70:
            return "PARTIAL_POSITION"
        return "WAIT_OR_DCA"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ies_calculator.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/scoring/ies_calculator.py tests/test_ies_calculator.py
git commit -m "feat: add IES calculator — gate logic, formula, action thresholds"
```

---

## Task 4: NAA Yield Calculator

**Purpose:** Net After-All Yield per holding: `(Gross Div - Fee Drag - Tax Drag) / Total Invested`. Tax data comes from the caller (sourced upstream from Tax Optimization Service). Cost basis and income fields come from the API request payload — they are portfolio accounting data, not market data.

**Files:**
- Create: `src/income-scoring-service/tests/test_naa_yield.py`
- Create: `src/income-scoring-service/app/scoring/naa_yield.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_naa_yield.py
from app.scoring.naa_yield import NAAYieldCalculator, NAAYieldResult, TaxProfile


def test_basic_calculation():
    # (1200 - 50 - 180) / 20000 = 970 / 20000 = 4.85%
    result = NAAYieldCalculator().compute(
        gross_annual_dividends=1200.0, annual_fee_drag=50.0,
        annual_tax_drag=180.0, total_invested=20000.0,
    )
    assert abs(result.naa_yield_pct - 4.85) < 0.01
    assert result.pre_tax_flag is False

def test_zero_fee_and_tax():
    result = NAAYieldCalculator().compute(1000.0, 0.0, 0.0, 10000.0)
    assert abs(result.naa_yield_pct - 10.0) < 0.01

def test_pre_tax_flag_when_tax_unavailable():
    # tax_drag=None → pre_tax_flag=True, no tax applied
    result = NAAYieldCalculator().compute(1000.0, 50.0, None, 10000.0)
    assert result.pre_tax_flag is True
    assert abs(result.naa_yield_pct - 9.5) < 0.01  # (1000-50)/10000

def test_floors_at_zero_if_negative():
    result = NAAYieldCalculator().compute(100.0, 200.0, 50.0, 10000.0)
    assert result.naa_yield_pct == 0.0

def test_tax_drag_estimate_from_profile():
    # qualified 100%, rate 15% → tax = 1000 * 0.15 = 150
    drag = NAAYieldCalculator.estimate_tax_drag(
        1000.0,
        TaxProfile(roc_pct=0.0, qualified_pct=1.0, ordinary_pct=0.0,
                   qualified_rate=0.15, ordinary_rate=0.22),
    )
    assert abs(drag - 150.0) < 0.01

def test_roc_has_zero_tax_drag():
    # 100% ROC → no current tax
    drag = NAAYieldCalculator.estimate_tax_drag(
        1000.0,
        TaxProfile(roc_pct=1.0, qualified_pct=0.0, ordinary_pct=0.0,
                   qualified_rate=0.15, ordinary_rate=0.22),
    )
    assert drag == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_naa_yield.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `naa_yield.py`**

```python
# app/scoring/naa_yield.py
"""
NAA Yield — Net After-All Yield.

Formula: (Gross Dividends - Annual Fee Drag - Annual Tax Drag) / Total Invested

All monetary inputs (gross dividends, fee drag, tax drag, total_invested)
come from the API caller's request payload — portfolio accounting data,
not market data. The caller is responsible for annualizing income_received
and sourcing tax drag from the Tax Optimization Service.

If tax data is unavailable (annual_tax_drag=None):
  - pre_tax_flag = True (shown in UI as "Yield shown pre-tax")
  - tax_drag treated as 0 (optimistic, not pessimistic)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class TaxProfile:
    roc_pct: float        # 0.0–1.0 — Return of Capital (0% current tax)
    qualified_pct: float
    ordinary_pct: float
    qualified_rate: float
    ordinary_rate: float


@dataclass
class NAAYieldResult:
    gross_annual_dividends: float
    annual_fee_drag: float
    annual_tax_drag: float
    net_income: float
    total_invested: float
    naa_yield_pct: float
    pre_tax_flag: bool


class NAAYieldCalculator:

    def compute(
        self,
        gross_annual_dividends: float,
        annual_fee_drag: float,
        annual_tax_drag: Optional[float],
        total_invested: float,
    ) -> NAAYieldResult:
        pre_tax_flag = annual_tax_drag is None
        tax = annual_tax_drag if annual_tax_drag is not None else 0.0
        net = max(0.0, gross_annual_dividends - annual_fee_drag - tax)
        pct = (net / total_invested * 100) if total_invested > 0 else 0.0
        return NAAYieldResult(
            gross_annual_dividends=gross_annual_dividends,
            annual_fee_drag=annual_fee_drag,
            annual_tax_drag=tax,
            net_income=net,
            total_invested=total_invested,
            naa_yield_pct=round(pct, 4),
            pre_tax_flag=pre_tax_flag,
        )

    @staticmethod
    def estimate_tax_drag(gross: float, profile: TaxProfile) -> float:
        """Estimate annual tax drag from income character and bracket rates."""
        return round(
            gross * profile.qualified_pct * profile.qualified_rate
            + gross * profile.ordinary_pct * profile.ordinary_rate,
            4,
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_naa_yield.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/scoring/naa_yield.py tests/test_naa_yield.py
git commit -m "feat: add NAA Yield calculator — net after-all yield with pre-tax fallback"
```

---

## Task 5: Portfolio Health Layer

**Purpose:** Aggregate individual HHS scores into two outputs. Output A: position-weighted aggregate HHS + UNSAFE/CB/gate-fail counts. Output B: independent metrics panel (NAA yield, Total Return, HHI). Total Return and NAA Yield use `original_cost`, `current_value`, and `income_received` from the API request payload — portfolio accounting data provided by the caller.

**Files:**
- Create: `src/income-scoring-service/tests/test_portfolio_health.py`
- Create: `src/income-scoring-service/app/scoring/portfolio_health.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_portfolio_health.py
from app.scoring.portfolio_health import PortfolioHealthCalculator, HoldingInput
from app.scoring.hhs_wrapper import HHSResult, HHSStatus
from app.scoring.naa_yield import NAAYieldResult


def _h(ticker, hhs_score, pos_val, unsafe=False, status=HHSStatus.SCORED,
       naa_pct=5.0, cost=None, current=None, income=0.0, tax=0.0):
    hhs = HHSResult(ticker=ticker, asset_class="REIT", status=status,
                    hhs_score=hhs_score, unsafe=unsafe,
                    income_pillar=70.0, durability_pillar=75.0)
    naa = NAAYieldResult(gross_annual_dividends=pos_val * 0.06, annual_fee_drag=0.0,
                         annual_tax_drag=0.0, net_income=pos_val * naa_pct / 100,
                         total_invested=cost or pos_val, naa_yield_pct=naa_pct,
                         pre_tax_flag=False)
    return HoldingInput(ticker=ticker, hhs=hhs, naa=naa,
                        position_value=pos_val, original_cost=cost or pos_val,
                        current_value=current or pos_val,
                        income_received=income, tax_drag=tax)


def test_aggregate_hhs_is_position_weighted():
    holdings = [_h("O", 80.0, 6000.0), _h("ARCC", 60.0, 4000.0)]
    result = PortfolioHealthCalculator().compute(holdings)
    # (80*6000 + 60*4000) / 10000 = 72.0
    assert abs(result.aggregate_hhs - 72.0) < 0.01

def test_unsafe_surfaced_regardless_of_aggregate():
    holdings = [_h("O", 85.0, 9000.0), _h("ARCC", 18.0, 1000.0, unsafe=True)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert result.unsafe_count == 1
    assert "ARCC" in result.unsafe_tickers

def test_gate_fail_excluded_from_aggregate():
    holdings = [_h("O", 80.0, 8000.0),
                _h("JUNK", None, 2000.0, status=HHSStatus.QUALITY_GATE_FAIL)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert abs(result.aggregate_hhs - 80.0) < 0.01
    assert result.gate_fail_count == 1

def test_insufficient_data_excluded_from_aggregate():
    holdings = [_h("O", 80.0, 8000.0),
                _h("NEW", None, 2000.0, status=HHSStatus.INSUFFICIENT_DATA)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert abs(result.aggregate_hhs - 80.0) < 0.01
    assert result.insufficient_data_count == 1

def test_portfolio_naa_yield_position_weighted():
    holdings = [_h("O", 80.0, 6000.0, naa_pct=5.0),
                _h("ARCC", 70.0, 4000.0, naa_pct=8.0)]
    result = PortfolioHealthCalculator().compute(holdings)
    # (5.0*6000 + 8.0*4000) / 10000 = 6.2%
    assert abs(result.portfolio_naa_yield_pct - 6.2) < 0.01

def test_hhi_flags_concentrated_holding():
    holdings = [_h("O", 80.0, 7000.0), _h("T", 75.0, 2000.0), _h("VZ", 70.0, 1000.0)]
    result = PortfolioHealthCalculator(hhi_flag_threshold=0.10).compute(holdings)
    # O = 70% weight > 10% threshold
    assert "O" in result.concentration_flags

def test_total_return_calculation():
    # (11000 - 10000 + 500 - 0) / 10000 = 15%
    holdings = [_h("O", 80.0, 11000.0, cost=10000.0, current=11000.0, income=500.0)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert abs(result.total_return_pct - 15.0) < 0.01

def test_none_aggregate_when_no_scored_holdings():
    holdings = [_h("JUNK", None, 5000.0, status=HHSStatus.QUALITY_GATE_FAIL)]
    result = PortfolioHealthCalculator().compute(holdings)
    assert result.aggregate_hhs is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_portfolio_health.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `portfolio_health.py`**

```python
# app/scoring/portfolio_health.py
"""
Portfolio Health Layer — two outputs, never collapsed.

Output A: position-weighted aggregate HHS. Gate-failed/stale excluded but counted.
Output B: independent metrics panel — NAA Yield, Total Return, HHI, placeholders.

Total Return and NAA Yield use portfolio accounting data (original_cost,
current_value, income_received, tax_drag) provided by the API caller.
Sharpe/Sortino/VaR: placeholder None — wired in Phase 3 via scenario-simulation-service.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from app.scoring.hhs_wrapper import HHSResult, HHSStatus
from app.scoring.naa_yield import NAAYieldResult


@dataclass
class HoldingInput:
    ticker: str
    hhs: HHSResult
    naa: NAAYieldResult
    position_value: float
    original_cost: float
    current_value: float
    income_received: float
    tax_drag: float


@dataclass
class PortfolioHealthResult:
    # Output A
    aggregate_hhs: Optional[float]
    scored_holding_count: int
    excluded_holding_count: int
    unsafe_count: int
    unsafe_tickers: list[str]
    gate_fail_count: int
    gate_fail_tickers: list[str] = field(default_factory=list)
    insufficient_data_count: int = 0
    stale_count: int = 0
    # Output B
    portfolio_naa_yield_pct: float = 0.0
    portfolio_naa_pre_tax_flag: bool = False
    total_return_pct: float = 0.0
    hhi: float = 0.0
    concentration_flags: list[str] = field(default_factory=list)
    sharpe: Optional[float] = None   # Phase 3
    sortino: Optional[float] = None  # Phase 3
    var_95: Optional[float] = None   # Phase 3


class PortfolioHealthCalculator:

    def __init__(self, hhi_flag_threshold: float = 0.10):
        self.hhi_flag_threshold = hhi_flag_threshold

    def compute(self, holdings: list[HoldingInput]) -> PortfolioHealthResult:
        scored  = [h for h in holdings if h.hhs.status == HHSStatus.SCORED and h.hhs.hhs_score is not None]
        fails   = [h for h in holdings if h.hhs.status == HHSStatus.QUALITY_GATE_FAIL]
        insuf   = [h for h in holdings if h.hhs.status == HHSStatus.INSUFFICIENT_DATA]
        stale   = [h for h in holdings if h.hhs.status == HHSStatus.STALE]
        unsafe  = [h for h in scored if h.hhs.unsafe]

        # Output A — Aggregate HHS
        total_val = sum(h.position_value for h in scored)
        aggregate_hhs = (
            sum(h.hhs.hhs_score * (h.position_value / total_val) for h in scored)
            if total_val > 0 else None
        )

        # Output B — NAA Yield (position-weighted across all holdings)
        all_invested = sum(h.naa.total_invested for h in holdings)
        naa_yield = (
            sum(h.naa.naa_yield_pct * (h.naa.total_invested / all_invested) for h in holdings)
            if all_invested > 0 else 0.0
        )
        pre_tax = any(h.naa.pre_tax_flag for h in holdings)

        # Total Return
        cost    = sum(h.original_cost for h in holdings)
        current = sum(h.current_value for h in holdings)
        income  = sum(h.income_received for h in holdings)
        taxes   = sum(h.tax_drag for h in holdings)
        total_return = ((current - cost + income - taxes) / cost * 100) if cost > 0 else 0.0

        # HHI
        all_val = sum(h.position_value for h in holdings)
        hhi, flags = 0.0, []
        if all_val > 0:
            for h in holdings:
                w = h.position_value / all_val
                hhi += w ** 2
                if w > self.hhi_flag_threshold:
                    flags.append(h.ticker)

        return PortfolioHealthResult(
            aggregate_hhs=round(aggregate_hhs, 2) if aggregate_hhs is not None else None,
            scored_holding_count=len(scored),
            excluded_holding_count=len(fails) + len(insuf) + len(stale),
            unsafe_count=len(unsafe),
            unsafe_tickers=[h.ticker for h in unsafe],
            gate_fail_count=len(fails),
            gate_fail_tickers=[h.ticker for h in fails],
            insufficient_data_count=len(insuf),
            stale_count=len(stale),
            portfolio_naa_yield_pct=round(naa_yield, 4),
            portfolio_naa_pre_tax_flag=pre_tax,
            total_return_pct=round(total_return, 4),
            hhi=round(hhi, 6),
            concentration_flags=flags,
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_portfolio_health.py -v
```
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/scoring/portfolio_health.py tests/test_portfolio_health.py
git commit -m "feat: add Portfolio Health layer — aggregate HHS, NAA yield, total return, HHI"
```

---

## Task 6: HHS API Endpoint

**Purpose:** Expose HHS via HTTP. Follows existing router registration pattern in `main.py`.

**Files:**
- Create: `src/income-scoring-service/app/api/hhs.py`
- Modify: `src/income-scoring-service/app/main.py`

- [ ] **Step 1: Create `app/api/hhs.py`**

`HHSStatus` is a `str` enum — use `model_config = ConfigDict(use_enum_values=True)` in Pydantic response model to serialize as plain string (consistent with how `GateStatus` is serialized in existing responses).

```python
# app/api/hhs.py
"""HHS endpoints — POST /hhs/evaluate"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.scoring.hhs_weights import HHSWeightDefaults, RiskProfile
from app.scoring.hhs_wrapper import HHSWrapper, HHSResult, HHSStatus
from app.scoring.income_scorer import IncomeScorer
from app.scoring.quality_gate import QualityGateEngine, GateStatus
from app.scoring.data_client import MarketDataClient
from app.scoring.weight_profile_loader import weight_profile_loader

logger = logging.getLogger(__name__)
router = APIRouter()
_wrapper = HHSWrapper()
_scorer  = IncomeScorer()
_gate    = QualityGateEngine()
_client  = MarketDataClient()


class HHSRequest(BaseModel):
    ticker: str
    asset_class: Optional[str] = None
    risk_profile: str = "moderate"


class HHSResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    ticker: str
    asset_class: str
    status: str
    hhs_score: Optional[float]
    income_pillar: Optional[float]
    durability_pillar: Optional[float]
    unsafe: bool
    unsafe_threshold_used: int
    income_weight_used: int
    durability_weight_used: int
    gate_fail_reasons: list[str]


@router.post("/hhs/evaluate", response_model=HHSResponse)
async def evaluate_hhs(request: HHSRequest, db: Session = Depends(get_db)):
    ticker = request.ticker.upper()
    risk_profile = RiskProfile(request.risk_profile)

    try:
        data = await _client.fetch(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {e}")

    asset_class = request.asset_class or data.get("asset_class", "DIVIDEND_STOCK")
    gate_result = _gate.evaluate(asset_class=asset_class, data=data)

    if gate_result.status in (GateStatus.FAIL, GateStatus.INSUFFICIENT_DATA):
        hhs = _wrapper.from_gate_result(gate_result, asset_class=asset_class, ticker=ticker)
    else:
        wp = weight_profile_loader.load(asset_class, db)
        score = _scorer.score(data=data, weight_profile=wp)
        score.ticker = ticker
        score.asset_class = asset_class
        hhs_weights = HHSWeightDefaults.get(asset_class, risk_profile)
        hhs = _wrapper.compute(score, hhs_weights)

    return HHSResponse(
        ticker=hhs.ticker, asset_class=hhs.asset_class, status=hhs.status,
        hhs_score=hhs.hhs_score, income_pillar=hhs.income_pillar,
        durability_pillar=hhs.durability_pillar, unsafe=hhs.unsafe,
        unsafe_threshold_used=hhs.unsafe_threshold_used,
        income_weight_used=hhs.income_weight_used,
        durability_weight_used=hhs.durability_weight_used,
        gate_fail_reasons=hhs.gate_fail_reasons,
    )
```

- [ ] **Step 2: Register router in `main.py`**

In `app/main.py`, line 19, the import reads:
```python
from app.api import health, scores, quality_gate, weights, signal_config, learning_loop, classification_accuracy
```

Update it to add `hhs`:
```python
from app.api import health, scores, quality_gate, weights, signal_config, learning_loop, classification_accuracy, hhs
```

After the last `app.include_router(...)` call, add (with auth dependency consistent with all other non-health routers):
```python
app.include_router(hhs.router, prefix="/hhs", tags=["HHS"], dependencies=[Depends(verify_token)])
```

- [ ] **Step 3: Smoke test**

```bash
cd src/income-scoring-service && uvicorn app.main:app --port 8003 &
sleep 2
curl -s -X POST http://localhost:8003/hhs/evaluate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"ticker": "O", "risk_profile": "moderate"}' | python -m json.tool
kill %1
```
Expected: JSON with `hhs_score`, `income_pillar`, `durability_pillar`, `unsafe` fields

- [ ] **Step 4: Commit**

```bash
git add app/api/hhs.py app/main.py
git commit -m "feat: add HHS API endpoint — POST /hhs/evaluate with auth"
```

---

## Task 7: Portfolio Health API Endpoint

**Files:**
- Create: `src/income-scoring-service/app/api/portfolio_health.py`
- Modify: `src/income-scoring-service/app/main.py`

- [ ] **Step 1: Create `app/api/portfolio_health.py`**

Callers provide cost basis, current value, income, fee drag, and tax drag in the request — these are portfolio accounting fields not available from market data.

```python
# app/api/portfolio_health.py
"""Portfolio Health — POST /portfolio/health"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.scoring.hhs_weights import HHSWeightDefaults, RiskProfile
from app.scoring.hhs_wrapper import HHSWrapper, HHSResult, HHSStatus
from app.scoring.naa_yield import NAAYieldCalculator
from app.scoring.portfolio_health import PortfolioHealthCalculator, HoldingInput
from app.scoring.income_scorer import IncomeScorer
from app.scoring.quality_gate import QualityGateEngine, GateStatus
from app.scoring.data_client import MarketDataClient
from app.scoring.weight_profile_loader import weight_profile_loader

logger = logging.getLogger(__name__)
router = APIRouter()
_wrapper  = HHSWrapper()
_scorer   = IncomeScorer()
_gate     = QualityGateEngine()
_client   = MarketDataClient()
_naa_calc = NAAYieldCalculator()


class HoldingRequest(BaseModel):
    ticker: str
    asset_class: Optional[str] = None
    position_value: float
    original_cost: float         # total cost basis — portfolio accounting data
    current_value: float
    income_received: float = 0.0  # annualised dividends received
    annual_fee_drag: float = 0.0
    annual_tax_drag: Optional[float] = None  # None → PRE_TAX flag


class PortfolioHealthRequest(BaseModel):
    holdings: list[HoldingRequest]
    risk_profile: str = "moderate"
    hhi_flag_threshold: Optional[float] = None


class PortfolioHealthResponse(BaseModel):
    aggregate_hhs: Optional[float]
    scored_holding_count: int
    excluded_holding_count: int
    unsafe_count: int
    unsafe_tickers: list[str]
    gate_fail_count: int
    insufficient_data_count: int
    stale_count: int
    portfolio_naa_yield_pct: float
    portfolio_naa_pre_tax_flag: bool
    total_return_pct: float
    hhi: float
    concentration_flags: list[str]
    sharpe: Optional[float]
    sortino: Optional[float]
    var_95: Optional[float]


@router.post("/portfolio/health", response_model=PortfolioHealthResponse)
async def portfolio_health(request: PortfolioHealthRequest, db: Session = Depends(get_db)):
    risk_profile = RiskProfile(request.risk_profile)
    threshold = request.hhi_flag_threshold or 0.10
    inputs: list[HoldingInput] = []

    for h in request.holdings:
        ticker = h.ticker.upper()
        asset_class = h.asset_class or "DIVIDEND_STOCK"
        try:
            data = await _client.fetch(ticker)
            asset_class = h.asset_class or data.get("asset_class", asset_class)
            gate = _gate.evaluate(asset_class=asset_class, data=data)
            if gate.status in (GateStatus.FAIL, GateStatus.INSUFFICIENT_DATA):
                hhs = _wrapper.from_gate_result(gate, asset_class=asset_class, ticker=ticker)
            else:
                wp = weight_profile_loader.load(asset_class, db)
                score = _scorer.score(data=data, weight_profile=wp)
                score.ticker = ticker
                score.asset_class = asset_class
                hhs = _wrapper.compute(score, HHSWeightDefaults.get(asset_class, risk_profile))
        except Exception as e:
            logger.warning("Could not score %s: %s — marking STALE", ticker, e)
            hhs = HHSResult(ticker=ticker, asset_class=asset_class, status=HHSStatus.STALE)

        naa = _naa_calc.compute(
            gross_annual_dividends=h.income_received,
            annual_fee_drag=h.annual_fee_drag,
            annual_tax_drag=h.annual_tax_drag,
            total_invested=h.original_cost,
        )
        inputs.append(HoldingInput(
            ticker=ticker, hhs=hhs, naa=naa,
            position_value=h.position_value, original_cost=h.original_cost,
            current_value=h.current_value, income_received=h.income_received,
            tax_drag=h.annual_tax_drag or 0.0,
        ))

    result = PortfolioHealthCalculator(hhi_flag_threshold=threshold).compute(inputs)
    return PortfolioHealthResponse(
        aggregate_hhs=result.aggregate_hhs,
        scored_holding_count=result.scored_holding_count,
        excluded_holding_count=result.excluded_holding_count,
        unsafe_count=result.unsafe_count,
        unsafe_tickers=result.unsafe_tickers,
        gate_fail_count=result.gate_fail_count,
        insufficient_data_count=result.insufficient_data_count,
        stale_count=result.stale_count,
        portfolio_naa_yield_pct=result.portfolio_naa_yield_pct,
        portfolio_naa_pre_tax_flag=result.portfolio_naa_pre_tax_flag,
        total_return_pct=result.total_return_pct,
        hhi=result.hhi,
        concentration_flags=result.concentration_flags,
        sharpe=result.sharpe, sortino=result.sortino, var_95=result.var_95,
    )
```

- [ ] **Step 2: Register router in `main.py`**

Update the import line (line 19) to add `portfolio_health`:
```python
from app.api import health, scores, quality_gate, weights, signal_config, \
    learning_loop, classification_accuracy, hhs, portfolio_health
```

Add after the HHS router registration:
```python
app.include_router(portfolio_health.router, prefix="/portfolio", tags=["Portfolio Health"],
                   dependencies=[Depends(verify_token)])
```

- [ ] **Step 3: Run full test suite — no regressions**

```bash
cd src/income-scoring-service
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all existing tests (`test_income_scorer`, `test_quality_gate`, `test_nav_erosion`, etc.) PASS. No regressions.

- [ ] **Step 4: Commit**

```bash
git add app/api/portfolio_health.py app/main.py
git commit -m "feat: add Portfolio Health API — two-output panel with auth"
```

---

## Task 8: Spec Alignment Verification

- [ ] **Step 1: Verify spec §3.1 — gate passthrough**

Confirm `from_gate_result()` in `hhs_wrapper.py` handles both FAIL and INSUFFICIENT_DATA distinctly:
```bash
grep -n "QUALITY_GATE_FAIL\|INSUFFICIENT_DATA" app/scoring/hhs_wrapper.py
```
Expected: both statuses appear as distinct HHSStatus values.

- [ ] **Step 2: Verify spec §3.2 — normalization**

Confirm `technical_entry_score` is never referenced in `compute()`:
```bash
grep "technical_entry" app/scoring/hhs_wrapper.py
```
Expected: no output. Technical Entry must not appear in HHS computation.

- [ ] **Step 3: Verify spec §3.6 — UNSAFE threshold**

```bash
pytest tests/test_hhs_wrapper.py::test_unsafe_flag_at_threshold \
       tests/test_hhs_wrapper.py::test_unsafe_flag_not_triggered_above_threshold -v
```
Expected: both PASS.

- [ ] **Step 4: Verify spec §4.1 — IES gate**

```bash
pytest tests/test_ies_calculator.py::test_blocked_when_hhs_below_threshold \
       tests/test_ies_calculator.py::test_blocked_when_unsafe -v
```
Expected: both PASS.

- [ ] **Step 5: Verify spec §6.1 — gate-failed excluded from aggregate**

```bash
pytest tests/test_portfolio_health.py::test_gate_fail_excluded_from_aggregate \
       tests/test_portfolio_health.py::test_insufficient_data_excluded_from_aggregate -v
```
Expected: both PASS.

- [ ] **Step 6: Verify spec §6.2 — HHI formula**

```bash
pytest tests/test_portfolio_health.py::test_hhi_flags_concentrated_holding -v
```
Expected: PASS.

- [ ] **Step 7: Update spec status**

Edit `docs/superpowers/specs/2026-03-24-holding-health-score-framework-design.md`:
Change `**Status:** Draft — Pending User Review` → `**Status:** Implemented — Phase 1`

- [ ] **Step 8: Final commit**

```bash
git add docs/superpowers/specs/2026-03-24-holding-health-score-framework-design.md
git commit -m "docs: mark HHS framework spec as Phase 1 implemented"
```

---

## Known Deferred Items (Phase 3)

1. **IES sub-metric computation** — Valuation (P/E vs 5yr avg, NAV premium/discount) and Technical (RSI, 200-DMA) require Agent-01 market data. Stub in `ies_calculator.py` accepts pre-scored values.
2. **HHS weight DB loader** — Phase 1 reads from `hhs_weights.py` defaults. Phase 3 adds DB-backed loader using the `HHSWeightProfile` table (already seeded).
3. **Learning loop for HHS weights** — quarterly ±1pt/5pt adjustment. Deferred per spec §7.
4. **Sharpe / Sortino / VaR** — Portfolio Health panel placeholders. Require Monte Carlo from scenario-simulation-service.
5. **Circuit Breaker CAUTION −5pt modifier** — interface slot reserved in `hhs_wrapper.compute(cb_caution_modifier=0.0)`. CB CRITICAL/EMERGENCY surfaced via existing alert pathway.
6. **Correlation** — Portfolio Health panel placeholder. Requires benchmark data wiring.
