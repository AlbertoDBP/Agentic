# NAV Erosion Analysis Microservice

Monte Carlo simulation service for analyzing NAV erosion in covered call ETFs and income securities.

## Overview

This microservice provides sophisticated Monte Carlo simulation for predicting NAV erosion patterns in covered call ETFs. It integrates with the Income Fortress Platform's Agent 3 (Scoring) to apply graduated penalties to the Sustainability score based on erosion risk.

### Key Features

- **Realistic Covered Call Modeling**: Accurate option payoff mechanics with upside capping
- **Market Regime Simulation**: Bull/Bear/Sideways/Volatile regime transitions
- **Premium-Volatility Correlation**: Dynamic premium modeling based on market conditions
- **Vectorized Performance**: 10K simulations in ~500ms, 50K in ~2.5s
- **Graduated Penalty System**: 0-30 point sustainability penalties based on erosion probability
- **30-Day Caching**: Efficient result caching with automatic expiration
- **Comprehensive Risk Classification**: 5-tier risk categorization (minimal to severe)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Service (Port 8003)                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Data Collector   │  │ Monte Carlo      │                │
│  │ - Historical data│  │ - 10K/50K sims   │                │
│  │ - Parameter calc │  │ - Regime models  │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Sustainability   │  │ Result Cache     │                │
│  │ - Penalty calc   │  │ - 30-day TTL     │                │
│  │ - Risk classify  │  │ - PostgreSQL     │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis (optional, for distributed caching)
- Docker & Docker Compose (recommended)

### Local Development

```bash
# Clone repository
cd nav-erosion-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
psql -U postgres -d income_platform < migrations/V2.0__nav_erosion_analysis.sql

# Start service
uvicorn service:app --reload --port 8003
```

### Docker Deployment

```bash
# Build image
docker build -t nav-erosion-service .

# Run with docker-compose
docker-compose -f docker-compose.nav-erosion.yml up -d

# Check health
curl http://localhost:8003/health
```

## API Endpoints

### POST /analyze

Run NAV erosion analysis for a single ticker.

**Request:**
```json
{
  "ticker": "JEPI",
  "analysis_type": "quick",
  "years": 3,
  "force_refresh": false
}
```

**Response:**
```json
{
  "ticker": "JEPI",
  "analysis_type": "quick",
  "cached": false,
  "results": {
    "median_annualized_nav_change_pct": -2.5,
    "probability_annual_erosion_gt_5pct": 45.2,
    "probability_annual_erosion_gt_10pct": 12.3,
    "median_annualized_total_return_pct": 6.8,
    ...
  },
  "sustainability_impact": {
    "penalty_points": 12.5,
    "severity": "medium",
    "rationale": "NAV erosion concerns: 45% probability of >5% annual NAV erosion..."
  },
  "risk_classification": {
    "category": "moderate",
    "description": "Moderate NAV erosion risk. Significant erosion possible over time.",
    "flag_for_review": false
  },
  "generated_at": "2026-02-04T10:30:00Z"
}
```

### POST /batch-analyze

Batch analysis for multiple tickers (max 50).

**Request:**
```json
{
  "tickers": ["JEPI", "JEPQ", "QYLD"],
  "analysis_type": "quick",
  "force_refresh": false
}
```

### GET /registry/covered-call-etfs

Get registry of known covered call ETFs.

### GET /ticker/{ticker}/should-analyze

Check if a ticker should have NAV erosion analysis.

### DELETE /cache/{ticker}

Invalidate cached analysis for a ticker.

### GET /health

Health check endpoint.

## Monte Carlo Engine

### Simulation Parameters

- **Quick Analysis**: 10,000 simulations, ~500ms runtime
- **Deep Analysis**: 50,000 simulations, ~2.5s runtime

### Market Regimes

- **Bull**: 1.5x expected return, 0.8x volatility, 0.8x premium
- **Bear**: -2x expected return, 1.5x volatility, 1.4x premium
- **Sideways**: 0x expected return, 0.6x volatility, 0.7x premium
- **Volatile**: 0.5x expected return, 2.0x volatility, 1.8x premium

### Covered Call Mechanics

1. Sell calls at strike = NAV × (1 + moneyness_target)
2. Capture premium income (~0.7% monthly typical)
3. If underlying > strike: NAV capped at strike (upside limited)
4. If underlying < strike: Full downside exposure
5. Distribute 95% of premium + some underlying income
6. Apply expense drag (35 bps annual typical)

## Sustainability Score Integration

### Penalty Tiers

| Probability of >5% Erosion | Penalty | Severity |
|----------------------------|---------|----------|
| < 30% | 0-5 pts | Low |
| 30-50% | 5-10 pts | Medium |
| 50-70% | 10-15 pts | High |
| > 70% | 15-30 pts | Severe |

### Additional Penalties

- **>10% erosion probability > 30%**: +15 pts
- **Median NAV change < -5%**: +10 pts
- **Median NAV change < -2%**: +5 pts

Maximum total penalty: **30 points** (significant but not disqualifying)

## Risk Classification

- **Minimal**: Prob <20%, Median >0% → Green
- **Low**: Prob <40%, Median >-2% → Yellow
- **Moderate**: Prob <60%, Median >-5% → Orange
- **High**: Prob <80%, Median >-10% → Red
- **Severe**: Prob >80% or Median <-10% → Dark Red

