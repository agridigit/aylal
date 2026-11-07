import { debugStateFrom } from "../debugState";

describe("debugStateFrom (deep link aylal://home?debugState=… used by Maestro flows)", () => {
  it("returns the requested state when E2E debug is enabled", () => {
    expect(debugStateFrom("error", true)).toBe("error");
    expect(debugStateFrom("loading", true)).toBe("loading");
  });
  it("ignores the parameter when E2E debug is disabled (production builds)", () => {
    expect(debugStateFrom("error", false)).toBeNull();
  });
  it("ignores unknown or missing values", () => {
    expect(debugStateFrom("boom", true)).toBeNull();
    expect(debugStateFrom(undefined, true)).toBeNull();
    expect(debugStateFrom(["error"], true)).toBe("error");
  });
});
