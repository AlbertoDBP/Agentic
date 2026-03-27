// Page-sensitive help content — displayed in the slide-out help panel
// Organized by page key and (for multi-tab pages) tab key.

export interface HelpSection {
  title: string;
  body: string;
}

export interface PageHelpContent {
  pageTitle: string;
  subtitle: string;
  sections: HelpSection[];
}

// ── Portfolio page — per-tab ─────────────────────────────────────────────────

export const PORTFOLIO_TAB_HELP: Record<string, PageHelpContent> = {
  portfolio: {
    pageTitle: "Holdings Tab",
    subtitle: "Your active positions with income metrics and health scores.",
    sections: [
      {
        title: "What you're seeing",
        body: "Each row is one active position. The table shows market value, projected annual income, current yield, and the Holding Health Score (HHS). Click any row to open a detailed breakdown panel on the right.",
      },
      {
        title: "Holding Health Score (HHS)",
        body: "HHS (0–100) is a composite of two pillars:\n• Income Pillar — yield quality and payout sustainability\n• Durability Pillar — leverage, dividend track record, and financial resilience\n\nStatus bands: STRONG ≥ 85 · GOOD ≥ 70 · WATCH ≥ 50 · CONCERN < 50. An UNSAFE flag overrides any score — it means the Durability pillar has fallen below the safety floor and the dividend is at elevated risk.",
      },
      {
        title: "Yield on Cost vs. Current Yield",
        body: "Current Yield = dividend ÷ today's price. It changes daily with the market.\n\nYield on Cost (YoC) = dividend ÷ what you paid. This grows over time as dividends increase. A high YoC position (e.g., 8–12%) is delivering strong returns on your original capital regardless of where the stock trades today.",
      },
      {
        title: "Annual Income",
        body: "Projected annual dividend income = current dividend rate × shares held. This is gross income before fees or taxes. For the after-tax estimate, switch to the Net After-All Yield (NAA) in the KPI strip above.",
      },
      {
        title: "Position weight & concentration",
        body: "Weight = this position's value ÷ total portfolio value. Positions above 5% are flagged. The HHI in the KPI strip measures overall concentration — values above 0.10 indicate moderate concentration risk. A single large position cutting its dividend can materially impact total income.",
      },
    ],
  },

  health: {
    pageTitle: "Health Tab",
    subtitle: "HHS scoring breakdown — understand why each holding scores the way it does.",
    sections: [
      {
        title: "What you're seeing",
        body: "The Health tab surfaces the HHS scoring breakdown for every position. Columns show the two sub-pillars (Income and Durability), the Income Entry Score (IES, when available), quality gate status, and factor-level details. Click a row to expand the full factor breakdown.",
      },
      {
        title: "Income Pillar (INC)",
        body: "Measures yield attractiveness and payout sustainability. Factors: current yield vs. sector benchmarks, payout ratio as % of earnings or distributable income, and FCF coverage of dividends. A high Income pillar means the yield is well-supported by actual cash flow.",
      },
      {
        title: "Durability Pillar (DUR)",
        body: "Measures financial resilience and dividend safety. Factors: debt levels (Net Debt/EBITDA), interest coverage ratio, consecutive years of dividend growth, recent 3-year dividend CAGR, and price volatility. Values ≤ 20 trigger the UNSAFE flag — act regardless of overall HHS.",
      },
      {
        title: "Income Entry Score (IES)",
        body: "IES (0–100) answers: 'Is now a good time to add or initiate this position?' It only calculates when HHS > 50 and no UNSAFE flag is present.\n\nValuation component (60%): yield vs. 5-year own average, Chowder Number, payout ratio.\nTechnical component (40%): RSI, price vs. 50/200-day SMAs, proximity to technical support.\n\nA high IES does not override a low HHS — health must come first.",
      },
      {
        title: "Quality Gate",
        body: "Before a score is assigned, the Quality Gate verifies minimum criteria are met:\n• PASS — all required data present, score is reliable\n• INSUFFICIENT_DATA — gate ran but key data was missing; score is provisional\n• FAIL — minimum criteria not met (e.g., fewer than 3 years of dividend history for a REIT)\n\nGate-failed holdings show '—' for HHS and are excluded from the Aggregate HHS.",
      },
      {
        title: "Factor breakdown (detail panel)",
        body: "Clicking a row opens the factor breakdown: each sub-score shows the raw value, the points awarded, and a brief note. Green factors are contributing positively; amber and red are dragging the score down. This is where you identify what needs to improve for a holding to move from WATCH to GOOD.",
      },
    ],
  },

  market: {
    pageTitle: "Market Tab",
    subtitle: "Live market data and technical indicators for your holdings.",
    sections: [
      {
        title: "What you're seeing",
        body: "Real-time and end-of-day market data for each position: price, day change, volume, 52-week range, market cap, and dividend metrics. Data is sourced from FMP (Financial Modeling Prep) and refreshed on each manual refresh or the nightly scheduled run.",
      },
      {
        title: "52-Week Range bar",
        body: "The progress bar shows where today's price sits within the 52-week trading range. Far left = near 52-week low (potential opportunity or falling knife). Far right = near 52-week high (potentially overbought or strong momentum). Useful for quick entry timing context.",
      },
      {
        title: "NAV / Premium-Discount (CEFs)",
        body: "For Closed-End Funds, this column shows NAV per share and the current premium (+) or discount (−) to NAV. CEFs at a discount may represent value — you're buying $1.00 of assets for less than $1.00. Deep or persistent discounts can also signal structural issues or poor management.",
      },
      {
        title: "Payout Ratio",
        body: "Dividends ÷ earnings (or distributable income for REITs/BDCs/CEFs). Above 100% means the company is paying out more than it earns from operations. Sustained above-100% payout ratios are the single strongest predictor of dividend cuts — monitor closely.",
      },
    ],
  },

  simulation: {
    pageTitle: "Income Simulation",
    subtitle: "Model how your income stream changes under different scenarios.",
    sections: [
      {
        title: "What this does",
        body: "The simulation lets you adjust holding-level assumptions (yield, growth rate, reinvestment) and see the aggregate impact on annual income. Use it to answer 'what if' questions: what if this CEF cuts its distribution by 20%? What if I add $10k to this BDC?",
      },
      {
        title: "Dividend growth assumptions",
        body: "Each position's growth rate defaults to its historical 5-year CAGR. Override it to model a more conservative or optimistic view. Growth compounds: a 5% annual increase on $5,000 of income adds ~$250/yr, reaching $8,100 in 10 years.",
      },
      {
        title: "DRIP (Dividend Reinvestment)",
        body: "When DRIP is enabled for a position, dividends are reinvested into additional shares at the current price. This compounds both income and position size over time. The simulation shows cumulative income with and without DRIP so you can compare the compounding effect.",
      },
    ],
  },

  projection: {
    pageTitle: "Income Projection",
    subtitle: "Long-horizon view of projected income growth from current holdings.",
    sections: [
      {
        title: "What you're seeing",
        body: "The projection builds a year-by-year income forecast using current dividends, your dividend growth rate assumptions, and optional DRIP reinvestment. The chart shows income bands (conservative / base / optimistic) and the cumulative total.",
      },
      {
        title: "Growth rate scenarios",
        body: "Conservative: uses half the historical CAGR (accounts for slowdowns or cuts). Base: uses the historical 5-year CAGR. Optimistic: uses the actual recent 3-year CAGR (periods of acceleration). The band between conservative and optimistic shows the realistic range of outcomes.",
      },
      {
        title: "Inflation-adjusted view",
        body: "Toggle 'Real' to see income in today's purchasing power. Using 2.5–3% inflation, $10,000 of income in year 10 is worth ~$7,800 in today's dollars. The real view helps evaluate whether your income is actually growing or just keeping up with inflation.",
      },
    ],
  },
};

