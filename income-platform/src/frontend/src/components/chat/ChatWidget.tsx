// src/frontend/src/components/chat/ChatWidget.tsx
"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { MessageCircle, X, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
import { ChatPanel } from "./ChatPanel";

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Extract portfolio ID from /portfolios/[id] URLs
  const portfolioId = pathname.match(/\/portfolios\/([^/]+)/)?.[1];

  const { messages, input, loading, setInput, send, retry, threads, fetchThreads, loadThread } =
    useChat({ portfolioId });

  // Load most recent thread when widget opens
  useEffect(() => {
    if (!open) return;
    fetchThreads();
  }, [open, fetchThreads]);

  // When threads load for the first time and widget is open, load the most recent
  const [didLoad, setDidLoad] = useState(false);
  useEffect(() => {
    if (!open || didLoad || threads.length === 0) return;
    setDidLoad(true);
    loadThread(threads[0].id);
  }, [open, threads, didLoad, loadThread]);

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "fixed bottom-5 right-5 z-50 w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all",
          "bg-blue-600 hover:bg-blue-500 text-white",
          open && "hidden"
        )}
        aria-label="Open assistant"
      >
        <MessageCircle className="w-5 h-5" />
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-5 right-5 z-50 w-[380px] h-[520px] rounded-xl shadow-2xl border border-border/60 bg-card flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/50 bg-card/80 shrink-0">
            <span className="text-sm font-semibold text-foreground">Platform Assistant</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground p-0.5 rounded"
                aria-label="Minimize"
              >
                <Minus className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground p-0.5 rounded"
                aria-label="Close"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <ChatPanel
            messages={messages}
            input={input}
            loading={loading}
            onInputChange={setInput}
            onSend={send}
            onRetry={retry}
            className="flex-1 min-h-0"
          />
        </div>
      )}
    </>
  );
}
