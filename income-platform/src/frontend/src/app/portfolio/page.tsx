"use client";

import { type ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { ScorePill } from "@/components/score-pill";
import { AlertBadge } from "@/components/alert-badge";
import { MetricCard } from "@/components/metric-card";
import { usePortfolio } from "@/lib/portfolio-context";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ASSET_CLASS_COLORS, API_BASE_URL } from "@/lib/config";
import type { Position } from "@/lib/types";
import { Search, DollarSign, TrendingUp, BarChart3, Activity, Plus, Pencil, Trash2, Upload, X, Check, Download, Wallet, RefreshCw, ChevronLeft, ChevronRight, SlidersHorizontal } from "lucide-react";
import { apiPost } from "@/lib/api";
import { useState, useMemo, useEffect, useRef, Suspense, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { type MarketData } from "@/lib/mock-portfolio-data";
import { VulnerabilityContent } from "@/app/vulnerability/page";
import { StressTestContent } from "@/app/stress-test/page";
import { SimulationContent } from "@/app/income-simulation/page";


type PortfolioTab = "summary" | "positions" | "health" | "market" | "vulnerability" | "stress-test" | "simulation";

const TAB_LABELS: Record<PortfolioTab, string> = {
  summary: "Summary",
  positions: "Holdings",
  health: "Health",
  market: "Market",
  vulnerability: "Vulnerability",
  "stress-test": "Stress Test",
  simulation: "Simulation",
};

const ASSET_TYPES = [
  "CEF",
  "COVERED_CALL_ETF",
  "BDC",
  "MORTGAGE_REIT",
  "EQUITY_REIT",
  "DIVIDEND_STOCK",
  "PREFERRED_STOCK",
  "BOND",
  "Common Stock",
  "UNKNOWN",
];
const FREQUENCIES = ["Monthly", "Quarterly", "Semi-Annual", "Annual"];

const positionColumns: ColumnDef<Position>[] = [
  {
    accessorKey: "symbol",
    header: "Symbol",
    cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
  },
  { accessorKey: "name", header: "Name" },
  {
    accessorKey: "asset_type",
    header: "Type",
    cell: ({ getValue }) => (
      <span className="rounded bg-secondary px-1.5 py-0.5 text-[11px] font-medium">{getValue<string>()}</span>
    ),
  },
  {
    accessorKey: "shares",
    header: "Shares",
    cell: ({ getValue }) => <span className="tabular-nums">{getValue<number>().toLocaleString()}</span>,
  },
  {
    accessorKey: "cost_basis",
    header: "Cost Basis",
    cell: ({ getValue }) => <span className="tabular-nums">{formatCurrency(getValue<number>())}</span>,
  },
  {
    accessorKey: "current_value",
    header: "Value",
    cell: ({ getValue }) => <span className="tabular-nums">{formatCurrency(getValue<number>())}</span>,
  },
  {
    id: "gain_loss",
    header: "Gain/Loss",
    accessorFn: (row) => row.current_value - row.cost_basis,
    cell: ({ row }) => {
      const gain = row.original.current_value - row.original.cost_basis;
      const pct = row.original.cost_basis > 0 ? (gain / row.original.cost_basis) * 100 : 0;
      return (
        <div>
          <span className={cn("tabular-nums text-sm", gain >= 0 ? "text-income" : "text-loss")}>
            {gain >= 0 ? "+" : ""}{formatCurrency(gain)}
          </span>
          <span className={cn("ml-1.5 text-[11px] tabular-nums", gain >= 0 ? "text-income/70" : "text-loss/70")}>
            ({pct >= 0 ? "+" : ""}{pct.toFixed(1)}%)
          </span>
        </div>
      );
    },
  },
  {
    accessorKey: "annual_income",
    header: "Income",
    cell: ({ getValue }) => <span className="tabular-nums text-income">{formatCurrency(getValue<number>())}</span>,
  },
  {
    accessorKey: "yield_on_cost",
    header: "YoC %",
    cell: ({ getValue }) => <span className="tabular-nums">{formatPercent(getValue<number>())}</span>,
  },
  {
    id: "weight",
    header: "Weight",
    accessorFn: (row) => row.current_value,
    cell: ({ row, table }) => {
      const total = table.getRowModel().rows.reduce((s, r) => s + r.original.current_value, 0);
      const pct = total > 0 ? (row.original.current_value / total) * 100 : 0;
      return <span className="tabular-nums text-xs">{pct.toFixed(1)}%</span>;
    },
  },
  {
    accessorKey: "score",
    header: "Score",
    cell: ({ getValue }) => {
      const v = getValue<number | undefined>();
      return v !== undefined ? <ScorePill score={v} /> : <span className="text-muted-foreground">—</span>;
    },
  },
  {
    accessorKey: "alert_count",
    header: "Alerts",
    enableSorting: false,
    cell: ({ getValue }) => {
      const c = getValue<number>();
      return c > 0 ? <AlertBadge severity="HIGH" count={c} /> : <span className="text-muted-foreground">—</span>;
    },
  },
  { accessorKey: "sector", header: "Sector" },
  { accessorKey: "industry", header: "Industry" },
  {
    accessorKey: "dividend_frequency",
    header: "Freq",
    cell: ({ getValue }) => {
      const v = getValue<string>();
      if (!v) return <span className="text-muted-foreground">—</span>;
      const short: Record<string, string> = { Monthly: "Mo", Quarterly: "Qtr", "Semi-Annual": "Semi", Annual: "Ann" };
      return <span className="text-xs">{short[v] ?? v}</span>;
    },
  },
  {
    accessorKey: "current_yield",
    header: "Curr Yield",
    meta: { defaultHidden: false },
    cell: ({ getValue }) => {
      const v = getValue<number | undefined>();
      return v !== undefined ? <span className="tabular-nums text-income">{v.toFixed(2)}%</span> : <span className="text-muted-foreground">—</span>;
    },
  },
  {
    accessorKey: "market_price",
    header: "Mkt Price",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | undefined>();
      return v !== undefined ? <span className="tabular-nums">{formatCurrency(v)}</span> : <span className="text-muted-foreground">—</span>;
    },
  },
  {
    accessorKey: "avg_cost",
    header: "Avg Cost",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | undefined>();
      return v !== undefined ? <span className="tabular-nums">{formatCurrency(v)}</span> : <span className="text-muted-foreground">—</span>;
    },
  },
  { accessorKey: "ex_div_date", header: "Ex-Date" },
  { accessorKey: "pay_date", header: "Pay Date" },
  {
    accessorKey: "dividend_growth_5y",
    header: "5Y Div Growth",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | undefined | null>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className={cn("tabular-nums", v >= 0 ? "text-income" : "text-loss")}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</span>;
    },
  },
  {
    accessorKey: "payout_ratio",
    header: "Payout %",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | undefined | null>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className={cn("tabular-nums", v > 100 ? "text-loss" : v > 90 ? "text-warning" : "")}>{v}%</span>;
    },
  },
  {
    accessorKey: "beta",
    header: "Beta",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null | undefined>();
      return v != null ? <span className="tabular-nums">{v.toFixed(2)}</span> : <span className="text-muted-foreground">—</span>;
    },
  },
  {
    accessorKey: "chowder_number",
    header: "Chowder",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null | undefined>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className={cn("tabular-nums font-medium", v >= 12 ? "text-income" : v >= 8 ? "text-yellow-400" : "text-red-400")}>{v.toFixed(1)}</span>;
    },
  },
  {
    accessorKey: "net_annual_income",
    header: "Net Income",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null | undefined>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className="tabular-nums text-income">{formatCurrency(v)}</span>;
    },
  },
  {
    accessorKey: "dca_stage",
    header: "DCA",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null | undefined>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className="rounded bg-blue-500/15 text-blue-400 px-1.5 py-0.5 text-[10px] font-medium">S{v}</span>;
    },
  },
  { accessorKey: "currency", header: "Currency", meta: { defaultHidden: true } },
  { accessorKey: "date_added", header: "Date Added", meta: { defaultHidden: true } },
];