Securities classified as High or Severe are flagged for manual review.

## Data Collection

### Required Historical Data

- **12 months minimum** (more is better)
- Monthly premium yields (option premium / NAV)
- Underlying index monthly returns
- Monthly distribution amounts
- Current NAV, price, expense ratio

### Data Quality Scoring

- **90-100**: Excellent (12+ months all data)
- **70-89**: Good (6-11 months)
- **50-69**: Acceptable (3-5 months)
- **< 50**: Poor (insufficient data)

Analysis runs with score ≥50, but results flagged if <70.

## Database Schema

### covered_call_etf_metrics

Stores historical data for analysis.

```sql
CREATE TABLE covered_call_etf_metrics (
    ticker VARCHAR(20),
    data_date DATE,
    nav FLOAT,
    market_price FLOAT,
    monthly_premium_yield FLOAT,
    underlying_return_1m FLOAT,
    monthly_distribution FLOAT,
    expense_ratio FLOAT,
    ...
);
```

### nav_erosion_analysis_cache

Caches simulation results for 30 days.

```sql
CREATE TABLE nav_erosion_analysis_cache (
    ticker VARCHAR(20),
    analysis_type VARCHAR(20),
    simulation_results JSONB,
    median_annualized_nav_change_pct FLOAT,
    probability_erosion_gt_5pct FLOAT,
    sustainability_penalty FLOAT,
    valid_until DATE,
    ...
);
```

## Testing

```bash
# Run all tests
pytest test_nav_erosion.py -v

# Run specific test class
pytest test_nav_erosion.py::TestMonteCarloEngine -v

# Run with coverage
pytest test_nav_erosion.py --cov=. --cov-report=html

# Performance benchmarks
pytest test_nav_erosion.py::TestPerformance -v -s
```

### Test Coverage

- Monte Carlo engine correctness
- Historical validation (JEPI actual data)
- Vectorized vs loop-based equivalence
- Regime transition mechanics
- Upside capping validation
- Sustainability penalty calculations
- Risk classification
- Parameter validation

## Performance Benchmarks

| Operation | Simulations | Runtime | Memory |
|-----------|-------------|---------|--------|
| Quick Analysis | 10,000 | ~500ms | ~200MB |
| Deep Analysis | 50,000 | ~2.5s | ~800MB |
| Batch (10 tickers) | 100,000 | ~5s | ~1.5GB |

All benchmarks on 2-core CPU with vectorized engine.

## Known Covered Call ETFs

- **JEPI**: JPMorgan Equity Premium Income (~9% yield)
- **JEPQ**: JPMorgan NASDAQ Premium Income (~11% yield)
- **QYLD**: Global X NASDAQ 100 Covered Call (~12% yield)
- **XYLD**: Global X S&P 500 Covered Call (~10% yield)
- **RYLD**: Global X Russell 2000 Covered Call (~13% yield)
- **DIVO**: Amplify Enhanced Dividend (~6% yield)
- **SVOL**: Simplify Volatility Premium (~12% yield)

## Integration with Agent 3 (Scoring)

```python
from sustainability_integration import NAVErosionSustainabilityIntegration

# Initialize integration
integration = NAVErosionSustainabilityIntegration(db_connection)

# Check if analysis needed
if integration.should_run_analysis(ticker, asset_class):
    
    # Run analysis (with caching)
    results = run_nav_erosion_analysis(ticker)
    
    # Calculate penalty
    penalty = integration.calculate_sustainability_penalty(results, asset_class)
    
    # Apply to sustainability score
    adjusted_score = base_sustainability_score - penalty['penalty_points']
```

## Monitoring

### Health Checks

```bash
# Service health
curl http://localhost:8003/health

# Docker health check (automatic)
docker ps  # Check health status
```

### Logging

Logs are written to `/app/logs/` in container.

```bash
# View logs
docker logs nav-erosion-service

# Follow logs
docker logs -f nav-erosion-service
```

### Metrics

Prometheus metrics exposed at `/metrics` (if enabled):

- `nav_erosion_analysis_duration_seconds`
- `nav_erosion_cache_hits_total`
- `nav_erosion_cache_misses_total`
- `nav_erosion_simulations_total`

## Troubleshooting

### Service won't start

Check database connectivity:
```bash
psql -U postgres -h localhost -d income_platform
```

### Slow simulations

- Verify NumPy vectorization is working
- Check CPU allocation in docker-compose
- Use Quick analysis (10K sims) for daily batch

### Cache not working

Verify PostgreSQL connection and table exists:
```sql
SELECT COUNT(*) FROM nav_erosion_analysis_cache;
```

### Inaccurate results

- Check data quality score (should be >70)
- Verify historical data completeness
- Validate parameter derivation in logs

## Future Enhancements

- [ ] Scenario analysis (user-defined regimes)
- [ ] Correlation with portfolio holdings
- [ ] Multi-year regime persistence modeling
- [ ] Machine learning for parameter prediction
- [ ] Real-time triggering on market events
- [ ] Integration with options pricing models

## License

Proprietary - Income Fortress Platform

## Support

For issues or questions:
- GitHub Issues: [repo]/issues
- Email: support@incomefortress.com
- Documentation: https://docs.incomefortress.com/nav-erosion
