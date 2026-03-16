"use client";

import { useState, useMemo } from "react";
import { TickerBadge } from "@/components/ticker-badge";
import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { DividendEvent } from "@/lib/types";
import { usePortfolio } from "@/lib/portfolio-context";

// Portfolio color palette — index matches portfolio order
const PORTFOLIO_COLORS = ["#3b82f6", "#8b5cf6", "#f59e0b", "#10b981", "#06b6d4", "#ef4444"];

// Asset type colors (for legend secondary info)
const ASSET_COLORS: Record<string, string> = {
  BDC: "#06b6d4", CEF: "#f59e0b", MLP: "#10b981", ETF: "#64748b",
  "Common Stock": "#3b82f6", Preferred: "#8b5cf6", Bond: "#a78bfa",
};

interface PortfolioDividendEvent extends DividendEvent {
  portfolio_id: string;
}

const MOCK_EVENTS: PortfolioDividendEvent[] = [
  { symbol: "O",    asset_type: "Common Stock", ex_date: "2026-03-02", pay_date: "2026-03-15", amount: 45.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "MAIN", asset_type: "BDC",          ex_date: "2026-03-05", pay_date: "2026-03-15", amount: 72.5,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "PFF",  asset_type: "ETF",          ex_date: "2026-03-06", pay_date: "2026-03-12", amount: 55.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "EPD",  asset_type: "MLP",          ex_date: "2026-03-10", pay_date: "2026-03-25", amount: 95.0,  frequency: "Quarterly", portfolio_id: "p1" },
  { symbol: "ARCC", asset_type: "BDC",          ex_date: "2026-03-14", pay_date: "2026-03-31", amount: 120.0, frequency: "Quarterly", portfolio_id: "p2" },
  { symbol: "PDI",  asset_type: "CEF",          ex_date: "2026-03-15", pay_date: "2026-04-01", amount: 72.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "SCHD", asset_type: "ETF",          ex_date: "2026-03-17", pay_date: "2026-03-21", amount: 38.0,  frequency: "Quarterly", portfolio_id: "p2" },
  { symbol: "VYM",  asset_type: "ETF",          ex_date: "2026-03-18", pay_date: "2026-03-21", amount: 52.0,  frequency: "Quarterly", portfolio_id: "p3" },
  { symbol: "GOF",  asset_type: "CEF",          ex_date: "2026-03-20", pay_date: "2026-03-31", amount: 63.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "ET",   asset_type: "MLP",          ex_date: "2026-03-22", pay_date: "2026-04-10", amount: 105.0, frequency: "Quarterly", portfolio_id: "p1" },
  { symbol: "HTGC", asset_type: "BDC",          ex_date: "2026-03-28", pay_date: "2026-04-15", amount: 88.0,  frequency: "Quarterly", portfolio_id: "p2" },
  { symbol: "JEPI", asset_type: "ETF",          ex_date: "2026-03-28", pay_date: "2026-04-04", amount: 67.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "NNN",  asset_type: "Common Stock", ex_date: "2026-03-28", pay_date: "2026-04-15", amount: 42.0,  frequency: "Quarterly", portfolio_id: "p3" },
  { symbol: "O",    asset_type: "Common Stock", ex_date: "2026-04-01", pay_date: "2026-04-15", amount: 45.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "MAIN", asset_type: "BDC",          ex_date: "2026-04-03", pay_date: "2026-04-15", amount: 72.5,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "PFF",  asset_type: "ETF",          ex_date: "2026-04-06", pay_date: "2026-04-12", amount: 55.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "JEPQ", asset_type: "ETF",          ex_date: "2026-04-08", pay_date: "2026-04-11", amount: 58.0,  frequency: "Monthly",   portfolio_id: "p1" },
  { symbol: "MPLX", asset_type: "MLP",          ex_date: "2026-04-10", pay_date: "2026-04-15", amount: 82.0,  frequency: "Quarterly", portfolio_id: "p1" },
  { symbol: "VICI", asset_type: "Common Stock", ex_date: "2026-04-15", pay_date: "2026-04-25", amount: 48.0,  frequency: "Quarterly", portfolio_id: "p2" },
];

type DateMode = "ex_date" | "pay_date";