const healthColumns: ColumnDef<Position>[] = [
  {
    accessorKey: "symbol",
    header: "Symbol",
    cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
  },
  { accessorKey: "name", header: "Name" },
  { accessorKey: "asset_type", header: "Type",
    cell: ({ getValue }) => <span className="rounded bg-secondary px-1.5 py-0.5 text-[11px] font-medium">{getValue<string>()}</span>,
  },
  {
    accessorKey: "score",
    header: "Score",
    cell: ({ getValue }) => {
      const v = getValue<number | undefined>();
      return v !== undefined ? <ScorePill score={v} /> : <span className="text-muted-foreground">—</span>;
    },
  },
  {
    accessorKey: "alert_count",
    header: "Alerts",
    cell: ({ getValue }) => {
      const c = getValue<number>();
      if (c > 0) return <AlertBadge severity="HIGH" count={c} />;
      return <span className="text-[11px] text-emerald-400">OK</span>;
    },
  },
  {
    id: "gain_pct",
    header: "Gain %",
    accessorFn: (row) => row.cost_basis > 0 ? ((row.current_value - row.cost_basis) / row.cost_basis) * 100 : 0,
    cell: ({ row }) => {
      const pct = row.original.cost_basis > 0 ? ((row.original.current_value - row.original.cost_basis) / row.original.cost_basis) * 100 : 0;
      return <span className={cn("tabular-nums", pct >= 0 ? "text-income" : "text-loss")}>{pct >= 0 ? "+" : ""}{pct.toFixed(1)}%</span>;
    },
  },
  {
    accessorKey: "yield_on_cost",
    header: "YoC %",
    cell: ({ getValue }) => <span className="tabular-nums">{formatPercent(getValue<number>())}</span>,
  },
  {
    accessorKey: "annual_income",
    header: "Income",
    cell: ({ getValue }) => <span className="tabular-nums text-income">{formatCurrency(getValue<number>())}</span>,
  },
  {
    id: "weight",
    header: "Weight",
    accessorFn: (row) => row.current_value,
    cell: ({ row, table }) => {
      const total = table.getRowModel().rows.reduce((s, r) => s + r.original.current_value, 0);
      const pct = total > 0 ? (row.original.current_value / total) * 100 : 0;
      const isOver = pct > 5;
      return <span className={cn("tabular-nums text-xs", isOver && "text-warning font-medium")}>{pct.toFixed(1)}%{isOver ? " !" : ""}</span>;
    },
  },
  { accessorKey: "sector", header: "Sector" },
  { accessorKey: "dividend_frequency", header: "Frequency" },
];


const marketColumns: ColumnDef<MarketData>[] = [
  {
    accessorKey: "symbol",
    header: "Symbol",
    cell: ({ row }) => <TickerBadge symbol={row.original.symbol} assetType={row.original.asset_type} />,
  },
  { accessorKey: "name", header: "Name" },
  {
    accessorKey: "price",
    header: "Price",
    cell: ({ getValue }) => <span className="tabular-nums font-medium">{formatCurrency(getValue<number>())}</span>,
  },
  {
    accessorKey: "change",
    header: "Change",
    cell: ({ row }) => (
      <div>
        <span className={cn("tabular-nums", row.original.change >= 0 ? "text-income" : "text-loss")}>
          {row.original.change >= 0 ? "+" : ""}{formatCurrency(row.original.change)}
        </span>
        <span className={cn("ml-1 text-[11px] tabular-nums", row.original.change >= 0 ? "text-income/70" : "text-loss/70")}>
          ({row.original.change_pct >= 0 ? "+" : ""}{row.original.change_pct.toFixed(2)}%)
        </span>
      </div>
    ),
  },
  { accessorKey: "volume", header: "Volume" },
  {
    id: "day_range",
    header: "Day Range",
    cell: ({ row }) => {
      const { day_low, day_high } = row.original;
      if (day_low == null || day_high == null) return <span className="text-muted-foreground">—</span>;
      return <span className="tabular-nums text-xs">{formatCurrency(day_low)} — {formatCurrency(day_high)}</span>;
    },
  },
  {
    id: "week52_range",
    header: "52W Range",
    cell: ({ row }) => {
      const { week52_low, week52_high, price } = row.original;
      if (week52_low == null || week52_high == null) return <span className="text-muted-foreground">—</span>;
      const range = week52_high - week52_low;
      const pct = range > 0 ? ((price - week52_low) / range) * 100 : 0;
      return (
        <div className="flex items-center gap-2">
          <span className="text-[10px] tabular-nums text-muted-foreground">{formatCurrency(week52_low)}</span>
          <div className="w-16 h-1.5 rounded-full bg-secondary relative">
            <div className="absolute h-1.5 rounded-full bg-primary" style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
          <span className="text-[10px] tabular-nums text-muted-foreground">{formatCurrency(week52_high)}</span>
        </div>
      );
    },
  },
  { accessorKey: "market_cap", header: "Mkt Cap" },
  {
    accessorKey: "pe_ratio",
    header: "P/E",
    cell: ({ getValue }) => {
      const v = getValue<number | null>();
      return v ? <span className="tabular-nums">{v.toFixed(1)}</span> : <span className="text-muted-foreground">—</span>;
    },
  },
  {
    accessorKey: "eps",
    header: "EPS",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className={cn("tabular-nums", v < 0 ? "text-loss" : "")}>{v < 0 ? "" : "$"}{v.toFixed(2)}</span>;
    },
  },
  {
    accessorKey: "dividend_yield",
    header: "Div Yield",
    cell: ({ getValue }) => <span className="tabular-nums text-income">{formatPercent(getValue<number>())}</span>,
  },
  {
    accessorKey: "payout_ratio",
    header: "Payout %",
    cell: ({ getValue }) => {
      const v = getValue<number | null>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className={cn("tabular-nums", v > 100 ? "text-loss" : v > 90 ? "text-warning" : "")}>{v}%</span>;
    },
  },
  {
    accessorKey: "dividend_growth_5y",
    header: "5Y Div Growth",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className={cn("tabular-nums", v >= 0 ? "text-income" : "text-loss")}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</span>;
    },
  },
  {
    id: "nav_pd",
    header: "NAV / Prem-Disc",
    meta: { defaultHidden: false },
    cell: ({ row }) => {
      const nav = row.original.nav;
      const pd = row.original.premium_discount;
      if (nav == null) return <span className="text-muted-foreground text-xs">—</span>;
      return (
        <div className="text-xs tabular-nums">
          <span className="text-muted-foreground">${nav.toFixed(2)}</span>
          {pd != null && (
            <span className={cn("ml-1.5", pd > 0 ? "text-loss" : "text-income")}>
              {pd > 0 ? "+" : ""}{pd.toFixed(1)}%
            </span>
          )}
        </div>
      );
    },
  },
  {
    accessorKey: "beta",
    header: "Beta",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => {
      const v = getValue<number | null>();
      if (v == null) return <span className="text-muted-foreground">—</span>;
      return <span className="tabular-nums">{v.toFixed(2)}</span>;
    },
  },
  {
    accessorKey: "avg_volume",
    header: "Avg Vol",
    meta: { defaultHidden: true },
    cell: ({ getValue }) => <span className="tabular-nums text-muted-foreground text-xs">{getValue<string>()}</span>,
  },
  { accessorKey: "ex_date", header: "Next Ex-Date" },
  {
    accessorKey: "last_updated",
    header: "Updated",
    cell: ({ getValue }) => <span className="text-xs text-muted-foreground">{getValue<string>()}</span>,
  },
];

