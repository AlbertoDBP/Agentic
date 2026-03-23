"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, BarChart2 } from "lucide-react";
import { MetricCard } from "@/components/metric-card";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS, API_BASE_URL } from "@/lib/config";
import type { Asset } from "@/lib/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="mb-3 text-sm font-medium text-muted-foreground uppercase tracking-wider">{title}</h2>
      {children}
    </div>
  );
}

function Row({ label, value, valueClass }: { label: string; value: React.ReactNode; valueClass?: string }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-border/40 last:border-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-xs font-medium tabular-nums", valueClass)}>{value ?? "—"}</dd>
    </div>
  );
}

function RsiBar({ rsi }: { rsi: number | null | undefined }) {
  if (rsi == null) return <span className="text-muted-foreground text-xs">—</span>;
  const pct = Math.min(Math.max(rsi, 0), 100);
  const color = rsi > 70 ? "#f87171" : rsi < 30 ? "#10b981" : "#94a3b8";
  const label = rsi > 70 ? "Overbought" : rsi < 30 ? "Oversold" : "Neutral";
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 flex-1 rounded-full bg-secondary">
        <div className="absolute h-2 rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
        <div className="absolute h-3 w-0.5 -top-0.5 rounded-full bg-white/50" style={{ left: "30%" }} />
        <div className="absolute h-3 w-0.5 -top-0.5 rounded-full bg-white/50" style={{ left: "70%" }} />
      </div>
      <span className="text-xs tabular-nums">{rsi.toFixed(1)}</span>
      <span className={cn("text-[10px]", rsi > 70 ? "text-red-400" : rsi < 30 ? "text-emerald-400" : "text-muted-foreground")}>{label}</span>
    </div>
  );
}

