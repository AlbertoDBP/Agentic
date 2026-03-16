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
import { ASSET_CLASS_COLORS } from "@/lib/config";
import type { Position } from "@/lib/types";
import { Search, DollarSign, TrendingUp, BarChart3, Activity, Plus, Pencil, Trash2, Upload, X, Check, Download, Wallet } from "lucide-react";
import { useState, useMemo, useEffect, useRef, Suspense, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { HD_POSITIONS, HD_MARKET_DATA, type MarketData } from "@/lib/mock-portfolio-data";

const MOCK_POSITIONS = HD_POSITIONS;

type PortfolioTab = "summary" | "positions" | "health" | "market";

const ASSET_TYPES = ["Common Stock", "BDC", "CEF", "MLP", "ETF", "Preferred", "Bond"];
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
  { accessorKey: "industry", header: "Industry", meta: { defaultHidden: true } },
  { accessorKey: "dividend_frequency", header: "Frequency" },
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
  { accessorKey: "last_ex_date", header: "Last Ex-Date", meta: { defaultHidden: true } },
  { accessorKey: "next_pay_date", header: "Pay Date", meta: { defaultHidden: true } },
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
      const v = getValue<number | undefined>();
      return v !== undefined ? <span className="tabular-nums">{v.toFixed(2)}</span> : <span className="text-muted-foreground">—</span>;
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

const MOCK_MARKET_DATA = HD_MARKET_DATA;

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
    cell: ({ row }) => (
      <span className="tabular-nums text-xs">
        {formatCurrency(row.original.day_low)} — {formatCurrency(row.original.day_high)}
      </span>
    ),
  },
  {
    id: "week52_range",
    header: "52W Range",
    cell: ({ row }) => {
      const pct = ((row.original.price - row.original.week52_low) / (row.original.week52_high - row.original.week52_low)) * 100;
      return (
        <div className="flex items-center gap-2">
          <span className="text-[10px] tabular-nums text-muted-foreground">{formatCurrency(row.original.week52_low)}</span>
          <div className="w-16 h-1.5 rounded-full bg-secondary relative">
            <div className="absolute h-1.5 rounded-full bg-primary" style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
          <span className="text-[10px] tabular-nums text-muted-foreground">{formatCurrency(row.original.week52_high)}</span>
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
      const v = getValue<number>();
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
  const { activePortfolio, portfolios, setActiveId, updatePortfolio } = usePortfolio();
  const searchParams = useSearchParams();
  const qualityFilter = searchParams.get("quality");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<PortfolioTab>("positions");

  // Cash editing
  const [editingCash, setEditingCash] = useState(false);
  const [cashInput, setCashInput] = useState("");

  // Persisted positions per portfolio
  const [positions, setPositions] = useState<Position[]>(MOCK_POSITIONS);
  const portfolioId = activePortfolio?.id || "p1";

  useEffect(() => {
    try {
      const saved = localStorage.getItem(`positions-${portfolioId}`);
      if (saved) setPositions(JSON.parse(saved));
      else setPositions(MOCK_POSITIONS); // fallback to mock
    } catch { setPositions(MOCK_POSITIONS); }
  }, [portfolioId]);

  const persistPositions = useCallback((next: Position[]) => {
    setPositions(next);
    localStorage.setItem(`positions-${portfolioId}`, JSON.stringify(next));
  }, [portfolioId]);

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

  const saveEdit = () => {
    if (!editingPositionId) return;
    const next = positions.map((p) => (p.id === editingPositionId ? { ...editForm } : p));
    persistPositions(next);
    setEditingPositionId(null);
  };

  const deletePosition = (id: string) => {
    persistPositions(positions.filter((p) => p.id !== id));
  };

  const addPosition = () => {
    if (!addForm.symbol.trim()) return;
    const newPos = { ...addForm, id: `pos-${Date.now()}`, portfolio_id: portfolioId };
    // Calculate YoC
    if (newPos.cost_basis > 0) {
      newPos.yield_on_cost = (newPos.annual_income / newPos.cost_basis) * 100;
    }
    persistPositions([...positions, newPos]);
    setAddForm(emptyPosition(portfolioId));
    setShowAddPosition(false);
  };

  // CSV parsing
  const handleCsvUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      if (!text) return;

      const lines = text.split("\n").filter((l) => l.trim());
      if (lines.length < 2) return;

      // Parse header
      const headers = lines[0].split(",").map((h) => h.trim().toLowerCase().replace(/['"]/g, ""));
      const symbolIdx = headers.findIndex((h) => h === "symbol" || h === "ticker");
      const nameIdx = headers.findIndex((h) => h === "name" || h === "company" || h === "description");
      const typeIdx = headers.findIndex((h) => h === "type" || h === "asset_type" || h === "asset type");
      const sharesIdx = headers.findIndex((h) => h === "shares" || h === "quantity" || h === "qty");
      const costIdx = headers.findIndex((h) => h === "cost_basis" || h === "cost basis" || h === "cost" || h === "total cost");
      const valueIdx = headers.findIndex((h) => h === "current_value" || h === "value" || h === "market value" || h === "market_value");
      const incomeIdx = headers.findIndex((h) => h === "annual_income" || h === "income" || h === "annual income");
      const sectorIdx = headers.findIndex((h) => h === "sector");
      const freqIdx = headers.findIndex((h) => h === "frequency" || h === "dividend_frequency" || h === "div frequency");

      if (symbolIdx === -1) {
        alert("CSV must have a 'Symbol' or 'Ticker' column.");
        return;
      }

      let added = 0;
      let updated = 0;
      const nextPositions = [...positions];

      for (let i = 1; i < lines.length; i++) {
        const vals = lines[i].split(",").map((v) => v.trim().replace(/['"$]/g, ""));
        const symbol = vals[symbolIdx]?.toUpperCase();
        if (!symbol) continue;

        const parseNum = (idx: number) => idx >= 0 && vals[idx] ? parseFloat(vals[idx].replace(/,/g, "")) || 0 : 0;

        const existing = nextPositions.findIndex((p) => p.symbol === symbol);
        const pos: Position = {
          id: existing >= 0 ? nextPositions[existing].id : `pos-${Date.now()}-${i}`,
          portfolio_id: portfolioId,
          symbol,
          name: nameIdx >= 0 ? vals[nameIdx] || "" : "",
          asset_type: typeIdx >= 0 ? vals[typeIdx] || "Common Stock" : "Common Stock",
          shares: parseNum(sharesIdx),
          cost_basis: parseNum(costIdx),
          current_value: parseNum(valueIdx),
          annual_income: parseNum(incomeIdx),
          yield_on_cost: 0,
          sector: sectorIdx >= 0 ? vals[sectorIdx] || "" : "",
          dividend_frequency: freqIdx >= 0 ? vals[freqIdx] || "Quarterly" : "Quarterly",
          alert_count: 0,
        };
        if (pos.cost_basis > 0) pos.yield_on_cost = (pos.annual_income / pos.cost_basis) * 100;

        if (existing >= 0) {
          nextPositions[existing] = pos;
          updated++;
        } else {
          nextPositions.push(pos);
          added++;
        }
      }

      persistPositions(nextPositions);
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

  const handleRowClick = (row: Position) => {
    if (editingPositionId) return; // Don't navigate while editing
    router.push(`/portfolio/${row.symbol}`);
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

      {/* Sub-tabs */}
      <div className="flex items-center gap-4 border-b border-border">
        {(["summary", "positions", "health", "market"] as PortfolioTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "border-b-2 px-1 pb-2 text-sm font-medium capitalize transition-colors",
              tab === t ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {t}
          </button>
        ))}
        {qualityFilter && (
          <a href="/portfolio" className="ml-auto text-xs text-primary hover:underline">Clear filter</a>
        )}
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
                      onClick={() => router.push(`/portfolio/${p.symbol}`)}
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
              <div className="grid grid-cols-6 gap-2">
                <input value={editForm.symbol} onChange={(e) => setEditForm({ ...editForm, symbol: e.target.value.toUpperCase() })} placeholder="Symbol"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-ring" />
                <input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} placeholder="Name"
                  className="col-span-2 rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
                <select value={editForm.asset_type} onChange={(e) => setEditForm({ ...editForm, asset_type: e.target.value })}
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                  {ASSET_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                <input type="number" value={editForm.shares} onChange={(e) => setEditForm({ ...editForm, shares: Number(e.target.value) })} placeholder="Shares"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <input value={editForm.sector || ""} onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })} placeholder="Sector"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
              </div>
              <div className="grid grid-cols-6 gap-2">
                <input type="number" step="0.01" value={editForm.cost_basis} onChange={(e) => setEditForm({ ...editForm, cost_basis: Number(e.target.value) })} placeholder="Cost Basis"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <input type="number" step="0.01" value={editForm.current_value} onChange={(e) => setEditForm({ ...editForm, current_value: Number(e.target.value) })} placeholder="Current Value"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <input type="number" step="0.01" value={editForm.annual_income} onChange={(e) => setEditForm({ ...editForm, annual_income: Number(e.target.value) })} placeholder="Annual Income"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring" />
                <select value={editForm.dividend_frequency || "Quarterly"} onChange={(e) => setEditForm({ ...editForm, dividend_frequency: e.target.value })}
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm">
                  {FREQUENCIES.map((f) => <option key={f}>{f}</option>)}
                </select>
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
            storageKey="portfolio-positions"
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
              Latest market data for {MOCK_MARKET_DATA.length} holdings — as of last market close
            </p>
            <span className="text-[10px] text-muted-foreground">Last updated: 2026-03-15 16:00 ET</span>
          </div>
          <DataTable columns={marketColumns} data={MOCK_MARKET_DATA} storageKey="portfolio-market" onRowClick={(row) => router.push(`/portfolio/${row.symbol}`)} />
        </>
      )}
    </div>
  );
}