// ── Scanner page ─────────────────────────────────────────────────────────────

export const SCANNER_PAGE_HELP: PageHelpContent = {
  pageTitle: "Income Scanner",
  subtitle: "Score and rank income securities against quality and attractiveness criteria.",
  sections: [
    {
      title: "How scoring works",
      body: "Each ticker is evaluated across two dimensions:\n\n1. Quality Gate — verifies minimum criteria: dividend track record, asset classification, and data completeness. Gate must PASS before a score is assigned.\n\n2. Income Score (0–100) — composite of: Valuation & Yield (40 pts), Financial Durability (40 pts), and Technical Entry (20 pts).\n\nGrade bands: A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D ≥ 50 · F < 50.",
    },
    {
      title: "Input modes",
      body: "Manual: type in tickers you want to evaluate (comma-separated).\n\nPortfolio: scan all active positions in one of your portfolios — useful for a regular health check.\n\nUniverse: scan the pre-configured income universe (curated list of high-quality income securities across CEFs, BDCs, REITs, preferred stocks, and dividend growers).",
    },
    {
      title: "Lens: analysis focus",
      body: "Lenses adjust which factors are weighted more heavily in the ranking:\n\n• Income: weights yield and payout sustainability higher\n• Entry: weights technical signals and IES (entry timing) higher\n• Durability: weights leverage, dividend streak, and coverage higher\n• Balanced: equal weighting across all factors (default)\n\nThe same ticker can rank very differently under different lenses.",
    },
    {
      title: "Filters",
      body: "Filters narrow the result set before scoring:\n• Min Yield: minimum dividend yield\n• Max Payout Ratio: screens out unsustainable payers\n• Quality Gate Only: shows only gate-passing tickers\n• Asset Class: filter to specific security types (CEF, BDC, REIT, etc.)\n• Min Score: only show results above a score threshold\n\nFilters apply after scoring, so a filtered-out ticker may still appear with a low score if the gate is the limiting factor.",
    },
    {
      title: "Adding to a portfolio",
      body: "Check the boxes next to tickers you like, then click 'Add to Portfolio'. This creates a Proposal — a pending action to add the position. Proposals appear in the Proposals page for review before execution. No trades are placed automatically.",
    },
  ],
};

