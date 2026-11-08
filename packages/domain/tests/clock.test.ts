import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { advancingClock, fixedClock, isBeforeLocalHour, localDay, localHour } from "../src/clock";

const TZ = "Africa/Casablanca";

function offsetMinutes(d: Date): number {
  const p = new Intl.DateTimeFormat("en-US", { timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).formatToParts(d);
  const g = (t: string) => Number(p.find((x) => x.type === t)!.value);
  return (Date.UTC(g("year"), g("month") - 1, g("day"), g("hour"), g("minute")) - d.getTime()) / 60000;
}

/** Instants where the Casablanca UTC offset changes during `year`, found by scanning, never hardcoded. */
function offsetChanges(year: number): Date[] {
  const out: Date[] = [];
  let prev = offsetMinutes(new Date(Date.UTC(year, 0, 1)));
  for (let h = 1; h < 366 * 24; h++) {
    const d = new Date(Date.UTC(year, 0, 1) + h * 3600_000);
    const o = offsetMinutes(d);
    if (o !== prev) out.push(d);
    prev = o;
  }
  return out;
}

describe("F4 injected clock (G7)", () => {
  it("given a fixed clock when reading now twice then the same instant is returned", () => {
    const c = fixedClock("2026-06-04T03:00:00Z");
    expect(c.now().toISOString()).toBe("2026-06-04T03:00:00.000Z");
    expect(c.now().getTime()).toBe(c.now().getTime());
  });
  it("given an advancing clock when advanced by 90 minutes then now moves by exactly that", () => {
    const c = advancingClock("2026-06-04T03:00:00Z");
    c.advance(90 * 60_000);
    expect(c.now().toISOString()).toBe("2026-06-04T04:30:00.000Z");
  });
  it("given 23:30 UTC in winter and in summer when asking the local day then it follows the offset of the zone database", () => {
    for (const iso of ["2026-01-15T23:30:00Z", "2026-07-15T23:30:00Z"]) {
      const t = new Date(iso);
      const expected = new Date(t.getTime() + offsetMinutes(t) * 60_000).toISOString().slice(0, 10);
      expect(localDay(fixedClock(iso).now(), TZ)).toBe(expected);
    }
  });
  it("given every UTC offset change of the year when crossing it then the local day and hour follow the zone database", () => {
    const changes = offsetChanges(2026);
    expect(changes.length).toBeGreaterThanOrEqual(2); // Ramadan: the offset changes at least twice a year
    for (const t of changes) {
      const before = new Date(t.getTime() - 3600_000);
      const hb = localHour(before, TZ), ha = localHour(t, TZ);
      expect(ha).not.toBe((hb + 1) % 24); // an hour is skipped or repeated at the transition
      expect(localDay(t, TZ)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });
  it("given local midnight when one minute before and after then the local day changes exactly there", () => {
    const winter = new Date("2026-01-15T00:00:00Z");
    for (let m = 0; m < 24 * 60; m += 1) {
      const t = new Date(winter.getTime() + m * 60_000);
      const prev = new Date(t.getTime() - 60_000);
      if (localDay(t, TZ) !== localDay(prev, TZ)) {
        expect(localHour(t, TZ)).toBe(0);
        return;
      }
    }
    throw new Error("no local midnight found in 24 h");
  });
  it("given the clock before and after 07:00 local when asking ready-before-7 then the boundary is exact", () => {
    for (let m = 0; m < 24 * 60; m += 1) {
      const t = new Date(Date.UTC(2026, 5, 4) + m * 60_000);
      const h = localHour(t, TZ);
      const minute = Number(new Intl.DateTimeFormat("en-US", { timeZone: TZ, minute: "numeric" }).format(t));
      expect(isBeforeLocalHour(t, 7, TZ)).toBe(h < 7);
      if (h === 6 && minute === 59) expect(isBeforeLocalHour(t, 7, TZ)).toBe(true);
      if (h === 7 && minute === 0) expect(isBeforeLocalHour(t, 7, TZ)).toBe(false);
    }
  });
  it("given the F4 domain sources then none reads the system time directly (inventory)", () => {
    const dir = new URL("../src/", import.meta.url);
    const files = readdirSync(dir).filter((f) => /^(.*irrigation.*|water.*|et0.*|leaching.*|clock.*)\.ts$/.test(f));
    expect(files).toContain("clock.ts");
    expect(files.length).toBeGreaterThanOrEqual(5);
    for (const f of files) {
      const lines = readFileSync(new URL(f, dir), "utf-8").split("\n");
      lines.forEach((line, i) => {
        if (/^\s*(\/\/|\*|\/\*)/.test(line) || line.includes("clock-allow")) return; // the single system-clock read is annotated
        expect(/(\bnew Date\(\)|Date\.now\(|performance\.now\()/.test(line), `${f}:${i + 1} ${line.trim()}`).toBe(false);
      });
    }
  });
});
