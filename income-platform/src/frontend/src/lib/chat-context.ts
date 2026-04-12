// src/frontend/src/lib/chat-context.ts

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}

function serviceHeaders() {
  return { Authorization: `Bearer ${serviceToken()}` };
}

// ── Exported helpers (also used by tests) ─────────────────────────────────────

export function truncateTitle(text: string): string {
  if (text.length <= 60) return text;
  const cut = text.slice(0, 60).lastIndexOf(" ");
  return text.slice(0, cut > 0 ? cut : 60) + "...";
}

export function buildPositionSummary(positions: any[]): string {
  if (!positions.length) return "_No positions found._\n";
  let out = "Symbol | Type | HHS | Score | IES\n---|---|---|---|---\n";
  for (const p of positions) {
    const ies = p.ies_calculated
      ? (p.ies_score?.toFixed(0) ?? "—")
      : `blocked(${p.ies_blocked_reason ?? "—"})`;
    out += `${p.symbol} | ${p.asset_type ?? "—"} | ${p.hhs_status ?? "—"} | ${p.score?.toFixed(0) ?? "—"} | ${ies}\n`;
  }
  return out;
}

export function buildPortfolioSnapshot(portfolio: any, isActive: boolean): string {
  let out = `### ${portfolio.name}${isActive ? " *(active)*" : ""}\n`;
  out += `- portfolio_id: ${portfolio.id}\n`;
  out += `- Value: $${(portfolio.total_value ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  out += `, Yield: ${portfolio.blended_yield?.toFixed(1) ?? "—"}%`;
  out += `, Positions: ${portfolio.position_count ?? 0}\n`;
  if (portfolio.monthly_income_target) {
    out += `- Monthly target: $${portfolio.monthly_income_target}\n`;
  }
  return out;
}

// ── Main context assembly ──────────────────────────────────────────────────────

export interface AssembleContextOptions {
  portfolioId?: string;
  userAuthHeader: string; // forwarded from the user's request
}

export async function assembleContext(opts: AssembleContextOptions): Promise<string> {
  const userHeaders = { Authorization: opts.userAuthHeader };
  const svcHeaders = serviceHeaders();

  // Parallel fetch — failures fall back to empty arrays/nulls
  const [portfolios, memories, skills] = await Promise.all([
    fetch(`${ADMIN_PANEL_URL}/api/portfolios`, { headers: userHeaders })
      .then((r) => r.ok ? r.json() : []).catch(() => []),
    fetch(`${ADMIN_PANEL_URL}/api/chat/memories`, { headers: svcHeaders })
      .then((r) => r.ok ? r.json() : []).catch(() => []),
    fetch(`${ADMIN_PANEL_URL}/api/chat/skills`, { headers: svcHeaders })
      .then((r) => r.ok ? r.json() : []).catch(() => []),
  ]);

  const activePortfolioId = opts.portfolioId ?? portfolios[0]?.id;

  let positions: any[] = [];
  let alerts: any[] = [];
  let proposals: any[] = [];
  let scannerResults: any[] = [];

  if (activePortfolioId) {
    [positions, alerts, proposals, scannerResults] = await Promise.all([
      fetch(`${ADMIN_PANEL_URL}/api/portfolios/${activePortfolioId}/positions`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${ADMIN_PANEL_URL}/api/alerts?limit=20`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${ADMIN_PANEL_URL}/api/proposals?status=pending&limit=20`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
      fetch(`${ADMIN_PANEL_URL}/api/scanner/results?portfolio_id=${activePortfolioId}`, { headers: userHeaders })
        .then((r) => r.ok ? r.json() : []).catch(() => []),
    ]);
  }

  let ctx = "";

  // Memories
  ctx += "## User Memories\n";
  ctx += memories.length > 0
    ? memories.map((m: any) => `- [${m.category ?? "general"}] ${m.content}`).join("\n")
    : "None stored yet.";
  ctx += "\n\n";

  // Skills
  ctx += "## User Skills\n";
  ctx += skills.length > 0
    ? skills.map((s: any) => `- **${s.name}** (trigger: "${s.trigger_phrase}")\n  ${s.procedure}`).join("\n\n")
    : "None defined yet.";
  ctx += "\n\n";

  // Portfolio snapshot
  ctx += "## Portfolio Snapshot\n";
  for (const p of portfolios) {
    ctx += buildPortfolioSnapshot(p, p.id === activePortfolioId);
  }
  ctx += "\n";

  // Position summary
  if (positions.length > 0) {
    const activeName = portfolios.find((p: any) => p.id === activePortfolioId)?.name ?? "portfolio";
    ctx += `## Position Summary (${activeName})\n`;
    ctx += buildPositionSummary(positions);
    if (!opts.portfolioId && portfolios.length > 1) {
      const others = portfolios.filter((p: any) => p.id !== activePortfolioId).map((p: any) => p.name).join(", ");
      ctx += `\n_(Showing ${activeName}. Other portfolios: ${others}. Use get_position_details for any symbol.)_\n`;
    }
    ctx += "\n";
  }

  // Alerts
  if (Array.isArray(alerts) && alerts.length > 0) {
    ctx += "## Active Alerts\n";
    for (const a of alerts.slice(0, 10)) {
      ctx += `- ${a.alert_type ?? a.type ?? "ALERT"}: ${a.symbol ?? a.ticker ?? "?"} — ${a.message ?? a.description ?? ""}\n`;
    }
    ctx += "\n";
  }

  // Pending proposals
  if (Array.isArray(proposals) && proposals.length > 0) {
    ctx += "## Pending Proposals\n";
    for (const p of proposals.slice(0, 10)) {
      ctx += `- ${p.action ?? p.proposal_type ?? "?"}: ${p.ticker ?? p.symbol ?? "?"} — ${(p.rationale ?? "").slice(0, 100)}\n`;
    }
    ctx += "\n";
  }

  // Scanner results
  if (Array.isArray(scannerResults) && scannerResults.length > 0) {
    ctx += "## Recent Scanner Results\n";
    for (const r of scannerResults.slice(0, 8)) {
      ctx += `- ${r.ticker ?? r.symbol}: IES ${r.ies_score?.toFixed(0) ?? "—"} — ${(r.rationale ?? "").slice(0, 80)}\n`;
    }
    ctx += "\n";
  }

  return ctx;
}
