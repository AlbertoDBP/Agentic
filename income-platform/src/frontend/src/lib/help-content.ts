// Contextual help text for Portfolio pages
// Used by HelpTooltip component throughout the UI

// ── Holdings tab columns ────────────────────────────────────────────────────
export const HOLDINGS_HELP: Record<string, string> = {
  symbol:
    "Ticker symbol. Click to open the position detail view with full scoring breakdown.",
  name: "Full company or fund name.",
  asset_type:
    "Asset class: CEF (Closed-End Fund), BDC (Business Development Company), REIT, ETF, Preferred Stock, Bond, or Common Stock.",
  shares: "Number of shares currently held.",
  cost_basis:
    "Total amount invested in this position (shares × average cost per share).",
  current_value: "Current market value of the position (shares × market price).",
  gain_loss:
    "Unrealized profit or loss vs. your cost basis. Does not include dividends received.",
  annual_income:
    "Projected annual dividend income from this position based on the current dividend rate × shares held.",
  yield_on_cost:
    "Yield on Cost (YoC): annual income ÷ your cost basis. Unlike current yield, this measures the return on what you actually paid. A 4% yielding stock bought 10 years ago that has doubled its dividend now pays ~8% YoC — a powerful indicator of long-term compounding. High YoC positions are rarely worth selling.",
  weight:
    "Position size as a % of total portfolio value. Values above 5% are flagged — concentration risk can amplify losses if a single holding cuts its dividend.",
  score:
    "Income Score (0–100): composite rating across three categories — Valuation & Yield (40 pts, yield attractiveness + Chowder Number + payout ratio), Financial Durability (40 pts, leverage + dividend streak + FCF), and Technical Entry (20 pts, RSI + moving averages + support proximity). This is the original per-ticker score; for portfolio-health tracking see HHS.",
  alert_count:
    "Number of active monitoring alerts. Alerts fire when yield spikes, coverage drops, or other risk thresholds are breached.",
  sector: "GICS sector classification (e.g. Financial Services, Real Estate).",
  industry: "Specific industry within the sector.",
  dividend_frequency:
    "How often dividends are paid: Monthly, Quarterly, Semi-Annual, or Annual. Monthly payers improve cash flow predictability.",
  current_yield:
    "Current yield = annualized dividend ÷ today's market price. A yield significantly above this ticker's own 5-year average can mean two things: the price has fallen (potential opportunity) or the market is pricing in a dividend cut (yield trap). Context matters — always cross-check payout ratio and FCF coverage.",
  market_price: "Latest market price per share.",
  avg_cost:
    "Your average cost per share across all purchase lots (cost basis ÷ shares).",
  ex_div_date:
    "Ex-dividend date. You must own shares before this date to receive the next scheduled dividend payment.",
  pay_date:
    "Payment date. The date dividends are deposited to your brokerage account.",
  dividend_growth_5y:
    "5-year annualized dividend growth rate (CAGR). Positive growth compounds your yield on cost over time.",
  payout_ratio:
    "Dividends as a % of earnings (or for REITs/BDCs, of distributable income). Above 100% means the company is paying out more than it earns — a sustainability red flag.",
  beta:
    "Price volatility relative to the S&P 500. Beta = 1.0 moves in lockstep with the market; < 1.0 is less volatile; > 1.0 amplifies market swings.",
  chowder_number:
    "Chowder Number = Current Yield + 5Y Dividend Growth. Rule of thumb: ≥ 12 for regular stocks; ≥ 8 for high-yield positions (yield > 3%). A higher number suggests strong total return potential.",
  net_annual_income:
    "Annual dividend income after deducting estimated expense ratio (fee drag) and tax withholding. More realistic than gross income for after-tax planning.",
  dca_stage:
    "Dollar-Cost Averaging stage. Stage 1 = initial position. Higher stages track subsequent accumulation tranches at different price levels.",
  currency: "Currency of the security.",
  date_added: "Date this position was first added to the portfolio.",
};

// ── Health tab columns ───────────────────────────────────────────────────────
export const HEALTH_HELP: Record<string, string> = {
  score: HOLDINGS_HELP.score,
  alert_count: HOLDINGS_HELP.alert_count,
  gain_pct:
    "Total price return as a % of cost basis. Does not include dividends received.",
  yield_on_cost: HOLDINGS_HELP.yield_on_cost,
  annual_income: HOLDINGS_HELP.annual_income,
  weight: HOLDINGS_HELP.weight,
  sector: HOLDINGS_HELP.sector,
  dividend_frequency: HOLDINGS_HELP.dividend_frequency,
};

