# Functional Specification: Feature Store V2

**Component:** Feature Store V2  
**Version:** 2.0.0  
**Status:** ✅ Complete  
**Last Updated:** February 2, 2026

---

## Purpose & Scope

The Feature Store V2 is responsible for extracting, transforming, and caching all features needed for asset scoring.

**What it does:**
- Extracts comprehensive features for all asset types
- Calculates NAV erosion data (3-year + 1-year history)
- Retrieves tax breakdown (ROC/qualified/ordinary)
- Computes coverage and leverage metrics
- Provides price history and technical indicators
- Caches features for performance (1-hour TTL)

**What it doesn't do:**
- Make scoring decisions (that's Income Scorer's job)
- Store features long-term (uses Redis cache only)
- Clean or validate data (returns raw features)

---

## Responsibilities

### Core Responsibilities
1. **Feature Extraction** - Pull data from yfinance and other sources
2. **NAV History Tracking** - 3-year price history with distributions
3. **Tax Breakdown Mapping** - ROC percentage from manual mapping or API
4. **Benchmark Data** - Retrieve comparison index data (SPY, QQQ, IWM)
5. **Technical Indicators** - Calculate SMA, RSI, volatility
6. **Caching** - Store features in Redis (1-hour TTL)

### Asset-Specific Extraction
- **Dividend Stocks:** Dividend history, FCF, aristocrat status
- **REITs/BDCs:** Coverage ratio, leverage, NAV per share
- **mREITs:** 12-month NAV change for penalty calculation
- **Covered Call ETFs:** NAV erosion components, tax breakdown, upside capture

---

## Interfaces

### Input Interface

**Primary Method:**
```python
def get_features(symbol: str, asset_type: AssetType) -> Dict[str, Any]
```

**Parameters:**
- `symbol` (str, required) - Ticker symbol
- `asset_type` (AssetType, required) - Asset classification for appropriate feature extraction

**Returns:** Dictionary with features or empty dict on error

**Example Usage:**
```python
from agents.feature_store_v2 import feature_store_v2
from agents.income_scorer_v6_final import AssetType

# Get features for BDC
features = feature_store_v2.get_features("ARCC", AssetType.BDC)

# Access specific features
coverage = features.get('distribution_coverage_ratio', 1.0)
yield_pct = features.get('dividend_yield', 0)
```

### Output Interface

**Returns:** Dictionary with the following structure:

**Basic Features (All Assets):**
```python
{
    'current_price': float,
    'previous_close': float,
    '52_week_high': float,
    '52_week_low': float,
    'volume': int,
    'avg_volume': int,
    'market_cap': float,
    'dividend_yield': float,  # As percentage (9.5 = 9.5%)
    'dividend_rate': float,
    'payout_ratio': float,
    'pe_ratio': float,
    'forward_pe': float,
    'pb_ratio': float,
    'debt_to_equity': float,
    'profit_margin': float,
    'roe': float,
    'beta': float
}
```

**Covered Call ETF Features:**
```python
{
    # NAV Erosion Components
    'nav_3y_start': float,
    'nav_current': float,
    'nav_1y_start': float,
    'period_days': int,
    'cumulative_distributions_3y': float,
    'cumulative_distributions_1y': float,
    'benchmark_nav_3y_start': float,
    'benchmark_nav_current': float,
    'benchmark_nav_1y_start': float,
    
    # Tax Breakdown
    'roc_percentage': float,  # 0.92 = 92%
    'qualified_dividend_pct': float,
    'ordinary_income_pct': float,
    'section_1256_treatment': bool,
    
    # Performance
    'total_return_1y': float,
    'underlying_index_return_1y': float,
    'distribution_yield': float,
    'expense_ratio': float,
    'aum_millions': float,
    
    # Track Record
    'inception_date': str,  # ISO format
    'fund_age_years': float,
    'distribution_consistency_score': int  # 0-100
}
```

**Coverage Asset Features (REIT/BDC/mREIT):**
```python
{
    'distribution_coverage_ratio': float,  # 1.25 = 125% coverage
    'debt_to_assets': float,  # For REITs
    'nav_per_share': float,
    'price_to_nav': float,
    'nav_change_12m': float  # -0.08 = -8% decline
}
```

