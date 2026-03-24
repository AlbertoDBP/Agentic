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
    "Yield on Cost (YoC): annual income ÷ cost basis. Measures the return on your original investment price — grows over time as dividends increase.",
  weight:
    "Position size as a % of total portfolio value. Values above 5% are flagged — concentration risk can amplify losses if a single holding cuts its dividend.",
  score:
    "Income Score (0–100). Composite rating across three categories: Valuation & Yield (40 pts), Financial Durability (40 pts), and Technical Entry (20 pts). Higher is better.",
  alert_count:
    "Number of active monitoring alerts. Alerts fire when yield spikes, coverage drops, or other risk thresholds are breached.",
  sector: "GICS sector classification (e.g. Financial Services, Real Estate).",
  industry: "Specific industry within the sector.",
  dividend_frequency:
    "How often dividends are paid: Monthly, Quarterly, Semi-Annual, or Annual. Monthly payers improve cash flow predictability.",
  current_yield:
    "Current dividend yield based on today's market price. A yield significantly above the 5-year average may indicate undervaluation — or a dividend at risk.",
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
