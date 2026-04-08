import { directionality } from "../lib/score-breakdown";

describe("directionality", () => {
  it("returns Strong at boundary 0.85", () => expect(directionality(17, 20)).toBe("Strong"));
  it("returns Strong above 0.85",       () => expect(directionality(20, 20)).toBe("Strong"));
  it("returns Moderate at 0.65",        () => expect(directionality(13, 20)).toBe("Moderate"));
  it("returns Moderate between 0.65-0.85", () => expect(directionality(15, 20)).toBe("Moderate"));
  it("returns Weak at 0.40",            () => expect(directionality(8, 20)).toBe("Weak"));
  it("returns Critical below 0.40",     () => expect(directionality(5, 20)).toBe("Critical"));
  it("handles max=0 gracefully",        () => expect(directionality(5, 0)).toBe("Weak"));
  it("handles score > max",             () => expect(directionality(25, 20)).toBe("Strong"));
});