// Empty position template
const emptyPosition = (portfolioId: string): Position => ({
  id: `pos-${Date.now()}`,
  portfolio_id: portfolioId,
  symbol: "",
  name: "",
  asset_type: "Common Stock",
  shares: 0,
  cost_basis: 0,
  current_value: 0,
  annual_income: 0,
  yield_on_cost: 0,
  sector: "",
  dividend_frequency: "Quarterly",
  alert_count: 0,
});

export default function PortfolioPage() {
  return (
    <Suspense fallback={<div className="p-6 text-muted-foreground">Loading...</div>}>
      <PortfolioContent />
    </Suspense>
  );
}

function PortfolioContent() {
  const router = useRouter();
  const { activePortfolio, portfolios, setActiveId, updatePortfolio, reloadPortfolios } = usePortfolio();
  const searchParams = useSearchParams();
  const qualityFilter = searchParams.get("quality");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const tabBarRef = useRef<HTMLDivElement>(null);

  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<PortfolioTab>("positions");

  // Cash editing
  const [editingCash, setEditingCash] = useState(false);
  const [cashInput, setCashInput] = useState("");

  // Broker sync
  const [syncLoading, setSyncLoading] = useState(false);
  const [lastSynced, setLastSynced] = useState<string | null>(null);

  // Portfolio settings modal
  const [showSettings, setShowSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({
    benchmark_ticker: "SCHD",
    target_yield: "",
    monthly_income_target: "",
    max_single_position_pct: "5.0",
    weight_value: 40,
    weight_safety: 40,
    weight_technicals: 20,
  });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null);

  // Seed lastSynced from portfolio's persisted last_refreshed_at
  useEffect(() => {
    if (activePortfolio?.last_refreshed_at) {
      const d = new Date(activePortfolio.last_refreshed_at);
      setLastSynced(d.toLocaleString());
    }
  }, [activePortfolio?.last_refreshed_at]);

  // Seed settings form from active portfolio
  useEffect(() => {
    if (activePortfolio) {
      setSettingsForm({
        benchmark_ticker: activePortfolio.benchmark_ticker ?? "SCHD",
        target_yield: activePortfolio.target_yield != null ? String(activePortfolio.target_yield) : "",
        monthly_income_target: activePortfolio.monthly_income_target != null ? String(activePortfolio.monthly_income_target) : "",
        max_single_position_pct: activePortfolio.max_single_position_pct != null ? String(activePortfolio.max_single_position_pct) : "5.0",
        weight_value: activePortfolio.weight_value ?? 40,
        weight_safety: activePortfolio.weight_safety ?? 40,
        weight_technicals: activePortfolio.weight_technicals ?? 20,
      });
    }
  }, [activePortfolio?.id]);

  const isBrokerLinked = activePortfolio?.sync_method === "broker_api";

  const syncBroker = async () => {
    if (!activePortfolio) return;
    setSyncLoading(true);
    try {
      if (isBrokerLinked) {
        // Broker-connected portfolio: sync positions from Alpaca
        const result = await apiPost<{ cash_balance?: number }>("/api/broker/sync", {
          broker: "alpaca",
          portfolio_id: activePortfolio.id,
        });
        if (result?.cash_balance !== undefined) {
          await updatePortfolio(activePortfolio.id, { cash_balance: result.cash_balance });
        }
      } else {
        // Manually managed portfolio: run full data refresh pipeline
        await fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/refresh`, {
          method: "POST",
          credentials: "include",
        });
      }
      await loadPositions(activePortfolio.id);
      await reloadPortfolios();
      setLastSynced(new Date().toLocaleTimeString());
    } catch { /* silent */ }
    finally { setSyncLoading(false); }
  };

  const saveSettings = async () => {
    if (!activePortfolio) return;
    const wTotal = settingsForm.weight_value + settingsForm.weight_safety + settingsForm.weight_technicals;
    if (Math.abs(wTotal - 100) > 0.5) {
      setSettingsMsg(`Weights must sum to 100 (currently ${wTotal.toFixed(0)})`);
      return;
    }
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/settings`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          benchmark_ticker: settingsForm.benchmark_ticker || null,
          target_yield: settingsForm.target_yield ? parseFloat(settingsForm.target_yield) : null,
          monthly_income_target: settingsForm.monthly_income_target ? parseFloat(settingsForm.monthly_income_target) : null,
          max_single_position_pct: settingsForm.max_single_position_pct ? parseFloat(settingsForm.max_single_position_pct) : null,
          weight_value: settingsForm.weight_value,
          weight_safety: settingsForm.weight_safety,
          weight_technicals: settingsForm.weight_technicals,
        }),
      });
      if (!res.ok) throw new Error("Save failed");
      await reloadPortfolios();
      setSettingsMsg("Saved");
      setTimeout(() => { setSettingsMsg(null); setShowSettings(false); }, 1500);
    } catch {
      setSettingsMsg("Save failed — try again");
    } finally {
      setSettingsSaving(false);
    }
  };

  // Positions — loaded from API, localStorage used for manual edits only
  const [positions, setPositions] = useState<Position[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const portfolioId = activePortfolio?.id || "";

  const loadPositions = useCallback(async (pid: string) => {
    if (!pid) return;
    setPositionsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/portfolios/${pid}/positions`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json() as Position[];
        setPositions(data);
        setPositionsLoading(false);
        return;
      }
    } catch { /* fall through */ }
    setPositions([]);
    setPositionsLoading(false);
  }, []);

  useEffect(() => {
    loadPositions(portfolioId);
  }, [portfolioId, loadPositions]);

  // Market data — loaded from cache API, filtered to active portfolio
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [marketDataDate, setMarketDataDate] = useState<string | null>(null);

  useEffect(() => {
    if (!portfolioId) return;
    fetch(`${API_BASE_URL}/api/market-data/positions?portfolio_id=${portfolioId}`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: MarketData[]) => {
        setMarketData(data);
        const d = data.find((r) => r.snapshot_date);
        if (d?.snapshot_date) setMarketDataDate(d.snapshot_date);
      })
      .catch(() => setMarketData([]));
  }, [portfolioId]);

  const persistPositions = useCallback((next: Position[]) => {
    setPositions(next);
  }, []);

  // Position editing
  const [editingPositionId, setEditingPositionId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Position>(emptyPosition(""));
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [addForm, setAddForm] = useState<Position>(emptyPosition(portfolioId));

  // CSV upload
  const [uploadResult, setUploadResult] = useState<{ added: number; updated: number } | null>(null);

  const startEdit = (pos: Position) => {
    setEditingPositionId(pos.id);
    setEditForm({ ...pos });
  };

  const saveEdit = async () => {
    if (!editingPositionId) return;
    const avg_cost_basis = Number(editForm.avg_cost ?? 0);  // cost per unit
    const qty = Number(editForm.shares ?? 0);
    const cost_basis = avg_cost_basis * qty;
    const current_price = editForm.market_price ?? (editForm.current_value && qty > 0 ? editForm.current_value / qty : avg_cost_basis);
    const current_value = qty * current_price;
    const annual_income = Number(editForm.annual_income ?? 0);
    const yoc = cost_basis > 0 ? (annual_income / cost_basis) * 100 : 0;
    const updated = { ...editForm, shares: qty, cost_basis, current_value, avg_cost: avg_cost_basis, yield_on_cost: yoc };

    try {
      await fetch(`${API_BASE_URL}/api/positions/${editingPositionId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quantity: qty,
          avg_cost_basis,
          current_price,
          annual_income,
          yield_on_cost: yoc,
          asset_type: updated.asset_type ?? "",
          sector: updated.sector ?? "",
          industry: updated.industry ?? "",
          dividend_frequency: updated.dividend_frequency ?? "",
        }),
      });
    } catch { /* fall through */ }

    const next = positions.map((p) => (p.id === editingPositionId ? updated : p));
    persistPositions(next);
    setEditingPositionId(null);
    await reloadPortfolios();
  };

  const deletePosition = async (id: string) => {
    try {
      await fetch(`${API_BASE_URL}/api/positions/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
    } catch { /* fall through — still remove locally */ }
    persistPositions(positions.filter((p) => p.id !== id));
    await reloadPortfolios();
  };

  const addPosition = async () => {
    if (!addForm.symbol.trim() || !portfolioId) return;
    const yoc = addForm.cost_basis > 0 ? (addForm.annual_income / addForm.cost_basis) * 100 : 0;
    try {
      await fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/positions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: addForm.symbol.trim().toUpperCase(),
          name: addForm.name || "",
          asset_type: addForm.asset_type || "Common Stock",
          shares: addForm.shares,
          cost_basis: addForm.cost_basis,
          current_value: addForm.current_value || addForm.cost_basis,
          annual_income: addForm.annual_income,
          yield_on_cost: yoc,
          sector: addForm.sector || "",
          dividend_frequency: addForm.dividend_frequency || "Quarterly",
        }),
      });
    } catch { /* fall through */ }
    setAddForm(emptyPosition(portfolioId));
    setShowAddPosition(false);
    await loadPositions(portfolioId);
    await reloadPortfolios();
  };

  // CSV parsing
  const handleCsvUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (ev) => {
      const text = ev.target?.result as string;
      if (!text) return;

      const lines = text.split("\n").filter((l) => l.trim());
      if (lines.length < 2) return;

      // RFC-4180 CSV parser — handles quoted fields containing commas
      const parseCsvLine = (line: string): string[] => {
        const fields: string[] = [];
        let cur = "", inQuote = false;
        for (let ci = 0; ci < line.length; ci++) {
          const ch = line[ci];
          if (ch === '"') { inQuote = !inQuote; }
          else if (ch === "," && !inQuote) { fields.push(cur.trim()); cur = ""; }
          else { cur += ch; }
        }
        fields.push(cur.trim());
        return fields;
      };

      // Parse header — normalize: lowercase, strip quotes/dollar signs/parens and contents
      const normalizeHeader = (h: string) =>
        h.toLowerCase().replace(/['"$]/g, "").replace(/\s*\(.*?\)/g, "").trim();
      const headers = parseCsvLine(lines[0]).map(normalizeHeader);

      const symbolIdx = headers.findIndex((h) => h === "symbol" || h === "ticker");
      const nameIdx   = headers.findIndex((h) => h === "name" || h === "company" || h === "description");
      const typeIdx   = headers.findIndex((h) => h === "type" || h === "asset_type" || h === "asset type");
      // Match "qty", "quantity", "shares", or anything starting with "qty"
      const sharesIdx = headers.findIndex((h) => h === "shares" || h === "quantity" || h === "qty" || h.startsWith("qty"));
      // "cost/share" and "cost per share" → treat as per-share cost (multiply by qty later)
      const costPerShareIdx = headers.findIndex((h) => h === "cost/share" || h === "cost per share" || h === "avg cost" || h === "avg_cost" || h === "average cost");
      const costTotalIdx    = headers.findIndex((h) => h === "cost_basis" || h === "cost basis" || h === "total cost" || h === "cost");
      const valueIdx  = headers.findIndex((h) => h === "current_value" || h === "value" || h === "market value" || h === "market_value");
      const incomeIdx = headers.findIndex((h) => h === "annual_income" || h === "income" || h === "annual income");
      const sectorIdx = headers.findIndex((h) => h === "sector");
      const freqIdx   = headers.findIndex((h) => h === "frequency" || h === "dividend_frequency" || h === "div frequency");

      if (symbolIdx === -1) {
        alert("CSV must have a 'Symbol' or 'Ticker' column.");
        return;
      }

      let added = 0;
      let updated = 0;
      // Only include positions from this CSV (don't carry forward all existing positions)
      const nextPositions: Position[] = [];

      for (let i = 1; i < lines.length; i++) {
        const vals = parseCsvLine(lines[i]).map((v) => v.replace(/[$,"]/g, "").trim());
        const symbol = vals[symbolIdx]?.toUpperCase();
        if (!symbol) continue;

        const parseNum = (idx: number) => idx >= 0 && vals[idx] ? parseFloat(vals[idx]) || 0 : 0;

        const qty = parseNum(sharesIdx);
        const costPerShare = parseNum(costPerShareIdx);
        // total cost_basis: prefer explicit total column, else qty × cost/share
        const costBasis = costTotalIdx >= 0 ? parseNum(costTotalIdx) : (qty > 0 && costPerShare > 0 ? Math.round(qty * costPerShare * 100) / 100 : 0);
        const currentValue = parseNum(valueIdx) || costBasis;
        const annualIncome = parseNum(incomeIdx);
        const yoc = costBasis > 0 ? (annualIncome / costBasis) * 100 : 0;

        const existing = positions.findIndex((p) => p.symbol === symbol);
        nextPositions.push({
          id: existing >= 0 ? positions[existing].id : `pos-${Date.now()}-${i}`,
          portfolio_id: portfolioId,
          symbol,
          name: nameIdx >= 0 ? vals[nameIdx] || "" : "",
          asset_type: typeIdx >= 0 ? vals[typeIdx] || "Common Stock" : "Common Stock",
          shares: qty,
          cost_basis: costBasis,
          current_value: currentValue,
          annual_income: annualIncome,
          yield_on_cost: yoc,
          sector: sectorIdx >= 0 ? vals[sectorIdx] || "" : "",
          dividend_frequency: freqIdx >= 0 ? vals[freqIdx] || "Quarterly" : "Quarterly",
          alert_count: 0,
        });
        if (existing >= 0) updated++; else added++;
      }

      // Persist to DB
      if (portfolioId && nextPositions.length > 0) {
        const payload = nextPositions.map((p) => ({
          symbol: p.symbol,
          name: p.name || "",
          asset_type: p.asset_type || "Common Stock",
          shares: p.shares,
          cost_basis: p.cost_basis,
          current_value: p.current_value || p.cost_basis,
          annual_income: p.annual_income,
          yield_on_cost: p.yield_on_cost,
          sector: p.sector || "",
          dividend_frequency: p.dividend_frequency || "Quarterly",
        }));
        try {
          await fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/positions/bulk`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
        } catch { /* fall through */ }
        await loadPositions(portfolioId);
        await reloadPortfolios();
      } else {
        persistPositions(nextPositions);
      }
      setUploadResult({ added, updated });
      setTimeout(() => setUploadResult(null), 4000);
    };
    reader.readAsText(file);
    // Reset input so same file can be uploaded again
    e.target.value = "";
  };

  // Export positions as CSV
  const exportCsv = () => {
    const headers = ["Symbol", "Name", "Type", "Shares", "Cost Basis", "Value", "Annual Income", "Sector", "Frequency"];
    const rows = positions.map((p) => [
      p.symbol, `"${p.name}"`, p.asset_type, p.shares, p.cost_basis, p.current_value,
      p.annual_income, p.sector || "", p.dividend_frequency || "",
    ].join(","));
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activePortfolio?.name || "portfolio"}-positions.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filtered = useMemo(() => {
    let result = positions;
    if (qualityFilter) {
      result = result.filter((p) => {
        if (!p.score) return qualityFilter === "low";
        if (qualityFilter === "high") return p.score >= 80;
        if (qualityFilter === "medium") return p.score >= 50 && p.score < 80;
        if (qualityFilter === "low") return p.score < 50;
        return true;
      });
    }
    if (!search) return result;
    const q = search.toLowerCase();
    return result.filter(
      (p) =>
        p.symbol.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        p.asset_type.toLowerCase().includes(q) ||
        (p.sector && p.sector.toLowerCase().includes(q))
    );
  }, [positions, search, qualityFilter]);

  const totalValue = positions.reduce((s, p) => s + p.current_value, 0);
  const totalCost = positions.reduce((s, p) => s + p.cost_basis, 0);
  const totalIncome = positions.reduce((s, p) => s + p.annual_income, 0);
  const totalGain = totalValue - totalCost;
  const avgYield = totalCost > 0 ? (totalIncome / totalCost) * 100 : 0;
  const top10 = [...positions].sort((a, b) => b.current_value - a.current_value).slice(0, 10);

  // Aggregate stats
  const portfolioBeta = useMemo(() => {
    const withBeta = positions.filter((p) => p.beta != null && p.current_value > 0);
    if (withBeta.length === 0 || totalValue === 0) return null;
    const betaTotal = withBeta.reduce((s, p) => s + (p.current_value / totalValue) * (p.beta as number), 0);
    const weightedTotal = withBeta.reduce((s, p) => s + p.current_value, 0) / totalValue;
    return betaTotal / weightedTotal;
  }, [positions, totalValue]);

  const top5IncomePct = useMemo(() => {
    if (totalIncome === 0) return 0;
    const sorted = [...positions].sort((a, b) => b.annual_income - a.annual_income).slice(0, 5);
    return (sorted.reduce((s, p) => s + p.annual_income, 0) / totalIncome) * 100;
  }, [positions, totalIncome]);

  const handleRowClick = (row: Position) => {
    if (editingPositionId) return; // Don't navigate while editing
    router.push(`/portfolio/${encodeURIComponent(row.symbol)}`);
  };

  return (
    <div className="space-y-4">
      {/* Hidden file input for CSV upload */}
      <input ref={fileInputRef} type="file" accept=".csv,.txt" className="hidden" onChange={handleCsvUpload} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{activePortfolio?.name || "Portfolio"}</h1>
          <p className="text-xs text-muted-foreground">
            {activePortfolio?.account_type} · {activePortfolio?.broker}
            {activePortfolio?.sync_method === "broker_api" && (
              <span className="ml-2 text-primary">· Auto-sync enabled</span>
            )}
            {activePortfolio?.last_synced && (
              <span className="ml-2">· Last synced: {activePortfolio.last_synced}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex flex-col items-end gap-0.5">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowSettings(true)}
                className="flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                title="Portfolio strategy settings"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Strategy
              </button>
              <button
                onClick={syncBroker}
                disabled={syncLoading}
                className="flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", syncLoading && "animate-spin")} />
                {syncLoading ? "Syncing…" : isBrokerLinked ? "Sync from Broker" : "Refresh Data"}
              </button>
            </div>
            {lastSynced && (
              <span className="text-[10px] text-muted-foreground">Updated {lastSynced}</span>
            )}
          </div>
          <select
            value={activePortfolio?.id || ""}
            onChange={(e) => setActiveId(e.target.value)}
            className="rounded-md border border-border bg-secondary px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading indicator */}
      {positionsLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCw className="h-3 w-3 animate-spin" />
          Loading positions from database…
        </div>
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-6 gap-2">
        <MetricCard label="Total Value" value={formatCurrency(totalValue, true)} icon={DollarSign} />
        <MetricCard label="Total Cost" value={formatCurrency(totalCost, true)} icon={BarChart3} />
        <MetricCard
          label="Gain/Loss"
          value={`${totalGain >= 0 ? "+" : ""}${formatCurrency(totalGain, true)}`}
          delta={`${totalGain >= 0 ? "+" : ""}${totalCost > 0 ? ((totalGain / totalCost) * 100).toFixed(1) : "0.0"}%`}
          deltaType={totalGain >= 0 ? "positive" : "negative"}
          icon={TrendingUp}
        />
        <MetricCard label="Annual Income" value={formatCurrency(totalIncome, true)} icon={DollarSign} />
        <MetricCard label="Yield on Cost" value={formatPercent(avgYield)} icon={Activity} />
        {/* Cash Balance — inline editable */}
        <div className="rounded-lg border border-border bg-card p-3 flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Wallet className="h-3.5 w-3.5 shrink-0" />
            <span>Cash Available</span>
          </div>
          {editingCash ? (
            <div className="flex items-center gap-1 mt-0.5">
              <input
                type="number"
                value={cashInput}
                onChange={(e) => setCashInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    updatePortfolio(activePortfolio?.id || "", { cash_balance: parseFloat(cashInput) || 0 });
                    setEditingCash(false);
                  }
                  if (e.key === "Escape") setEditingCash(false);
                }}
                autoFocus
                className="w-full rounded border border-border bg-secondary px-2 py-0.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <button
                onClick={() => { updatePortfolio(activePortfolio?.id || "", { cash_balance: parseFloat(cashInput) || 0 }); setEditingCash(false); }}
                className="rounded bg-primary p-0.5 text-primary-foreground"
              ><Check className="h-3 w-3" /></button>
              <button onClick={() => setEditingCash(false)} className="rounded border border-border p-0.5">
                <X className="h-3 w-3" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => { setCashInput(String(activePortfolio?.cash_balance ?? 0)); setEditingCash(true); }}
              className="text-left text-base font-semibold tabular-nums text-income hover:opacity-80 transition-opacity truncate"
              title="Click to edit cash balance"
            >
              {formatCurrency(activePortfolio?.cash_balance ?? 0, true)}
            </button>
          )}
          <span className="text-[10px] text-muted-foreground">Click to update</span>
        </div>
      </div>

      {/* Aggregate stats bar */}
      {positions.length > 0 && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-md border border-border/60 bg-secondary/30 px-4 py-2 text-xs">
          <span className="text-muted-foreground">
            Portfolio Beta:{" "}
            <strong className={cn("font-semibold",
              portfolioBeta == null ? "text-muted-foreground" :
              portfolioBeta > 1.2 ? "text-yellow-400" : portfolioBeta < 0.8 ? "text-income" : "text-foreground"
            )}>
              {portfolioBeta != null ? portfolioBeta.toFixed(2) : "—"}
            </strong>
          </span>
          <span className="text-muted-foreground">
            Wt. Avg YoC: <strong className="font-semibold text-foreground">{avgYield.toFixed(2)}%</strong>
          </span>
          <span className="text-muted-foreground">
            Top-5 Income Concentration:{" "}
            <strong className={cn("font-semibold",
              top5IncomePct >= 70 ? "text-yellow-400" : top5IncomePct >= 50 ? "text-blue-400" : "text-foreground"
            )}>
              {top5IncomePct.toFixed(0)}%
            </strong>
          </span>
          <span className="text-muted-foreground">
            Positions: <strong className="font-semibold text-foreground">{positions.length}</strong>
          </span>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="relative flex items-center border-b border-border">
        <button
          onClick={() => tabBarRef.current?.scrollBy({ left: -120, behavior: "smooth" })}
          className="shrink-0 flex items-center justify-center h-8 w-6 text-muted-foreground hover:text-foreground bg-background border-r border-border"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div ref={tabBarRef} className="flex items-center gap-4 overflow-x-auto scrollbar-hide px-2" style={{ scrollbarWidth: "none" }}>
          {(["summary", "positions", "health", "market", "vulnerability", "stress-test", "simulation"] as PortfolioTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "shrink-0 border-b-2 px-1 pb-2 text-sm font-medium transition-colors",
                tab === t ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
          {qualityFilter && (
            <a href="/portfolio" className="ml-auto text-xs text-primary hover:underline shrink-0">Clear filter</a>
          )}
        </div>
        <button
          onClick={() => tabBarRef.current?.scrollBy({ left: 120, behavior: "smooth" })}
          className="shrink-0 flex items-center justify-center h-8 w-6 text-muted-foreground hover:text-foreground bg-background border-l border-border"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* ── Summary ── */}
      {tab === "summary" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">Monthly Income Estimate</h3>
              <div className="grid grid-cols-4 gap-2">
                {["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].map((m) => (
                  <div key={m} className="rounded-md bg-secondary/50 px-2 py-1.5 text-center">
                    <p className="text-[10px] text-muted-foreground">{m}</p>
                    <p className="text-xs font-medium tabular-nums text-income">{formatCurrency(totalIncome / 12)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex justify-between border-t border-border pt-2 text-sm">
                <span className="text-muted-foreground">Total Annual</span>
                <span className="font-semibold tabular-nums text-income">{formatCurrency(totalIncome)}</span>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">Top 10 Positions by Value</h3>
              <div className="space-y-1.5">
                {top10.map((p, i) => {
                  const wPct = totalValue > 0 ? (p.current_value / totalValue) * 100 : 0;
                  return (
                    <button
                      key={p.id}
                      onClick={() => router.push(`/portfolio/${encodeURIComponent(p.symbol)}`)}
                      className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-secondary/50 transition-colors"
                    >
                      <span className="w-4 text-[10px] text-muted-foreground tabular-nums">{i + 1}</span>
                      <TickerBadge symbol={p.symbol} assetType={p.asset_type} />
                      <div className="ml-auto flex items-center gap-3">
                        <span className="text-xs tabular-nums">{formatCurrency(p.current_value, true)}</span>
                        <span className="w-12 text-right text-[11px] tabular-nums text-muted-foreground">{wPct.toFixed(1)}%</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Income Quality by Score Grade */}
          {(() => {
            const gradeMap: Record<string, { label: string; color: string; income: number; count: number }> = {
              A: { label: "A — Excellent", color: "#10b981", income: 0, count: 0 },
              B: { label: "B — Good",      color: "#3b82f6", income: 0, count: 0 },
              C: { label: "C — Fair",      color: "#f59e0b", income: 0, count: 0 },
              D: { label: "D — Weak",      color: "#f97316", income: 0, count: 0 },
              F: { label: "F — Poor",      color: "#ef4444", income: 0, count: 0 },
              "?": { label: "Unscored",    color: "#64748b", income: 0, count: 0 },
            };
            positions.forEach((p) => {
              const s = p.score ?? -1;
              const g = s >= 80 ? "A" : s >= 60 ? "B" : s >= 40 ? "C" : s >= 20 ? "D" : s >= 0 ? "F" : "?";
              gradeMap[g].income += p.annual_income;
              gradeMap[g].count += 1;
            });
            const total = Object.values(gradeMap).reduce((s, g) => s + g.income, 0);
            const grades = Object.entries(gradeMap).filter(([, g]) => g.count > 0);
            return (
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">Income Quality by Score</h3>
                <div className="space-y-2">
                  {grades.map(([key, g]) => {
                    const pct = total > 0 ? (g.income / total) * 100 : 0;
                    return (
                      <div key={key} className="flex items-center gap-3">
                        <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: g.color }} />
                        <span className="w-28 text-sm">{g.label}</span>
                        <div className="flex-1"><div className="h-1.5 rounded-full bg-secondary"><div className="h-1.5 rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: g.color }} /></div></div>
                        <span className="w-10 text-right text-xs tabular-nums">{pct.toFixed(0)}%</span>
                        <span className="w-16 text-right text-xs tabular-nums text-income">{formatCurrency(g.income, true)}</span>
                        <span className="w-8 text-right text-[10px] tabular-nums text-muted-foreground">{g.count}x</span>
                      </div>
                    );
                  })}
                </div>
                {grades.length === 0 && <p className="text-xs text-muted-foreground">No scored positions yet</p>}
              </div>
            );
          })()}

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">By Asset Type</h3>
              <div className="space-y-2">
                {Object.entries(
                  positions.reduce<Record<string, { value: number; income: number; count: number }>>((acc, p) => {
                    if (!acc[p.asset_type]) acc[p.asset_type] = { value: 0, income: 0, count: 0 };
                    acc[p.asset_type].value += p.current_value;
                    acc[p.asset_type].income += p.annual_income;
                    acc[p.asset_type].count += 1;
                    return acc;
                  }, {})
                )
                  .sort((a, b) => b[1].value - a[1].value)
                  .map(([type, data]) => {
                    const pct = totalValue > 0 ? (data.value / totalValue) * 100 : 0;
                    return (
                      <div key={type} className="flex items-center gap-3">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: ASSET_CLASS_COLORS[type] || "#64748b" }} />
                        <span className="w-28 text-sm">{type}</span>
                        <div className="flex-1"><div className="h-1.5 rounded-full bg-secondary"><div className="h-1.5 rounded-full" style={{ width: `${pct}%`, backgroundColor: ASSET_CLASS_COLORS[type] || "#64748b" }} /></div></div>
                        <span className="w-12 text-right text-xs tabular-nums">{pct.toFixed(1)}%</span>
                        <span className="w-20 text-right text-xs tabular-nums">{formatCurrency(data.value, true)}</span>
                        <span className="w-16 text-right text-xs tabular-nums text-income">{formatCurrency(data.income, true)}</span>
                      </div>
                    );
                  })}
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">By Sector</h3>
              <div className="space-y-2">
                {Object.entries(
                  positions.reduce<Record<string, { value: number; income: number; count: number }>>((acc, p) => {
                    const s = p.sector || "Other";
                    if (!acc[s]) acc[s] = { value: 0, income: 0, count: 0 };
                    acc[s].value += p.current_value;
                    acc[s].income += p.annual_income;
                    acc[s].count += 1;
                    return acc;
                  }, {})
                )
                  .sort((a, b) => b[1].value - a[1].value)
                  .map(([sector, data]) => {
                    const pct = totalValue > 0 ? (data.value / totalValue) * 100 : 0;
                    const colors: Record<string, string> = { Financials: "#3b82f6", Energy: "#10b981", "Real Estate": "#f59e0b", "Fixed Income": "#8b5cf6" };
                    return (
                      <div key={sector} className="flex items-center gap-3">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colors[sector] || "#64748b" }} />
                        <span className="w-28 text-sm">{sector}</span>
                        <div className="flex-1"><div className="h-1.5 rounded-full bg-secondary"><div className="h-1.5 rounded-full" style={{ width: `${pct}%`, backgroundColor: colors[sector] || "#64748b" }} /></div></div>
                        <span className="w-12 text-right text-xs tabular-nums">{pct.toFixed(1)}%</span>
                        <span className="w-20 text-right text-xs tabular-nums">{formatCurrency(data.value, true)}</span>
                        <span className="w-16 text-right text-xs tabular-nums text-income">{formatCurrency(data.income, true)}</span>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Positions ── */}
      {tab === "positions" && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {filtered.length} positions{qualityFilter ? ` (${qualityFilter} quality)` : ""} · Click a row to view details
            </p>
            <div className="flex items-center gap-2">
              {uploadResult && (
                <span className="text-xs text-income">
                  <Check className="inline h-3 w-3 mr-0.5" />
                  {uploadResult.added} added, {uploadResult.updated} updated
                </span>
              )}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              >
                <Upload className="h-3.5 w-3.5" /> Import CSV
              </button>
              <button
                onClick={exportCsv}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              >
                <Download className="h-3.5 w-3.5" /> Export
              </button>
              <button
                onClick={() => { setShowAddPosition(true); setAddForm(emptyPosition(portfolioId)); }}
                className="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" /> Add Position
              </button>
              <div className="relative w-60">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input type="text" placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)}
                  className="w-full rounded-md border border-border bg-secondary pl-9 pr-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
            </div>
          </div>

          {/* Add position form */}
          {showAddPosition && (
            <div className="rounded-lg border border-dashed border-primary/30 bg-card p-4 space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">New Position</h4>
              <div className="grid grid-cols-6 gap-2">
                <input value={addForm.symbol} onChange={(e) => setAddForm({ ...addForm, symbol: e.target.value.toUpperCase() })} placeholder="Symbol" autoFocus
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-ring" />
                <input value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} placeholder="Name"
                  className="col-span-2 rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
                <select value={addForm.asset_type} onChange={(e) => setAddForm({ ...addForm, asset_type: e.target.value })}
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                  {ASSET_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                <input type="number" value={addForm.shares || ""} onChange={(e) => setAddForm({ ...addForm, shares: Number(e.target.value) })} placeholder="Shares"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <input value={addForm.sector || ""} onChange={(e) => setAddForm({ ...addForm, sector: e.target.value })} placeholder="Sector"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
              </div>
              <div className="grid grid-cols-6 gap-2">
                <input type="number" step="0.01" value={addForm.cost_basis || ""} onChange={(e) => setAddForm({ ...addForm, cost_basis: Number(e.target.value) })} placeholder="Cost Basis"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <input type="number" step="0.01" value={addForm.current_value || ""} onChange={(e) => setAddForm({ ...addForm, current_value: Number(e.target.value) })} placeholder="Current Value"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <input type="number" step="0.01" value={addForm.annual_income || ""} onChange={(e) => setAddForm({ ...addForm, annual_income: Number(e.target.value) })} placeholder="Annual Income"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <select value={addForm.dividend_frequency || "Quarterly"} onChange={(e) => setAddForm({ ...addForm, dividend_frequency: e.target.value })}
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                  {FREQUENCIES.map((f) => <option key={f}>{f}</option>)}
                </select>
                <button onClick={addPosition} disabled={!addForm.symbol.trim()}
                  className="flex items-center justify-center gap-1 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                  <Check className="h-3 w-3" /> Add
                </button>
                <button onClick={() => setShowAddPosition(false)}
                  className="flex items-center justify-center gap-1 rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary">
                  <X className="h-3 w-3" /> Cancel
                </button>
              </div>
            </div>
          )}

          {/* Inline editing table */}
          {editingPositionId ? (
            <div className="rounded-lg border border-border bg-card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Editing: {editForm.symbol}
                </h4>
                <div className="flex gap-2">
                  <button onClick={saveEdit} className="flex items-center gap-1 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90">
                    <Check className="h-3 w-3" /> Save
                  </button>
                  <button onClick={() => setEditingPositionId(null)} className="flex items-center gap-1 rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary">
                    <X className="h-3 w-3" /> Cancel
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Type</p>
                  <select value={editForm.asset_type || "Common Stock"} onChange={(e) => setEditForm({ ...editForm, asset_type: e.target.value })}
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                    {ASSET_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Qty</p>
                  <input type="number" step="1" value={editForm.shares} onChange={(e) => setEditForm({ ...editForm, shares: Number(e.target.value) })} placeholder="Qty"
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Cost/Unit</p>
                  <input type="number" step="0.01" value={editForm.avg_cost ?? ""} onChange={(e) => setEditForm({ ...editForm, avg_cost: Number(e.target.value) })} placeholder="Cost per share"
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Annual Income</p>
                  <input type="number" step="0.01" value={editForm.annual_income} onChange={(e) => setEditForm({ ...editForm, annual_income: Number(e.target.value) })} placeholder="Annual Income"
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Sector</p>
                  <input value={editForm.sector || ""} onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })} placeholder="Sector"
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Industry</p>
                  <input value={editForm.industry || ""} onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })} placeholder="Industry"
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
                <div className="space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">Frequency</p>
                  <select value={editForm.dividend_frequency || "Quarterly"} onChange={(e) => setEditForm({ ...editForm, dividend_frequency: e.target.value })}
                    className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                    {FREQUENCIES.map((f) => <option key={f}>{f}</option>)}
                  </select>
                </div>
              </div>
            </div>
          ) : null}

          {/* Positions DataTable with edit/delete actions */}
          <DataTable
            columns={[
              ...positionColumns,
              {
                id: "actions",
                header: "",
                enableSorting: false,
                cell: ({ row }) => (
                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => startEdit(row.original)}
                      className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                      title="Edit position"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => { if (confirm(`Delete ${row.original.symbol}?`)) deletePosition(row.original.id); }}
                      className="rounded p-1 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 transition-colors"
                      title="Delete position"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ),
              },
            ]}
            data={filtered}
            storageKey="portfolio-positions-v2"
            onRowClick={handleRowClick}
            enableRowSelection
          />
        </>
      )}

      {/* ── Health ── */}
      {tab === "health" && (
        <>
          <p className="text-sm text-muted-foreground">All {positions.length} positions — sorted by score. Overweight positions (&gt;5%) flagged.</p>
          <DataTable columns={healthColumns} data={positions} storageKey="portfolio-health" onRowClick={handleRowClick} />
        </>
      )}

      {/* ── Market Data ── */}
      {tab === "market" && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Market data for {marketData.length} holdings — as of last cache refresh
            </p>
            {marketDataDate && (
              <span className="text-[10px] text-muted-foreground">Snapshot: {marketDataDate}</span>
            )}
          </div>
          <DataTable columns={marketColumns} data={marketData} storageKey="portfolio-market" onRowClick={(row) => router.push(`/portfolio/${encodeURIComponent(row.symbol)}`)} />
        </>
      )}

      {/* ── Vulnerability ── */}
      {tab === "vulnerability" && (
        <VulnerabilityContent defaultPortfolioId={portfolioId} />
      )}

      {/* ── Stress Test ── */}
      {tab === "stress-test" && (
        <StressTestContent defaultPortfolioId={portfolioId} />
      )}

      {/* ── Income Simulation ── */}
      {tab === "simulation" && (
        <SimulationContent defaultPortfolioId={portfolioId} />
      )}

      {/* ── Portfolio Settings Modal ── */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div>
                <h2 className="text-sm font-semibold">Portfolio Strategy Settings</h2>
                <p className="text-[11px] text-muted-foreground mt-0.5">{activePortfolio?.name}</p>
              </div>
              <button onClick={() => setShowSettings(false)} className="rounded-md p-1.5 hover:bg-secondary transition-colors">
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>

            <div className="px-5 py-4 space-y-5">
              {/* Benchmark & targets */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Targets</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Benchmark Ticker</label>
                    <input
                      type="text"
                      value={settingsForm.benchmark_ticker}
                      onChange={(e) => setSettingsForm({ ...settingsForm, benchmark_ticker: e.target.value.toUpperCase() })}
                      className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="SCHD"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Target Yield (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={settingsForm.target_yield}
                      onChange={(e) => setSettingsForm({ ...settingsForm, target_yield: e.target.value })}
                      className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="e.g. 6.0"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Monthly Income Target ($)</label>
                    <input
                      type="number"
                      step="100"
                      value={settingsForm.monthly_income_target}
                      onChange={(e) => setSettingsForm({ ...settingsForm, monthly_income_target: e.target.value })}
                      className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="e.g. 5000"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Max Single Position (%)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={settingsForm.max_single_position_pct}
                      onChange={(e) => setSettingsForm({ ...settingsForm, max_single_position_pct: e.target.value })}
                      className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="5.0"
                    />
                  </div>
                </div>
              </div>

              {/* Algorithm weights */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Scoring Weights</p>
                  <span className={cn("text-xs font-medium tabular-nums",
                    Math.abs(settingsForm.weight_value + settingsForm.weight_safety + settingsForm.weight_technicals - 100) > 0.5
                      ? "text-red-400" : "text-income"
                  )}>
                    Total: {settingsForm.weight_value + settingsForm.weight_safety + settingsForm.weight_technicals}%
                  </span>
                </div>
                <div className="space-y-3">
                  {[
                    { key: "weight_value" as const, label: "Valuation & Yield", color: "#3b82f6" },
                    { key: "weight_safety" as const, label: "Financial Durability", color: "#10b981" },
                    { key: "weight_technicals" as const, label: "Technical Entry", color: "#a78bfa" },
                  ].map(({ key, label, color }) => (
                    <div key={key} className="space-y-1.5">
                      <div className="flex justify-between">
                        <label className="text-xs text-muted-foreground">{label}</label>
                        <span className="text-xs font-medium tabular-nums">{settingsForm[key]}%</span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={100}
                        step={5}
                        value={settingsForm[key]}
                        onChange={(e) => setSettingsForm({ ...settingsForm, [key]: Number(e.target.value) })}
                        style={{ accentColor: color }}
                        className="w-full"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Save/cancel */}
              {settingsMsg && (
                <p className={cn("text-xs", settingsMsg === "Saved" ? "text-income" : "text-red-400")}>{settingsMsg}</p>
              )}
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setShowSettings(false)}
                  className="rounded-md border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-secondary transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={saveSettings}
                  disabled={settingsSaving}
                  className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  <Check className="h-3.5 w-3.5" />
                  {settingsSaving ? "Saving…" : "Save Settings"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
