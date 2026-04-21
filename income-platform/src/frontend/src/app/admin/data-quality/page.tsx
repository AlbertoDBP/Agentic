// src/frontend/src/app/admin/data-quality/page.tsx
"use client";

import { useEffect, useState } from "react";
import type { DataQualityIssue } from "@/lib/types";
import { X } from "lucide-react";

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
  const [detail, setDetail] = useState<DataQualityIssue | null>(null);

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
                <IssueRow key={issue.id} issue={issue} onAction={load} onDetail={setDetail} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail panel */}
      {detail && <DetailPanel issue={detail} onClose={() => setDetail(null)} onAction={async () => { setDetail(null); await load(); }} />}
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

function IssueRow({ issue, onAction, onDetail }: { issue: DataQualityIssue; onAction: () => void; onDetail: (i: DataQualityIssue) => void }) {
  const [actioning, setActioning] = useState(false);

  const action = async (endpoint: string) => {
    setActioning(true);
    await fetch(`/api/data-quality/issues/${issue.id}/${endpoint}`, { method: "POST" });
    setActioning(false);
    onAction();
  };

  const diagCode = (issue.diagnostic as Record<string, string> | null)?.code ?? "—";

  return (
    <tr className="hover:bg-muted/50 cursor-pointer" onClick={() => onDetail(issue)}>
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
      <td className="px-3 py-2">
        <span className="font-mono text-xs text-muted-foreground">{diagCode}</span>
      </td>
      <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
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

function DetailPanel({ issue, onClose, onAction }: { issue: DataQualityIssue; onClose: () => void; onAction: () => Promise<void> }) {
  const [actioning, setActioning] = useState(false);

  const action = async (endpoint: string) => {
    setActioning(true);
    await fetch(`/api/data-quality/issues/${issue.id}/${endpoint}`, { method: "POST" });
    setActioning(false);
    await onAction();
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-md bg-card border-l border-border z-50 flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <span className="font-mono font-bold text-foreground text-base">{issue.symbol}</span>
            <span className="ml-2 text-sm text-muted-foreground">{issue.field_name}</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Summary grid */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Severity" value={issue.severity} className={issue.severity === "critical" ? "text-red-400" : "text-amber-400"} />
            <Field label="Status" value={issue.status ?? "—"} />
            <Field label="Asset Class" value={issue.asset_class ?? "—"} />
            <Field label="Attempts" value={String(issue.attempt_count ?? 0)} />
            <Field label="Created" value={fmt(issue.created_at)} />
            <Field label="Last Attempt" value={fmt(issue.last_attempted_at)} />
            {issue.source_used && <Field label="Source Used" value={issue.source_used} />}
            {issue.resolved_at && <Field label="Resolved At" value={fmt(issue.resolved_at)} />}
          </div>

          {/* Diagnostic */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">Diagnostic</p>
            {issue.diagnostic ? (
              <pre className="rounded-md bg-muted/60 border border-border p-3 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(issue.diagnostic, null, 2)}
              </pre>
            ) : (
              <p className="text-xs text-muted-foreground italic">No diagnostic data</p>
            )}
          </div>
        </div>

        {/* Actions footer */}
        <div className="px-5 py-4 border-t border-border flex gap-3">
          <button
            disabled={actioning}
            onClick={() => action("retry")}
            className="flex-1 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 disabled:opacity-50 transition-colors"
          >
            Retry
          </button>
          <button
            disabled={actioning}
            onClick={() => action("reclassify")}
            className="flex-1 rounded-md border border-border hover:bg-muted text-foreground text-sm font-medium py-2 disabled:opacity-50 transition-colors"
          >
            Reclassify
          </button>
          <button
            disabled={actioning}
            onClick={() => action("mark-na")}
            className="flex-1 rounded-md border border-border hover:bg-muted text-muted-foreground text-sm font-medium py-2 disabled:opacity-50 transition-colors"
          >
            Mark N/A
          </button>
        </div>
      </div>
    </>
  );
}

function Field({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-0.5">{label}</p>
      <p className={`text-sm font-medium text-foreground ${className ?? ""}`}>{value}</p>
    </div>
  );
}

function fmt(v: string | null | undefined): string {
  if (!v) return "—";
  try { return new Date(v).toLocaleString(); } catch { return String(v); }
}