export default function CalendarPage() {
  const { portfolios } = usePortfolio();
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(2); // 0-indexed, 2 = March
  const [dateMode, setDateMode] = useState<DateMode>("ex_date");
  const [filterPortfolio, setFilterPortfolio] = useState<string>("all");

  const monthName = new Date(year, month).toLocaleString("en-US", { month: "long", year: "numeric" });
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDow = new Date(year, month, 1).getDay();

  // Portfolio color map (stable — index-based)
  const portfolioColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    portfolios.forEach((p, i) => { map[p.id] = PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length]; });
    return map;
  }, [portfolios]);

  const eventsThisMonth = useMemo(() => {
    return MOCK_EVENTS.filter((e) => {
      const d = new Date(e[dateMode]);
      const matchDate = d.getFullYear() === year && d.getMonth() === month;
      const matchPortfolio = filterPortfolio === "all" || e.portfolio_id === filterPortfolio;
      return matchDate && matchPortfolio;
    });
  }, [year, month, dateMode, filterPortfolio]);

  const eventsByDay = useMemo(() => {
    const map: Record<number, PortfolioDividendEvent[]> = {};
    eventsThisMonth.forEach((e) => {
      const day = new Date(e[dateMode]).getDate();
      if (!map[day]) map[day] = [];
      map[day].push(e);
    });
    return map;
  }, [eventsThisMonth, dateMode]);

  const totalThisMonth = eventsThisMonth.reduce((s, e) => s + e.amount, 0);

  const nextMonthEvents = MOCK_EVENTS.filter((e) => {
    const nm = month === 11 ? 0 : month + 1;
    const ny = month === 11 ? year + 1 : year;
    const d = new Date(e[dateMode]);
    const matchPortfolio = filterPortfolio === "all" || e.portfolio_id === filterPortfolio;
    return d.getFullYear() === ny && d.getMonth() === nm && matchPortfolio;
  });
  const totalNextMonth = nextMonthEvents.reduce((s, e) => s + e.amount, 0);

  const prevMonth = () => { if (month === 0) { setMonth(11); setYear(year - 1); } else setMonth(month - 1); };
  const nextMonth = () => { if (month === 11) { setMonth(0); setYear(year + 1); } else setMonth(month + 1); };

  // Per-portfolio totals for this month
  const portfolioTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    eventsThisMonth.forEach((e) => {
      totals[e.portfolio_id] = (totals[e.portfolio_id] || 0) + e.amount;
    });
    return totals;
  }, [eventsThisMonth]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Income Calendar</h1>

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
          {/* Portfolio filter */}
          <select
            value={filterPortfolio}
            onChange={(e) => setFilterPortfolio(e.target.value)}
            className="rounded-md border border-border bg-secondary px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Portfolios</option>
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          {/* Ex-date / Pay-date toggle */}
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

      {/* ── Portfolio Legend ── */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border bg-card px-4 py-2.5">
        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mr-1">Portfolios</span>
        {portfolios.map((p, i) => {
          const color = PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length];
          const total = portfolioTotals[p.id] || 0;
          return (
            <button
              key={p.id}
              onClick={() => setFilterPortfolio(filterPortfolio === p.id ? "all" : p.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs transition-all",
                filterPortfolio === p.id ? "ring-2 ring-offset-1 ring-offset-card" : "opacity-80 hover:opacity-100"
              )}
              style={{
                backgroundColor: `${color}18`,
                borderColor: color,
                border: `1px solid ${color}40`,
                ringColor: color,
              } as React.CSSProperties}
            >
              <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className="font-medium">{p.name}</span>
              {total > 0 && (
                <span className="tabular-nums text-muted-foreground">{formatCurrency(total)}</span>
              )}
            </button>
          );
        })}
        {filterPortfolio !== "all" && (
          <button
            onClick={() => setFilterPortfolio("all")}
            className="text-[11px] text-primary hover:underline ml-auto"
          >
            Show all
          </button>
        )}
      </div>

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
            const isToday = day === 16 && month === 2 && year === 2026;
            const dayTotal = events.reduce((s, e) => s + e.amount, 0);
            return (
              <div
                key={day}
                className={cn(
                  "min-h-20 border-b border-r border-border p-1.5",
                  isToday && "bg-primary/5"
                )}
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
                  {events.map((e) => {
                    const color = portfolioColorMap[e.portfolio_id] || PORTFOLIO_COLORS[0];
                    return (
                      <div
                        key={`${e.symbol}-${e.portfolio_id}-${day}`}
                        className="flex items-center gap-1 rounded px-1 py-0.5 text-[10px]"
                        style={{ backgroundColor: `${color}18`, borderLeft: `2px solid ${color}` }}
                        title={`${e.symbol} — ${portfolios.find(p => p.id === e.portfolio_id)?.name || e.portfolio_id}`}
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

      {/* Asset type reference */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {Object.entries(ASSET_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <span className="h-2 w-2 rounded-sm shrink-0" style={{ backgroundColor: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
