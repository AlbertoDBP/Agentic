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
}

export interface Position {
  id: string;
  portfolio_id: string;
  symbol: string;
  name: string;
  asset_type: string;
  shares: number;
  cost_basis: number;
  current_value: number;
  annual_income: number;
  yield_on_cost: number;
  score?: number;
  sector?: string;
  industry?: string;
  dividend_frequency?: string;
  last_ex_date?: string;
  alert_count?: number;
  market_price?: number;
  avg_cost?: number;
  current_yield?: number;
  next_pay_date?: string;
  dividend_growth_5y?: number | null;
  payout_ratio?: number | null;
  beta?: number;
  currency?: string;
  cusip?: string;
  date_added?: string;
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
