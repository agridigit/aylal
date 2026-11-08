import { LIMITS } from "./irrigation-limits";

export interface EventInput {
  duration_min?: number | null; volume_m3?: number | null; performed_on: string; today: string; slot_count: number; area_ha?: number | null;
}
const err = (field: string, code: string) => ({ field, code, i18n_key: `irrigation.event.${field}.${code}` });
const DAY = 86_400_000;
const days = (a: string, b: string) => Math.round((Date.parse(a) - Date.parse(b)) / DAY);

/** R3: exactly one of duration or volume, caps (24 h, 24 per day and sector, 1000 m3/ha, 400 days back); a second event on the slot is only flagged. */
export function validateIrrigationEvent(i: EventInput): {
  valid: boolean; errors: any[]; possible_duplicate: boolean;
} {
  const errors: { field: string; code: string; i18n_key: string }[] = [];
  const hasD = i.duration_min !== null && i.duration_min !== undefined;
  const hasV = i.volume_m3 !== null && i.volume_m3 !== undefined;
  if (hasD === hasV) errors.push(err(hasD ? "volume_m3" : "duration_min", "exactly_one_of_duration_or_volume"));
  if (hasD && !(i.duration_min! >= 1 && i.duration_min! <= LIMITS.durationMin)) errors.push(err("duration_min", "out_of_range"));
  if (hasV && !(i.volume_m3! > 0)) errors.push(err("volume_m3", "out_of_range"));
  if (hasV && i.area_ha && i.volume_m3! > LIMITS.volumeM3PerHa * i.area_ha) errors.push(err("volume_m3", "out_of_range"));
  const back = days(i.today, i.performed_on);
  if (back < 0) errors.push(err("performed_on", "in_the_future"));
  else if (back > LIMITS.backdateDays) errors.push(err("performed_on", "too_old"));
  if (i.slot_count >= LIMITS.eventsPerDaySector) errors.push(err("performed_on", "events_per_day_sector"));
  return { valid: errors.length === 0, errors, possible_duplicate: i.slot_count >= 1 };
}
