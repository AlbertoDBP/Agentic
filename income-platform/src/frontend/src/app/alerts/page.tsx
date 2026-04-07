"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { TickerBadge } from "@/components/ticker-badge";
import { AlertBadge } from "@/components/alert-badge";
import { formatDateTime } from "@/lib/utils";
import type { Alert } from "@/lib/types";
import { usePortfolio } from "@/lib/portfolio-context";
import { apiGet, apiPost } from "@/lib/api";

// ---------- Alert type metadata ----------

interface AlertMeta {
  label: string;
  icon: string;
  whatItMeans: string;
  action: string;
}

const ALERT_META: Record<string, AlertMeta> = {
  VETO_FLAG: {
    label: "Veto Flag",
    icon: "🚫",
    whatItMeans:
      "The scoring engine has flagged this holding for a significant quality concern — such as missing financials, a payout ratio above safe thresholds, or a credit-quality warning. The position is being tracked but scored with reduced confidence.",
    action:
      "Review the holding's score detail. If the concern is a known data gap, check if the data-quality engine has resolved it. Otherwise, evaluate whether to reduce or exit the position.",
  },
  NAV_DISCOUNT_WIDE: {
    label: "Wide NAV Discount",
    icon: "📉",
    whatItMeans:
      "This closed-end fund (CEF) is trading at an unusually wide discount to its Net Asset Value. Historically, wide discounts can revert to mean, but they can also widen further if the fund faces distribution cuts or poor sentiment.",
    action:
      "Check if the discount is wider than the fund's 52-week average. A widening discount with a stable distribution can be a buy signal. A widening discount with rising payout ratio warrants caution.",
  },
  NAV_PREMIUM_HIGH: {
    label: "High NAV Premium",
    icon: "📈",
    whatItMeans:
      "This closed-end fund is trading at a premium above its Net Asset Value. Buying at a premium means you pay more than the fund's underlying assets are worth. If the premium compresses, you will lose value even if the NAV stays flat.",
    action:
      "Consider waiting for the premium to compress before adding to the position. Existing holders may consider trimming if the premium is unusually high relative to the fund's history.",
  },
  YIELD_SPIKE: {
    label: "Yield Spike",
    icon: "⚠️",
    whatItMeans:
      "The trailing yield for this holding has spiked significantly. A yield spike usually means the price dropped sharply, which can signal market concern about the distribution or the issuer's financial health.",
    action:
      "Investigate the cause of the price drop. Check recent news, earnings, and whether the dividend/distribution has been confirmed. A yield spike accompanied by a payout ratio above 100% is a red flag.",
  },
  YIELD_DROP: {
    label: "Yield Drop",
    icon: "📉",
    whatItMeans:
      "The income yield for this position has fallen meaningfully. This could be due to a dividend cut, a price rally outpacing income growth, or a missed distribution.",
    action:
      "Confirm whether the distribution was actually reduced, or whether the price rise alone explains the yield compression. Check the payout schedule and any company guidance.",
  },
  PAYOUT_RATIO_HIGH: {
    label: "High Payout Ratio",
    icon: "⚡",
    whatItMeans:
      "This company is paying out a very high percentage of its earnings (or free cash flow) as dividends. A payout ratio above 90–100% is unsustainable for most equities and may signal an upcoming dividend cut.",
    action:
      "Check whether free cash flow supports the distribution even if earnings-based payout ratio is high. REITs and BDCs use different metrics (AFFO, NII). For traditional equities, a ratio above 90% warrants close monitoring.",
  },
  CHOWDER_LOW: {
    label: "Low Chowder Number",
    icon: "❄️",
    whatItMeans:
      "The Chowder Number (yield + 5-year dividend growth rate) has fallen below the target threshold (typically 12 for equities, 8 for utilities). This metric measures the income growth quality of a dividend growth holding.",
    action:
      "Evaluate whether slowing dividend growth is a temporary pause or a structural trend. Holdings with a persistently low Chowder Number may no longer justify their place in an income-growth strategy.",
  },
  DIV_CUT: {
    label: "Dividend Cut",
    icon: "✂️",
    whatItMeans:
      "The dividend or distribution for this holding has been reduced. This is one of the most significant events for an income portfolio — it directly reduces income and often signals underlying financial stress.",
    action:
      "Review the company's rationale for the cut. If the cut is part of a recapitalization or balance-sheet repair, a recovery may follow. If it reflects deteriorating fundamentals, consider exiting the position.",
  },
  PRICE_BELOW_SMA200: {
    label: "Below 200-Day SMA",
    icon: "📊",
    whatItMeans:
      "The price is trading below its 200-day simple moving average. This is a technical indicator suggesting the holding is in a longer-term downtrend. Not inherently alarming for income investors, but worth tracking.",
    action:
      "Assess whether the position is undervalued (a buying opportunity) or experiencing fundamental deterioration. Combine with fundamental analysis — a strong balance sheet below the 200-day SMA can be attractive for long-term income investors.",
  },
  RSI_OVERSOLD: {
    label: "Oversold (RSI)",
    icon: "🔻",
    whatItMeans:
      "The 14-day Relative Strength Index (RSI) is below 30, indicating the holding has been sold aggressively in a short period. Oversold conditions can precede a price recovery, especially for fundamentally sound income holdings.",
    action:
      "Verify that the selloff is not driven by a dividend cut or fundamental issue. If fundamentals are intact, an oversold income stock can represent a higher-yield entry point.",
  },
  RSI_OVERBOUGHT: {
    label: "Overbought (RSI)",
    icon: "🔺",
    whatItMeans:
      "The 14-day RSI is above 70, indicating the holding has been bought aggressively. Overbought conditions can precede a price correction.",
    action:
      "Avoid adding at overbought levels unless conviction is very high. Existing holders may consider trimming to lock in gains and reduce yield compression risk.",
  },
  DATA_MISSING: {
    label: "Data Missing",
    icon: "❓",
    whatItMeans:
      "Key financial data for this holding could not be retrieved from market data providers. Scores and projections for this position may be incomplete or inaccurate.",
    action:
      "The data-quality engine is attempting to resolve this automatically. No action required unless the issue persists. Check the Data Quality page for details.",
  },
};

