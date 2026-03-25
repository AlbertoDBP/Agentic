"use client";

import { useState, useMemo, useEffect } from "react";
import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { usePortfolio } from "@/lib/portfolio-context";
import { API_BASE_URL } from "@/lib/config";

const PORTFOLIO_COLORS = ["#3b82f6", "#8b5cf6", "#f59e0b", "#10b981", "#06b6d4", "#ef4444"];

interface MonthTotal {
  month: string;       // "Jan", "Feb", …
  month_num: number;   // 1-12
  total: number;
}

interface PositionMonth {
  symbol: string;
  name: string;
  annual_income: number;
  frequency: string;
  monthly: Record<number, number>;  // month_num → amount
  ex_div_date?: string | null;
  pay_date?: string | null;
}

interface IncomeByMonth {
  portfolio_id: string;
  monthly_totals: MonthTotal[];
  positions: PositionMonth[];
  annual_total: number;
}

type DateMode = "ex_date" | "pay_date";

export default function CalendarPage() {
  const { portfolios, activePortfolio } = usePortfolio();
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [month, setMonth] = useState(() => new Date().getMonth()); // 0-indexed
  const [dateMode, setDateMode] = useState<DateMode>("pay_date");
  const [filterPortfolioId, setFilterPortfolioId] = useState<string>("all");

  // Per-portfolio income data keyed by portfolio id
  const [incomeData, setIncomeData] = useState<Record<string, IncomeByMonth>>({});
  const [loading, setLoading] = useState(false);

  const portfolioColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    portfolios.forEach((p, i) => { map[p.id] = PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length]; });
    return map;
  }, [portfolios]);

  // Fetch income distribution for all portfolios
  useEffect(() => {
    if (portfolios.length === 0) return;
    setLoading(true);
    Promise.all(
      portfolios.map((p) =>
        fetch(`${API_BASE_URL}/api/portfolios/${p.id}/income-by-month`, { credentials: "include" })
          .then((r) => r.ok ? r.json() as Promise<IncomeByMonth> : null)
          .catch(() => null)
      )
    ).then((results) => {
      const map: Record<string, IncomeByMonth> = {};
      results.forEach((data, i) => {
        if (data) map[portfolios[i].id] = data;
      });
      setIncomeData(map);
    }).finally(() => setLoading(false));
  }, [portfolios]);

  const monthName = new Date(year, month).toLocaleString("en-US", { month: "long", year: "numeric" });
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDow = new Date(year, month, 1).getDay();
  const calMonthNum = month + 1; // 1-indexed

  // Collect per-day events from position data
  interface CalEvent {
    symbol: string;
    name: string;
    amount: number;
    frequency: string;
    portfolio_id: string;
  }

  const eventsByDay = useMemo(() => {
    const map: Record<number, CalEvent[]> = {};

    const targetPortfolios = filterPortfolioId === "all"
      ? portfolios
      : portfolios.filter((p) => p.id === filterPortfolioId);

    for (const p of targetPortfolios) {
      const data = incomeData[p.id];
      if (!data) continue;
      for (const pos of data.positions) {
        const amt = pos.monthly[calMonthNum];
        if (!amt) continue;

        // Use actual ex_div or pay date if available and matches this month/year
        let day: number | null = null;
        const dateStr = dateMode === "ex_date" ? pos.ex_div_date : pos.pay_date;
        if (dateStr) {
          const d = new Date(dateStr);
          if (d.getFullYear() === year && d.getMonth() + 1 === calMonthNum) {
            day = d.getDate();
          }
        }
        // Fall back to frequency-based approximation
        if (!day) {
          const approx = pos.frequency === "Monthly" ? 15
            : pos.frequency === "Quarterly" ? 20
            : pos.frequency === "Semi-Annual" ? 20
            : 28;
          day = Math.min(approx, daysInMonth);
        }

        if (!map[day]) map[day] = [];
        map[day].push({ symbol: pos.symbol, name: pos.name, amount: amt, frequency: pos.frequency, portfolio_id: p.id });
      }
    }
    return map;
  }, [incomeData, filterPortfolioId, portfolios, calMonthNum, daysInMonth, dateMode, year]);

  const totalThisMonth = useMemo(() => {
    return Object.values(eventsByDay).flat().reduce((s, e) => s + e.amount, 0);
  }, [eventsByDay]);

  // Next month total
  const totalNextMonth = useMemo(() => {
    const nm = calMonthNum === 12 ? 1 : calMonthNum + 1;
    let total = 0;
    const targetPortfolios = filterPortfolioId === "all"
      ? portfolios
      : portfolios.filter((p) => p.id === filterPortfolioId);
    for (const p of targetPortfolios) {
      const data = incomeData[p.id];
      if (!data) continue;
      for (const pos of data.positions) {
        total += pos.monthly[nm] || 0;
      }
    }
    return total;
  }, [incomeData, filterPortfolioId, portfolios, calMonthNum]);

  const portfolioTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    Object.values(eventsByDay).flat().forEach((e) => {
      totals[e.portfolio_id] = (totals[e.portfolio_id] || 0) + e.amount;
    });
    return totals;
  }, [eventsByDay]);

  const today = new Date();
  const prevMonth = () => { if (month === 0) { setMonth(11); setYear(year - 1); } else setMonth(month - 1); };
  const nextMonth = () => { if (month === 11) { setMonth(0); setYear(year + 1); } else setMonth(month + 1); };

  const isEmpty = portfolios.length === 0 || Object.keys(incomeData).length === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Income Calendar</h1>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {isEmpty && !loading ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-card py-16 text-center">
          <p className="text-sm font-medium">No income data yet</p>
          <p className="mt-1 text-xs text-muted-foreground">Upload a portfolio with positions to populate the calendar.</p>
        </div>
      ) : (
        <>
          {/* Income strip */}
          <div className="flex gap-6 text-sm">
            <span>This month: <strong className="tabular-nums text-income">{formatCurrency(totalThisMonth)}</strong></span>
            <span>Next month: <strong className="tabular-nums text-muted-foreground">{formatCurrency(totalNextMonth)}</strong></span>
          </div>

          {/* Controls */}
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <button onClick={prevMonth} className="rounded-md border border-border p-1.5 hover:bg-secondary transition-colors">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="w-40 text-center text-sm font-medium">{monthName}</span>
              <button onClick={nextMonth} className="rounded-md border border-border p-1.5 hover:bg-secondary transition-colors">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <select
                value={filterPortfolioId}
                onChange={(e) => setFilterPortfolioId(e.target.value)}
                className="rounded-md border border-border bg-secondary px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="all">All Portfolios</option>
                {portfolios.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>

              <div className="flex gap-1 rounded-lg border border-border bg-secondary p-0.5">
                {(["ex_date", "pay_date"] as DateMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setDateMode(m)}
                    className={cn(
                      "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                      dateMode === m ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
                    )}
                  >
                    {m === "ex_date" ? "Ex-Date" : "Pay Date"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Portfolio legend */}
          {portfolios.length > 1 && (
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border bg-card px-4 py-2.5">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mr-1">Portfolios</span>
              {portfolios.map((p, i) => {
                const color = PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length];
                const total = portfolioTotals[p.id] || 0;
                return (
                  <button
                    key={p.id}
                    onClick={() => setFilterPortfolioId(filterPortfolioId === p.id ? "all" : p.id)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs transition-all",
                      filterPortfolioId === p.id ? "ring-2 ring-offset-1 ring-offset-card" : "opacity-80 hover:opacity-100"
                    )}
                    style={{ backgroundColor: `${color}18`, border: `1px solid ${color}40` }}
                  >
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span className="font-medium">{p.name}</span>
                    {total > 0 && <span className="tabular-nums text-muted-foreground">{formatCurrency(total)}</span>}
                  </button>
                );
              })}
              {filterPortfolioId !== "all" && (
                <button onClick={() => setFilterPortfolioId("all")} className="text-[11px] text-primary hover:underline ml-auto">
                  Show all
                </button>
              )}
            </div>
          )}

          {/* Calendar grid */}
          <div className="rounded-lg border border-border bg-card">
            <div className="grid grid-cols-7 border-b border-border">
              {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
                <div key={d} className="px-2 py-2 text-center text-[11px] font-medium text-muted-foreground">{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {Array.from({ length: firstDow }, (_, i) => (
                <div key={`empty-${i}`} className="min-h-20 border-b border-r border-border bg-secondary/30" />
              ))}
              {Array.from({ length: daysInMonth }, (_, i) => {
                const day = i + 1;
                const events = eventsByDay[day] || [];
                const isToday = day === today.getDate() && month === today.getMonth() && year === today.getFullYear();
                const dayTotal = events.reduce((s, e) => s + e.amount, 0);
                return (
                  <div
                    key={day}
                    className={cn("min-h-20 border-b border-r border-border p-1.5", isToday && "bg-primary/5")}
                  >
                    <div className="flex items-start justify-between mb-0.5">
                      <span className={cn(
                        "inline-block text-[11px] tabular-nums",
                        isToday ? "rounded-full bg-primary px-1.5 text-primary-foreground font-bold" : "text-muted-foreground"
                      )}>
                        {day}
                      </span>
                      {dayTotal > 0 && (
                        <span className="text-[9px] tabular-nums text-income font-medium">{formatCurrency(dayTotal)}</span>
                      )}
                    </div>
                    <div className="space-y-0.5">
                      {events.map((e, idx) => {
                        const color = portfolioColorMap[e.portfolio_id] || PORTFOLIO_COLORS[0];
                        return (
                          <div
                            key={`${e.symbol}-${idx}`}
                            className="flex items-center gap-1 rounded px-1 py-0.5 text-[10px]"
                            style={{ backgroundColor: `${color}18`, borderLeft: `2px solid ${color}` }}
                            title={`${e.symbol} · ${e.frequency} · ${portfolios.find((p) => p.id === e.portfolio_id)?.name || ""}`}
                          >
                            <span className="font-mono font-medium">{e.symbol}</span>
                            <span className="ml-auto tabular-nums text-muted-foreground">${e.amount.toFixed(0)}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground text-center">
            Uses actual ex-div / pay dates when available · Falls back to frequency-based estimate · Updates after market data refresh
          </p>
        </>
      )}
    </div>
  );
}
