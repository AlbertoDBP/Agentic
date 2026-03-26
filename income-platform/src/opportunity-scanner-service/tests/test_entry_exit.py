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
            price=44.0 * 1.03,
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
            price=44.0 * 1.05,
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
            week_52_high=62.0,
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
            sma_200=44.0,
            resistance_level=60.0,
            week_52_high=62.0,
            dividend_yield=8.0,
            nav_value=50.0,
        )
        # technical=46.0, yield~43.48, nav=47.5 → entry_limit~43.48
        assert result.entry_limit == pytest.approx(43.478, rel=1e-3)
        assert result.zone_status == ZoneStatus.ABOVE_ENTRY

    def test_fully_populated_bdc_exit_chooses_lowest_signal(self):
        """BDC exit: technical~58.9, yield~58.82, nav=52.5 → exit=52.5."""
        result = compute_entry_exit(
            asset_class="BDC",
            price=50.0,
            support_level=44.0,
            sma_200=None,
            resistance_level=62.0,
            week_52_high=62.0,
            dividend_yield=8.0,
            nav_value=50.0,
        )
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
        """RSI is not an input — signals dict should not contain it."""
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
