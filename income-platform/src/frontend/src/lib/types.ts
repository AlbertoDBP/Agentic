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
