"""Bond pricing via present-value discounting of future cash flows.

Given a bond's coupon rate, maturity date, face value, and a market
yield obtained from the FRED Treasury yield curve, computes a theoretical
clean price (per $100 face value) using standard semi-annual discounting.

Treasury yield source: FRED (Federal Reserve Economic Data) — free, no
API key required. Series used: DGS1, DGS2, DGS3, DGS5, DGS7, DGS10,
DGS20, DGS30.
"""
import logging
from datetime import date, datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# FRED series → term_years for yield-curve interpolation
_FRED_SERIES = [
    ("DGS1",  1),
    ("DGS2",  2),
    ("DGS3",  3),
    ("DGS5",  5),
    ("DGS7",  7),
    ("DGS10", 10),
    ("DGS20", 20),
    ("DGS30", 30),
]

_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_FRED_TIMEOUT = 10.0  # seconds per request

# Add a spread to Treasury yield to approximate corporate bond YTM.
# Investment-grade corporate bonds typically trade 50–200 bps above
# comparable-maturity Treasuries.  150 bps is a reasonable mid-range proxy.
_DEFAULT_SPREAD_BPS = 150  # 1.50% above Treasury curve


class BondPricer:
    """Prices bonds using FRED Treasury yields + a configurable credit spread."""

    async def fetch_yield_curve(self) -> dict[int, float]:
        """Fetch the most recent Treasury yield for each standard maturity.

        Returns dict: {term_years: yield_pct}  e.g. {2: 3.82, 5: 3.97, ...}
        """
        curve: dict[int, float] = {}
        async with httpx.AsyncClient(timeout=_FRED_TIMEOUT) as client:
            for series_id, term in _FRED_SERIES:
                try:
                    resp = await client.get(_FRED_CSV_URL, params={"id": series_id})
                    if resp.status_code != 200:
                        continue
                    lines = [ln for ln in resp.text.strip().splitlines()
                             if ln and not ln.startswith("DATE")]
                    if not lines:
                        continue
                    parts = lines[-1].split(",")
                    if len(parts) >= 2 and parts[1].strip() not in (".", ""):
                        curve[term] = float(parts[1].strip())
                except Exception as exc:
                    logger.warning("FRED fetch failed for %s: %s", series_id, exc)
        return curve

    def interpolate_yield(self, curve: dict[int, float], years_to_maturity: float) -> Optional[float]:
        """Linearly interpolate the yield curve to the given maturity.

        Returns the yield in percent (e.g. 4.25 means 4.25%).
        """
        if not curve:
            return None

        sorted_terms = sorted(curve.keys())

        if years_to_maturity <= sorted_terms[0]:
            return curve[sorted_terms[0]]
        if years_to_maturity >= sorted_terms[-1]:
            return curve[sorted_terms[-1]]

        for i in range(len(sorted_terms) - 1):
            t_lo, t_hi = sorted_terms[i], sorted_terms[i + 1]
            if t_lo <= years_to_maturity <= t_hi:
                y_lo, y_hi = curve[t_lo], curve[t_hi]
                frac = (years_to_maturity - t_lo) / (t_hi - t_lo)
                return y_lo + frac * (y_hi - y_lo)

        return None

    def price_bond(
        self,
        coupon_rate_pct: float,
        maturity: date,
        face: float = 100.0,
        frequency: int = 2,
        ytm_pct: float = 5.0,
        settle: Optional[date] = None,
    ) -> float:
        """Compute the dirty (full) price of a bond.

        Args:
            coupon_rate_pct: Annual coupon rate as a percentage (e.g. 2.625).
            maturity:        Maturity date.
            face:            Face value (default 100).
            frequency:       Coupon payments per year (default 2 = semi-annual).
            ytm_pct:         Yield to maturity as a percentage (e.g. 4.5).
            settle:          Settlement date (default: today).

        Returns:
            Price per $100 face value.
        """
        settle = settle or date.today()
        ytm = ytm_pct / 100.0
        coupon_annual = face * (coupon_rate_pct / 100.0)
        coupon_per_period = coupon_annual / frequency
        r = ytm / frequency  # per-period discount rate

        # Build coupon dates stepping back from maturity in period increments
        from dateutil.relativedelta import relativedelta
        months_per_period = 12 // frequency
        coupon_dates: list[date] = []
        d = maturity
        while d > settle:
            coupon_dates.append(d)
            d -= relativedelta(months=months_per_period)
        coupon_dates.reverse()

        if not coupon_dates:
            return face

        # Fractional period to first coupon (for accrued interest)
        first_coupon = coupon_dates[0]
        prev_coupon = first_coupon - relativedelta(months=months_per_period)
        days_to_next = (first_coupon - settle).days
        days_in_period = (first_coupon - prev_coupon).days
        t_first = days_to_next / days_in_period

        pv = 0.0
        for i, cpn_date in enumerate(coupon_dates):
            t = t_first + i
            cash_flow = coupon_per_period
            if cpn_date == maturity:
                cash_flow += face
            pv += cash_flow / (1 + r) ** t

        return round(pv * (100.0 / face), 4)

    async def get_price(
        self,
        coupon_rate_pct: float,
        maturity_str: str,
        face: float = 100.0,
        frequency: int = 2,
        spread_bps: int = _DEFAULT_SPREAD_BPS,
    ) -> Optional[float]:
        """Fetch Treasury yields and return theoretical bond price per $100 face.

        Returns price per $100 face, or None on failure.
        """
        try:
            maturity = datetime.strptime(maturity_str, "%Y-%m-%d").date()
            today = date.today()
            years_to_maturity = (maturity - today).days / 365.25

            if years_to_maturity <= 0:
                logger.warning("Bond matured: %s", maturity_str)
                return face

            curve = await self.fetch_yield_curve()
            if not curve:
                logger.warning("Could not fetch Treasury yield curve from FRED")
                return None

            treasury_yield = self.interpolate_yield(curve, years_to_maturity)
            if treasury_yield is None:
                return None

            ytm = treasury_yield + (spread_bps / 100.0)
            logger.info(
                "Bond pricing: coupon=%.3f%% maturity=%s ytm=%.3f%% "
                "(treasury=%.3f%% + spread=%dbps)",
                coupon_rate_pct, maturity_str, ytm, treasury_yield, spread_bps,
            )

            return self.price_bond(
                coupon_rate_pct=coupon_rate_pct,
                maturity=maturity,
                face=face,
                frequency=frequency,
                ytm_pct=ytm,
            )

        except Exception as exc:
            logger.warning("BondPricer.get_price failed: %s", exc)
            return None