function RangeBar({ price, low, high }: { price: number; low: number; high: number }) {
  const range = high - low;
  const pct = range > 0 ? ((price - low) / range) * 100 : 0;
  return (
    <div className="space-y-1">
      <div className="relative h-2 w-full rounded-full bg-secondary">
        <div className="absolute h-2 rounded-full bg-primary/50 transition-all" style={{ width: `${Math.min(Math.max(pct, 2), 100)}%` }} />
        <div className="absolute h-3 w-0.5 -top-0.5 rounded-full bg-primary" style={{ left: `${Math.min(Math.max(pct, 1), 99)}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{formatCurrency(low)}</span>
        <span className="text-foreground font-medium">{pct.toFixed(0)}% of range</span>
        <span>{formatCurrency(high)}</span>
      </div>
    </div>
  );
}

export default function AssetDetailPage() {
  const params = useParams();
  const rawSymbol = params.symbol as string;
  const symbol = decodeURIComponent(rawSymbol).toUpperCase();

  const [asset, setAsset] = useState<Asset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE_URL}/api/market-data/asset/${encodeURIComponent(symbol)}`, { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(`Asset not found: ${symbol}`);
        return res.json() as Promise<Asset>;
      })
      .then(setAsset)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [symbol]);

  const backLink = (
    <Link href="/market" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-4 w-4" /> Back to Market
    </Link>
  );

  if (loading) return (
    <div className="space-y-4">
      {backLink}
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading {symbol}…</span>
      </div>
    </div>
  );

  if (error || !asset) return (
    <div className="space-y-4">
      {backLink}
      <p className="text-muted-foreground text-sm">{error ?? `Asset not found: ${symbol}`}</p>
    </div>
  );

  const color = ASSET_CLASS_COLORS[asset.asset_type] || "#64748b";
  const changeColor = asset.change_pct >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        {backLink}
        <div className="mt-3 flex items-center gap-3">
          <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
          <h1 className="text-2xl font-semibold">{symbol}</h1>
          <span className="rounded bg-secondary px-2 py-0.5 text-xs font-medium">{asset.asset_type}</span>
          <BarChart2 className="h-4 w-4 text-muted-foreground" />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {asset.name}
          {asset.sector ? ` · ${asset.sector}` : ""}
          {asset.industry ? ` · ${asset.industry}` : ""}
        </p>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Price" value={formatCurrency(asset.price)} />
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-medium text-muted-foreground">Daily Change</p>
          <p className={cn("mt-1 text-2xl font-semibold tabular-nums tracking-tight", changeColor)}>
            {asset.change_pct >= 0 ? "+" : ""}{asset.change_pct.toFixed(2)}%
          </p>
          {asset.change != null && (
            <p className={cn("mt-1 text-xs font-medium", changeColor)}>
              {asset.change >= 0 ? "+" : ""}{formatCurrency(Math.abs(asset.change))}
            </p>
          )}
        </div>
        <MetricCard label="Dividend Yield" value={formatPercent(asset.dividend_yield)} />
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-medium text-muted-foreground">NAV Prem/Disc</p>
          <p className={cn(
            "mt-1 text-2xl font-semibold tabular-nums tracking-tight",
            asset.premium_discount != null ? (asset.premium_discount > 0 ? "text-yellow-400" : "text-income") : "text-muted-foreground"
          )}>
            {asset.premium_discount != null
              ? `${asset.premium_discount >= 0 ? "+" : ""}${asset.premium_discount.toFixed(2)}%`
              : "—"}
          </p>
          {asset.nav != null && (
            <p className="mt-1 text-xs text-muted-foreground">NAV {formatCurrency(asset.nav)}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* ── Technicals & Entry Logic ────────────────────────────────────── */}
        <Section title="Technicals & Entry">
          <dl className="space-y-1">
            <div className="py-1.5 border-b border-border/40">
              <div className="flex justify-between mb-1">
                <dt className="text-xs text-muted-foreground">RSI (14d)</dt>
              </div>
              <RsiBar rsi={asset.rsi_14d} />
            </div>
            {asset.week52_low != null && asset.week52_high != null && (
              <div className="py-1.5 border-b border-border/40">
                <dt className="text-xs text-muted-foreground mb-1">52-Week Range</dt>
                <RangeBar price={asset.price} low={asset.week52_low!} high={asset.week52_high!} />
              </div>
            )}
          </dl>
          <dl className="mt-2 space-y-0">
            <Row label="SMA 50"
              value={asset.sma_50 != null ? formatCurrency(asset.sma_50) : null}
              valueClass={asset.sma_50 != null ? (asset.price > asset.sma_50 ? "text-income" : "text-red-400") : ""} />
            <Row label="SMA 200"
              value={asset.sma_200 != null ? formatCurrency(asset.sma_200) : null}
              valueClass={asset.sma_200 != null ? (asset.price > asset.sma_200 ? "text-income" : "text-red-400") : ""} />
            <Row label="Support"
              value={asset.support_level != null ? formatCurrency(asset.support_level) : null} />
            <Row label="Resistance"
              value={asset.resistance_level != null ? formatCurrency(asset.resistance_level) : null} />
            <Row label="Analyst Target"
              value={asset.analyst_price_target != null ? formatCurrency(asset.analyst_price_target) : null}
              valueClass={asset.analyst_price_target != null ? (asset.analyst_price_target > asset.price ? "text-income" : "text-red-400") : ""} />
            <Row label="Volume (10d avg)"
              value={asset.avg_volume != null
                ? (asset.avg_volume >= 1_000_000 ? `${(asset.avg_volume / 1_000_000).toFixed(1)}M` : `${(asset.avg_volume / 1_000).toFixed(0)}K`)
                : null} />
          </dl>
        </Section>

        {/* ── Fundamental Valuation ───────────────────────────────────────── */}
        <Section title="Fundamental Valuation">
          <dl className="space-y-0">
            <Row label="Market Cap"
              value={asset.market_cap
                ? (asset.market_cap >= 1000 ? `$${(asset.market_cap / 1000).toFixed(1)}B` : `$${asset.market_cap.toFixed(0)}M`)
                : null} />
            <Row label="P/E Ratio"
              value={asset.pe_ratio != null ? asset.pe_ratio.toFixed(1) : null} />
            <Row label="P/B Ratio"
              value={asset.price_to_book != null ? asset.price_to_book.toFixed(2) : null} />
            <Row label="EPS"
              value={asset.eps != null ? formatCurrency(asset.eps) : null} />
            <Row label="Payout Ratio"
              value={asset.payout_ratio != null ? `${asset.payout_ratio.toFixed(1)}%` : null}
              valueClass={asset.payout_ratio != null ? (asset.payout_ratio > 100 ? "text-red-400" : asset.payout_ratio > 90 ? "text-yellow-400" : "") : ""} />
            <Row label="Beta"
              value={asset.beta != null ? asset.beta.toFixed(2) : null} />
            <Row label="FCF Yield"
              value={asset.free_cash_flow_yield != null ? formatPercent(asset.free_cash_flow_yield * 100) : null} />
            <Row label="Return on Equity"
              value={asset.return_on_equity != null ? formatPercent(asset.return_on_equity * 100) : null} />
            <Row label="Insider Ownership"
              value={asset.insider_ownership_pct != null ? formatPercent(asset.insider_ownership_pct) : null} />
            <Row label="Next Earnings"
              value={asset.next_earnings_date ? new Date(asset.next_earnings_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null} />
          </dl>
        </Section>

        {/* ── Income Stability ────────────────────────────────────────────── */}
        <Section title="Income Stability">
          <dl className="space-y-0">
            <Row label="Current Yield"
              value={formatPercent(asset.dividend_yield)}
              valueClass="text-income" />
            <Row label="5-Year Avg Yield"
              value={asset.yield_5yr_avg != null ? formatPercent(asset.yield_5yr_avg) : null} />
            <Row label="Chowder Number"
              value={asset.chowder_number != null ? asset.chowder_number.toFixed(1) : null}
              valueClass={asset.chowder_number != null ? (asset.chowder_number >= 12 ? "text-income" : asset.chowder_number >= 8 ? "text-yellow-400" : "text-red-400") : ""} />
            <Row label="Div Growth (5Y)"
              value={asset.dividend_growth_5y != null ? `${asset.dividend_growth_5y >= 0 ? "+" : ""}${asset.dividend_growth_5y.toFixed(1)}%` : null}
              valueClass={asset.dividend_growth_5y != null ? (asset.dividend_growth_5y >= 0 ? "text-income" : "text-red-400") : ""} />
            <Row label="CAGR 3-Year"
              value={asset.div_cagr_3yr != null ? formatPercent(asset.div_cagr_3yr) : null} />
            <Row label="CAGR 10-Year"
              value={asset.div_cagr_10yr != null ? formatPercent(asset.div_cagr_10yr) : null} />
            <Row label="Consecutive Growth Yrs"
              value={asset.consecutive_growth_yrs != null ? `${asset.consecutive_growth_yrs} yrs` : null}
              valueClass={asset.consecutive_growth_yrs != null ? (asset.consecutive_growth_yrs >= 25 ? "text-income" : asset.consecutive_growth_yrs >= 10 ? "text-blue-400" : "") : ""} />
            <Row label="Buyback Yield"
              value={asset.buyback_yield != null ? formatPercent(asset.buyback_yield * 100) : null} />
            <Row label="Ex-Div Date"
              value={asset.ex_date ? new Date(asset.ex_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null} />
            <Row label="Pay Date"
              value={asset.pay_date ? new Date(asset.pay_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null} />
            <Row label="Frequency"
              value={asset.div_frequency} />
          </dl>
        </Section>

        {/* ── Risk & Debt ──────────────────────────────────────────────────── */}
        <Section title="Risk & Debt">
          <dl className="space-y-0">
            <Row label="Credit Rating"
              value={asset.credit_rating}
              valueClass={asset.credit_rating
                ? (["AAA", "AA+", "AA", "AA-", "A+", "A", "A-"].includes(asset.credit_rating) ? "text-income"
                  : ["BBB+", "BBB", "BBB-"].includes(asset.credit_rating) ? "text-blue-400"
                  : ["BB+", "BB", "BB-", "B+", "B", "B-"].includes(asset.credit_rating) ? "text-yellow-400"
                  : "text-red-400")
                : ""} />
            <Row label="Coverage Metric"
              value={asset.coverage_metric_type} />
            <Row label="Interest Coverage"
              value={asset.interest_coverage_ratio != null ? `${asset.interest_coverage_ratio.toFixed(1)}×` : null}
              valueClass={asset.interest_coverage_ratio != null ? (asset.interest_coverage_ratio >= 3 ? "text-income" : asset.interest_coverage_ratio >= 1.5 ? "text-yellow-400" : "text-red-400") : ""} />
            <Row label="Net Debt / EBITDA"
              value={asset.net_debt_ebitda != null ? `${asset.net_debt_ebitda.toFixed(1)}×` : null}
              valueClass={asset.net_debt_ebitda != null ? (asset.net_debt_ebitda <= 2 ? "text-income" : asset.net_debt_ebitda <= 4 ? "text-yellow-400" : "text-red-400") : ""} />
            <Row label="Beta"
              value={asset.beta != null ? asset.beta.toFixed(2) : null} />
          </dl>

          {/* NAV section for CEF/REIT types */}
          {asset.nav != null && (
            <>
              <div className="border-t border-border/40 mt-3 pt-3">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">NAV</p>
              </div>
              <dl className="space-y-0">
                <Row label="NAV / Share" value={formatCurrency(asset.nav)} />
                <Row label="Premium / Discount"
                  value={asset.premium_discount != null ? `${asset.premium_discount >= 0 ? "+" : ""}${asset.premium_discount.toFixed(2)}%` : null}
                  valueClass={asset.premium_discount != null ? (asset.premium_discount > 0 ? "text-yellow-400" : "text-income") : ""} />
              </dl>
            </>
          )}
        </Section>

        {/* ── Structural & Costs ───────────────────────────────────────────── */}
        <Section title="Structural & Costs">
          <dl className="space-y-0">
            <Row label="Expense Ratio"
              value={asset.expense_ratio != null ? `${(asset.expense_ratio * 100).toFixed(2)}%` : null}
              valueClass={asset.expense_ratio != null ? (asset.expense_ratio <= 0.005 ? "text-income" : asset.expense_ratio <= 0.01 ? "text-yellow-400" : "text-red-400") : ""} />
            <Row label="Management Fee"
              value={asset.management_fee != null ? `${(asset.management_fee * 100).toFixed(2)}%` : null} />
            <Row label="Externally Managed"
              value={asset.is_externally_managed != null ? (asset.is_externally_managed ? "Yes" : "No") : null}
              valueClass={asset.is_externally_managed ? "text-yellow-400" : ""} />
            <Row label="Insider Ownership"
              value={asset.insider_ownership_pct != null ? formatPercent(asset.insider_ownership_pct) : null} />
          </dl>

          {(asset.tax_qualified_pct != null || asset.tax_ordinary_pct != null) && (
            <>
              <div className="border-t border-border/40 mt-3 pt-3">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Tax Treatment</p>
              </div>
              <dl className="space-y-0">
                <Row label="Qualified Div"
                  value={asset.tax_qualified_pct != null ? `${asset.tax_qualified_pct.toFixed(0)}%` : null}
                  valueClass="text-income" />
                <Row label="Ordinary Income"
                  value={asset.tax_ordinary_pct != null ? `${asset.tax_ordinary_pct.toFixed(0)}%` : null} />
                <Row label="Return of Capital"
                  value={asset.tax_roc_pct != null ? `${asset.tax_roc_pct.toFixed(0)}%` : null}
                  valueClass={asset.tax_roc_pct != null && asset.tax_roc_pct > 0 ? "text-blue-400" : ""} />
              </dl>
            </>
          )}
        </Section>

        {/* ── Snapshot Info ────────────────────────────────────────────────── */}
        <Section title="Data Info">
          <dl className="space-y-0">
            <Row label="Sector" value={asset.sector} />
            <Row label="Industry" value={asset.industry} />
            <Row label="Snapshot Date"
              value={asset.snapshot_date ? new Date(asset.snapshot_date).toLocaleDateString() : null} />
            <Row label="Avg Volume"
              value={asset.avg_volume != null
                ? (asset.avg_volume >= 1_000_000 ? `${(asset.avg_volume / 1_000_000).toFixed(1)}M` : `${(asset.avg_volume / 1_000).toFixed(0)}K`)
                : null} />
          </dl>
        </Section>
      </div>
    </div>
  );
}
