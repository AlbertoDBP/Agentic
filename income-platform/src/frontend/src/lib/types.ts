export interface Portfolio {
  id: string;
  name: string;
  account_type: string;
  broker?: string;
  position_count?: number;
  total_value?: number;
  cash_balance?: number;
  sync_method?: "manual" | "csv_upload" | "broker_api";
  broker_api_key?: string;
  broker_secret_key?: string;
  sync_interval_hours?: number;
  last_synced?: string;
  last_refreshed_at?: string | null;
  // Aggregate KPIs (returned by /api/portfolios, computed server-side)
  annual_income?: number | null;
  blended_yield?: number | null;
  // Strategy settings
  benchmark_ticker?: string;
  target_yield?: number | null;
  monthly_income_target?: number | null;
  max_single_position_pct?: number | null;
  // Algorithm weights
  weight_value?: number;
  weight_safety?: number;
  weight_technicals?: number;
}

export interface Position {
  id: string;
  portfolio_id: string;
  symbol: string;
  name: string;
  asset_type: string;
  // Holdings core
  shares: number;
  cost_basis: number;
  current_value: number;
  market_price?: number;
  avg_cost?: number;
  acquired_date?: string | null;
  total_dividends_received?: number;
  // DCA / DRIP
  dca_stage?: number;
  drip_enabled?: boolean;
  // Income
  annual_income: number;
  yield_on_cost: number;
  current_yield?: number;
  dividend_frequency?: string;
  // Income efficiency
  annual_fee_drag?: number | null;
  estimated_tax_drag?: number | null;
  net_annual_income?: number | null;
  // Tax treatment
  tax_qualified_pct?: number;
  tax_ordinary_pct?: number;
  tax_roc_pct?: number;
  expense_ratio?: number | null;
  management_fee?: number | null;
  is_externally_managed?: boolean;
  // Score
  score?: number;
  grade?: string;
  recommendation?: string;
  valuation_yield_score?: number;
  financial_durability_score?: number;
  technical_entry_score?: number;
  nav_erosion_penalty?: number;
  signal_penalty?: number;
  factor_details?: Record<string, { value: number; score: number; weight: number }> | null;
  nav_erosion_details?: { prob_erosion_gt_5pct?: number; median_annual_nav_change_pct?: number; risk_classification?: string; penalty_applied?: number } | null;
  // HHS/IES v3.0
  hhs_score?: number | null;
  income_pillar_score?: number | null;
  durability_pillar_score?: number | null;
  income_weight?: number | null;
  durability_weight?: number | null;
  unsafe_flag?: boolean | null;
  unsafe_threshold?: number;
  hhs_status?: string | null;
  ies_score?: number | null;
  ies_calculated?: boolean;
  ies_blocked_reason?: string | null;
  quality_gate_status?: string;
  quality_gate_reasons?: string[] | null;
  hhs_commentary?: string | null;
  valid_until?: string | null;
  // Classification
  sector?: string;
  industry?: string;
  alert_count?: number;
  // Market price data
  daily_change_pct?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  market_cap?: number | null;
  pe_ratio?: number | null;
  eps?: number | null;
  payout_ratio?: number | null;
  beta?: number | null;
  chowder_number?: number | null;
  nav_value?: number | null;
  nav_discount_pct?: number | null;
  ex_div_date?: string | null;
  pay_date?: string | null;
  avg_volume?: number | null;
  // Technicals (v2)
  sma_50?: number | null;
  sma_200?: number | null;
  rsi_14d?: number | null;
  rsi_14w?: number | null;
  support_level?: number | null;
  resistance_level?: number | null;
  // Income stats (v2)
  dividend_growth_5y?: number | null;
  yield_5yr_avg?: number | null;
  div_cagr_3yr?: number | null;
  div_cagr_10yr?: number | null;
  consecutive_growth_yrs?: number | null;
  buyback_yield?: number | null;
  // Risk & debt (v2)
  coverage_metric_type?: string | null;
  interest_coverage_ratio?: number | null;
  net_debt_ebitda?: number | null;
  credit_rating?: string | null;
  free_cash_flow_yield?: number | null;
  return_on_equity?: number | null;
  // Analyst (v2)
  analyst_price_target?: number | null;
  next_earnings_date?: string | null;
  insider_ownership_pct?: number | null;
  // Dates
  price_updated_at?: string;
  last_ex_date?: string;
  next_pay_date?: string;
  // Legacy/misc
  currency?: string;
  date_added?: string;
}

