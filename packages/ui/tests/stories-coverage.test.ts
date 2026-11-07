import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { catalog, STATES } from "../src/components/catalog";

const EXPECTED = ["Button", "Text", "Icon", "TextField", "Card", "Skeleton", "EmptyState", "ErrorState", "OfflineBanner", "SyncBadge", "Switch", "ListItem"];
const pascal = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

describe("component stories coverage", () => {
  it("Given the design system, When listing components, Then the 12 base components are exported", () => {
    expect(catalog.map((c) => c.name).sort()).toEqual([...EXPECTED].sort());
  });

  it("Given the states, When listed, Then they are default, active, disabled, loading, error", () => {
    expect([...STATES]).toEqual(["default", "active", "disabled", "loading", "error"]);
  });

  for (const c of catalog) {
    it(`Given ${c.name}, When reading its stories, Then every variant x state has a story`, () => {
      const file = new URL(`../src/components/${c.name}.stories.tsx`, import.meta.url);
      expect(existsSync(file)).toBe(true);
      const src = readFileSync(file, "utf-8");
      expect(c.variants.length).toBeGreaterThan(0);
      for (const v of c.variants) for (const s of STATES) {
        expect(src, `${c.name}: ${pascal(v)}${pascal(s)}`).toMatch(new RegExp(`export const ${pascal(v)}${pascal(s)}\\b`));
      }
    });
  }
});
