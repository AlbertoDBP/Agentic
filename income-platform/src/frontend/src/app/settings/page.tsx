"use client";

import { useState, useEffect } from "react";
import { usePortfolio } from "@/lib/portfolio-context";
import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Save, Plus, Trash2, Check, X, Pencil, Sun, Moon, Cloud, Upload, Wifi, WifiOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

type SettingsTab = "global" | "portfolios" | "portfolio-config";

interface GlobalSettings {
  notification_email: string;
  currency: string;
  date_format: string;
  alert_severity_filter: string[];
}

interface PortfolioConfig {
  income_goal: number;
  max_position_pct: number;
  target_yield: number;
  auto_reinvest: boolean;
  tax_loss_harvesting: boolean;
  rebalance_threshold: number;
  auto_execute_proposals: boolean;
}

interface TaxProfile {
  annual_income: number;
  filing_status: string;
  state_code: string;
}

interface TtlRow {
  asset_class: string;
  ttl_days: number;
}

const TTL_ASSET_CLASSES = ["_default", "BDC", "mREIT", "REIT", "Preferred", "Stock", "CEF", "Bond"];

const DEFAULT_GLOBAL: GlobalSettings = {
  notification_email: "",
  currency: "USD",
  date_format: "MM/DD/YYYY",
  alert_severity_filter: ["CRITICAL", "HIGH", "MEDIUM"],
};

const DEFAULT_CONFIG: PortfolioConfig = {
  income_goal: 50000,
  max_position_pct: 5,
  target_yield: 7.5,
  auto_reinvest: false,
  tax_loss_harvesting: false,
  rebalance_threshold: 2,
  auto_execute_proposals: false,
};