function getAlertMeta(alertType: string): AlertMeta {
  return (
    ALERT_META[alertType] ?? {
      label: alertType.replace(/_/g, " "),
      icon: "ℹ️",
      whatItMeans: "An automated scan detected a condition worth reviewing for this holding.",
      action: "Review the holding's current data and recent news.",
    }
  );
}

// ---------- Component ----------

export default function AlertsPage() {
  const router = useRouter();
  const { portfolios } = usePortfolio();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("ALL");
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    const portfolioId = portfolios[0]?.id;
    if (!portfolioId) return;
    setLoading(true);
    apiGet<{ alerts: Alert[] } | Alert[]>(
      `/api/alerts?portfolio_id=${portfolioId}&status=ACTIVE`
    )
      .then((data) => {
        const list = Array.isArray(data)
          ? data
          : (data as { alerts: Alert[] }).alerts ?? [];
        setAlerts(list);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [portfolios]);

  const resolveAlert = useCallback(async (id: string) => {
    setResolvingId(id);
    try {
      await apiPost(`/api/alerts/${id}/resolve`);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, status: "RESOLVED" as const } : a
        )
      );
    } catch {
      // Silently fall back to optimistic update if API fails
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, status: "RESOLVED" as const } : a
        )
      );
    } finally {
      setResolvingId(null);
    }
  }, []);

  const activeAlerts = alerts.filter((a) => a.status === "ACTIVE");
  const resolvedAlerts = alerts.filter((a) => a.status !== "ACTIVE");

  const alertTypes = Array.from(new Set(alerts.map((a) => a.alert_type))).sort();
  const severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

  const filtered = activeAlerts.filter((a) => {
    if (filterType !== "ALL" && a.alert_type !== filterType) return false;
    if (filterSeverity !== "ALL" && a.severity !== filterSeverity) return false;
    return true;
  });

  const countBySeverity = (sev: string) =>
    activeAlerts.filter((a) => a.severity === sev).length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">Alerts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Automated monitoring for holdings in this portfolio
          </p>
        </div>
        <button
          onClick={() => setShowHelp((v) => !v)}
          className="text-xs text-muted-foreground hover:text-foreground border border-border rounded-md px-2.5 py-1.5 transition-colors"
        >
          {showHelp ? "Hide guide" : "How alerts work"}
        </button>
      </div>

      {/* Help panel */}
      {showHelp && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3 text-sm">
          <h2 className="font-semibold text-base">How the alert system works</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h3 className="font-medium text-foreground">Confirmation gate</h3>
              <p className="text-muted-foreground">
                Alerts go through a two-scan confirmation process before becoming
                actionable:
              </p>
              <ul className="space-y-1 text-muted-foreground">
                <li>
                  <span className="text-amber-400 font-medium">PENDING</span> —
                  detected in the most recent scan. May be transient.
                </li>
                <li>
                  <span className="text-red-400 font-medium">CONFIRMED</span> —
                  detected in two consecutive scans. More reliable signal.
                </li>
              </ul>
              <p className="text-muted-foreground">
                Scans run automatically whenever the market data refreshes (typically
                daily). Transient data glitches rarely survive two scans.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-medium text-foreground">Resolving alerts</h3>
              <p className="text-muted-foreground">
                Click <strong>Resolve</strong> to acknowledge an alert. This marks it
                as reviewed in the system. If the underlying condition persists, the
                scanner will re-open the alert in a future scan.
              </p>
              <h3 className="font-medium text-foreground mt-3">Scope</h3>
              <p className="text-muted-foreground">
                Alerts shown here are filtered to holdings in your active portfolio.
                Click any row to see a plain-English explanation and recommended action.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Severity summary badges */}
      <div className="flex flex-wrap gap-2">
        {severities.map((sev) => {
          const count = countBySeverity(sev);
          if (count === 0) return null;
          const colors: Record<string, string> = {
            CRITICAL: "bg-red-500/15 text-red-400 border-red-500/30",
            HIGH: "bg-orange-500/15 text-orange-400 border-orange-500/30",
            MEDIUM: "bg-amber-500/15 text-amber-400 border-amber-500/30",
            LOW: "bg-blue-500/15 text-blue-400 border-blue-500/30",
          };
          return (
            <button
              key={sev}
              onClick={() =>
                setFilterSeverity((prev) => (prev === sev ? "ALL" : sev))
              }
              className={`rounded-full border px-3 py-1 text-xs font-semibold transition-opacity ${
                colors[sev]
              } ${filterSeverity !== "ALL" && filterSeverity !== sev ? "opacity-40" : ""}`}
            >
              {count} {sev}
            </button>
          );
        })}
        {activeAlerts.length === 0 && !loading && (
          <span className="text-sm text-muted-foreground">No active alerts for this portfolio.</span>
        )}
      </div>

      {/* Filters */}
      {activeAlerts.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded-md border border-border bg-secondary text-sm px-2.5 py-1.5 text-foreground"
          >
            <option value="ALL">All types</option>
            {alertTypes.map((t) => (
              <option key={t} value={t}>
                {getAlertMeta(t).icon} {getAlertMeta(t).label}
              </option>
            ))}
          </select>
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="rounded-md border border-border bg-secondary text-sm px-2.5 py-1.5 text-foreground"
          >
            <option value="ALL">All severities</option>
            {severities.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {(filterType !== "ALL" || filterSeverity !== "ALL") && (
            <button
              onClick={() => {
                setFilterType("ALL");
                setFilterSeverity("ALL");
              }}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Clear filters
            </button>
          )}
          <span className="ml-auto text-xs text-muted-foreground">
            {filtered.length} of {activeAlerts.length} active alerts
          </span>
        </div>
      )}

      {loading && (
        <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          Loading alerts…
        </div>
      )}
      {error && !loading && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Alert rows */}
      {filtered.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/40">
                <th className="px-3 py-2 text-left font-medium text-muted-foreground w-24">Severity</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground w-28">Symbol</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Alert</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground hidden md:table-cell">Description</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground hidden lg:table-cell w-36">Created</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground w-36"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((alert) => {
                const meta = getAlertMeta(alert.alert_type);
                const isExpanded = expandedId === alert.id;
                return (
                  <>
                    <tr
                      key={alert.id}
                      onClick={() =>
                        setExpandedId((prev) =>
                          prev === alert.id ? null : alert.id
                        )
                      }
                      className="border-b border-border/60 hover:bg-secondary/30 cursor-pointer transition-colors"
                    >
                      <td className="px-3 py-2.5">
                        <AlertBadge severity={alert.severity} />
                      </td>
                      <td className="px-3 py-2.5">
                        <TickerBadge symbol={alert.symbol} />
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="font-medium">
                          {meta.icon} {meta.label}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-muted-foreground hidden md:table-cell max-w-xs truncate">
                        {alert.description ?? "—"}
                      </td>
                      <td className="px-3 py-2.5 text-muted-foreground tabular-nums text-xs hidden lg:table-cell">
                        {formatDateTime(alert.created_at)}
                      </td>
                      <td className="px-3 py-2.5">
                        <div
                          className="flex items-center gap-1.5 justify-end"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={() => router.push(`/portfolios/${encodeURIComponent(alert.symbol)}`)}
                            className="rounded-md border border-border bg-secondary px-2 py-1 text-xs font-medium hover:bg-accent transition-colors"
                          >
                            View
                          </button>
                          <button
                            onClick={() => resolveAlert(alert.id)}
                            disabled={resolvingId === alert.id}
                            className="rounded-md border border-border bg-secondary px-2 py-1 text-xs font-medium hover:bg-accent transition-colors disabled:opacity-50"
                          >
                            {resolvingId === alert.id ? "…" : "Resolve"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${alert.id}-detail`} className="border-b border-border/60 bg-secondary/20">
                        <td colSpan={6} className="px-4 py-3">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                What this means
                              </p>
                              <p className="text-foreground leading-relaxed">{meta.whatItMeans}</p>
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                Recommended action
                              </p>
                              <p className="text-foreground leading-relaxed">{meta.action}</p>
                            </div>
                          </div>
                          {alert.description && (
                            <p className="mt-2 text-xs text-muted-foreground">
                              <span className="font-medium">Scanner detail:</span>{" "}
                              {alert.description}
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Resolved section */}
      {resolvedAlerts.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground list-none flex items-center gap-1">
            <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
            {resolvedAlerts.length} resolved alerts (this session)
          </summary>
          <div className="mt-2 rounded-lg border border-border/60 overflow-hidden opacity-60">
            <table className="w-full text-sm">
              <tbody>
                {resolvedAlerts.map((alert) => {
                  const meta = getAlertMeta(alert.alert_type);
                  return (
                    <tr key={alert.id} className="border-b border-border/40">
                      <td className="px-3 py-2">
                        <AlertBadge severity={alert.severity} />
                      </td>
                      <td className="px-3 py-2">
                        <TickerBadge symbol={alert.symbol} />
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {meta.icon} {meta.label}
                      </td>
                      <td className="px-3 py-2">
                        <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold bg-emerald-400/10 text-emerald-400">
                          RESOLVED
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
