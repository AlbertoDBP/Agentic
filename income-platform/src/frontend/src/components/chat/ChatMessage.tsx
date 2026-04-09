// src/frontend/src/components/chat/ChatMessage.tsx
import { cn } from "@/lib/utils";
import { ToolCard } from "./ToolCard";

export interface ChatMessageData {
  id?: string;
  role: "user" | "assistant";
  text?: string;
  toolCards?: Array<{ id: string; name: string; result?: Record<string, unknown>; pending?: boolean }>;
  streaming?: boolean;
}

interface ChatMessageProps {
  message: ChatMessageData;
}

// Minimal markdown renderer — bold, inline code, links
function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, '<code class="bg-muted/40 px-0.5 rounded text-[11px]">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-400 hover:underline">$1</a>');
}

function renderText(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Table detection
    if (line.includes("|") && lines[i + 1]?.match(/^\|[-| ]+\|$/)) {
      const headers = line.split("|").filter(Boolean).map((s) => s.trim());
      i += 2; // skip separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|")) {
        rows.push(lines[i].split("|").filter(Boolean).map((s) => s.trim()));
        i++;
      }
      elements.push(
        <div key={i} className="overflow-x-auto my-2">
          <table className="text-xs w-full border-collapse">
            <thead>
              <tr className="border-b border-border/50">
                {headers.map((h, j) => (
                  <th key={j} className="text-left px-2 py-1 text-muted-foreground font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/20">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-2 py-1"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(cell) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // List items
    if (line.match(/^[-*] /)) {
      const items: string[] = [];
      while (i < lines.length && lines[i].match(/^[-*] /)) {
        items.push(lines[i].slice(2));
        i++;
      }
      elements.push(
        <ul key={i} className="list-disc list-inside space-y-0.5 my-1.5 pl-1 text-sm">
          {items.map((item, j) => (
            <li key={j} dangerouslySetInnerHTML={{ __html: renderMarkdown(item) }} />
          ))}
        </ul>
      );
      continue;
    }

    // Regular paragraph
    if (line.trim()) {
      elements.push(
        <p key={i} className="text-sm leading-relaxed"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(line) }} />
      );
    } else {
      elements.push(<div key={i} className="h-1.5" />);
    }
    i++;
  }

  return elements;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-2.5", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-[9px] font-bold text-blue-400">AI</span>
        </div>
      )}
      <div className={cn("max-w-[85%] space-y-1", isUser ? "items-end" : "items-start")}>
        {/* Tool cards (before text for assistant) */}
        {!isUser && message.toolCards?.map((tc) => (
          <ToolCard key={tc.id} name={tc.name} result={tc.result} pending={tc.pending} />
        ))}

        {/* Text bubble */}
        {message.text && (
          <div className={cn(
            "rounded-lg px-3 py-2 text-sm",
            isUser
              ? "bg-blue-600/20 border border-blue-500/30 text-foreground"
              : "bg-muted/30 border border-border/30 text-foreground"
          )}>
            {isUser ? (
              <p className="text-sm whitespace-pre-wrap">{message.text}</p>
            ) : (
              <div className="space-y-1">{renderText(message.text)}</div>
            )}
            {message.streaming && (
              <span className="inline-block w-1.5 h-3.5 bg-blue-400 ml-0.5 animate-pulse rounded-sm" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
