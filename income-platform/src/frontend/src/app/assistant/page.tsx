// src/frontend/src/app/assistant/page.tsx
"use client";
import { useEffect, useState } from "react";
import { Plus, Trash2, Brain, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
import { ChatPanel } from "@/components/chat/ChatPanel";

interface Memory { id: string; content: string; category: string | null; created_at: string; }
interface Skill { id: string; name: string; trigger_phrase: string; procedure: string; }

function groupByDate(threads: Array<{ id: string; title: string; updated_at: string }>) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, typeof threads> = {
    Today: [],
    Yesterday: [],
    "This Week": [],
    Older: [],
  };

  for (const t of threads) {
    const d = new Date(t.updated_at);
    if (d >= today) groups["Today"].push(t);
    else if (d >= yesterday) groups["Yesterday"].push(t);
    else if (d >= weekAgo) groups["This Week"].push(t);
    else groups["Older"].push(t);
  }

  return groups;
}

export default function AssistantPage() {
  const { threads, activeThreadId, messages, input, loading, threadsLoading,
    setInput, send, retry, fetchThreads, loadThread, startNewThread } = useChat();

  const [showMemoryPanel, setShowMemoryPanel] = useState(false);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);

  useEffect(() => { fetchThreads(); }, [fetchThreads]);

  const loadMemoriesAndSkills = async () => {
    const [mRes, sRes] = await Promise.all([
      fetch("/api/chat/memories"),
      fetch("/api/chat/skills"),
    ]);
    if (mRes.ok) setMemories(await mRes.json());
    if (sRes.ok) setSkills(await sRes.json());
  };

  const deleteMemory = async (id: string) => {
    await fetch(`/api/chat/memories/${id}`, { method: "DELETE" });
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const deleteSkill = async (id: string) => {
    await fetch(`/api/chat/skills/${id}`, { method: "DELETE" });
    setSkills((prev) => prev.filter((s) => s.id !== id));
  };

  const grouped = groupByDate(threads);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left sidebar */}
      <div className="w-72 shrink-0 border-r border-border/50 bg-card/30 flex flex-col">
        <div className="p-3 border-b border-border/40 flex items-center gap-2 shrink-0">
          <button
            onClick={startNewThread}
            className="flex-1 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-md hover:bg-muted/30 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Chat
          </button>
          <button
            onClick={() => { setShowMemoryPanel((o) => !o); loadMemoriesAndSkills(); }}
            className={cn(
              "p-1.5 rounded-md transition-colors",
              showMemoryPanel
                ? "bg-blue-600/20 text-blue-400"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
            )}
            title="Memory & Skills"
          >
            <Brain className="w-4 h-4" />
          </button>
        </div>

        {showMemoryPanel ? (
          /* Memory & Skills panel */
          <div className="flex-1 overflow-y-auto p-3 space-y-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-blue-400 mb-2 flex items-center gap-1">
                <Brain className="w-3 h-3" /> Memories
              </div>
              {memories.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No memories yet. Tell the assistant to &quot;remember&quot; something.</p>
              ) : (
                <div className="space-y-1.5">
                  {memories.map((m) => (
                    <div key={m.id} className="flex gap-1.5 group">
                      <p className="flex-1 text-xs text-foreground/80">{m.content}</p>
                      <button onClick={() => deleteMemory(m.id)}
                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-400">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-blue-400 mb-2 flex items-center gap-1">
                <Zap className="w-3 h-3" /> Skills
              </div>
              {skills.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No skills yet. Describe a workflow and ask the assistant to save it as a skill.</p>
              ) : (
                <div className="space-y-2">
                  {skills.map((s) => (
                    <div key={s.id} className="group border border-border/30 rounded p-2">
                      <div className="flex justify-between items-start">
                        <span className="text-xs font-medium">{s.name}</span>
                        <button onClick={() => deleteSkill(s.id)}
                          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-400">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-[10px] text-blue-400 mt-0.5">trigger: &quot;{s.trigger_phrase}&quot;</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Thread list */
          <div className="flex-1 overflow-y-auto">
            {threadsLoading && (
              <p className="text-xs text-muted-foreground p-3">Loading…</p>
            )}
            {Object.entries(grouped).map(([label, group]) =>
              group.length > 0 ? (
                <div key={label}>
                  <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground/60 px-3 pt-3 pb-1">
                    {label}
                  </p>
                  {group.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => loadThread(t.id)}
                      className={cn(
                        "w-full text-left px-3 py-2 text-xs truncate hover:bg-muted/30 transition-colors",
                        activeThreadId === t.id ? "bg-muted/40 text-foreground" : "text-muted-foreground"
                      )}
                    >
                      {t.title ?? "Untitled"}
                    </button>
                  ))}
                </div>
              ) : null
            )}
          </div>
        )}
      </div>

      {/* Right panel */}
      <ChatPanel
        messages={messages}
        input={input}
        loading={loading}
        onInputChange={setInput}
        onSend={send}
        onRetry={retry}
        className="flex-1 min-w-0"
        placeholder="Ask about your portfolio, run an analysis, or define a new skill…"
      />
    </div>
  );
}
