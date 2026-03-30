// src/frontend/src/components/proposals/order-status-panel.tsx
"use client";

import { useEffect, useRef } from "react";
import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  FilledOrderCard,
  PartialOrderCard,
  PendingOrderCard,
  PaperOrderCard,
} from "./order-card";
import type { LiveOrder, PaperOrder } from "@/lib/types";

const POLL_INTERVAL_MS = 10_000;

interface OrderStatusPanelProps {
  liveOrders: LiveOrder[];
  paperOrders: PaperOrder[];
  submittedAt: Date;
  onRefresh: () => void;
  onCancelOrder: (orderId: string, broker: string) => void;
  onCancelRest: (orderId: string, broker: string) => void;
  onMarkPaperExecuted: (proposalId: number, fillPrice: number, fillDate: string) => void;
  lastRefreshedAt: Date | null;
}

export function OrderStatusPanel({
  liveOrders,
  paperOrders,
  submittedAt,
  onRefresh,
  onCancelOrder,
  onCancelRest,
  onMarkPaperExecuted,
  lastRefreshedAt,
}: OrderStatusPanelProps) {
  const allTerminal = liveOrders.every(
    (o) => o.status === "filled" || o.status === "cancelled"
  );

  // Auto-poll every 10s until all orders are terminal
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (allTerminal) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }
    timerRef.current = setInterval(onRefresh, POLL_INTERVAL_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [allTerminal, onRefresh]);

  const filledCount = liveOrders.filter((o) => o.status === "filled").length;
  const partialCount = liveOrders.filter((o) => o.status === "partially_filled").length;
  const pendingCount = liveOrders.filter((o) => o.status === "pending").length;

  const allOrders = [
    ...liveOrders.map((o) => ({ type: "live" as const, data: o })),
    ...paperOrders.map((o) => ({ type: "paper" as const, data: o })),
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-border flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">
            Order Status
            {liveOrders.length > 0 && (
              <span className="text-muted-foreground font-normal ml-2">
                {filledCount} filled · {partialCount} partial · {pendingCount} pending
              </span>
            )}
            {paperOrders.length > 0 && (
              <span className="text-muted-foreground font-normal ml-2">
                {paperOrders.length} paper
              </span>
            )}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Submitted {submittedAt.toLocaleTimeString()}
            {!allTerminal && " · auto-refreshing"}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground rounded border border-border px-2 py-1"
          title="Refresh order status"
        >
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
      </div>

      {lastRefreshedAt && (
        <p className="px-5 py-1 text-[10px] text-muted-foreground border-b border-border bg-muted/10">
          Last updated {lastRefreshedAt.toLocaleTimeString()}
        </p>
      )}

      {/* Order cards */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {allOrders.map(({ type, data }) => {
          if (type === "paper") {
            return (
              <PaperOrderCard
                key={`paper-${(data as PaperOrder).proposal_id}`}
                order={data as PaperOrder}
                onMarkExecuted={(price, date) =>
                  onMarkPaperExecuted((data as PaperOrder).proposal_id, price, date)
                }
              />
            );
          }
          const o = data as LiveOrder;
          if (o.status === "filled") {
            return <FilledOrderCard key={o.order_id} order={o} />;
          }
          if (o.status === "partially_filled") {
            return (
              <PartialOrderCard
                key={o.order_id}
                order={o}
                onCancelRest={() => onCancelRest(o.order_id, o.broker)}
              />
            );
          }
          return (
            <PendingOrderCard
              key={o.order_id}
              order={o}
              onCancel={() => onCancelOrder(o.order_id, o.broker)}
            />
          );
        })}
      </div>

      {/* Footer summary */}
      <div className="border-t border-border px-5 py-3 flex items-center justify-between text-xs">
        <div className="flex gap-4 text-muted-foreground">
          <span>
            Filled:{" "}
            <span className="text-emerald-400 font-medium">
              ${liveOrders
                .filter((o) => o.status === "filled")
                .reduce((s, o) => s + o.filled_qty * (o.avg_fill_price ?? 0), 0)
                .toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
          </span>
          {pendingCount + partialCount > 0 && (
            <span>
              Pending:{" "}
              <span className="text-amber-400 font-medium">
                ${liveOrders
                  .filter((o) => o.status === "pending" || o.status === "partially_filled")
                  .reduce((s, o) => s + (o.qty - o.filled_qty) * (o.limit_price ?? 0), 0)
                  .toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
