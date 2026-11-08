import { resolveEfficiency } from "@aylal/domain/irrigation-efficiency";
import { validateIrrigationSystem, type FieldError, type SystemInput } from "@aylal/domain/irrigation-system-validation";

export interface SystemDb {
  insert(table: string, row: Record<string, unknown>): Promise<void>;
  update(table: string, id: string, patch: Record<string, unknown>): Promise<void>;
  getAll(table: string, where?: Record<string, unknown>): Promise<Record<string, any>[]>;
  pendingCrud(table: string, id: string): Promise<unknown[]>;
}
export interface SystemDeps {
  db: SystemDb;
  newId: () => string;
  farmId: string;
}
/** `id` is empty and `errors` filled when nothing was saved. */
type SaveResult = { ok: boolean; id: string; errors: FieldError[] };

const TABLE = "irrigation_systems";

/** Offline description of an irrigation system: validated by the shared rule, saved locally (one active system per parcel), "pending" until replayed. */
export function createSystemViewModel(deps: SystemDeps) {
  return {
    async save(parcelId: string, input: SystemInput): Promise<SaveResult> {
      const check = validateIrrigationSystem(input);
      if (!check.valid) return { ok: false, id: "", errors: check.errors };
      const existing = (await deps.db.getAll(TABLE, { parcel_id: parcelId }))[0];
      if (existing) {
        await deps.db.update(TABLE, existing.id, { ...input });
        return { ok: true, id: existing.id, errors: [] };
      }
      const id = deps.newId();
      await deps.db.insert(TABLE, { id, farm_id: deps.farmId, parcel_id: parcelId, ...input });
      return { ok: true, id, errors: [] };
    },
    async read(parcelId: string) {
      const row = (await deps.db.getAll(TABLE, { parcel_id: parcelId }))[0];
      if (!row) return null;
      const eff = resolveEfficiency({ kind: row.kind, efficiency: row.efficiency ?? null });
      return { ...row, efficiency_effective: eff.efficiency, efficiency_is_default: eff.is_default };
    },
    async syncState(id: string): Promise<"pending" | "synced"> {
      return (await deps.db.pendingCrud(TABLE, id)).length > 0 ? "pending" : "synced";
    },
  };
}
