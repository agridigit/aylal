import { validate } from "@aylal/domain/validation";
import { deriveSyncState, type SyncState } from "./syncState";

/** Minimal local-database port; the PowerSync/SQLite adapter implements it (inserts enqueue ps_crud). */
export interface LocalDb {
  insert(table: string, row: Record<string, unknown> & { id: string }): Promise<void>;
  getById(table: string, id: string): Promise<Record<string, any> | null>;
  pendingCrud(table: string, id: string): Promise<unknown[]>;
}

export type TrialRecordInput = { farm_id: string; title: string; note?: string | null; quantity?: number | null };

function uuidv4(): string {
  const b = Array.from({ length: 16 }, () => Math.floor(Math.random() * 256));
  b[6] = ((b[6] as number) & 0x0f) | 0x40;
  b[8] = ((b[8] as number) & 0x3f) | 0x80;
  const h = b.map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export async function saveTrialRecord(db: LocalDb, input: TrialRecordInput): Promise<string> {
  const { farm_id, ...fields } = input;
  const verdict = validate("trial_record.create", fields);
  if (!verdict.valid) throw new Error(`invalid trial record: ${verdict.errors.map((e) => e.field).join(",")}`);
  const id = uuidv4();
  await db.insert("trial_records", { id, farm_id, ...fields, title: fields.title.trim() });
  return id;
}

export async function getRecordSyncState(db: LocalDb, id: string): Promise<SyncState> {
  const row = await db.getById("trial_records", id);
  const pending = await db.pendingCrud("trial_records", id);
  return deriveSyncState({
    hasPendingOps: pending.length > 0,
    hasConflict: Boolean(row?.has_conflict),
    serverVersion: row?.server_version ?? null,
  });
}
