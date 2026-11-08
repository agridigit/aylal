import { staleness } from "@aylal/domain/staleness";

export interface Freshness {
  state: "fresh" | "stale" | "never";
  ageHours: number | null;
  fetchedAt: string | null;
}

/** What every dashboard screen shows about the age of its data (FR-017). */
export function describeFreshness(fetchedAt: string | null, now: string): Freshness {
  const s = staleness(fetchedAt, now);
  if (fetchedAt === null) return { state: "never", ageHours: null, fetchedAt: null };
  return { state: s.stale ? "stale" : "fresh", ageHours: s.ageHours, fetchedAt };
}
