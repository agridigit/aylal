import { describe, expect, it } from "vitest";
import { tokens } from "../src/tokens";

function lum(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
export function ratio(a: string, b: string): number {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("theme contrast", () => {
  it("Given the sun theme, When measuring text on background and surface, Then the ratio is at least 7:1", () => {
    const t = tokens.themes.sun;
    expect(ratio(t.text, t.background)).toBeGreaterThanOrEqual(7);
    expect(ratio(t.text, t.surface)).toBeGreaterThanOrEqual(7);
    expect(ratio(t.onPrimary, t.primary)).toBeGreaterThanOrEqual(7);
  });

  it("Given the light and dark themes, When measuring text on background, Then the ratio is at least 4.5:1", () => {
    for (const k of ["light", "dark"] as const) {
      expect(ratio(tokens.themes[k].text, tokens.themes[k].background)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
