export type Stage = { key: string; gdd_from: number; label_key?: string };

const DAY_MS = 86_400_000;

/** Estimated stage: growing degree days when known, otherwise elapsed days (approximate). */
export function estimateStage(
  crop: { cycle: string; stages?: readonly Stage[] },
  season: { sowing_date?: string | null },
  today: string,
  gdd?: number | null,
): { stage: string | null; approximate: boolean } {
  const stages = [...(crop.stages ?? [])].sort((a, b) => a.gdd_from - b.gdd_from);
  if (!stages.length) return { stage: null, approximate: false };
  let value: number;
  const approximate = gdd == null;
  if (gdd != null) value = gdd;
  else {
    if (!season.sowing_date) return { stage: null, approximate: false };
    value = Math.floor((Date.parse(today) - Date.parse(season.sowing_date)) / DAY_MS);
  }
  if (value < 0) return { stage: null, approximate };
  let current = stages[0] as Stage;
  for (const s of stages) if (value >= s.gdd_from) current = s;
  return { stage: current.key, approximate };
}

/** The farmer's correction always wins over the estimate. */
export function displayStage(season: { stage_estimated?: string | null; stage_corrected?: string | null }): string | null {
  return season.stage_corrected ?? season.stage_estimated ?? null;
}