// ── Market tab columns ───────────────────────────────────────────────────────
export const MARKET_HELP: Record<string, string> = {
  price: "Latest market price per share.",
  change:
    "Today's price change in dollars and % vs. yesterday's closing price.",
  volume: "Number of shares traded today.",
  day_range: "Intraday trading range: today's low and high price.",
  week52_range:
    "52-week price range with a bar showing where today's price sits in that range.",
  market_cap:
    "Total market capitalization (price × shares outstanding). Millions or billions.",
  pe_ratio:
    "Price-to-Earnings ratio. Lower generally means cheaper relative to earnings — but context matters by sector.",
  eps: "Earnings Per Share. Net income divided by shares outstanding.",
  dividend_yield: HOLDINGS_HELP.current_yield,
  payout_ratio: HOLDINGS_HELP.payout_ratio,
  dividend_growth_5y: HOLDINGS_HELP.dividend_growth_5y,
  nav_pd:
    "NAV (Net Asset Value) per share and the current premium (+) or discount (−) to NAV. Closed-end funds trading at a discount may represent value; deep discounts can signal structural issues.",
  beta: HOLDINGS_HELP.beta,
  avg_volume: "30-day average daily trading volume. Useful for assessing liquidity.",
  ex_date: HOLDINGS_HELP.ex_div_date,
};

// ── Score component explanations (detail page) ───────────────────────────────
export const SCORE_COMPONENT_HELP: Record<string, string> = {
  "Valuation & Yield":
    "Up to 40 points. Rewards attractive current yield, yield above the stock's own 5-year average (potential undervaluation), a strong Chowder Number, and a sustainable payout ratio.",
  "Financial Durability":
    "Up to 40 points. Rewards consecutive years of dividend growth, recent dividend CAGR, low leverage (Net Debt/EBITDA), strong interest coverage, high free cash flow yield, and a solid credit rating.",
  "Technical Entry":
    "Up to 20 points. Rewards buying at a technically favorable entry point: RSI in neutral/oversold territory, price above key moving averages, and proximity to technical support.",
};

// ── Factor-level explanations (Why This Score table) ────────────────────────
export const FACTOR_HELP: Record<string, string> = {
  dividend_yield:
    "Current dividend yield. Scored relative to comparable income securities — higher yield earns more points up to a cap that filters out unsustainable 'yield traps'.",
  yield_vs_5yr_avg:
    "Current yield vs. this stock's own 5-year average yield. Trading above the historical average may indicate undervaluation or elevated risk — the score rewards moderate above-average yield.",
  chowder_number:
    "Yield + 5Y Dividend Growth CAGR. Rule of thumb ≥ 12 for dividend growth stocks, ≥ 8 for high-yield (> 3%). Higher values suggest both income and total return potential.",
  payout_ratio:
    "Dividends as % of earnings or distributable income. Below 60% earns full points; 60–80% earns partial; above 100% penalizes — the company is paying more than it earns.",
  consecutive_yrs:
    "Consecutive years of uninterrupted dividend growth. Dividend Champions (25+ yrs) and Aristocrats earn maximum points. Cuts or freezes reset the counter.",
  div_cagr_3yr:
    "3-year dividend CAGR. Measures recent dividend momentum — a company growing its dividend 8–10%+ annually compounds yield on cost significantly.",
  interest_coverage:
    "EBIT ÷ Interest Expense. How many times the company can cover its debt interest payments from operating earnings. ≥ 3× is healthy; < 1.5× is a red flag.",
  net_debt_ebitda:
    "Net Debt ÷ EBITDA. Leverage ratio. < 2× is conservative; > 4× raises sustainability concerns for most sectors (utilities and REITs have higher norms).",
  fcf_yield:
    "Free Cash Flow ÷ Market Cap. Measures cash generation relative to price. Higher FCF yield means the business has more cash to sustain and grow dividends.",
  credit_rating:
    "Moody's/S&P credit rating. Investment grade (BBB− and above) earns full points. High yield (junk) ratings receive partial or no credit.",
  rsi:
    "RSI (14-day Relative Strength Index). 30–70 = neutral zone; < 30 = oversold (potential buy signal); > 70 = overbought (avoid chasing momentum). Oversold earns more points.",
  sma_signal:
    "Price vs. 50-day and 200-day Simple Moving Averages. Bullish: price above both SMAs. Bearish: 'death cross' (50-day < 200-day). Positive signal earns technical entry points.",
  price_vs_support:
    "Proximity of current price to the nearest technical support level. Buying close to support improves the risk/reward profile and earns additional entry points.",
  debt_safety:
    "Composite debt safety score combining interest coverage, Net Debt/EBITDA, and credit rating. Rewards low leverage and strong debt service capacity.",
  fcf_coverage:
    "Free cash flow coverage of dividends. FCF ÷ total dividend payout. > 1.5× means dividends are well-covered by actual cash generation, not just reported earnings.",
  price_momentum:
    "Short-term price momentum score. Combines recent price vs. moving averages to assess trend direction at time of scoring.",
};

