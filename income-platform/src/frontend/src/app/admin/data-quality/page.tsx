// src/frontend/src/app/admin/data-quality/page.tsx
"use client";

import { useEffect, useState } from "react";
import type { DataQualityIssue } from "@/lib/types";

async function fetchIssues(params: Record<string, string>): Promise<DataQualityIssue[]> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api/data-quality/issues?${qs}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.issues ?? [];
}

const SEVERITY_OPTIONS = ["", "critical", "warning"] as const;
const STATUS_OPTIONS = ["", "missing", "fetching", "resolved", "unresolvable"] as const;

export default function DataQualityPage() {
  const [issues, setIssues] = useState<DataQualityIssue[]>([]);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("missing");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (severity) params.severity = severity;
    if (status) params.status = status;
    const data = await fetchIssues(params);
    setIssues(data);
    setLoading(false);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [severity, status]);

  const critical = issues.filter((i) => i.severity === "critical");
  const warnings = issues.filter((i) => i.severity === "warning");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-foreground">Data Quality</h1>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Critical Issues" value={critical.length} color="text-red-600 dark:text-red-400" />
        <KpiCard label="Warnings" value={warnings.length} color="text-amber-600 dark:text-amber-400" />
        <KpiCard
          label="Unresolvable"
          value={issues.filter((i) => i.status === "unresolvable").length}
          color="text-muted-foreground"
        />
        <KpiCard
          label="Resolved (shown)"
          value={issues.filter((i) => i.status === "resolved").length}
          color="text-emerald-600 dark:text-emerald-400"
        />
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          className="rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          aria-label="Filter by severity"
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All severities"}</option>
          ))}
        </select>
        <select
          className="rounded border border-border bg-background px-3 py-1.5 text-sm text-foreground"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All statuses"}</option>
          ))}
        </select>
        <button
          className="rounded border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted"
          onClick={load}
        >
          Refresh
        </button>
      </div>

      {/* Issues table */}
      {loading ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : issues.length === 0 ? (
        <p className="text-muted-foreground text-sm">No issues found.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                {["Ticker", "Class", "Field", "Severity", "Status", "Attempts", "Diagnostic", "Actions"].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {issues.map((issue) => (
                <IssueRow key={issue.id} issue={issue} onAction={load} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function IssueRow({ issue, onAction }: { issue: DataQualityIssue; onAction: () => void }) {
  const [actioning, setActioning] = useState(false);

  const action = async (endpoint: string) => {
    setActioning(true);
    await fetch(`/api/data-quality/issues/${issue.id}/${endpoint}`, { method: "POST" });
    setActioning(false);
    onAction();
  };

  const diagCode = (issue.diagnostic as Record<string, string> | null)?.code ?? "—";

  return (
    <tr className="hover:bg-muted/50">
      <td className="px-3 py-2 font-mono font-medium text-foreground">{issue.symbol}</td>
      <td className="px-3 py-2 text-muted-foreground">{issue.asset_class}</td>
      <td className="px-3 py-2 font-mono text-foreground">{issue.field_name}</td>
      <td className="px-3 py-2">
        <span className={`font-medium ${issue.severity === "critical" ? "text-red-600 dark:text-red-400" : "text-amber-600 dark:text-amber-400"}`}>
          {issue.severity}
        </span>
      </td>
      <td className="px-3 py-2 text-muted-foreground">{issue.status}</td>
      <td className="px-3 py-2 text-center text-muted-foreground">{issue.attempt_count}</td>
      <td className="px-3 py-2" title={JSON.stringify(issue.diagnostic, null, 2)}>
        <span className="cursor-help font-mono text-xs text-muted-foreground">{diagCode}</span>
      </td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button
            disabled={actioning}
            onClick={() => action("retry")}
            className="text-xs text-blue-600 hover:underline dark:text-blue-400 disabled:opacity-50"
          >
            Retry
          </button>
          <button
            disabled={actioning}
            onClick={() => action("mark-na")}
            className="text-xs text-muted-foreground hover:underline disabled:opacity-50"
          >
            Mark N/A
          </button>
          <button
            disabled={actioning}
            onClick={() => action("reclassify")}
            className="text-xs text-muted-foreground hover:underline disabled:opacity-50"
          >
            Reclassify
          </button>
        </div>
      </td>
    </tr>
  );
}
