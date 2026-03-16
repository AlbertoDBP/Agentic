"use client";

import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table";
import { TickerBadge } from "@/components/ticker-badge";
import { AlertBadge } from "@/components/alert-badge";
import { formatDateTime } from "@/lib/utils";
import type { Alert } from "@/lib/types";

const MOCK_ALERTS: Alert[] = [
  { id: "a1", symbol: "PDI", alert_type: "NAV_EROSION", severity: "CRITICAL", status: "ACTIVE", description: "NAV declined 8.2% in 30 days, exceeding -5% threshold", created_at: "2026-03-12T14:30:00Z" },
  { id: "a2", symbol: "GOF", alert_type: "PREMIUM_SPIKE", severity: "HIGH", status: "ACTIVE", description: "Trading at 12.5% premium to NAV, above 10% threshold", created_at: "2026-03-11T09:15:00Z" },
  { id: "a3", symbol: "ARCC", alert_type: "COVERAGE_DROP", severity: "MEDIUM", status: "ACTIVE", description: "Dividend coverage ratio dropped to 1.05x from 1.18x", created_at: "2026-03-10T16:00:00Z" },
  { id: "a4", symbol: "MAIN", alert_type: "NAV_EROSION", severity: "LOW", status: "RESOLVED", description: "Minor NAV fluctuation resolved after earnings", created_at: "2026-03-08T11:00:00Z" },
  { id: "a5", symbol: "ET", alert_type: "DISTRIBUTION_CUT", severity: "MEDIUM", status: "RESOLVED", description: "Distribution growth slowed to 1% YoY", created_at: "2026-03-05T08:30:00Z" },
];

const columns: ColumnDef<Alert>[] = [
  {
    accessorKey: "severity",
    header: "Severity",
    cell: ({ getValue }) => <AlertBadge severity={getValue<string>()} />,
  },
  {
    accessorKey: "symbol",
    header: "Symbol",
    cell: ({ getValue }) => <TickerBadge symbol={getValue<string>()} />,
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
        <button className="rounded-md border border-border bg-secondary px-2.5 py-1 text-xs font-medium hover:bg-accent transition-colors">
          Resolve
        </button>
      ) : null,
  },
];

export default function AlertsPage() {
  const activeCount = MOCK_ALERTS.filter((a) => a.status === "ACTIVE").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Alerts</h1>
        <span className="text-sm text-muted-foreground">{activeCount} active</span>
      </div>
      <DataTable columns={columns} data={MOCK_ALERTS} storageKey="alerts" />
    </div>
  );
}
