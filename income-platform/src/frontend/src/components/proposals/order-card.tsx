// src/frontend/src/components/proposals/order-card.tsx
"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { LiveOrder, PaperOrder } from "@/lib/types";

// ── Filled card ───────────────────────────────────────────────────────────────

export function FilledOrderCard({ order }: { order: LiveOrder }) {
  const total = order.filled_qty * (order.avg_fill_price ?? 0);

  return (
    <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 overflow-hidden">
      <OrderCardHeader order={order} />
      <div className="p-4 grid grid-cols-3 gap-3">
        <DetailCell label="Shares" value={order.filled_qty.toString()} className="text-emerald-400" />
        <DetailCell label="Avg Price" value={`$${(order.avg_fill_price ?? 0).toFixed(2)}`} className="text-emerald-400" />
        <DetailCell label="Total Paid" value={`$${total.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} className="text-emerald-400" />
        {order.filled_at && (
          <DetailCell label="Filled At" value={new Date(order.filled_at).toLocaleTimeString()} />
        )}
      </div>
    </div>
  );
}

// ── Partial fill card ─────────────────────────────────────────────────────────

export function PartialOrderCard({
  order,
  marketPrice,
  onCancelRest,
  onRaiseLimit,
}: {
  order: LiveOrder;
  marketPrice?: number;
  onCancelRest: () => void;
  onRaiseLimit?: (newPrice: number) => void;
}) {
  const pct = order.qty > 0 ? (order.filled_qty / order.qty) * 100 : 0;
  const remaining = order.qty - order.filled_qty;

  return (
    <div className="rounded-xl border border-amber-800/40 overflow-hidden">
      <OrderCardHeader order={order} onCancel={onCancelRest} cancelLabel="Cancel Rest" />
      <div className="p-4 space-y-3">
        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
            <span>Fill progress</span>
            <span className="text-amber-400 font-medium">
              {order.filled_qty} / {order.qty} shares ({pct.toFixed(0)}%)
            </span>
          </div>
          <div className="h-1.5 bg-muted/40 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-400 rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Details grid */}
        <div className="grid grid-cols-3 gap-3">
          <DetailCell label="Filled" value={`${order.filled_qty} sh`} className="text-emerald-400" />
          <DetailCell label="Avg Price" value={`$${(order.avg_fill_price ?? 0).toFixed(2)}`} />
          <DetailCell label="Remaining" value={`${remaining} sh`} className="text-amber-400" />
          <DetailCell label="Limit Price" value={order.limit_price != null ? `$${order.limit_price.toFixed(2)}` : "—"} />
        </div>

        {/* Action banner */}
        <div className="rounded-lg bg-amber-950/30 border border-amber-800/40 p-3 text-xs text-amber-300 space-y-2">
          <p>{remaining} shares remain unfilled.
            {order.limit_price != null && marketPrice != null && marketPrice > order.limit_price && (
              <> Limit ${order.limit_price.toFixed(2)} is below market ${marketPrice.toFixed(2)}.</>
            )}
            {" "}GTC order remains active until filled or cancelled.
          </p>
          <div className="flex gap-2">
            <button
              onClick={onCancelRest}
              className="text-[11px] px-2.5 py-1 rounded border border-red-800/50 bg-red-950/30 text-red-400 hover:bg-red-950/50"
            >
              Cancel remaining {remaining} shares
            </button>
            {marketPrice != null && onRaiseLimit && (
              <button
                onClick={() => onRaiseLimit(marketPrice)}
                className="text-[11px] px-2.5 py-1 rounded border border-border bg-muted/20 text-muted-foreground hover:text-foreground"
              >
                Raise limit to ${marketPrice.toFixed(2)}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Pending card ──────────────────────────────────────────────────────────────

export function PendingOrderCard({
  order,
  onCancel,
}: {
  order: LiveOrder;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-xl border border-border overflow-hidden opacity-70">
      <OrderCardHeader order={order} onCancel={onCancel} cancelLabel="Cancel Order" />
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <DetailCell label="Quantity" value={`${order.qty} shares`} />
          <DetailCell label="Limit Price" value={order.limit_price != null ? `$${order.limit_price.toFixed(2)}` : "Market"} />
          <DetailCell label="Est. Value" value={order.limit_price != null ? `$${(order.qty * order.limit_price).toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"} />
        </div>
        <p className="text-xs text-muted-foreground text-center py-1">
          Waiting for market — order live, no fills yet
        </p>
      </div>
    </div>
  );
}

// ── Paper order card ──────────────────────────────────────────────────────────

export function PaperOrderCard({
  order,
  onMarkExecuted,
}: {
  order: PaperOrder;
  onMarkExecuted: (fillPrice: number, fillDate: string) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [fillPrice, setFillPrice] = useState(order.limit_price?.toFixed(2) ?? "");
  const [fillDate, setFillDate] = useState(new Date().toISOString().slice(0, 10));

  const orderText = [
    `Action:  BUY`,
    `Symbol:  ${order.ticker}`,
    `Qty:     ${order.qty} shares`,
    `Type:    ${order.order_type === "market" ? "Market" : `Limit @ $${order.limit_price?.toFixed(2) ?? "?"}`}`,
    `TIF:     ${order.time_in_force.toUpperCase()}`,
    `Account: ${order.portfolio_name} (manual)`,
  ].join("\n");

  const copyToClipboard = () => navigator.clipboard.writeText(orderText);
  const exportCSV = () => {
    const csv = `Action,Symbol,Qty,Type,Limit,TIF,Account\nBUY,${order.ticker},${order.qty},${order.order_type},${order.limit_price ?? ""},${order.time_in_force},${order.portfolio_name}`;
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `order-${order.ticker}.csv`;
    a.click();
  };

  return (
    <div className="rounded-xl border border-blue-900/40 bg-blue-950/20 overflow-hidden">
      <div className="px-4 py-3 bg-blue-950/30 border-b border-blue-900/40 flex items-center justify-between">
        <div>
          <span className="font-mono font-bold text-blue-300">{order.ticker}</span>
          <span className="text-xs text-blue-400/70 ml-2">{order.portfolio_name} · no broker connected</span>
        </div>
        <span className="text-xs font-semibold rounded-full px-2.5 py-0.5 bg-blue-900/40 text-blue-300 border border-blue-800/40">
          Paper Order
        </span>
      </div>
      <div className="p-4 space-y-3">
        <pre className="text-xs font-mono text-blue-300/80 bg-blue-950/30 rounded-lg border border-blue-900/30 p-3 leading-loose whitespace-pre">
          {orderText}
        </pre>
        <div className="flex gap-2">
          <button onClick={copyToClipboard} className="text-xs px-3 py-1.5 rounded border border-border bg-muted/20 text-muted-foreground hover:text-foreground">
            ⎘ Copy
          </button>
          <button onClick={exportCSV} className="text-xs px-3 py-1.5 rounded border border-border bg-muted/20 text-muted-foreground hover:text-foreground">
            ↓ CSV
          </button>
          {!order.executed && (
            <button
              onClick={() => setShowForm(!showForm)}
              className="text-xs px-3 py-1.5 rounded border border-emerald-800/40 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40"
            >
              ✓ Mark as Executed
            </button>
          )}
          {order.executed && (
            <span className="text-xs text-emerald-400 flex items-center gap-1">✓ Marked executed</span>
          )}
        </div>
        {showForm && (
          <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
            <p className="text-xs text-muted-foreground">Enter actual fill details:</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Fill Price</label>
                <input
                  type="number"
                  value={fillPrice}
                  onChange={(e) => setFillPrice(e.target.value)}
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                />
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Fill Date</label>
                <input
                  type="date"
                  value={fillDate}
                  onChange={(e) => setFillDate(e.target.value)}
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
                />
              </div>
            </div>
            <button
              onClick={() => {
                onMarkExecuted(parseFloat(fillPrice), fillDate);
                setShowForm(false);
              }}
              disabled={!fillPrice || !fillDate}
              className="w-full text-xs py-1.5 rounded bg-emerald-700 text-white hover:bg-emerald-600 disabled:opacity-40"
            >
              Confirm Execution
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Shared sub-components ─────────────────────────────────────────────────────

function OrderCardHeader({
  order,
  onCancel,
  cancelLabel = "Cancel",
}: {
  order: LiveOrder;
  onCancel?: () => void;
  cancelLabel?: string;
}) {
  const statusConfig: Record<string, { label: string; cls: string }> = {
    filled:           { label: "✓ Filled",       cls: "bg-emerald-950/40 text-emerald-400 border-emerald-800/40" },
    partially_filled: { label: "⚠ Partial Fill", cls: "bg-amber-950/40 text-amber-400 border-amber-800/40" },
    pending:          { label: "⏳ Pending",      cls: "bg-amber-950/40 text-amber-400 border-amber-800/40" },
    cancelled:        { label: "✗ Cancelled",     cls: "bg-muted/40 text-muted-foreground border-border" },
  };
  const cfg = statusConfig[order.status] ?? statusConfig.pending;

  return (
    <div className="px-4 py-3 bg-card/50 border-b border-border flex items-center justify-between">
      <div>
        <span className="font-mono font-bold">{order.ticker}</span>
        {order.order_id && (
          <span className="text-[10px] text-muted-foreground font-mono ml-2">#{order.order_id.slice(0, 8)}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className={cn("text-xs font-semibold rounded-full px-2.5 py-0.5 border", cfg.cls)}>
          {cfg.label}
        </span>
        {onCancel && order.status !== "filled" && order.status !== "cancelled" && (
          <button
            onClick={onCancel}
            className="text-[11px] px-2 py-1 rounded border border-red-800/40 bg-red-950/20 text-red-400 hover:bg-red-950/40"
          >
            {cancelLabel}
          </button>
        )}
      </div>
    </div>
  );
}

function DetailCell({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={cn("text-sm font-semibold mt-0.5", className)}>{value}</p>
    </div>
  );
}