// Standalone asset view (for /market page — asset-centric, no position info)
export interface Asset {
  symbol: string;
  name: string;
  asset_type: string;
  sector?: string;
  industry?: string;
  // Price
  price: number;
  change_pct: number;
  change: number;
  volume: number;
  day_high?: number | null;
  day_low?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  market_cap?: number | null;
  // Technicals
  sma_50?: number | null;
  sma_200?: number | null;
  rsi_14d?: number | null;
  support_level?: number | null;
  resistance_level?: number | null;
  // Fundamental valuation
  pe_ratio?: number | null;
  eps?: number | null;
  price_to_book?: number | null;
  // Income
  dividend_yield: number;
  payout_ratio?: number | null;
  chowder_number?: number | null;
  yield_5yr_avg?: number | null;
  dividend_growth_5y?: number | null;
  div_cagr_3yr?: number | null;
  div_cagr_10yr?: number | null;
  consecutive_growth_yrs?: number | null;
  buyback_yield?: number | null;
  ex_date?: string | null;
  pay_date?: string | null;
  div_frequency?: string | null;
  // NAV / CEF
  nav?: number | null;
  premium_discount?: number | null;
  // Risk & debt
  beta?: number | null;
  credit_rating?: string | null;
  interest_coverage_ratio?: number | null;
  net_debt_ebitda?: number | null;
  debt_to_equity?: number | null;
  coverage_metric_type?: string | null;
  coverage_ratio?: number | null;
  leverage_pct?: number | null;
  // Fundamentals
  free_cash_flow_yield?: number | null;
  return_on_equity?: number | null;
  analyst_price_target?: number | null;
  next_earnings_date?: string | null;
  insider_ownership_pct?: number | null;
  // Structural
  expense_ratio?: number | null;
  management_fee?: number | null;
  is_externally_managed?: boolean;
  avg_volume?: number | null;
  snapshot_date?: string | null;
  // Tax treatment (from securities)
  tax_qualified_pct?: number | null;
  tax_ordinary_pct?: number | null;
  tax_roc_pct?: number | null;
}

export interface Alert {
  id: string;
  symbol: string;
  alert_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: "ACTIVE" | "RESOLVED" | "SNOOZED";
  description?: string;
  created_at: string;
}

export interface NavAlert {
  symbol: string;
  alert_type: string;
  severity: string;
  status: string;
  premium_discount?: number;
  z_score?: number;
}

export interface Proposal {
  id: string;
  proposal_type: string;
  symbol: string;
  summary?: string;
  title?: string;
  status: "PENDING" | "ACCEPTED" | "REJECTED";
  created_at: string;
  analyst_source?: string;
  analyst_sentiment?: string;
  score?: number;
  yield_estimate?: number;
  risk_flags?: string[];
}

export interface IncomeProjection {
  month: string;
  projected: number;
  actual?: number;
  confidence_low?: number;
  confidence_high?: number;
}

export interface ProjectionSummary {
  annual_total: number;
  monthly_average: number;
  projections: IncomeProjection[];
}

export interface DividendEvent {
  symbol: string;
  asset_type: string;
  ex_date: string;
  pay_date: string;
  amount: number;
  frequency?: string;
}

export interface PortfolioMetrics {
  total_value: number;
  annual_income: number;
  blended_yield: number;
  active_alerts: number;
  positions_count: number;
}

export interface AllocationItem {
  name: string;
  value: number;
  percentage: number;
  color: string;
}

