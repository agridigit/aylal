import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import * as mod from "../src/irrigation-advice";
import { runVectors } from "./_f4";

describe("F4 advice (shared vectors f4_advice.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_advice.json");
});

describe("F4 referential gaps -> unavailable, never a default value (shared vectors f4_reference_gaps.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_reference_gaps.json");

  it("given the domain sources then no Kc, root depth or soil reserve literal exists (inventory)", () => {
    const dir = new URL("../src/", import.meta.url);
    const files = readdirSync(dir).filter((f) => /^(.*irrigation.*|water.*|et0.*|leaching.*|effective-rain.*|rainfed.*|advice.*|application.*)\.ts$/.test(f));
    expect(files).toContain("irrigation-advice.ts");
    const bad = /\b(kc|root_?depth\w*|rootDepth\w*|taw\w*|available_water\w*|reserve\w*|soil\w*)\s*[:=]\s*-?\d+(\.\d+)?/i;
    for (const f of files) {
      readFileSync(new URL(f, dir), "utf-8").split("\n").forEach((line, i) => {
        if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
        expect(bad.test(line), `${f}:${i + 1} ${line.trim()}`).toBe(false);
      });
    }
  });
});
