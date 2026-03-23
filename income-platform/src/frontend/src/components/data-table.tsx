"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type VisibilityState,
  type ColumnOrderState,
  type RowSelectionState,
} from "@tanstack/react-table";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ArrowDown, ArrowUp, ArrowUpDown, Settings2, GripVertical,
  ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Lock,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  storageKey?: string;
  enableRowSelection?: boolean;
  onRowClick?: (row: TData) => void;
  frozenColumns?: number;   // # of left columns to freeze (default 1)
  maxHeight?: string;       // css max-height of scroll area (default "62vh")
}

const SCROLL_AMT = 240;

export function DataTable<TData, TValue>({
  columns,
  data,
  storageKey,
  enableRowSelection = false,
  onRowClick,
  frozenColumns = 1,
  maxHeight = "62vh",
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [columnOrder, setColumnOrder] = useState<ColumnOrderState>([]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [frozenCount, setFrozenCount] = useState(frozenColumns);

  // Drag state for column reorder
  const [dragColId, setDragColId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  // Single scroll container ref
  const scrollRef = useRef<HTMLDivElement>(null);

  // Sticky offsets: left position for each frozen column
  const [stickyOffsets, setStickyOffsets] = useState<number[]>([]);

  // Scroll button availability
  const [canScrollLeft, setCanScrollLeft]   = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [canScrollUp, setCanScrollUp]       = useState(false);
  const [canScrollDown, setCanScrollDown]   = useState(false);

  // ── Restore persisted state ──
  useEffect(() => {
    if (!storageKey) return;
    try {
      const saved = localStorage.getItem(`dt-${storageKey}`);
      if (saved) {
        const state = JSON.parse(saved);
        if (state.visibility) setColumnVisibility(state.visibility);
        if (state.order) {
          // Always keep 'actions' column last
          const order = (state.order as string[]).filter((id: string) => id !== "actions");
          order.push("actions");
          setColumnOrder(order);
        }
        if (typeof state.frozen === "number") setFrozenCount(state.frozen);
      } else {
        const defaults: VisibilityState = {};
        for (const col of columns) {
          const id = (col as { accessorKey?: string }).accessorKey ?? (col as { id?: string }).id;
          const meta = (col as { meta?: { defaultHidden?: boolean } }).meta;
          if (id && meta?.defaultHidden) defaults[id] = false;
        }
        if (Object.keys(defaults).length > 0) setColumnVisibility(defaults);
      }
    } catch { /* ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  // ── Persist state ──
  useEffect(() => {
    if (!storageKey) return;
    localStorage.setItem(
      `dt-${storageKey}`,
      JSON.stringify({ visibility: columnVisibility, order: columnOrder, frozen: frozenCount })
    );
  }, [columnVisibility, columnOrder, frozenCount, storageKey]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility, columnOrder, rowSelection },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnOrderChange: setColumnOrder,
    onRowSelectionChange: enableRowSelection ? setRowSelection : undefined,
    enableRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  // ── Measure sticky offsets from actual th widths ──
  const measureOffsets = useCallback(() => {
    if (!scrollRef.current || frozenCount === 0) { setStickyOffsets([]); return; }
    const ths = Array.from(
      scrollRef.current.querySelectorAll("table > thead > tr > th")
    ) as HTMLElement[];
    const offsets: number[] = [];
    let cum = 0;
    for (let i = 0; i < Math.min(frozenCount, ths.length); i++) {
      offsets.push(cum);
      cum += ths[i]?.offsetWidth ?? 120;
    }
    setStickyOffsets(offsets);
  }, [frozenCount]);

  useEffect(() => {
    // Defer to next frame so the DOM is painted with correct widths
    const id = requestAnimationFrame(measureOffsets);
    return () => cancelAnimationFrame(id);
  }, [measureOffsets, columnVisibility, columnOrder, data]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(measureOffsets));
    ro.observe(el);
    return () => ro.disconnect();
  }, [measureOffsets]);

  // ── Track scroll state ──
  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 1);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
    setCanScrollUp(el.scrollTop > 1);
    setCanScrollDown(el.scrollTop + el.clientHeight < el.scrollHeight - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Defer so layout is complete before measuring overflow
    const id = requestAnimationFrame(updateScrollState);
    el.addEventListener("scroll", updateScrollState, { passive: true });
    const ro = new ResizeObserver(updateScrollState);
    ro.observe(el);
    return () => { cancelAnimationFrame(id); el.removeEventListener("scroll", updateScrollState); ro.disconnect(); };
  }, [updateScrollState, data, columnVisibility, columnOrder]);

  const doScroll = (dir: "left" | "right" | "up" | "down") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({
      left: dir === "right" ? SCROLL_AMT : dir === "left" ? -SCROLL_AMT : 0,
      top:  dir === "down"  ? SCROLL_AMT : dir === "up"   ? -SCROLL_AMT : 0,
      behavior: "smooth",
    });
  };

  // ── Drag handlers ──
  const handleDragStart = (e: React.DragEvent, colId: string) => {
    setDragColId(colId);
    e.dataTransfer.effectAllowed = "move";
  };
  const handleDragOver = (e: React.DragEvent, colId: string) => {
    e.preventDefault();
    if (colId !== dragColId) setDropTargetId(colId);
  };
  const handleDrop = (e: React.DragEvent, targetColId: string) => {
    e.preventDefault();
    if (!dragColId || dragColId === targetColId) { setDragColId(null); setDropTargetId(null); return; }
    const currentOrder = columnOrder.length > 0
      ? [...columnOrder]
      : columns.map((c) => {
          if ("accessorKey" in c && c.accessorKey) return String(c.accessorKey);
          if ("id" in c && c.id) return c.id as string;
          return "";
        }).filter(Boolean);
    const dragIdx   = currentOrder.indexOf(dragColId);
    const targetIdx = currentOrder.indexOf(targetColId);
    if (dragIdx === -1 || targetIdx === -1) { setDragColId(null); setDropTargetId(null); return; }
    currentOrder.splice(dragIdx, 1);
    currentOrder.splice(targetIdx, 0, dragColId);
    setColumnOrder(currentOrder);
    setDragColId(null);
    setDropTargetId(null);
  };
  const handleDragEnd = () => { setDragColId(null); setDropTargetId(null); };

  const visibleCols = table.getVisibleLeafColumns();

  // bg-card in hex — must match exactly so frozen cells cover scrolled content
  // We use a CSS var reference that works in both themes
  const FROZEN_BG = "var(--color-card)";

  return (
    <div className="flex gap-1 min-w-0">
      {/* ── Main content ── */}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">

        {/* ── Toolbar (never scrolls) ── */}
        <div className="flex items-center justify-between gap-2 shrink-0">
          {/* Freeze selector */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Lock className="h-3 w-3" />
            <span>Freeze:</span>
            {[0, 1, 2, 3].map((n) => (
              <button
                key={n}
                onClick={() => setFrozenCount(n)}
                className={cn(
                  "rounded px-1.5 py-0.5 text-[11px] transition-colors",
                  frozenCount === n
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary hover:bg-secondary/80"
                )}
              >
                {n === 0 ? "None" : `${n} col${n > 1 ? "s" : ""}`}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            {/* Horizontal scroll buttons */}
            <div className="flex gap-0.5 border border-border rounded-md">
              <button
                onClick={() => doScroll("left")}
                disabled={!canScrollLeft}
                className="rounded-l-md p-1 text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-20 transition-colors"
                title="Scroll left"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => doScroll("right")}
                disabled={!canScrollRight}
                className="rounded-r-md p-1 text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-20 transition-colors"
                title="Scroll right"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Column visibility */}
            <DropdownMenu>
              <DropdownMenuTrigger className="inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
                <Settings2 className="h-3.5 w-3.5" />
                Columns
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48 max-h-72 overflow-y-auto">
                {table
                  .getAllColumns()
                  .filter((col) => col.getCanHide())
                  .map((col) => (
                    <DropdownMenuCheckboxItem
                      key={col.id}
                      checked={col.getIsVisible()}
                      onCheckedChange={(v) => col.toggleVisibility(!!v)}
                      className="capitalize text-xs"
                    >
                      {typeof col.columnDef.header === "string" ? col.columnDef.header : col.id}
                    </DropdownMenuCheckboxItem>
                  ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* ── Scroll container: ONLY this scrolls ── */}
        <div
          ref={scrollRef}
          className="rounded-lg border border-border overflow-auto"
          style={{ maxHeight, minWidth: 0 }}
        >
          {/*
            Native <table> — NO shadcn Table wrapper (which adds overflow-x-auto div).
            border-collapse:separate + border-spacing:0 is REQUIRED for position:sticky
            on <th>/<td> to work correctly.
          */}
          <table
            style={{
              borderCollapse: "separate",
              borderSpacing: 0,
              minWidth: "max-content",
              width: "100%",
            }}
          >
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header, visIdx) => {
                    const colId = header.column.id;
                    const isSticky = visIdx < frozenCount;
                    const leftPx = stickyOffsets[visIdx] ?? 0;
                    return (
                      <th
                        key={header.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e, colId)}
                        onDragOver={(e) => handleDragOver(e, colId)}
                        onDrop={(e) => handleDrop(e, colId)}
                        onDragEnd={handleDragEnd}
                        className={cn(
                          "h-9 px-2 text-left align-middle text-xs font-medium text-muted-foreground whitespace-nowrap border-b border-border",
                          // Always sticky-top so header doesn't scroll vertically
                          dragColId === colId && "opacity-40",
                          dropTargetId === colId && dragColId !== colId && "border-l-2 border-l-primary",
                          isSticky && "border-r border-border/60"
                        )}
                        style={{
                          position: "sticky",
                          top: 0,
                          // frozen columns also stick horizontally
                          ...(isSticky ? { left: `${leftPx}px` } : {}),
                          // frozen header cells need higher z-index than frozen body cells
                          zIndex: isSticky ? 30 : 20,
                          background: FROZEN_BG,
                          // GPU layer to prevent flicker
                          willChange: "transform",
                          boxShadow: isSticky ? "2px 0 4px rgba(0,0,0,0.15)" : undefined,
                        }}
                      >
                        <div className="flex items-center gap-1">
                          {isSticky ? (
                            <Lock className="h-2.5 w-2.5 opacity-30 shrink-0" />
                          ) : (
                            <GripVertical className="h-3 w-3 opacity-20 hover:opacity-60 shrink-0 cursor-grab" />
                          )}
                          <span
                            onClick={header.column.getToggleSortingHandler()}
                            className={cn(
                              "flex items-center gap-1",
                              header.column.getCanSort() && "cursor-pointer select-none"
                            )}
                          >
                            {header.isPlaceholder
                              ? null
                              : flexRender(header.column.columnDef.header, header.getContext())}
                            {header.column.getCanSort() && (
                              <span className="ml-0.5">
                                {header.column.getIsSorted() === "asc"  ? <ArrowUp className="h-3 w-3" />
                               : header.column.getIsSorted() === "desc" ? <ArrowDown className="h-3 w-3" />
                               : <ArrowUpDown className="h-3 w-3 opacity-30" />}
                              </span>
                            )}
                          </span>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>

            <tbody>
              {table.getRowModel().rows?.length ? (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={cn(
                      "border-b border-border transition-colors hover:bg-muted/30",
                      onRowClick && "cursor-pointer",
                      row.getIsSelected() && "bg-primary/5"
                    )}
                    onClick={() => {
                      if (onRowClick) onRowClick(row.original);
                      if (enableRowSelection) row.toggleSelected();
                    }}
                  >
                    {row.getVisibleCells().map((cell, visIdx) => {
                      const isSticky = visIdx < frozenCount;
                      const leftPx = stickyOffsets[visIdx] ?? 0;
                      return (
                        <td
                          key={cell.id}
                          className={cn(
                            "px-2 py-2 text-sm whitespace-nowrap align-middle",
                            isSticky && "border-r border-border/60"
                          )}
                          style={{
                            // frozen body cells stick left but NOT top
                            ...(isSticky ? {
                              position: "sticky",
                              left: `${leftPx}px`,
                              zIndex: 10,
                              background: FROZEN_BG,
                              willChange: "transform",
                              boxShadow: "2px 0 4px rgba(0,0,0,0.12)",
                            } : {
                              background: "transparent",
                            }),
                          }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={visibleCols.length}
                    className="h-24 text-center text-muted-foreground"
                    style={{ background: FROZEN_BG }}
                  >
                    No data.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Horizontal scroll hint ── */}
        {(canScrollLeft || canScrollRight) && (
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground justify-center shrink-0">
            <ChevronLeft className={cn("h-3 w-3", !canScrollLeft && "opacity-20")} />
            <span>scroll horizontally</span>
            <ChevronRight className={cn("h-3 w-3", !canScrollRight && "opacity-20")} />
          </div>
        )}

        {/* ── Row selection count ── */}
        {enableRowSelection && Object.keys(rowSelection).length > 0 && (
          <p className="text-xs text-muted-foreground shrink-0">
            {Object.keys(rowSelection).length} row(s) selected
          </p>
        )}
      </div>

      {/* ── Vertical scroll elevator (right side) ── */}
      <div className="flex flex-col justify-center gap-1 pt-8 shrink-0">
        <button
          onClick={() => doScroll("up")}
          disabled={!canScrollUp}
          className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-20 transition-colors border border-border"
          title="Scroll up"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <div className="flex-1 flex items-center justify-center">
          <div
            className="w-0.5 rounded-full bg-border"
            style={{ minHeight: "2rem" }}
          />
        </div>
        <button
          onClick={() => doScroll("down")}
          disabled={!canScrollDown}
          className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-20 transition-colors border border-border"
          title="Scroll down"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