export interface HealthStatus {
  service: string;
  healthy: boolean;
  port?: number;
}

export interface SchedulerJob {
  id: string;
  name: string;
  next_run_time: string;
  trigger: string;
}

export interface PortfolioListItem {
  id: string;
  name: string;
  tax_status?: string;
  broker?: string;
  last_refresh?: string | null;
  holding_count: number;
  total_value: number;
  annual_income: number;
  naa_yield?: number | null;
  naa_yield_pre_tax?: boolean;
  agg_yoc?: number | null;
  agg_hhs?: number | null;
  total_return?: number | null;
  hhi?: number;
  unsafe_count: number;
  gate_fail_count: number;
  concentration_by_class: Array<{ class: string; value: number; pct: number }>;
}

export interface PortfolioSummary extends PortfolioListItem {
  concentration_by_sector: Array<{ sector: string; value: number; pct: number }>;
  top_income_holdings: Array<{
    ticker: string;
    asset_class?: string;
    annual_income: number;
    income_pct: number;
    unsafe: boolean;
  }>;
  scores_unavailable?: boolean;
}

// ── Scanner v2 types ──────────────────────────────────────────────────────────

export interface EntryExit {
  entry_limit: number | null;
  exit_limit: number | null;
  current_price: number | null;
  pct_from_entry: number | null;
  zone_status: "BELOW_ENTRY" | "IN_ZONE" | "NEAR_ENTRY" | "ABOVE_ENTRY" | "UNKNOWN";
  signals: {
    technical_entry: number | null;
    yield_entry: number | null;
    nav_entry: number | null;
    technical_exit: number | null;
    yield_exit: number | null;
    nav_exit: number | null;
  };
}

export interface PortfolioContext {
  already_held: boolean;
  held_shares: number | null;
  held_weight_pct: number | null;
  asset_class_weight_pct: number;
  sector_weight_pct: number;
  class_overweight: boolean;
  sector_overweight: boolean;
  is_underperformer: boolean;
  underperformer_reason: "income_pillar" | "durability_pillar" | null;
  replacing_ticker: string | null;
}

export interface ScanItem {
  rank: number;
  ticker: string;
  asset_class: string;
  score: number;
  grade: string;
  recommendation: string;
  chowder_number: number | null;
  chowder_signal: string | null;
  signal_penalty: number;
  passed_quality_gate: boolean;
  veto_flag: boolean;
  score_details: {
    valuation_yield_score?: number;
    financial_durability_score?: number;
    technical_entry_score?: number;
    nav_erosion_penalty?: number;
  };
  entry_exit?: EntryExit | null;
  portfolio_context?: PortfolioContext | null;
  analyst_context?: AnalystContext | null;
}

export interface AnalystContext {
  analyst_id:           number | null;
  analyst_name:         string | null;
  analyst_accuracy:     number | null;
  analyst_sector_alpha: Record<string, number> | null;
  price_guidance_type:  string | null;
  price_guidance_value: Record<string, unknown> | null;
  staleness_weight:     number | null;
  sourced_at:           string | null;   // ISO datetime
  recommendation:       string | null;   // "BUY" | "SELL" | etc.
  is_active:            boolean;         // false = history row (previous ingestion cycle)
  is_proposed:          boolean;         // true = already submitted as a proposal
  proposed_at:          string | null;   // ISO datetime of most recent proposal
}

export type PositionOverrides = Record<string, { amount_usd: number; target_price: number }>;

export interface ScanResult {
  scan_id: string;
  total_scanned: number;
  total_passed: number;
  total_vetoed: number;
  items: ScanItem[];
  filters_applied: Record<string, unknown>;
  created_at: string;
}

export interface ProposalDraft {
  proposal_id: string;
  status: string;
  tickers: Array<{
    ticker: string;
    entry_limit: number | null;
    exit_limit: number | null;
    zone_status: string;
    score: number;
    asset_class: string;
  }>;
  entry_limits: Record<string, number | null>;
  target_portfolio_id: string;
  created_at: string;
}

