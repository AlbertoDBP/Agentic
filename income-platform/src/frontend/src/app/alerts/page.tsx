"use client";

import { useState, useCallback } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { AlertBadge } from "@/components/alert-badge";
import { formatDateTime } from "@/lib/utils";
import type { Alert } from "@/lib/types";

const INITIAL_ALERTS: Alert[] = [];

export default function AlertsPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<Alert[]>(INITIAL_ALERTS);

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
      <DataTable columns={columns} data={alerts} storageKey="alerts" />
    </div>
  );
}
