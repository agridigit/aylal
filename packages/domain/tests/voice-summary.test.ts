import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { orderSummary } from "../src/voice-summary";

const v: { name: string; parcels: { parcel_id: string; color: string; reason_key: string }[]; expected: string[] }[] = JSON.parse(
  readFileSync(new URL("../vectors/f3_summary.json", import.meta.url), "utf-8"),
);

describe("F3 voice summary order (FR-016)", () => {
  for (const c of v) {
    it(`given ${c.name} then the order matches`, () => {
      expect(orderSummary(c.parcels).map((p) => p.parcel_id)).toEqual(c.expected);
    });
  }
});