// ── Proposal execution workflow types ────────────────────────────────────────

export interface ProposalWithPortfolio {
  id: number;
  ticker: string;
  portfolio_id: string | null;
  platform_score: number | null;
  platform_alignment: string | null;
  analyst_recommendation: string | null;
  analyst_yield_estimate: number | null;
  platform_yield_estimate: number | null;
  entry_price_low: number | null;
  entry_price_high: number | null;
  position_size_pct: number | null;
  recommended_account: string | null;
  analyst_thesis_summary: string | null;
  analyst_safety_grade: string | null;
  platform_income_grade: string | null;
  sizing_rationale: string | null;
  divergence_notes: string | null;
  veto_flags: Record<string, unknown> | null;
  status: string;
  // Market enrichment (from proposal-service DB joins)
  current_price?: number | null;
  zone_status?: string | null;
  pct_from_entry?: number | null;
  valuation_yield_score?: number | null;
  financial_durability_score?: number | null;
  technical_entry_score?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  nav_value?: number | null;
  nav_discount_pct?: number | null;
  created_at: string | null;
}

export type OrderType = "market" | "limit" | "stop_limit";
export type TimeInForce = "day" | "gtc" | "ioc";

export interface OrderParams {
  order_type: OrderType;
  limit_price: number | null;    // null for market orders
  shares: number | null;
  dollar_amount: number | null;  // linked to shares via limit_price
  time_in_force: TimeInForce;
}

export type BrokerOrderStatus =
  | "pending"
  | "partially_filled"
  | "filled"
  | "cancelled"
  | "paper";

export interface LiveOrder {
  proposal_id: number;
  ticker: string;
  portfolio_id: string;
  order_id: string;         // broker order ID
  broker: string;           // e.g. "alpaca" — round-tripped from placement response
  status: BrokerOrderStatus;
  qty: number;
  filled_qty: number;
  avg_fill_price: number | null;
  limit_price: number | null;
  filled_at: string | null;
  submitted_at: string | null;
}

export interface PaperOrder {
  proposal_id: number;
  ticker: string;
  portfolio_id: string;
  qty: number;
  order_type: OrderType;
  limit_price: number | null;
  time_in_force: TimeInForce;
  portfolio_name: string;
  executed: boolean;          // true after "Mark as Executed"
}

export interface PortfolioImpact {
  cash_required: number;
  added_annual_income: number;
  new_portfolio_yield: number | null;   // null if portfolio value unknown
  concentration_pct: number | null;     // per-ticker, null if portfolio value unknown
}

// ── Data Quality ─────────────────────────────────────────────────────────────

export interface DataQualityIssue {
  id: number;
  symbol: string;
  field_name: string;
  asset_class: string;
  status: "missing" | "fetching" | "resolved" | "unresolvable";
  /** Lower-cased by design — distinct from Alert.severity which uses UPPER_CASE. Not interchangeable. */
  severity: "warning" | "critical";
  attempt_count: number;
  last_attempted_at: string | null;
  resolved_at: string | null;
  source_used: string | null;
  diagnostic: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface GateStatus {
  /** Always present — the object is only returned when portfolio_id is known. */
  portfolio_id: string;
  status: "passed" | "blocked" | "pending";
  blocking_issue_count: number;
  gate_passed_at: string | null;
}

export interface RefreshLog {
  /** Always present — the object is only returned when portfolio_id is known. */
  portfolio_id: string;
  market_data_refreshed_at: string | null;
  scores_recalculated_at: string | null;
  market_staleness_hrs: number | null;
  holdings_complete_count: number | null;
  holdings_incomplete_count: number | null;
  critical_issues_count: number | null;
}

export interface PortfolioHealth {
  gate: GateStatus | null;
  refresh_log: RefreshLog | null;
  /** Keys are symbols with at least one open issue. Use `issues_by_symbol[sym] ?? []` for safe access. */
  issues_by_symbol: Record<string, DataQualityIssue[]>;
}
