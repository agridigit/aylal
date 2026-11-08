import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { isScenePublishable } from "../src/vigor";

const v: { clear_pct: number; publishable: boolean }[] = JSON.parse(readFileSync(new URL("../vectors/f3_cloud_rule.json", import.meta.url), "utf-8"));

describe("F3 80 % clear-sky rule (FR-007)", () => {
  for (const c of v) {
    it(`given ${c.clear_pct} % clear when publishing then ${c.publishable}`, () => {
      expect(isScenePublishable(c.clear_pct)).toBe(c.publishable);
    });
  }
});
