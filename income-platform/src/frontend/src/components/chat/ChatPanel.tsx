// src/frontend/src/components/chat/ChatPanel.tsx
"use client";
import { useEffect, useRef, KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessageData } from "./ChatMessage";

interface ChatPanelProps {
  messages: ChatMessageData[];
  input: string;
  loading: boolean;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onRetry?: () => void;
  className?: string;
  placeholder?: string;
}

export function ChatPanel({
  messages,
  input,
  loading,
  onInputChange,
  onSend,
  onRetry,
  className,
  placeholder = "Ask anything about your portfolio…",
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground text-xs pt-8">
            Ask about your portfolio, holdings, or scores.
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} onRetry={msg.isError ? onRetry : undefined} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-border/50 px-3 py-2 flex gap-2 items-end shrink-0">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={1}
          disabled={loading}
          className={cn(
            "flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60",
            "focus:outline-none min-h-[32px] max-h-[120px] py-1.5",
            "disabled:opacity-50"
          )}
          style={{ height: "auto" }}
          onInput={(e) => {
            const t = e.target as HTMLTextAreaElement;
            t.style.height = "auto";
            t.style.height = `${Math.min(t.scrollHeight, 120)}px`;
          }}
        />
        <button
          onClick={onSend}
          disabled={loading || !input.trim()}
          className={cn(
            "w-7 h-7 rounded-md flex items-center justify-center shrink-0 transition-colors",
            "bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          )}
        >
          <Send className="w-3.5 h-3.5 text-white" />
        </button>
      </div>
    </div>
  );
}