// ── Dashboard ────────────────────────────────────────────────────────────────

export const DASHBOARD_PAGE_HELP: PageHelpContent = {
  pageTitle: "Dashboard",
  subtitle: "Portfolio-level overview across all your income accounts.",
  sections: [
    {
      title: "What you're seeing",
      body: "The dashboard shows all your portfolios as cards. Each card displays the key health and income metrics for that account. Use it to spot portfolios that need attention (low HHS, UNSAFE flags) at a glance.",
    },
    {
      title: "Aggregate HHS",
      body: "Each card shows the portfolio's Aggregate HHS — a position-weighted average of all holding HHS scores. Think of it as a single-number portfolio health grade. Flag if it drops below 65. Click into a portfolio to see which holdings are dragging it down.",
    },
    {
      title: "NAA Yield",
      body: "Net After-All Yield: after fee drag and estimated tax withholding. This is the most realistic representation of what you actually receive. The difference between gross yield and NAA yield can be 1–3% depending on the account type and holding mix.",
    },
    {
      title: "Unsafe count",
      body: "The red UNSAFE badge on a portfolio card counts how many holdings have a Durability pillar at or below the safety floor. Even one UNSAFE position warrants a review — it means the dividend is structurally at risk.",
    },
  ],
};

// ── Vulnerability page ───────────────────────────────────────────────────────

export const VULNERABILITY_PAGE_HELP: PageHelpContent = {
  pageTitle: "Vulnerability Analysis",
  subtitle: "Identify income holdings most at risk of a dividend cut or deterioration.",
  sections: [
    {
      title: "What you're seeing",
      body: "Vulnerability surfaces holdings that show early warning signs: rising payout ratios, declining FCF, deteriorating credit, low or falling Durability pillar scores. It is a forward-looking risk view, not a real-time alert.",
    },
    {
      title: "Risk factors",
      body: "Each holding is evaluated against a set of vulnerability indicators:\n• Payout ratio > 90% (near-unsustainable)\n• FCF coverage < 1.0× (paying dividends from debt or reserves)\n• Durability pillar < 30 (structurally weak)\n• Dividend freeze or cut in the last 12 months\n• Debt/EBITDA > 5× (over-leveraged)\n\nA holding can be flagged by one or several factors simultaneously.",
    },
    {
      title: "Priority ranking",
      body: "Holdings are ranked by vulnerability score — more flags and more severe flags score higher (worse). UNSAFE holdings always appear at the top. Use this ranked list to prioritize your review and decide whether to reduce, hold, or exit.",
    },
  ],
};

