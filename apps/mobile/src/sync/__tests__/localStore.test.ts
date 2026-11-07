import { saveTrialRecord, getRecordSyncState, type LocalDb } from "../db";

// In-memory stand-in for the SQLite/PowerSync connection; inserts enqueue a ps_crud entry like PowerSync does.
function fakeDb(): LocalDb & { crud: { table: string; id: string }[] } {
  const tables: Record<string, Record<string, any>> = {};
  const crud: { table: string; id: string }[] = [];
  return {
    crud,
    async insert(table, row) {
      (tables[table] ??= {})[row.id] = row;
      crud.push({ table, id: row.id });
    },
    async getById(table, id) {
      return tables[table]?.[id] ?? null;
    },
    async pendingCrud(table, id) {
      return crud.filter((c) => c.table === table && c.id === id);
    },
  };
}

describe("local store", () => {
  it("given no network when the farmer creates a trial record then it is saved locally", async () => {
    const db = fakeDb();
    const id = await saveTrialRecord(db, { farm_id: "f1", title: "Row 3", quantity: 4 });
    expect(await db.getById("trial_records", id)).toMatchObject({ title: "Row 3", quantity: 4 });
  });

  it("given a locally saved record then its id is a client-generated uuid", async () => {
    const id = await saveTrialRecord(fakeDb(), { farm_id: "f1", title: "x" });
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  it("given an operation waiting in ps_crud then the record state is pending", async () => {
    const db = fakeDb();
    const id = await saveTrialRecord(db, { farm_id: "f1", title: "x" });
    expect(await getRecordSyncState(db, id)).toBe("pending");
  });

  it("given an invalid title then nothing is saved and no operation is queued", async () => {
    const db = fakeDb();
    await expect(saveTrialRecord(db, { farm_id: "f1", title: "   " })).rejects.toThrow();
    expect(db.crud).toHaveLength(0);
  });
});
