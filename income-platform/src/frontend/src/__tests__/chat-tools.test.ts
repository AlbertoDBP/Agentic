// src/frontend/src/__tests__/chat-tools.test.ts
import { buildToolDefinitions } from "@/lib/chat-tools";

describe("buildToolDefinitions", () => {
  it("returns 7 tools", () => {
    const tools = buildToolDefinitions();
    expect(tools).toHaveLength(7);
  });

  it("all tools have required Anthropic schema fields", () => {
    const tools = buildToolDefinitions();
    for (const tool of tools) {
      expect(tool.name).toBeDefined();
      expect(tool.description).toBeDefined();
      expect(tool.input_schema).toBeDefined();
      expect(tool.input_schema.type).toBe("object");
    }
  });

  it("create_proposal_draft requires ticker and portfolio_id", () => {
    const tools = buildToolDefinitions();
    const t = tools.find((t) => t.name === "create_proposal_draft")!;
    expect(t.input_schema.required).toContain("ticker");
    expect(t.input_schema.required).toContain("portfolio_id");
  });

  it("get_score_breakdown requires symbol", () => {
    const tools = buildToolDefinitions();
    const t = tools.find((t) => t.name === "get_score_breakdown")!;
    expect(t.input_schema.required).toContain("symbol");
  });
});
