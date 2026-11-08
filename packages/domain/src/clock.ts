/** F4 injected clock (G7). Mirror: services/api/app/domain/clock.py. The only system-time read is annotated `clock-allow`. */
export interface Clock {
  now(): Date;
}

export const FARM_TZ = "Africa/Casablanca";

export function fixedClock(iso: string): Clock {
  const t = new Date(iso).getTime();
  return { now: () => new Date(t) };
}

export interface AdvancingClock extends Clock {
  advance(ms: number): void;
}

export function advancingClock(iso: string): AdvancingClock {
  let t = new Date(iso).getTime();
  return {
    now: () => new Date(t),
    advance(ms: number) {
      t += ms;
    },
  };
}

export function systemClock(): Clock {
  return { now: () => new Date(Date.now()) }; // clock-allow
}

function parts(d: Date, tz: string): Record<string, string> {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit",
  });
  const out: Record<string, string> = {};
  for (const p of fmt.formatToParts(d)) out[p.type] = p.value;
  return out;
}

/** Local calendar day (YYYY-MM-DD) in the zone database of `tz`. */
export function localDay(d: Date, tz: string = FARM_TZ): string {
  const p = parts(d, tz);
  return `${p.year}-${p.month}-${p.day}`;
}

export function localHour(d: Date, tz: string = FARM_TZ): number {
  return Number(parts(d, tz).hour);
}

export function isBeforeLocalHour(d: Date, hour: number, tz: string = FARM_TZ): boolean {
  return localHour(d, tz) < hour;
}