**Dividend Stock Features:**
```python
{
    'dividend_growth_5y': float,  # Annualized growth rate
    'dividend_history_years': float,
    'dividend_cuts_10y': int,  # Count of dividend cuts
    'fcf': float,  # Free cash flow
    'fcf_payout_ratio': float
}
```

**Technical Indicators (All Assets):**
```python
{
    'sma_50': float,
    'sma_200': float,
    'rsi_14': float,  # 0-100
    'volatility_annualized': float,
    'support_52w': float,
    'resistance_52w': float
}
```

---

## Feature Extraction Methods

### 1. Basic Features Extraction

**Source:** yfinance `ticker.info`

```python
def _extract_basic_features(ticker, info: Dict) -> Dict:
    # Price metrics
    current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
    
    # Dividend metrics
    dividend_yield = info.get('dividendYield', 0) * 100
    
    # Valuation metrics
    pe_ratio = info.get('trailingPE', 0)
    
    # Financial health
    debt_to_equity = info.get('debtToEquity', 0) / 100
    
    return features
```

**Error Handling:**
- Missing fields return 0 or None
- Percentage fields normalized (0.095 → 9.5%)
- All numeric conversions wrapped in try/except

---

### 2. NAV Erosion Extraction (Covered Call ETFs)

**Components Needed:**
1. NAV at start (3 years ago)
2. NAV at current
3. Cumulative distributions over period
4. Benchmark NAV start/current

**Calculation:**
```python
end_date = datetime.now()
start_date_3y = end_date - timedelta(days=3*365 + 30)

# Get price history (Adj Close ≈ NAV for ETFs)
history_3y = ticker.history(start=start_date_3y, end=end_date)
nav_3y_start = history_3y['Close'].iloc[0]
nav_current = history_3y['Close'].iloc[-1]

# Cumulative distributions
dividends = ticker.dividends
cum_dist_3y = dividends.loc[start_date_3y:end_date].sum()

# Benchmark data
benchmark_symbol = BENCHMARK_MAP.get(symbol, 'SPY')
benchmark = yf.Ticker(benchmark_symbol)
benchmark_history = benchmark.history(start=start_date_3y, end=end_date)
```

**Fallback Strategy:**
- If 3-year data unavailable → use 1-year
- If 1-year unavailable → return None for NAV erosion features
- Benchmark defaults to SPY if mapping not found

---

### 3. Tax Breakdown Retrieval

**Primary Source:** Manual mapping in `KNOWN_TAX_BREAKDOWNS` dict

```python
KNOWN_TAX_BREAKDOWNS = {
    'SPYI': {
        'roc_percentage': 0.92,
        'qualified_dividend_pct': 0.05,
        'ordinary_income_pct': 0.03,
        'section_1256_treatment': True
    },
    # ... more ETFs
}
```

**Fallback for Unknown ETFs:**
```python
# Default: Conservative estimate for stocks
{
    'roc_percentage': 0.0,
    'qualified_dividend_pct': 0.75,
    'ordinary_income_pct': 0.25,
    'section_1256_treatment': False
}
```

**Update Process:**
- Quarterly review of ETF 19a-1 notices
- Update `KNOWN_TAX_BREAKDOWNS` with actual percentages
- Document update in CHANGELOG

---

### 4. Coverage Metrics Extraction (REITs/BDCs)

**Approximation from yfinance:**
```python
# Distribution coverage ratio
# Ideally: NII / Distributions or FFO / Distributions
# Available: Use payout_ratio as proxy
coverage_ratio = info.get('payoutRatio', 1.0)

# For REITs: debt-to-assets
total_assets = info.get('totalAssets', 0)
total_debt = info.get('totalDebt', 0)
debt_to_assets = total_debt / total_assets if total_assets > 0 else 0

# NAV per share
nav_per_share = info.get('bookValue', 0)
price_to_nav = current_price / nav_per_share if nav_per_share > 0 else 1.0
```

**Limitations:**
- yfinance doesn't provide NII or FFO directly
- Payout ratio used as proxy (inverse of coverage)
- For precise coverage, would need SEC filings or specialized APIs

---

### 5. Technical Indicators Calculation

**Moving Averages:**
```python
history = ticker.history(period='1y')

# 50-day SMA
sma_50 = history['Close'].tail(50).mean()

# 200-day SMA
sma_200 = history['Close'].tail(200).mean()
```

