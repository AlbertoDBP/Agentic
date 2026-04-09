// src/frontend/src/__tests__/chat-context.test.ts
import { buildPositionSummary, buildPortfolioSnapshot, truncateTitle } from "@/lib/chat-context";

describe("truncateTitle", () => {
  it("truncates at word boundary within 60 chars", () => {
    const long = "What are the highest yielding positions in my portfolio right now";
    const result = truncateTitle(long);
    expect(result.length).toBeLessThanOrEqual(63); // "..." adds 3
    expect(result).toContain("...");
  });

  it("returns as-is when under 60 chars", () => {
    expect(truncateTitle("Short title")).toBe("Short title");
  });
});

describe("buildPositionSummary", () => {
  const positions = [
    { symbol: "MAIN", asset_type: "BDC", hhs_status: "GOOD", score: 82, ies_calculated: true, ies_score: 76 },
    { symbol: "OXLC", asset_type: "CEF", hhs_status: "UNSAFE", score: 41, ies_calculated: false, ies_blocked_reason: "UNSAFE_FLAG" },
  ];

  it("formats position table with symbol, type, HHS, score, IES", () => {
    const result = buildPositionSummary(positions as any[]);
    expect(result).toContain("MAIN");
    expect(result).toContain("GOOD");
    expect(result).toContain("82");
    expect(result).toContain("UNSAFE");
    expect(result).toContain("blocked");
  });
});

describe("buildPortfolioSnapshot", () => {
  it("handles missing optional fields gracefully", () => {
    const portfolio = { id: "abc", name: "Test", total_value: null, blended_yield: null, position_count: 0 };
    const result = buildPortfolioSnapshot(portfolio as any, true);
    expect(result).toContain("Test");
    expect(result).not.toThrow;
  });
});
