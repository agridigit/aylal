import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { fixedClock } from "../../src/clock";
import * as limits from "../../src/economics-limits";
import * as trend from "../../src/price-trend";
import { pick, type Mod } from "./_f8";

const RULE_FILES = ["money", "expense-allocation", "farm-economics", "stock-ledger", "weighted-average-cost", "price-trend", "receipt-proposal", "economics-limits"];
const day = (iso: string, delta: number): string => new Date(Date.parse(`${iso}T00:00:00Z`) + delta * 86_400_000).toISOString().slice(0, 10);

describe("F8 injected clock (G7, FR-021)", () => {
  // 2026-06-04T23:30Z is already 2026-06-05 in Africa/Casablanca (UTC+1 in June)
  const clock = fixedClock("2026-06-04T23:30:00Z");
  const status = (...a: unknown[]): unknown => pick(limits as unknown as Mod, "date_status")(...a);

  it("given a UTC evening when reading the farm day then the local Casablanca date is used", () => {
    expect(status("2026-06-05", clock)).toBe("ok");
    expect(status(day("2026-06-05", 1), clock)).toBe("ok");
  });
  it("given the future tolerance when dating an entry then local today + 1 passes and + 2 is refused", () => {
    expect(status(day("2026-06-05", 2), clock)).toBe("in_future");
  });
  it("given the backdating cap when dating an entry then 800 days pass and 801 are refused", () => {
    expect(status(day("2026-06-05", -800), clock)).toBe("ok");
    expect(status(day("2026-06-05", -801), clock)).toBe("too_old");
  });
  it("given the price window when asked then it covers 13 weeks ending on the local day", () => {
    const w = pick(trend as unknown as Mod, "trend_window")(clock);
    expect(w).toEqual({ from: day("2026-06-05", -91), to: "2026-06-05", weeks: 13 });
  });
  it("given a price when older than 14 local days then it is stale, 14 is not", () => {
    const stale = pick(trend as unknown as Mod, "is_stale_price");
    expect(stale(day("2026-06-05", -14), clock)).toBe(false);
    expect(stale(day("2026-06-05", -15), clock)).toBe(true);
  });
  it("given the F8 rule modules then each exports something and none reads the system clock", () => {
    const direct = /(new Date\(\)|Date\.now\(|performance\.now\(|Intl\.DateTimeFormat\(\)\.resolved)/;
    for (const f of RULE_FILES) {
      const text = readFileSync(new URL(`../../src/${f}.ts`, import.meta.url), "utf-8");
      expect(text.includes("export function") || text.includes("export const"), `${f}.ts is still a skeleton`).toBe(true);
      for (const [i, line] of text.split("\n").entries()) {
        expect(direct.test(line.split("//")[0]!) && !line.includes("clock-allow"), `${f}.ts:${i + 1}`).toBe(false);
      }
    }
  });
});