// ── Stress Test page ─────────────────────────────────────────────────────────

export const STRESS_TEST_PAGE_HELP: PageHelpContent = {
  pageTitle: "Stress Test",
  subtitle: "Simulate the income impact of dividend cuts, rate shocks, or market dislocations.",
  sections: [
    {
      title: "What you're seeing",
      body: "The stress test applies user-defined shocks to the portfolio and shows the before/after income impact. It answers: 'how much annual income would I lose if X% of my CEFs cut distributions by Y%?'",
    },
    {
      title: "Scenario types",
      body: "• Rate shock: simulates the income change if interest rates rise/fall by a specified amount (affects leveraged CEFs and rate-sensitive REITs most)\n• Distribution cut: applies a haircut % to selected asset classes or individual holdings\n• Sector stress: reduces income from an entire sector by a specified %\n• Custom: set individual holding-level shocks",
    },
    {
      title: "Reading the results",
      body: "The results show total income before vs. after, the $ and % impact, and a holding-level breakdown ranked by impact size. Concentrated positions in rate-sensitive assets will dominate the stress results — this is intentional, as it reveals where the portfolio is fragile.",
    },
  ],
};

// ── Alerts page ──────────────────────────────────────────────────────────────

export const ALERTS_PAGE_HELP: PageHelpContent = {
  pageTitle: "Alerts",
  subtitle: "Real-time notifications when holding metrics breach configured thresholds.",
  sections: [
    {
      title: "What triggers alerts",
      body: "Alerts fire when a monitored metric crosses a configured threshold during a market data refresh:\n• Yield spike (> X% above 5-yr avg) — may indicate a cut is coming\n• Payout ratio breach (> configured max)\n• Coverage drop (FCF coverage falls below 1.0×)\n• HHS drop (score falls by > 10 points in one period)\n• UNSAFE flag set (Durability pillar hits the floor)",
    },
    {
      title: "Alert severity",
      body: "Critical: UNSAFE flag, dividend cut confirmed, or payout > 110%\nWarning: Payout 80–110%, yield spike, coverage weakening\nInfo: Score change, data refresh completion\n\nCritical alerts require manual acknowledgement. Warnings auto-dismiss after 7 days if the metric recovers.",
    },
    {
      title: "Managing alerts",
      body: "Click an alert to see the triggering metric and the holding's current state. Use 'Dismiss' to acknowledge once or 'Snooze' to suppress for N days. Configure per-holding thresholds in the position detail view (Health tab → click holding → settings icon).",
    },
  ],
};

// ── Tax page ─────────────────────────────────────────────────────────────────

export const TAX_PAGE_HELP: PageHelpContent = {
  pageTitle: "Tax Analysis",
  subtitle: "Estimate the tax drag on your income across account types and holding structures.",
  sections: [
    {
      title: "What you're seeing",
      body: "The tax page estimates the annual tax liability on dividend and distribution income based on account type (taxable, IRA, Roth), dividend classification (qualified vs. ordinary), and your marginal rate input.",
    },
    {
      title: "Dividend classification",
      body: "Qualified dividends (most common stocks held > 60 days): taxed at capital gains rates (0%, 15%, or 20%).\n\nOrdinary dividends (REITs, most BDC income, bond interest): taxed as ordinary income.\n\nReturn of capital (some CEFs, MLPs): tax-deferred until you sell — reduces your cost basis.\n\nThe mix matters: a 7% yielding REIT in a taxable account may net less after-tax than a 5.5% qualified dividend payer.",
    },
    {
      title: "Account placement strategy",
      body: "High-yield ordinary income (REITs, BDCs) belong in tax-deferred accounts (IRA/401k). Qualified dividend payers are more tax-efficient in taxable accounts. Municipal bonds and return-of-capital distributions are the most favorable in taxable accounts. The platform flags suboptimal placement when it detects ordinary income in taxable accounts.",
    },
  ],
};
