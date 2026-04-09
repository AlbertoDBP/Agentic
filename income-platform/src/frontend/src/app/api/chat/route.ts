// src/frontend/src/app/api/chat/route.ts
import { NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { assembleContext, truncateTitle } from "@/lib/chat-context";
import { buildToolDefinitions, executeTool } from "@/lib/chat-tools";
import { SYSTEM_PROMPT } from "@/lib/chat-system-prompt";

const ADMIN_PANEL_URL = process.env.ADMIN_PANEL_URL ?? "http://localhost:8100";
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

function serviceToken(): string {
  return process.env.SERVICE_JWT_TOKEN ?? process.env.SERVICE_TOKEN ?? "dev-token";
}
function svcHeaders() {
  return { Authorization: `Bearer ${serviceToken()}`, "Content-Type": "application/json" };
}

// ── Thread helpers ─────────────────────────────────────────────────────────────

async function createThread(title: string): Promise<string> {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads`, {
    method: "POST",
    headers: svcHeaders(),
    body: JSON.stringify({ title }),
  });
  const data = await r.json();
  return data.id as string;
}

async function saveMessages(threadId: string, messages: Array<{ role: string; raw: object }>) {
  await fetch(`${ADMIN_PANEL_URL}/api/chat/threads/${threadId}/messages`, {
    method: "POST",
    headers: svcHeaders(),
    body: JSON.stringify(messages),
  }).catch(() => {/* best effort */});
}

async function loadHistory(threadId: string): Promise<Anthropic.MessageParam[]> {
  const r = await fetch(`${ADMIN_PANEL_URL}/api/chat/threads/${threadId}/messages`, {
    headers: { Authorization: `Bearer ${serviceToken()}` },
  }).catch(() => null);
  if (!r?.ok) return [];
  const rows: Array<{ role: string; raw: Anthropic.MessageParam }> = await r.json();
  return rows.map((m) => m.raw);
}

// ── Main handler ───────────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const enc = new TextEncoder();
  const { message, thread_id, portfolio_id } = await req.json() as {
    message: string;
    thread_id?: string;
    portfolio_id?: string;
  };

  const userAuth = req.headers.get("authorization") ?? `Bearer ${serviceToken()}`;

  const stream = new ReadableStream({
    async start(controller) {
      const emit = (obj: object) =>
        controller.enqueue(enc.encode(`data: ${JSON.stringify(obj)}\n\n`));

      try {
        // 1. Create or resolve thread
        const threadId = thread_id ?? await createThread(truncateTitle(message));
        emit({ type: "thread_id", thread_id: threadId });

        // 2. Load thread history before saving the user message to avoid duplicates
        const history = await loadHistory(threadId);

        // 3. Save user message (after history load so it isn't included in history)
        await saveMessages(threadId, [{ role: "user", raw: { role: "user", content: message } }]);

        // 4. Assemble context
        const contextStr = await assembleContext({ portfolioId: portfolio_id, userAuthHeader: userAuth });

        // 5. Build messages array
        let messages: Anthropic.MessageParam[] = [
          ...history,
          { role: "user", content: message },
        ];

        const tools = buildToolDefinitions();

        // 6. Multi-turn streaming loop (max 5 rounds)
        let finalContentBlocks: Anthropic.ContentBlock[] = [];
        const intermediateMessages: Array<{ role: string; raw: object }> = [];

        for (let round = 0; round < 5; round++) {
          const response = await anthropic.messages.create({
            model: "claude-sonnet-4-6",
            max_tokens: 4096,
            system: `${SYSTEM_PROMPT}\n\n${contextStr}`,
            messages,
            tools,
            stream: true,
          });

          const contentBlocks: Anthropic.ContentBlock[] = [];
          let currentBlock: any = null;
          let stopReason = "";

          for await (const event of response) {
            if (event.type === "content_block_start") {
              currentBlock = { ...event.content_block };
              if (event.content_block.type === "text") {
                (currentBlock as any).text = "";
              } else if (event.content_block.type === "tool_use") {
                (currentBlock as any)._inputStr = "";
                emit({ type: "tool_start", name: event.content_block.name, id: event.content_block.id });
              }
            } else if (event.type === "content_block_delta") {
              if (event.delta.type === "text_delta" && currentBlock?.type === "text") {
                currentBlock.text += event.delta.text;
                emit({ type: "text", text: event.delta.text });
              } else if (event.delta.type === "input_json_delta" && currentBlock?.type === "tool_use") {
                currentBlock._inputStr = (currentBlock._inputStr ?? "") + event.delta.partial_json;
              }
            } else if (event.type === "content_block_stop") {
              if (currentBlock) {
                if (currentBlock.type === "tool_use") {
                  try { currentBlock.input = JSON.parse(currentBlock._inputStr ?? "{}"); }
                  catch { currentBlock.input = {}; }
                  delete currentBlock._inputStr;
                }
                contentBlocks.push(currentBlock);
              }
            } else if (event.type === "message_delta") {
              stopReason = event.delta.stop_reason ?? "";
            }
          }

          finalContentBlocks = contentBlocks;

          if (stopReason !== "tool_use") break;

          // Execute tools
          const toolUseBlocks = contentBlocks.filter(
            (b): b is Anthropic.ToolUseBlock => b.type === "tool_use"
          );
          const toolResults: Anthropic.ToolResultBlockParam[] = [];

          for (const block of toolUseBlocks) {
            const result = await executeTool(block.name, block.input as Record<string, unknown>);
            emit({ type: "tool_result", id: block.id, name: block.name, result });
            toolResults.push({
              type: "tool_result",
              tool_use_id: block.id,
              content: JSON.stringify(result),
            });
          }

          messages = [
            ...messages,
            { role: "assistant", content: contentBlocks },
            { role: "user", content: toolResults },
          ];

          // Collect intermediate messages for persistence
          intermediateMessages.push(
            { role: "assistant", raw: { role: "assistant", content: contentBlocks } },
            { role: "user", raw: { role: "user", content: toolResults } },
          );
        }

        // 7. Save intermediate tool turns + final assistant message
        await saveMessages(threadId, [
          ...intermediateMessages,
          { role: "assistant", raw: { role: "assistant", content: finalContentBlocks } },
        ]);

        emit({ type: "done" });
      } catch (err) {
        emit({ type: "error", message: err instanceof Error ? err.message : String(err) });
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
