// src/frontend/src/components/portfolio/completeness-badge.tsx
import type { DataQualityIssue } from "@/lib/types";

interface CompletenessBadgeProps {
  issues: DataQualityIssue[];
}

export function CompletenessBadge({ issues }: CompletenessBadgeProps) {
  const criticalCount = issues.filter(
    (i) => i.severity === "critical" && i.status !== "resolved"
  ).length;
  const warningCount = issues.filter(
    (i) => i.severity === "warning" && i.status !== "resolved"
  ).length;
  const openCount = criticalCount + warningCount;

  if (openCount === 0) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 dark:text-emerald-400"
        title="All required data fields present"
      >
        <span aria-hidden="true">✓</span> Complete
      </span>
    );
  }

  if (criticalCount > 0) {
    const fields = issues
      .filter((i) => i.severity === "critical" && i.status !== "resolved")
      .map((i) => i.field_name)
      .join(", ");
    return (
      <a
        href="/admin/data-quality"
        className="inline-flex items-center gap-1 text-xs font-medium text-red-700 hover:underline dark:text-red-400"
        title={`Missing: ${fields}`}
      >
        <span aria-hidden="true">✕</span> {criticalCount} critical
      </a>
    );
  }

  const fields = issues
    .filter((i) => i.severity === "warning" && i.status !== "resolved")
    .map((i) => i.field_name)
    .join(", ");
  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400"
      title={`Warning: ${fields}`}
    >
      <span aria-hidden="true">⚠</span> {warningCount} warning
    </span>
  );
}
