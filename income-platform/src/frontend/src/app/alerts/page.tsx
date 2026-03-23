"use client";

import { useState, useCallback, useEffect } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { AlertBadge } from "@/components/alert-badge";
import { formatDateTime } from "@/lib/utils";
import type { Alert } from "@/lib/types";
import { usePortfolio } from "@/lib/portfolio-context";
import { apiGet } from "@/lib/api";

export default function AlertsPage() {
  const router = useRouter();
  const { portfolios } = usePortfolio();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const portfolioId = portfolios[0]?.id;
    if (!portfolioId) return;
    setLoading(true);
    apiGet<{ alerts: Alert[] } | Alert[]>(`/api/alerts?portfolio_id=${portfolioId}&status=ACTIVE`)
      .then((data) => {
        const list = Array.isArray(data) ? data : (data as { alerts: Alert[] }).alerts ?? [];
        setAlerts(list);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [portfolios]);

  const resolveAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, status: "RESOLVED" as const } : a));
  }, []);

  const columns: ColumnDef<Alert>[] = [
    {
      accessorKey: "severity",
      header: "Severity",
      cell: ({ getValue }) => <AlertBadge severity={getValue<string>()} />,
    },
    {
      accessorKey: "symbol",
      header: "Symbol",
      cell: ({ getValue }) => (
        <button onClick={() => router.push(`/portfolio/${getValue<string>()}`)} className="hover:underline">
          <TickerBadge symbol={getValue<string>()} />
        </button>
      ),
    },
    { accessorKey: "alert_type", header: "Type" },
    { accessorKey: "description", header: "Description" },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ getValue }) => {
        const s = getValue<string>();
        return (
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              s === "ACTIVE" ? "bg-red-400/10 text-red-400" : "bg-emerald-400/10 text-emerald-400"
            }`}
          >
            {s}
          </span>
        );
      },
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ getValue }) => (
        <span className="text-muted-foreground tabular-nums text-xs">{formatDateTime(getValue<string>())}</span>
      ),
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      enableHiding: false,
      cell: ({ row }) =>
        row.original.status === "ACTIVE" ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => resolveAlert(row.original.id)}
              className="rounded-md border border-border bg-secondary px-2.5 py-1 text-xs font-medium hover:bg-accent transition-colors"
            >
              Resolve
            </button>
            <button
              onClick={() => router.push(`/portfolio/${row.original.symbol}`)}
              className="rounded-md border border-border bg-secondary px-2.5 py-1 text-xs font-medium hover:bg-accent transition-colors"
            >
              View
            </button>
          </div>
        ) : null,
    },
  ];

  const activeCount = alerts.filter((a) => a.status === "ACTIVE").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Alerts</h1>
        <span className="text-sm text-muted-foreground">{activeCount} active · Alerts are per-symbol (all portfolios)</span>
      </div>
      {loading && (
        <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          Loading alerts...
        </div>
      )}
      {error && !loading && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}
      <DataTable columns={columns} data={alerts} storageKey="alerts" />
    </div>
  );
}
