// src/frontend/src/lib/chat-tools.ts
import type Anthropic from "@anthropic-ai/sdk";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const AGENT03_URL = process.env.AGENT03_URL ?? "http://localhost:8003";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

function svcHeaders() {
  return { Authorization: `Bearer ${serviceToken()}` };
}

// ── Tool definitions (Anthropic schema) ───────────────────────────────────────

export function buildToolDefinitions(): Anthropic.Tool[] {
  return [
    {
      name: "create_proposal_draft",
      description:
        "Creates a ProposalDraft in the proposals workflow via Agent 12. The engine derives action, quantity, and rationale from live scoring — do not invent these values. Use when the user asks to buy, sell, or rebalance a specific holding.",
      input_schema: {
        type: "object" as const,
        properties: {
          ticker: { type: "string", description: "Stock ticker symbol (e.g. OXLC)" },
          portfolio_id: { type: "string", description: "UUID of the target portfolio" },
          trigger_mode: { type: "string", enum: ["on_demand"], description: "Always 'on_demand'" },
        },
        required: ["ticker", "portfolio_id"],
      },
    },
    {
      name: "get_position_details",
      description:
        "Fetches full position data for one symbol: market data, cost basis, income metrics, HHS/IES scores, and factor breakdown. Use when the user asks about a specific holding in detail.",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string" },
          portfolio_id: { type: "string" },
        },
        required: ["symbol", "portfolio_id"],
      },
    },
    {
      name: "get_score_breakdown",
      description:
        "Returns factor_details (8 scoring sub-components with score/max/value) for a symbol from Agent 03. Use when the user asks why a score is high or low.",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "get_scanner_results",
      description:
        "Returns the latest cached scanner results for a portfolio (ADD/TRIM candidates). Does NOT trigger a new scan — shows the most recent run by Agent 07.",
      input_schema: {
        type: "object" as const,
        properties: {
          portfolio_id: { type: "string" },
        },
        required: ["portfolio_id"],
      },
    },
    {
      name: "get_analyst_signals",
      description:
        "Returns analyst signals and frameworks for a specific ticker from Agent 02's newsletter ingestion (Seeking Alpha commentary, analyst philosophy).",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "get_portfolio_income",
      description:
        "Returns monthly income distribution for a portfolio: per-month totals ($), per-position breakdown by frequency (Monthly/Quarterly/Semi-Annual/Annual), and annual income total. Use when the user asks about income, monthly income, distributions, cash flow, or dividend schedule.",
      input_schema: {
        type: "object" as const,
        properties: {
          portfolio_id: { type: "string", description: "UUID of the portfolio" },
        },
        required: ["portfolio_id"],
      },
    },
    {
      name: "get_tax_profile",
      description:
        "Returns the tax breakdown for a specific symbol: income character (qualified dividends, ordinary income, return of capital), effective tax rate, and after-tax yield. Use when the user asks about tax efficiency, after-tax income, or the tax treatment of a specific holding.",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string", description: "Ticker symbol (e.g. MAIN)" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "get_portfolio_tax_optimization",
      description:
        "Runs a full portfolio-level tax optimization analysis: after-tax income estimates, account placement recommendations (taxable vs. tax-advantaged), and harvest opportunities. Use when the user asks about portfolio tax efficiency, tax savings, or optimizing tax placement.",
      input_schema: {
        type: "object" as const,
        properties: {
          portfolio_id: { type: "string", description: "Portfolio UUID" },
          filing_status: {
            type: "string",
            enum: ["SINGLE", "MARRIED_FILING_JOINTLY", "MARRIED_FILING_SEPARATELY", "HEAD_OF_HOUSEHOLD"],
            description: "Tax filing status (default: SINGLE)",
          },
          state_code: { type: "string", description: "Two-letter state code for state tax (e.g. CA, NY). Omit for federal-only." },
        },
        required: ["portfolio_id"],
      },
    },
    {
      name: "run_income_projection",
      description:
        "Projects future portfolio income over a time horizon with P10/P50/P90 percentiles and per-position breakdown. Use when the user asks about future income, income forecasts, or income reliability.",
      input_schema: {
        type: "object" as const,
        properties: {
          portfolio_id: { type: "string", description: "Portfolio UUID" },
          horizon_months: {
            type: "number",
            description: "Projection horizon in months (1–60, default 12)",
          },
        },
        required: ["portfolio_id"],
      },
    },
    {
      name: "run_stress_test",
      description:
        "Runs a stress-test scenario on a portfolio to estimate income and value impact. Use when the user asks about risk, rate hikes, market corrections, or portfolio resilience. Available scenario_types: RATE_HIKE_200BPS, MARKET_CORRECTION_20, or CUSTOM.",
      input_schema: {
        type: "object" as const,
        properties: {
          portfolio_id: { type: "string", description: "Portfolio UUID" },
          scenario_type: {
            type: "string",
            enum: ["RATE_HIKE_200BPS", "MARKET_CORRECTION_20", "CUSTOM"],
            description: "Predefined scenario name or CUSTOM",
          },
          scenario_params: {
            type: "object",
            description: "Required only when scenario_type is CUSTOM. E.g. { income_shock: -0.15, price_shock: -0.20 }",
          },
        },
        required: ["portfolio_id", "scenario_type"],
      },
    },
    {
      name: "get_market_data",
      description:
        "Fetches live price and fundamental data for a symbol: current price, yield, P/E, debt ratios, dividend coverage, and other market metrics from the market data service.",
      input_schema: {
        type: "object" as const,
        properties: {
          symbol: { type: "string", description: "Ticker symbol" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "save_memory",
      description:
        "Stores a fact, preference, or rule about the user or their portfolio in persistent memory. Call whenever the user says 'remember', 'always', or states a preference.",
      input_schema: {
        type: "object" as const,
        properties: {
          content: { type: "string", description: "The memory to store" },
          category: {
            type: "string",
            enum: ["constraint", "preference", "rule", "fact"],
            description: "Category of the memory",
          },
        },
        required: ["content"],
      },
    },
    {
      name: "save_skill",
      description:
        "Stores a named analytical workflow that can be triggered by a phrase in future conversations.",
      input_schema: {
        type: "object" as const,
        properties: {
          name: { type: "string", description: "Display name, e.g. 'BDC Health Check'" },
          trigger_phrase: { type: "string", description: "Phrase the user types to invoke this skill" },
          procedure: { type: "string", description: "Step-by-step procedure description" },
        },
        required: ["name", "trigger_phrase", "procedure"],
      },
    },
  ];
}

// ── Tool execution ─────────────────────────────────────────────────────────────

export async function executeTool(
  name: string,
  input: Record<string, unknown>
): Promise<Record<string, unknown>> {
  try {
    switch (name) {
      case "create_proposal_draft": {
        const body = {
          ticker: input.ticker,
          portfolio_id: input.portfolio_id,
          trigger_mode: "on_demand",
        };
        const r = await fetch(`${ADMIN_PANEL_URL}/api/proposals/generate`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) return { error: `Proposal generation failed: HTTP ${r.status}` };
        const data = await r.json();
        return {
          proposal_id: data.id ?? data.proposal_id,
          action: data.action ?? data.proposal_type,
          rationale: data.rationale ?? "",
          link: "/proposals",
          message: `ProposalDraft created for ${input.ticker}. View in /proposals.`,
        };
      }

      case "get_position_details": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/portfolios/${input.portfolio_id}/positions`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { error: `Positions fetch failed: HTTP ${r.status}` };
        const positions: any[] = await r.json();
        const pos = positions.find(
          (p) => p.symbol?.toUpperCase() === String(input.symbol).toUpperCase()
        );
        return pos ?? { error: `Symbol ${input.symbol} not found in portfolio` };
      }

      case "get_score_breakdown": {
        const r = await fetch(`${AGENT03_URL}/scores/${input.symbol}`, {
          headers: svcHeaders(),
        });
        if (!r.ok) return { error: `Score fetch failed: HTTP ${r.status}` };
        const data = await r.json();
        return {
          symbol: input.symbol,
          hhs_score: data.hhs_score,
          hhs_status: data.hhs_status,
          ies_score: data.ies_score,
          factor_details: data.factor_details ?? {},
        };
      }

      case "get_scanner_results": {
        // Run a fresh scan for this portfolio and return the top results
        const r = await fetch(`${ADMIN_PANEL_URL}/api/scanner/scan`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ portfolio_id: input.portfolio_id, limit: 20 }),
        });
        if (!r.ok) return { error: `Scanner fetch failed: HTTP ${r.status}` };
        const data = await r.json();
        return { results: data.items ?? [], scan_id: data.scan_id, total_passed: data.total_passed };
      }

      case "get_analyst_signals": {
        // Scan a single ticker to get its analyst context and scoring details
        const r = await fetch(`${ADMIN_PANEL_URL}/api/scanner/scan`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ tickers: [String(input.symbol).toUpperCase()], limit: 1 }),
        });
        if (!r.ok) return { signals: [], message: "No analyst data available" };
        const data = await r.json();
        const item = (data.items ?? [])[0];
        if (!item) return { signals: [], message: "No data found for ticker" };
        return { symbol: item.ticker, analyst_context: item.analyst_context, score_details: item.score_details, recommendation: item.recommendation };
      }

      case "get_portfolio_income": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/portfolios/${input.portfolio_id}/income-by-month`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { error: `Income fetch failed: HTTP ${r.status}` };
        return await r.json();
      }

      case "get_tax_profile": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/tax/profile/${input.symbol}`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { error: `Tax profile fetch failed: HTTP ${r.status}` };
        return await r.json();
      }

      case "get_portfolio_tax_optimization": {
        const body: Record<string, unknown> = { portfolio_id: input.portfolio_id };
        if (input.filing_status) body.filing_status = input.filing_status;
        if (input.state_code) body.state_code = input.state_code;
        const r = await fetch(`${ADMIN_PANEL_URL}/api/tax/optimize/portfolio`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) return { error: `Tax optimization failed: HTTP ${r.status}` };
        return await r.json();
      }

      case "run_income_projection": {
        const body: Record<string, unknown> = { portfolio_id: input.portfolio_id };
        if (input.horizon_months) body.horizon_months = input.horizon_months;
        const r = await fetch(`${ADMIN_PANEL_URL}/api/scenarios/income-projection`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) return { error: `Income projection failed: HTTP ${r.status}` };
        return await r.json();
      }

      case "run_stress_test": {
        const body: Record<string, unknown> = {
          portfolio_id: input.portfolio_id,
          scenario_type: input.scenario_type,
        };
        if (input.scenario_params) body.scenario_params = input.scenario_params;
        const r = await fetch(`${ADMIN_PANEL_URL}/api/scenarios/stress-test`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) return { error: `Stress test failed: HTTP ${r.status}` };
        return await r.json();
      }

      case "get_market_data": {
        const r = await fetch(
          `${ADMIN_PANEL_URL}/api/market-data/fundamentals/${input.symbol}`,
          { headers: svcHeaders() }
        );
        if (!r.ok) return { error: `Market data fetch failed: HTTP ${r.status}` };
        return await r.json();
      }

      case "save_memory": {
        const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/memories`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ content: input.content, category: input.category }),
        });
        if (!r.ok) return { error: "Failed to save memory" };
        return { saved: true, content: input.content };
      }

      case "save_skill": {
        const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, {
          method: "POST",
          headers: { ...svcHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({
            name: input.name,
            trigger_phrase: input.trigger_phrase,
            procedure: input.procedure,
          }),
        });
        if (!r.ok) return { error: "Failed to save skill" };
        return { saved: true, name: input.name, trigger_phrase: input.trigger_phrase };
      }

      default:
        return { error: `Unknown tool: ${name}` };
    }
  } catch (err) {
    return { error: String(err) };
  }
}
