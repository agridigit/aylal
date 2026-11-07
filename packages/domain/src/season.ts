export function canStartSeason(active: readonly { crop_id: string }[], cropId: string): "ok" | "season_already_active" {
  return active.some((s) => s.crop_id === cropId) ? "season_already_active" : "ok";
}

export type SeasonDateInput = { planting_year?: number | null; sowing_date?: string | null };

function validIsoDate(s: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const [y, mo, da] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const d = new Date(Date.UTC(y, mo - 1, da));
  return d.getUTCFullYear() === y && d.getUTCMonth() === mo - 1 && d.getUTCDate() === da;
}

/** Perennials take a planting year (1900..next year), annuals a sowing date; never both. */
export function seasonDate(crop: { cycle: string }, input: SeasonDateInput, today: string):
  { ok: true } | { ok: false; code: string } {
  const year = input.planting_year ?? null;
  const sowing = input.sowing_date ?? null;
  if (year !== null && sowing !== null) return { ok: false, code: "both_dates_forbidden" };
  if (year === null && sowing === null) return { ok: false, code: "date_required" };
  if (crop.cycle === "perennial") {
    if (year === null) return { ok: false, code: "wrong_date_kind" };
    const max = Number(today.slice(0, 4)) + 1;
    return Number.isInteger(year) && year >= 1900 && year <= max ? { ok: true } : { ok: false, code: "planting_year_out_of_range" };
  }
  if (sowing === null) return { ok: false, code: "wrong_date_kind" };
  return validIsoDate(sowing) ? { ok: true } : { ok: false, code: "sowing_date_invalid" };
}

export type SeasonStartPlan = { ok: true; closeIds: string[] } | { ok: false; code: "season_already_active" };

/** Rotation: only the requested active seasons are closed; the new crop may not stay active twice. */
export function planSeasonStart(active: readonly { id: string; crop_id: string }[], cropId: string, closeIds: readonly string[]): SeasonStartPlan {
  const closing = new Set(closeIds);
  const closed = active.filter((s) => closing.has(s.id));
  if (active.some((s) => !closing.has(s.id) && s.crop_id === cropId)) return { ok: false, code: "season_already_active" };
  return { ok: true, closeIds: closed.map((s) => s.id) };
}
