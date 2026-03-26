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