export default function SettingsPage() {
  const { portfolios, activePortfolio, setActiveId, addPortfolio, updatePortfolio, deletePortfolio, theme, setTheme } = usePortfolio();
  const [tab, setTab] = useState<SettingsTab>("global");
  const [saved, setSaved] = useState(false);

  // Global settings — load from localStorage
  const [global, setGlobal] = useState<GlobalSettings>(DEFAULT_GLOBAL);

  // Tax profile state — saved to admin panel
  const [taxProfile, setTaxProfile] = useState<TaxProfile>({ annual_income: 100000, filing_status: "SINGLE", state_code: "" });
  const [taxSaving, setTaxSaving] = useState(false);
  const [taxError, setTaxError] = useState<string | null>(null);
  useEffect(() => {
    fetch("/api/user/preferences").then((r) => r.json()).then((d) => {
      if (d && (d.annual_income || d.filing_status)) {
        setTaxProfile({
          annual_income: d.annual_income ?? 100000,
          filing_status: d.filing_status ?? "SINGLE",
          state_code: d.state_code ?? "",
        });
      }
    }).catch(() => {/* ignore */});
  }, []);

  const saveTaxProfile = async () => {
    setTaxSaving(true);
    setTaxError(null);
    try {
      const resp = await fetch("/api/user/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(taxProfile),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Save failed");
      flash();
    } catch (err) {
      setTaxError(err instanceof Error ? err.message : String(err));
    } finally {
      setTaxSaving(false);
    }
  };

  // TTL config state
  const [ttlConfig, setTtlConfig] = useState<TtlRow[]>([]);
  const [ttlSaving, setTtlSaving] = useState(false);
  const [ttlError, setTtlError] = useState<string | null>(null);
  useEffect(() => {
    try {
      const s = localStorage.getItem("globalSettings");
      if (s) setGlobal(JSON.parse(s));
    } catch { /* ignore */ }
  }, []);

  // Per-portfolio config — load from localStorage keyed by portfolio id
  const [config, setConfig] = useState<PortfolioConfig>(DEFAULT_CONFIG);
  const [configPortfolioId, setConfigPortfolioId] = useState<string>("");

  // Initialize configPortfolioId to activePortfolio once loaded
  useEffect(() => {
    if (activePortfolio?.id && !configPortfolioId) {
      setConfigPortfolioId(activePortfolio.id);
    }
  }, [activePortfolio, configPortfolioId]);

  // Reload config whenever the selected portfolio changes
  useEffect(() => {
    if (!configPortfolioId) return;
    try {
      const s = localStorage.getItem(`portfolioConfig-${configPortfolioId}`);
      if (s) setConfig(JSON.parse(s));
      else setConfig(DEFAULT_CONFIG);
    } catch { setConfig(DEFAULT_CONFIG); }
  }, [configPortfolioId]);

  // Load TTL config
  useEffect(() => {
    fetch("/api/analyst-ideas/ttl-config")
      .then((r) => r.json())
      .then((data: TtlRow[]) => {
        if (Array.isArray(data)) setTtlConfig(data);
      })
      .catch(() => {/* silently ignore */});
  }, []);

  const getTtlDays = (assetClass: string): string => {
    const row = ttlConfig.find((r) => r.asset_class === assetClass);
    return row ? String(row.ttl_days) : "";
  };

  const setTtlDays = (assetClass: string, value: string) => {
    const days = parseInt(value, 10);
    if (isNaN(days) || days < 1) return;
    setTtlConfig((prev) => {
      const exists = prev.find((r) => r.asset_class === assetClass);
      if (exists) return prev.map((r) => r.asset_class === assetClass ? { ...r, ttl_days: days } : r);
      return [...prev, { asset_class: assetClass, ttl_days: days }];
    });
  };

  const saveTtlConfig = async () => {
    setTtlSaving(true);
    setTtlError(null);
    try {
      const resp = await fetch("/api/analyst-ideas/ttl-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ttlConfig),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail ?? "Save failed");
      flash();
    } catch (err) {
      setTtlError(err instanceof Error ? err.message : String(err));
    } finally {
      setTtlSaving(false);
    }
  };

  const saveGlobal = () => {
    localStorage.setItem("globalSettings", JSON.stringify(global));
    flash();
  };

  const saveConfig = () => {
    if (!configPortfolioId) return;
    localStorage.setItem(`portfolioConfig-${configPortfolioId}`, JSON.stringify(config));
    flash();
  };

  const flash = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // Broker connection test state (per portfolio)
  const [testingConnection, setTestingConnection] = useState<string | null>(null); // portfolio id being tested
  const [connectionResults, setConnectionResults] = useState<Record<string, { ok: boolean; message: string }>>({});
  // Credential save state (in edit form)
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [credentialSaveResult, setCredentialSaveResult] = useState<{ ok: boolean; message: string } | null>(null);

  const testBrokerConnection = async (portfolioId: string, broker: string) => {
    setTestingConnection(portfolioId);
    try {
      const resp = await fetch(`/broker/connection?broker=${encodeURIComponent(broker.toLowerCase())}`);
      const data = await resp.json();
      if (resp.ok && data.connected) {
        setConnectionResults((prev) => ({
          ...prev,
          [portfolioId]: {
            ok: true,
            message: `Connected: $${(data.buying_power ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })} buying power`,
          },
        }));
      } else {
        setConnectionResults((prev) => ({
          ...prev,
          [portfolioId]: { ok: false, message: data.detail ?? "Connection failed" },
        }));
      }
    } catch (err) {
      setConnectionResults((prev) => ({
        ...prev,
        [portfolioId]: { ok: false, message: err instanceof Error ? err.message : "Network error" },
      }));
    } finally {
      setTestingConnection(null);
    }
  };

  // Portfolio edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", account_type: "", broker: "", sync_method: "manual" as "manual" | "csv_upload" | "broker_api", broker_api_key: "", broker_secret_key: "", sync_interval_hours: 24 });

  // Add portfolio state
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState({ name: "", account_type: "Taxable", broker: "" });

  const startEdit = (p: typeof portfolios[0]) => {
    setEditingId(p.id);
    setEditForm({ name: p.name, account_type: p.account_type, broker: p.broker || "", sync_method: p.sync_method || "manual", broker_api_key: p.broker_api_key || "", broker_secret_key: p.broker_secret_key || "", sync_interval_hours: p.sync_interval_hours || 24 });
  };

  const saveEdit = () => {
    if (!editingId) return;
    updatePortfolio(editingId, {
      name: editForm.name,
      account_type: editForm.account_type,
      broker: editForm.broker,
      sync_method: editForm.sync_method,
      broker_api_key: editForm.sync_method === "broker_api" ? editForm.broker_api_key : undefined,
      broker_secret_key: editForm.sync_method === "broker_api" ? editForm.broker_secret_key : undefined,
      sync_interval_hours: editForm.sync_method === "broker_api" ? editForm.sync_interval_hours : undefined,
    });
    setEditingId(null);
    flash();
  };

  const handleAdd = () => {
    if (!addForm.name.trim()) return;
    addPortfolio({ name: addForm.name, account_type: addForm.account_type, broker: addForm.broker, position_count: 0, total_value: 0 });
    setAddForm({ name: "", account_type: "Taxable", broker: "" });
    setShowAdd(false);
    flash();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Settings</h1>
        {saved && (
          <span className="flex items-center gap-1 rounded-md bg-income/10 px-3 py-1 text-xs font-medium text-income animate-in fade-in">
            <Check className="h-3 w-3" /> Saved
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg border border-border bg-secondary p-1 w-fit">
        {([
          { key: "global", label: "Global" },
          { key: "portfolios", label: "Portfolios" },
          { key: "portfolio-config", label: "Portfolio Config" },
        ] as { key: SettingsTab; label: string }[]).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "rounded-md px-4 py-1.5 text-xs font-medium transition-colors",
              tab === t.key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Global */}
      {tab === "global" && (
        <div className="max-w-lg space-y-4 rounded-lg border border-border bg-card p-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Notification Email</label>
            <input
              type="email"
              value={global.notification_email}
              onChange={(e) => setGlobal({ ...global, notification_email: e.target.value })}
              placeholder="you@example.com"
              className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Currency</label>
              <select
                value={global.currency}
                onChange={(e) => setGlobal({ ...global, currency: e.target.value })}
                className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm text-foreground"
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Date Format</label>
              <select
                value={global.date_format}
                onChange={(e) => setGlobal({ ...global, date_format: e.target.value })}
                className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm text-foreground"
              >
                <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                <option value="YYYY-MM-DD">YYYY-MM-DD</option>
              </select>
            </div>
          </div>

          {/* Theme toggle */}
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Theme</label>
            <div className="flex gap-2">
              <button
                onClick={() => setTheme("dark")}
                className={cn(
                  "flex items-center gap-1.5 rounded-md border px-4 py-1.5 text-xs font-medium transition-colors",
                  theme === "dark"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                <Moon className="h-3.5 w-3.5" /> Dark
              </button>
              <button
                onClick={() => setTheme("light")}
                className={cn(
                  "flex items-center gap-1.5 rounded-md border px-4 py-1.5 text-xs font-medium transition-colors",
                  theme === "light"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                <Sun className="h-3.5 w-3.5" /> Light
              </button>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Alert Notifications</label>
            <div className="flex gap-3">
              {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
                <label key={s} className="flex items-center gap-1.5 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={global.alert_severity_filter.includes(s)}
                    onChange={(e) => {
                      setGlobal({
                        ...global,
                        alert_severity_filter: e.target.checked
                          ? [...global.alert_severity_filter, s]
                          : global.alert_severity_filter.filter((x) => x !== s),
                      });
                    }}
                    className="rounded border-border accent-primary"
                  />
                  {s}
                </label>
              ))}
            </div>
          </div>
          <button
            onClick={saveGlobal}
            className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Save className="h-4 w-4" /> Save Settings
          </button>

          {/* Tax Profile */}
          <div className="mt-8 pt-6 border-t border-border">
            <h3 className="text-sm font-semibold mb-1">Tax Profile</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Used by the tax optimizer to calculate after-tax yield and account placement recommendations.
            </p>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Annual Income</label>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={taxProfile.annual_income}
                  onChange={(e) => setTaxProfile({ ...taxProfile, annual_income: Number(e.target.value) })}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">Filing Status</label>
                  <select
                    value={taxProfile.filing_status}
                    onChange={(e) => setTaxProfile({ ...taxProfile, filing_status: e.target.value })}
                    className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm text-foreground"
                  >
                    <option value="SINGLE">Single</option>
                    <option value="MARRIED_JOINT">Married Filing Jointly</option>
                    <option value="MARRIED_SEPARATE">Married Filing Separately</option>
                    <option value="HEAD_OF_HOUSEHOLD">Head of Household</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">State Code</label>
                  <input
                    type="text"
                    maxLength={2}
                    value={taxProfile.state_code}
                    onChange={(e) => setTaxProfile({ ...taxProfile, state_code: e.target.value.toUpperCase() })}
                    placeholder="CA"
                    className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm text-foreground uppercase focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>
              {taxError && <p className="text-xs text-red-400">{taxError}</p>}
              <Button
                size="sm"
                variant="outline"
                onClick={saveTaxProfile}
                disabled={taxSaving}
              >
                {taxSaving ? "Saving…" : "Save Tax Profile"}
              </Button>
            </div>
          </div>

          {/* Analyst Suggestion Expiry */}
          <div className="mt-8 pt-6 border-t border-border">
            <h3 className="text-sm font-semibold mb-1">Analyst Suggestion Expiry</h3>
            <p className="text-xs text-muted-foreground mb-4">
              How long analyst suggestions remain visible after ingestion.
              Use <code className="bg-muted rounded px-1">_default</code> as the fallback for unspecified asset classes.
            </p>
            <div className="space-y-2 max-w-sm">
              {TTL_ASSET_CLASSES.map((cls) => (
                <div key={cls} className="flex items-center justify-between gap-4">
                  <label className="text-xs text-muted-foreground w-28 shrink-0">
                    {cls === "_default" ? "Default (days)" : cls}
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={getTtlDays(cls)}
                    onChange={(e) => setTtlDays(cls, e.target.value)}
                    placeholder="45"
                    className="w-20 rounded border border-border bg-background px-2 py-1 text-sm text-foreground text-right"
                  />
                </div>
              ))}
            </div>
            {ttlError && <p className="text-xs text-red-400 mt-2">{ttlError}</p>}
            <Button
              size="sm"
              variant="outline"
              onClick={saveTtlConfig}
              disabled={ttlSaving}
              className="mt-4"
            >
              {ttlSaving ? "Saving…" : "Save TTL Config"}
            </Button>
          </div>
        </div>
      )}

      {/* Portfolio Management */}
      {tab === "portfolios" && (
        <div className="space-y-3 max-w-2xl">
          {portfolios.map((p) => (
            <div key={p.id} className="rounded-lg border border-border bg-card px-5 py-3">
              {editingId === p.id ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      placeholder="Portfolio name"
                      className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                    <select
                      value={editForm.account_type}
                      onChange={(e) => setEditForm({ ...editForm, account_type: e.target.value })}
                      className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground"
                    >
                      <option>Taxable</option>
                      <option>Roth IRA</option>
                      <option>Traditional IRA</option>
                      <option>401(k)</option>
                      <option>HSA</option>
                    </select>
                    <input
                      value={editForm.broker}
                      onChange={(e) => setEditForm({ ...editForm, broker: e.target.value })}
                      placeholder="Broker"
                      className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>

                  {/* Sync configuration */}
                  <div className="rounded-md border border-border bg-secondary/50 p-3 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Data Sync</p>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="mb-0.5 block text-[10px] text-muted-foreground">Sync Method</label>
                        <select
                          value={editForm.sync_method}
                          onChange={(e) => setEditForm({ ...editForm, sync_method: e.target.value as "manual" | "csv_upload" | "broker_api" })}
                          className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm"
                        >
                          <option value="manual">Manual</option>
                          <option value="csv_upload">CSV Upload</option>
                          <option value="broker_api">Broker API</option>
                        </select>
                      </div>
                      {editForm.sync_method === "broker_api" && (
                        <>
                          <div>
                            <label className="mb-0.5 block text-[10px] text-muted-foreground">API Key ID</label>
                            <input
                              type="password"
                              value={editForm.broker_api_key}
                              onChange={(e) => setEditForm({ ...editForm, broker_api_key: e.target.value })}
                              placeholder="••••••••"
                              className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                            />
                          </div>
                          <div>
                            <label className="mb-0.5 block text-[10px] text-muted-foreground">Secret Key</label>
                            <input
                              type="password"
                              value={editForm.broker_secret_key}
                              onChange={(e) => setEditForm({ ...editForm, broker_secret_key: e.target.value })}
                              placeholder="••••••••"
                              className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                            />
                          </div>
                        </>
                      )}
                    </div>
                    {editForm.sync_method === "broker_api" && (
                      <>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="mb-0.5 block text-[10px] text-muted-foreground">Sync Interval (hours)</label>
                            <select
                              value={editForm.sync_interval_hours}
                              onChange={(e) => setEditForm({ ...editForm, sync_interval_hours: Number(e.target.value) })}
                              className="w-full rounded-md border border-border bg-secondary px-2 py-1 text-sm"
                            >
                              <option value={1}>Every 1h</option>
                              <option value={4}>Every 4h</option>
                              <option value={8}>Every 8h</option>
                              <option value={12}>Every 12h</option>
                              <option value={24}>Every 24h</option>
                            </select>
                          </div>
                        </div>
                        <p className="text-[10px] text-muted-foreground">
                          Alpaca: provide both API Key ID and Secret Key from alpaca.markets → Paper Trading → API Keys
                        </p>
                        {/* Save credentials to broker-service */}
                        <div className="flex items-center gap-2 mt-1">
                          <button
                            type="button"
                            disabled={savingCredentials || !editForm.broker_api_key || !editForm.broker_secret_key}
                            onClick={async () => {
                              setSavingCredentials(true);
                              setCredentialSaveResult(null);
                              try {
                                const resp = await fetch("/broker/credentials", {
                                  method: "POST",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({
                                    broker: editForm.broker || "alpaca",
                                    api_key: editForm.broker_api_key,
                                    api_secret: editForm.broker_secret_key,
                                  }),
                                });
                                const data = await resp.json();
                                if (resp.ok && data.ok) {
                                  setCredentialSaveResult({ ok: true, message: `Connected: $${(data.buying_power ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })} buying power` });
                                } else {
                                  setCredentialSaveResult({ ok: false, message: data.detail ?? "Failed" });
                                }
                              } catch (err) {
                                setCredentialSaveResult({ ok: false, message: err instanceof Error ? err.message : "Network error" });
                              } finally {
                                setSavingCredentials(false);
                              }
                            }}
                            className="flex items-center gap-1 rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary disabled:opacity-50 transition-colors"
                          >
                            {savingCredentials
                              ? <><Loader2 className="h-3 w-3 animate-spin" /> Validating…</>
                              : <><Wifi className="h-3 w-3" /> Save &amp; Test Credentials</>}
                          </button>
                          {credentialSaveResult && (
                            <span className={cn("text-xs flex items-center gap-1", credentialSaveResult.ok ? "text-emerald-400" : "text-red-400")}>
                              {credentialSaveResult.ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                              {credentialSaveResult.message}
                            </span>
                          )}
                        </div>
                      </>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button onClick={saveEdit} className="flex items-center gap-1 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90">
                      <Check className="h-3 w-3" /> Save
                    </button>
                    <button onClick={() => setEditingId(null)} className="flex items-center gap-1 rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary">
                      <X className="h-3 w-3" /> Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {p.account_type} · {p.broker || "—"} · {p.position_count ?? 0} positions · {formatCurrency(p.total_value ?? 0, true)}
                      {p.sync_method && p.sync_method !== "manual" && (
                        <span className="ml-2 inline-flex items-center gap-1">
                          · {p.sync_method === "broker_api" ? <Cloud className="inline h-3 w-3" /> : <Upload className="inline h-3 w-3" />}
                          {p.sync_method === "broker_api" ? `API sync every ${p.sync_interval_hours || 24}h` : "CSV upload"}
                          {p.last_synced && <span className="text-[10px]">· last {new Date(p.last_synced).toLocaleDateString()}</span>}
                        </span>
                      )}
                    </p>
                    {/* Connection test result */}
                    {connectionResults[p.id] && (
                      <p className={cn(
                        "text-xs mt-1 flex items-center gap-1",
                        connectionResults[p.id].ok ? "text-emerald-400" : "text-red-400"
                      )}>
                        {connectionResults[p.id].ok
                          ? <Wifi className="h-3 w-3" />
                          : <WifiOff className="h-3 w-3" />}
                        {connectionResults[p.id].message}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {p.broker && (
                      <button
                        onClick={() => testBrokerConnection(p.id, p.broker!)}
                        disabled={testingConnection === p.id}
                        className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary transition-colors disabled:opacity-50"
                        title="Test broker connection"
                      >
                        {testingConnection === p.id
                          ? <Loader2 className="h-3 w-3 animate-spin inline" />
                          : <Wifi className="h-3 w-3 inline" />}
                        {" "}Test
                      </button>
                    )}
                    <button
                      onClick={() => startEdit(p)}
                      className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary transition-colors"
                    >
                      <Pencil className="mr-1 inline h-3 w-3" />Edit
                    </button>
                    {activePortfolio?.id === p.id ? (
                      <span className="rounded-md border border-primary bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <Check className="mr-1 inline h-3 w-3" />Active
                      </span>
                    ) : (
                      <button
                        onClick={() => { setActiveId(p.id); flash(); }}
                        className="rounded-md border border-border px-3 py-1 text-xs font-medium text-foreground/70 hover:text-foreground hover:bg-secondary transition-colors"
                      >
                        Set Active
                      </button>
                    )}
                    {portfolios.length > 1 && (
                      <button
                        onClick={() => { if (confirm(`Delete "${p.name}"?`)) deletePortfolio(p.id); }}
                        className="rounded-md border border-border px-2 py-1 text-xs text-red-400 hover:bg-red-400/10 transition-colors"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Add portfolio form */}
          {showAdd ? (
            <div className="rounded-lg border border-dashed border-border bg-card px-5 py-3 space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <input
                  value={addForm.name}
                  onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                  placeholder="Portfolio name"
                  autoFocus
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <select
                  value={addForm.account_type}
                  onChange={(e) => setAddForm({ ...addForm, account_type: e.target.value })}
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground"
                >
                  <option>Taxable</option>
                  <option>Roth IRA</option>
                  <option>Traditional IRA</option>
                  <option>401(k)</option>
                  <option>HSA</option>
                </select>
                <input
                  value={addForm.broker}
                  onChange={(e) => setAddForm({ ...addForm, broker: e.target.value })}
                  placeholder="Broker"
                  className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleAdd}
                  disabled={!addForm.name.trim()}
                  className="flex items-center gap-1 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  <Plus className="h-3 w-3" /> Add
                </button>
                <button onClick={() => setShowAdd(false)} className="flex items-center gap-1 rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-secondary">
                  <X className="h-3 w-3" /> Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-1.5 rounded-md border border-dashed border-border px-4 py-2.5 text-sm text-foreground/60 hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <Plus className="h-4 w-4" /> Add Portfolio
            </button>
          )}
        </div>
      )}

      {/* Per-Portfolio Config */}
      {tab === "portfolio-config" && (
        <div className="max-w-lg space-y-4 rounded-lg border border-border bg-card p-5">
          <div className="flex items-center gap-3">
            <label className="text-xs text-muted-foreground whitespace-nowrap">Configure:</label>
            <select
              value={configPortfolioId}
              onChange={(e) => setConfigPortfolioId(e.target.value)}
              className="rounded-md border border-border bg-secondary px-2 py-1 text-sm text-foreground flex-1"
            >
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Target Annual Income ($)</label>
            <input
              type="number"
              value={config.income_goal}
              onChange={(e) => setConfig({ ...config, income_goal: Number(e.target.value) })}
              className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Max Position %</label>
              <input
                type="number"
                step="0.5"
                value={config.max_position_pct}
                onChange={(e) => setConfig({ ...config, max_position_pct: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Target Yield %</label>
              <input
                type="number"
                step="0.1"
                value={config.target_yield}
                onChange={(e) => setConfig({ ...config, target_yield: Number(e.target.value) })}
                className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Rebalance Threshold %</label>
            <input
              type="number"
              step="0.5"
              value={config.rebalance_threshold}
              onChange={(e) => setConfig({ ...config, rebalance_threshold: Number(e.target.value) })}
              className="w-full rounded-md border border-border bg-secondary px-3 py-1.5 text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="space-y-2">
            {[
              { key: "auto_reinvest" as const, label: "Auto-reinvest dividends" },
              { key: "tax_loss_harvesting" as const, label: "Tax-loss harvesting enabled" },
              { key: "auto_execute_proposals" as const, label: "Auto-execute accepted proposals" },
            ].map((toggle) => (
              <label key={toggle.key} className="flex items-center justify-between rounded-md border border-border bg-secondary px-3 py-2">
                <span className="text-sm">{toggle.label}</span>
                <button
                  onClick={() => setConfig({ ...config, [toggle.key]: !config[toggle.key] })}
                  className={cn(
                    "relative h-5 w-9 rounded-full transition-colors",
                    config[toggle.key] ? "bg-primary" : "bg-muted"
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
                      config[toggle.key] ? "left-4.5" : "left-0.5"
                    )}
                  />
                </button>
              </label>
            ))}
          </div>
          <button
            onClick={saveConfig}
            className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Save className="h-4 w-4" /> Save Configuration
          </button>
        </div>
      )}
    </div>
  );
}