**RSI (14-day):**
```python
def _calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1]
```

**Volatility (Annualized):**
```python
returns = history['Close'].pct_change().dropna()
volatility = returns.std() * np.sqrt(252)
```

---

## Caching Strategy

### Cache Keys
```python
cache_key = f"features_v2:{symbol}"
```

### Cache Structure
```python
self.cache[cache_key] = (features, cached_at)
```

### Cache TTL
- **Default:** 1 hour (3600 seconds)
- **Rationale:** Market data doesn't change frequently enough to warrant shorter TTL
- **Invalidation:** Automatic expiration after 1 hour

### Cache Hit/Miss Logic
```python
if cache_key in self.cache:
    cached_features, cached_at = self.cache[cache_key]
    if (datetime.now() - cached_at).seconds < self.cache_ttl:
        return cached_features  # Cache hit
# Cache miss - extract fresh features
```

---

## Dependencies

### External APIs
- **yfinance 0.2.35** - Market data (primary source)
- **No other APIs** in Phase 1

### Future Data Sources
- Financial Modeling Prep - More accurate coverage ratios
- Alpha Vantage - Enhanced historical data
- Polygon.io - Real-time data
- SEC EDGAR - Scrape 19a-1 notices for tax breakdowns

---

## Non-Functional Requirements

### Performance
- **Latency:** <1 second for cached features
- **Latency:** <3 seconds for fresh extraction
- **Cache Hit Rate:** >80% for frequently-scored symbols
- **Success Rate:** >99% (feature extraction succeeds)