// ── Penalty explanations ─────────────────────────────────────────────────────
export const PENALTY_HELP: Record<string, string> = {
  nav_erosion:
    "Penalty applied to CEFs and closed-end structures where historical NAV has eroded. Chronic NAV decline means distributions are partially return-of-capital, not true income.",
  signal_penalty:
    "Penalty applied when multiple technical indicators (RSI overbought, death cross, price below support) align bearishly, suggesting a poor entry timing.",
};

// ── HHS / IES v3.0 explanations ───────────────────────────────────────────────
export const HHS_HELP: Record<string, string> = {
  hhs_score:
    "Holding Health Score (0–100): weighted blend of two pillars — Income (yield quality + payout sustainability) and Durability (debt safety + dividend consistency). Think of it as the overall fitness score for an income holding. Scores ≥ 85 are STRONG; ≥ 70 GOOD; ≥ 50 WATCH; < 50 CONCERN. Holdings pending their quality gate evaluation show —.",
  income_pillar:
    "Income Pillar (0–100): measures how attractive and sustainable the income stream is. Factors: current yield vs. market, payout ratio, FCF coverage of dividends. A high Income score means the yield is compelling and the company has cash to back it up.",
  durability_pillar:
    "Durability Pillar (0–100): measures financial resilience and dividend track record. Factors: debt levels (Net Debt/EBITDA), interest coverage, dividend growth streak, and price volatility. Values ≤ 20 trigger the UNSAFE flag — the holding is at risk of a dividend cut regardless of its yield.",
  unsafe_flag:
    "UNSAFE: the Durability pillar has fallen to or below the safety floor (default: 20). This overrides a high HHS — the income stream is at elevated risk. Immediate review recommended. Common triggers: leverage spike, dividend freeze, or credit downgrade.",
  hhs_status:
    "HHS status bands: STRONG ≥ 85 (high conviction, hold) · GOOD ≥ 70 (solid, monitor) · WATCH ≥ 50 (acceptable, increased attention) · CONCERN < 50 (weak fundamentals, consider action) · UNSAFE = Durability ≤ threshold (structural risk regardless of score).",
  ies_score:
    "Income Entry Score (0–100): only calculated when HHS > 50 and no UNSAFE flag — it answers 'is now a good time to add?' Valuation component (60%): yield vs. 5-yr avg, Chowder Number, payout ratio. Technical component (40%): RSI, price vs. SMAs, proximity to support.",
  ies_blocked:
    "IES blocked — entry timing could not be evaluated. UNSAFE_FLAG: durability is critical, adding more would increase risk. HHS_BELOW_THRESHOLD: fundamentals are too weak to assess entry. INSUFFICIENT_DATA: the quality gate lacked enough data to evaluate this holding.",
  quality_gate:
    "Quality Gate: a pre-scoring check that verifies minimum data and fundamental criteria are met before assigning a score. PASS = all required criteria met and score is reliable. INSUFFICIENT_DATA = gate ran but key data was missing; score is provisional and may change on rescore.",
  agg_hhs:
    "Aggregate HHS: the position-size-weighted average HHS across all scored holdings. Gate-failed and stale holdings (not rescored within the configured window) are excluded. A useful single-number summary of portfolio health — flag if it drops below 65.",
  naa_yield:
    "Net After-All Yield: (Annual Dividend − Expense Ratio Drag − Estimated Tax Withholding) ÷ Total Invested. More realistic than the raw yield for after-tax income planning. Holdings missing tax data are shown pre-tax and marked with *.",
  hhi:
    "Herfindahl-Hirschman Index: sum of squared position weights (0–1). A perfectly equal 10-position portfolio = 0.10. Values > 0.10 indicate moderate concentration; > 0.25 is high concentration. Flagged in amber above the threshold — one bad holding could materially impact income.",
  chowder_number:
    "Chowder Number = Current Yield + 5-Year Dividend Growth CAGR. Rule of thumb: ≥ 12 for regular dividend stocks; ≥ 8 for high-yield positions (yield > 3%). A strong Chowder Number suggests both current income and compounding potential. Informational — not used in HHS scoring.",
};
