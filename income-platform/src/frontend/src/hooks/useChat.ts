// src/frontend/src/hooks/useChat.ts
"use client";
import { useState, useCallback, useRef } from "react";
import type { ChatMessageData } from "@/components/chat/ChatMessage";

interface Thread {
  id: string;
  title: string;
  updated_at: string;
}

interface UseChatOptions {
  portfolioId?: string;
}

export function useChat(opts: UseChatOptions = {}) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>();
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // ── Thread list ──────────────────────────────────────────────────────────────

  const fetchThreads = useCallback(async () => {
    setThreadsLoading(true);
    try {
      const r = await fetch("/api/chat/threads");
      if (r.ok) setThreads(await r.json());
    } finally {
      setThreadsLoading(false);
    }
  }, []);

  const loadThread = useCallback(async (threadId: string) => {
    setActiveThreadId(threadId);
    const r = await fetch(`/api/chat/threads/${threadId}/messages`);
    if (!r.ok) return;
    const rows: Array<{ role: string; raw: { role: string; content: unknown } }> = await r.json();

    const msgs: ChatMessageData[] = rows.map((row, i) => {
      if (row.role === "user") {
        const content = typeof row.raw.content === "string" ? row.raw.content : "";
        return { id: `${threadId}-${i}`, role: "user" as const, text: content };
      }
      // assistant: extract text from content blocks
      const blocks = Array.isArray(row.raw.content) ? row.raw.content : [];
      const text = blocks
        .filter((b: unknown) => (b as Record<string, unknown>).type === "text")
        .map((b: unknown) => (b as Record<string, unknown>).text as string)
        .join("");
      const toolCards = blocks
        .filter((b: unknown) => (b as Record<string, unknown>).type === "tool_use")
        .map((b: unknown) => {
          const block = b as Record<string, unknown>;
          return { id: block.id as string, name: block.name as string };
        });
      return { id: `${threadId}-${i}`, role: "assistant" as const, text, toolCards };
    });

    setMessages(msgs);
  }, []);

  const startNewThread = useCallback(() => {
    setActiveThreadId(undefined);
    setMessages([]);
  }, []);

  // ── Send message ─────────────────────────────────────────────────────────────

  const send = useCallback(async (text?: string) => {
    const msg = text ?? input;
    if (!msg.trim() || loading) return;
    setInput("");
    setLoading(true);

    // Optimistic user message
    const userMsg: ChatMessageData = { id: `user-${Date.now()}`, role: "user", text: msg };
    setMessages((prev) => [...prev, userMsg]);

    // Placeholder assistant message
    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", text: "", streaming: true, toolCards: [] },
    ]);

    abortRef.current = new AbortController();

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          thread_id: activeThreadId,
          portfolio_id: opts.portfolioId,
        }),
        signal: abortRef.current.signal,
      });

      if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);

      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += dec.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const evt of events) {
          if (!evt.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(evt.slice(6)) as Record<string, unknown>;

            if (payload.type === "thread_id" && !activeThreadId) {
              setActiveThreadId(payload.thread_id as string);
              // Refresh thread list to show new thread
              fetchThreads();
            } else if (payload.type === "text") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, text: (m.text ?? "") + (payload.text as string) }
                    : m
                )
              );
            } else if (payload.type === "tool_start") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCards: [
                          ...(m.toolCards ?? []),
                          { id: payload.id as string, name: payload.name as string, pending: true },
                        ],
                      }
                    : m
                )
              );
            } else if (payload.type === "tool_result") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCards: (m.toolCards ?? []).map((tc) =>
                          tc.id === payload.id
                            ? { ...tc, result: payload.result as Record<string, unknown>, pending: false }
                            : tc
                        ),
                      }
                    : m
                )
              );
            } else if (payload.type === "done") {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
              );
            } else if (payload.type === "error") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, text: `Error: ${payload.message as string}`, streaming: false }
                    : m
                )
              );
            }
          } catch {
            // malformed JSON line — skip
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: "Request failed. Please try again.", streaming: false }
              : m
          )
        );
      }
    } finally {
      setLoading(false);
    }
  }, [input, loading, activeThreadId, opts.portfolioId, fetchThreads]);

  return {
    threads,
    activeThreadId,
    messages,
    input,
    setInput,
    loading,
    threadsLoading,
    fetchThreads,
    loadThread,
    startNewThread,
    send,
  };
}
