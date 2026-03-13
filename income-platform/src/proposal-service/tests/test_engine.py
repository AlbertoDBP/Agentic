"""40 tests for proposal engine logic."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.proposal_engine.engine import ProposalError, ProposalResult, run_proposal
from tests.conftest import (
    make_entry_price,
    make_score,
    make_signal,
    make_tax_placement,
)


def run(coro):
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1: Aligned proposal — sentiment and platform agree (8 tests)
# ---------------------------------------------------------------------------

class TestAlignedProposal:
    def _patch_fetch(self, signal=None, score=None, entry=None, tax=None):
        sig = signal or make_signal(sentiment=0.0)
        sc = score or make_score(total_score=50.0, nav_erosion_penalty=5.0)
        en = entry or make_entry_price()
        tx = tax or make_tax_placement()
        return patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        )

    def test_alignment_is_aligned(self):
        # sentiment=0.0, platform_score=50 → divergence=0 → Aligned
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.platform_alignment == "Aligned"

    def test_ticker_uppercased(self):
        with self._patch_fetch():
            result = run(run_proposal("o"))
        assert result.ticker == "O"

    def test_status_is_pending(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.status == "pending"

    def test_analyst_fields_populated(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.analyst_recommendation == "Buy"
        assert result.analyst_safety_grade == "A"
        assert result.analyst_signal_id == 101
        assert result.analyst_id == 5

    def test_platform_score_populated(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.platform_score == 50.0

    def test_entry_price_populated(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.entry_price_low == 52.0
        assert result.entry_price_high == 55.0
        assert result.position_size_pct == 5.0

    def test_recommended_account_populated(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.recommended_account == "Roth IRA"

    def test_trigger_mode_passed(self):
        with self._patch_fetch():
            result = run(run_proposal("O", trigger_mode="signal_driven"))
        assert result.trigger_mode == "signal_driven"


# ---------------------------------------------------------------------------
# Group 2: Vetoed proposal — nav_erosion_penalty > 15 triggers veto (8 tests)
# ---------------------------------------------------------------------------

class TestVetoedProposal:
    def _patch_fetch_veto(self, nav_erosion: float = 20.0):
        sig = make_signal(sentiment=0.8)
        sc = make_score(total_score=75.0, nav_erosion_penalty=nav_erosion)
        en = make_entry_price()
        tx = make_tax_placement()
        return patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        )

    def test_veto_when_nav_erosion_over_15(self):
        with self._patch_fetch_veto(nav_erosion=20.0):
            result = run(run_proposal("O"))
        assert result.platform_alignment == "Vetoed"

    def test_veto_flags_contain_penalty(self):
        with self._patch_fetch_veto(nav_erosion=20.0):
            result = run(run_proposal("O"))
        assert result.veto_flags is not None
        assert "nav_erosion_penalty" in result.veto_flags

    def test_no_veto_when_nav_erosion_at_15(self):
        # exactly 15 — NOT greater than, so no veto
        with self._patch_fetch_veto(nav_erosion=15.0):
            result = run(run_proposal("O"))
        assert result.platform_alignment != "Vetoed"

    def test_veto_when_grade_f(self):
        sig = make_signal(sentiment=0.8)
        sc = make_score(total_score=30.0, grade="F", nav_erosion_penalty=5.0)
        tx = make_tax_placement()
        en = make_entry_price()
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        ):
            result = run(run_proposal("O"))
        assert result.platform_alignment == "Vetoed"
        assert "grade" in result.veto_flags

    def test_veto_divergence_notes_present(self):
        with self._patch_fetch_veto(nav_erosion=20.0):
            result = run(run_proposal("O"))
        assert result.divergence_notes is not None
        assert "VETO" in result.divergence_notes

    def test_veto_status_still_pending(self):
        with self._patch_fetch_veto(nav_erosion=20.0):
            result = run(run_proposal("O"))
        assert result.status == "pending"

    def test_veto_analyst_fields_still_populated(self):
        with self._patch_fetch_veto(nav_erosion=20.0):
            result = run(run_proposal("O"))
        assert result.analyst_recommendation == "Buy"
        assert result.analyst_sentiment == 0.8

    def test_veto_just_above_threshold(self):
        with self._patch_fetch_veto(nav_erosion=15.1):
            result = run(run_proposal("O"))
        assert result.platform_alignment == "Vetoed"


# ---------------------------------------------------------------------------
# Group 3: Divergent proposal — large divergence (6 tests)
# ---------------------------------------------------------------------------

class TestDivergentProposal:
    def _patch_fetch_divergent(self):
        # sentiment=0.9, platform_score=10 → platform_sentiment=-0.8, divergence=1.7 → Divergent
        sig = make_signal(sentiment=0.9)
        sc = make_score(total_score=10.0, nav_erosion_penalty=5.0)
        en = make_entry_price()
        tx = make_tax_placement()
        return patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        )

    def test_alignment_is_divergent(self):
        with self._patch_fetch_divergent():
            result = run(run_proposal("O"))
        assert result.platform_alignment == "Divergent"

    def test_no_veto_flags(self):
        with self._patch_fetch_divergent():
            result = run(run_proposal("O"))
        assert result.veto_flags is None

    def test_divergence_notes_populated(self):
        with self._patch_fetch_divergent():
            result = run(run_proposal("O"))
        assert result.divergence_notes is not None
        assert "Divergent" in result.divergence_notes

    def test_analyst_sentiment_present(self):
        with self._patch_fetch_divergent():
            result = run(run_proposal("O"))
        assert result.analyst_sentiment == 0.9

    def test_platform_score_low(self):
        with self._patch_fetch_divergent():
            result = run(run_proposal("O"))
        assert result.platform_score == 10.0

    def test_both_lenses_in_result(self):
        with self._patch_fetch_divergent():
            result = run(run_proposal("O"))
        assert result.analyst_recommendation is not None
        assert result.platform_income_grade is not None


# ---------------------------------------------------------------------------
# Group 4: Batch tickers — multiple proposals returned (5 tests)
# ---------------------------------------------------------------------------

class TestBatchTickers:
    def _make_fetch_side_effect(self, tickers):
        calls = []
        for ticker in tickers:
            sig = make_signal(ticker=ticker)
            sc = make_score()
            en = make_entry_price()
            tx = make_tax_placement()
            calls.append((sig, sc, en, tx))
        return calls

    def test_two_tickers_two_results(self):
        side_effects = self._make_fetch_side_effect(["O", "MAIN"])
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(side_effect=side_effects),
        ):
            r1 = run(run_proposal("O"))
            r2 = run(run_proposal("MAIN"))
        assert r1.ticker == "O"
        assert r2.ticker == "MAIN"

    def test_each_ticker_has_independent_proposal(self):
        side_effects = self._make_fetch_side_effect(["O", "MAIN"])
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(side_effect=side_effects),
        ):
            r1 = run(run_proposal("O"))
            r2 = run(run_proposal("MAIN"))
        assert r1.ticker != r2.ticker

    def test_batch_respects_trigger_mode(self):
        sig = make_signal()
        sc = make_score()
        en = make_entry_price()
        tx = make_tax_placement()
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        ):
            result = run(run_proposal("O", trigger_mode="signal_driven"))
        assert result.trigger_mode == "signal_driven"

    def test_batch_ticker_uppercased(self):
        sig = make_signal(ticker="MAIN")
        sc = make_score()
        en = make_entry_price()
        tx = make_tax_placement()
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        ):
            result = run(run_proposal("main"))
        assert result.ticker == "MAIN"

    def test_scan_id_sets_trigger_ref(self):
        sig = make_signal()
        sc = make_score()
        en = make_entry_price()
        tx = make_tax_placement()
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        ):
            result = run(run_proposal("O", scan_id="abc-123"))
        assert result.trigger_ref_id == "scan:abc-123"


# ---------------------------------------------------------------------------
# Group 5: Agent 02 failure → ProposalError raised (5 tests)
# ---------------------------------------------------------------------------

class TestAgent02Failure:
    def test_raises_proposal_error_on_agent02_failure(self):
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(side_effect=Exception("Connection refused")),
        ):
            with pytest.raises(ProposalError):
                run(run_proposal("O"))

    def test_proposal_error_message_contains_ticker(self):
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(side_effect=Exception("timeout")),
        ):
            with pytest.raises(ProposalError) as exc_info:
                run(run_proposal("XYZ"))
        assert "XYZ" in str(exc_info.value)

    def test_http_error_raises_proposal_error(self):
        import httpx
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(side_effect=httpx.HTTPError("404")),
        ):
            with pytest.raises(ProposalError):
                run(run_proposal("O"))

    def test_no_partial_result_on_agent02_failure(self):
        with patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(side_effect=Exception("unreachable")),
        ):
            result = None
            try:
                result = run(run_proposal("O"))
            except ProposalError:
                pass
        assert result is None

    def test_proposal_error_is_exception_subclass(self):
        assert issubclass(ProposalError, Exception)


# ---------------------------------------------------------------------------
# Group 6: Entry price fallback when Agent 04 unavailable (4 tests)
# ---------------------------------------------------------------------------

class TestEntryPriceFallback:
    def _patch_no_agent04(self):
        sig = make_signal()
        sc = make_score()
        # Agent 04 returns None
        tx = make_tax_placement()
        return patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, None, tx)),
        )

    def test_market_fallback_flag_set(self):
        with self._patch_no_agent04():
            result = run(run_proposal("O"))
        assert result.entry_method == "market_fallback"

    def test_entry_price_fields_none_on_fallback(self):
        with self._patch_no_agent04():
            result = run(run_proposal("O"))
        assert result.entry_price_low is None
        assert result.entry_price_high is None

    def test_proposal_still_generated_on_agent04_failure(self):
        with self._patch_no_agent04():
            result = run(run_proposal("O"))
        assert result is not None
        assert result.ticker == "O"

    def test_alignment_still_computed_on_agent04_failure(self):
        with self._patch_no_agent04():
            result = run(run_proposal("O"))
        assert result.platform_alignment is not None


# ---------------------------------------------------------------------------
# Group 7: Proposal expiry date = +14 days (4 tests)
# ---------------------------------------------------------------------------

class TestProposalExpiry:
    def _patch_fetch(self):
        sig = make_signal()
        sc = make_score()
        en = make_entry_price()
        tx = make_tax_placement()
        return patch(
            "app.proposal_engine.engine.data_fetcher.fetch_all",
            new=AsyncMock(return_value=(sig, sc, en, tx)),
        )

    def test_expires_at_is_set(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.expires_at is not None

    def test_expires_at_is_14_days_from_now(self):
        from datetime import timedelta
        before = datetime.now(timezone.utc)
        with self._patch_fetch():
            result = run(run_proposal("O"))
        after = datetime.now(timezone.utc)
        delta = result.expires_at - before
        assert 13 <= delta.days <= 14

    def test_expires_at_is_timezone_aware(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert result.expires_at.tzinfo is not None

    def test_expires_at_type_is_datetime(self):
        with self._patch_fetch():
            result = run(run_proposal("O"))
        assert isinstance(result.expires_at, datetime)
