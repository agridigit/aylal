import { localDay, type Clock } from "@aylal/domain/clock";
import { validateIrrigationEvent } from "@aylal/domain/irrigation-event";
import { fromDuration, fromVolume } from "@aylal/domain/irrigation-units";

export interface RecordDb {
  insert(table: string, row: Record<string, unknown>): Promise<void>;
  update(table: string, id: string, patch: Record<string, unknown>): Promise<void>;
  getAll(table: string, where?: Record<string, unknown>): Promise<Record<string, any>[]>;
  pendingCrud(table: string, id: string): Promise<unknown[]>;
}
export interface RecordSystem { rate_mm_h: number | null; efficiency: number | null; area_m2: number | null; sectors_count: number }
export interface RecordDeps { db: RecordDb; newId: () => string; farmId: string; role: string; clock: Clock; system?: RecordSystem }
export interface AdviceToRecord { parcel_id: string; sectors: { sector_no: number; minutes: number }[]; [extra: string]: unknown }
type Recorded = {
  ok: boolean; id: string; pending: boolean; gestures: number; volume_m3?: number | null; duration_min?: number | null;
  errors: { field: string; code: string; i18n_key: string }[];
};

const TABLE = "irrigation_events";

/** Records an irrigation locally (one gesture from the advice), marked "to send", counted at once in the local balance. */
export function createRecordViewModel(deps: RecordDeps) {
  const applied = new Map<string, number>(); // `${parcel}|${day}` -> net mm, cancelled rows excluded
  const sys = deps.system ?? { rate_mm_h: null, efficiency: null, area_m2: null, sectors_count: 1 };
  const today = () => localDay(deps.clock.now());

  async function save(row: { parcel_id: string; performed_on: string; sector_no: number | null; duration_min: number | null; volume_m3: number | null }, netMm: number | null): Promise<Recorded> {
    const id = deps.newId();
    const mode = row.duration_min !== null ? "duration" : "volume";
    await deps.db.insert(TABLE, { id, farm_id: deps.farmId, ...row, input_mode: mode, status: "done" });
    if (netMm !== null) {
      const key = `${row.parcel_id}|${row.performed_on}`;
      applied.set(key, (applied.get(key) ?? 0) + netMm);
    }
    return { ok: true, id, pending: true, gestures: 1, errors: [] };
  }

  async function record(row: { parcel_id: string; performed_on: string; sector_no?: number | null; duration_min: number | null; volume_m3: number | null }, netMm: (() => number | null)): Promise<Recorded> {
    const sector = row.sector_no ?? null;
    const slot = (await deps.db.getAll(TABLE, { parcel_id: row.parcel_id, performed_on: row.performed_on })).filter((r) => r.status === "done" && (r.sector_no ?? null) === sector).length;
    const check = validateIrrigationEvent({
      duration_min: row.duration_min, volume_m3: row.volume_m3, performed_on: row.performed_on, today: today(), slot_count: slot,
      area_ha: sys.area_m2 === null ? null : sys.area_m2 / 10_000,
    });
    if (!check.valid) return { ok: false, id: "", pending: false, gestures: 0, errors: check.errors };
    return await save({ ...row, sector_no: sector }, netMm());
  }

  return {
    async recordFromAdvice(advice: AdviceToRecord, sectorNo: number) {
      const minutes = advice.sectors.find((s) => s.sector_no === sectorNo)?.minutes ?? null;
      const performed_on = today();
      const net = minutes === null ? null : fromDuration({ minutes, ...sys }).net_mm;
      return await save({ parcel_id: advice.parcel_id, performed_on, sector_no: sectorNo, duration_min: minutes, volume_m3: null }, net);
    },
    async recordByDuration(i: { parcel_id: string; duration_min: number; performed_on: string; sector_no?: number | null }) {
      const converted = fromDuration({ minutes: i.duration_min, ...sys });
      const out = await record({ ...i, volume_m3: null }, () => converted.net_mm);
      return { ...out, volume_m3: out.ok ? converted.volume_m3 : null };
    },
    async recordByVolume(i: { parcel_id: string; volume_m3: number; performed_on: string; sector_no?: number | null }) {
      const converted = fromVolume({ volume_m3: i.volume_m3, ...sys });
      const out = await record({ ...i, duration_min: null }, () => converted.net_mm);
      return { ...out, duration_min: out.ok ? converted.minutes : null };
    },
    localAppliedMm(parcelId: string, day: string): number {
      return applied.get(`${parcelId}|${day}`) ?? 0;
    },
    async cancel(id: string) {
      const row = (await deps.db.getAll(TABLE)).find((r) => r.id === id);
      await deps.db.update(TABLE, id, { status: "cancelled" });
      if (row?.status === "done") {
        // the net depth of a cancelled row leaves the local balance at once (recomputed from the row, not remembered)
        const key = `${row.parcel_id}|${row.performed_on}`;
        const minutes = row.duration_min ?? (row.volume_m3 === null ? null : fromVolume({ volume_m3: row.volume_m3, ...sys }).minutes);
        const net = minutes === null ? 0 : (fromDuration({ minutes, ...sys }).net_mm ?? 0);
        applied.set(key, Math.max(0, (applied.get(key) ?? 0) - net));
      }
    },
  };
}