### Reliability
- **Error Handling:** Return empty dict on failure (don't crash scorer)
- **Fallback Data:** Use 1-year if 3-year unavailable
- **Retry Logic:** None (accept transient failures gracefully)
- **Timeout:** 10 seconds max per yfinance request

### Data Quality
- **NAV Proxy Error:** <0.5% (Adj Close vs actual NAV)
- **Missing Fields:** Return 0 or None (documented behavior)
- **Stale Data:** Maximum 1 hour staleness (cache TTL)

---

## Error Handling

### Common Errors

**Error 1: Symbol Not Found**
```python
try:
    ticker = yf.Ticker(symbol)
    info = ticker.info
except Exception as e:
    logger.error(f"Symbol {symbol} not found: {e}")
    return {}
```

**Error 2: Insufficient History**
```python
if len(history_3y) < 20:
    logger.warning(f"Insufficient 3y history for {symbol}, trying 1y")
    history_1y = ticker.history(period='1y')
    if len(history_1y) < 20:
        logger.error(f"Insufficient history for {symbol}")
        return {}  # NAV erosion features will be missing
```

**Error 3: Missing Dividends**
```python
dividends = ticker.dividends
if dividends.empty:
    logger.warning(f"No dividend history for {symbol}")
    cumulative_distributions = 0  # Asset may not pay dividends
```

---

## Success Criteria

### Functional Success
1. ✅ Extracts all required features for each asset type
2. ✅ NAV erosion calculation matches reference formula
3. ✅ Tax breakdown returns correct values for mapped ETFs
4. ✅ Cache hit rate >80% for frequently-scored symbols
5. ✅ Returns empty dict (not crash) on errors

### Performance Success
1. ✅ Cache hit response <1 second
2. ✅ Fresh extraction <3 seconds (95th percentile)
3. ✅ Feature extraction success rate >99%

### Data Quality Success
1. ✅ NAV proxy error <0.5% vs actual NAV
2. ✅ Tax breakdown accuracy 100% for mapped ETFs
3. ✅ Coverage ratio within 5% of actual (where verifiable)

---

## Integration Points

### Upstream Consumers
- **Income Scorer V6** - Primary consumer
- **Portfolio Analyzer** - Uses features for analysis
- **Backtesting Engine** - Historical features

### Downstream Dependencies
- **yfinance** - Market data provider
- **Redis** - Cache storage (future enhancement)

### Event Triggers
- **Cache Miss** - Log for monitoring cache hit rate
- **Extraction Failure** - Alert if failure rate >1%

---

## Examples

### Example 1: Basic Feature Extraction

**Input:**
```python
features = feature_store_v2.get_features("JNJ", AssetType.DIVIDEND_STOCK)
```

**Output:**
```python
{
    'current_price': 160.50,
    'dividend_yield': 3.1,
    'dividend_rate': 4.76,
    'payout_ratio': 0.50,
    'pe_ratio': 24.5,
    'debt_to_equity': 0.45,
    'roe': 0.25,
    'dividend_growth_5y': 0.06,
    'dividend_history_years': 30.5,
    'dividend_cuts_10y': 0,
    'sma_50': 158.20,
    'sma_200': 155.80,
    'rsi_14': 65.3
}
```

---

### Example 2: Covered Call ETF with NAV Erosion

**Input:**
```python
features = feature_store_v2.get_features("SPYI", AssetType.COVERED_CALL_ETF)
```

**Output:**
```python
{
    # Basic
    'current_price': 52.30,
    'dividend_yield': 11.8,
    
    # NAV Erosion
    'nav_3y_start': 50.00,
    'nav_current': 52.30,
    'period_days': 1095,
    'cumulative_distributions_3y': 18.50,
    'benchmark_nav_3y_start': 380.00,
    'benchmark_nav_current': 485.00,
    
    # Tax
    'roc_percentage': 0.92,
    'qualified_dividend_pct': 0.05,
    'ordinary_income_pct': 0.03,
    'section_1256_treatment': True,
    
    # Performance
    'total_return_1y': 0.15,
    'underlying_index_return_1y': 0.22,
    'distribution_yield': 11.8,
    'expense_ratio': 0.0068,
    'aum_millions': 1250.0,
    
    # Track Record
    'inception_date': '2022-01-15',
    'fund_age_years': 2.05,
    'distribution_consistency_score': 95
}
```

---

### Example 3: BDC with Coverage Metrics

**Input:**
```python
features = feature_store_v2.get_features("ARCC", AssetType.BDC)
```

**Output:**
```python
{
    # Basic
    'current_price': 20.15,
    'dividend_yield': 9.5,
    
    # Coverage
    'distribution_coverage_ratio': 1.25,
    'debt_to_equity': 1.05,
    'nav_per_share': 16.80,
    'price_to_nav': 1.20,
    'nav_change_12m': -0.03,
    
    # Technical
    'sma_50': 19.80,
    'sma_200': 19.50,
    'rsi_14': 58.2,
    'volatility_annualized': 0.18
}
```

---

## Limitations & Known Issues

### Limitation 1: NAV Proxy Error
- **Issue:** Uses Adj Close as NAV proxy for ETFs
- **Impact:** ~0.5% error margin
- **Mitigation:** Acceptable for income-focused analysis
- **Future:** Use actual NAV from ETF provider APIs

### Limitation 2: Manual Tax Breakdown
- **Issue:** Tax breakdown requires manual updates
- **Impact:** Limited to ~20 mapped ETFs
- **Mitigation:** Quarterly update process documented
- **Future:** Automate 19a-1 notice scraping

### Limitation 3: Coverage Ratio Approximation
- **Issue:** yfinance doesn't provide NII or FFO
- **Impact:** Uses payout ratio as proxy (inverse)
- **Mitigation:** Good enough for screening
- **Future:** Integrate Financial Modeling Prep API

### Limitation 4: No Real-Time Data
- **Issue:** yfinance data delayed 15+ minutes
- **Impact:** Scores may use slightly stale prices
- **Mitigation:** Not critical for long-term income investing
- **Future:** Integrate real-time data provider

---

## Maintenance

### Quarterly Tasks
- [ ] Update `KNOWN_TAX_BREAKDOWNS` with latest 19a-1 data
- [ ] Review cache hit rates and adjust TTL if needed
- [ ] Verify NAV proxy accuracy on sample ETFs
- [ ] Check yfinance API stability

### As-Needed Tasks
- [ ] Add new ETFs to tax breakdown mapping
- [ ] Adjust benchmark mappings for new ETFs
- [ ] Update sector thresholds based on market changes

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-02-02 | Enhanced extraction with NAV erosion, tax breakdown |
| 1.0.0 | - | Initial version (deprecated) |

---

## Related Documents

- [Income Scorer V6](income-scorer-v6.md) - Primary consumer
- [Implementation Spec](../implementation/feature-store-v2-impl.md)
- [Testing Spec](../testing/feature-store-v2-tests.md)

---

**Document Owner:** Alberto DBP  
**Last Reviewed:** February 2, 2026  
**Next Review:** May 1, 2026
