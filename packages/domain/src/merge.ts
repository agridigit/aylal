import { areaHa } from "./area";
import { ringsTouch } from "./overlap";
import type { Pt } from "./area";

export type MergeField = { id: string; ring: Pt[] };
export type MergeSeason = { id: string; field_id: string; crop_id: string; started_at: string; ended_at: string | null };
export type MergeResult =
  | { ok: true; areaHa: number; keptSeasonIds: string[]; droppedSeasonIds: string[] }
  | { ok: false; code: "merge_not_contiguous" | "merge_needs_two_fields" };

/** Merge fields into the survivor: they must form one contiguous group; duplicate active crops keep the oldest season. */
export function mergeFields(survivor: MergeField, others: readonly MergeField[], seasons: readonly MergeSeason[]): MergeResult {
  if (others.length === 0) return { ok: false, code: "merge_needs_two_fields" };
  const all = [survivor, ...others];
  const seen = new Set<number>([0]);
  const queue = [0];
  while (queue.length) {
    const i = queue.shift()!;
    all.forEach((f, j) => { if (!seen.has(j) && ringsTouch((all[i] as MergeField).ring, f.ring)) { seen.add(j); queue.push(j); } });
  }
  if (seen.size !== all.length) return { ok: false, code: "merge_not_contiguous" };

  const ids = new Set(all.map((f) => f.id));
  const mine = seasons.filter((s) => ids.has(s.field_id));
  const dropped = new Set<string>();
  const byCrop = new Map<string, MergeSeason[]>();
  for (const s of mine) if (s.ended_at === null) byCrop.set(s.crop_id, [...(byCrop.get(s.crop_id) ?? []), s]);
  for (const group of byCrop.values()) {
    const sorted = [...group].sort((a, b) => a.started_at.localeCompare(b.started_at) || a.id.localeCompare(b.id));
    sorted.slice(1).forEach((s) => dropped.add(s.id));
  }
  return {
    ok: true,
    areaHa: all.reduce((s, f) => s + areaHa(f.ring), 0),
    keptSeasonIds: mine.filter((s) => !dropped.has(s.id)).map((s) => s.id),
    droppedSeasonIds: [...dropped],
  };
}
