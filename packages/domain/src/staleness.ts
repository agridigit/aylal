/** Data older than this is shown as stale (FR-017). */
export const STALE_AFTER_HOURS = 24;

/** Age of a piece of data and whether it is stale; never negative, no invented date when nothing was loaded. */
export function staleness(
  fetchedAt: string | null,
  now: string | Date,
  staleAfterHours: number = STALE_AFTER_HOURS,
): { ageHours: number | null; stale: boolean } {
  if (fetchedAt === null) return { ageHours: null, stale: true };
  const ageHours = Math.max(0, (new Date(now).getTime() - Date.parse(fetchedAt)) / 3_600_000);
  return { ageHours, stale: ageHours > staleAfterHours };
}
