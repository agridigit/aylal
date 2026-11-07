import { createLocalDb, type PowerSyncLike } from "../powersyncAdapter";

function fakePs() {
  const calls: { sql: string; params: unknown[] }[] = [];
  const ps: PowerSyncLike & { rows: any[] } = {
    rows: [],
    async execute(sql, params = []) {
      calls.push({ sql, params });
      return {};
    },
    async getOptional(sql, params = []) {
      calls.push({ sql, params });
      return ps.rows[0] ?? null;
    },
    async getAll(sql, params = []) {
      calls.push({ sql, params });
      return ps.rows;
    },
  };
  return { ps, calls };
}

describe("PowerSync adapter behind LocalDb", () => {
  it("given a record when inserting then it is written to the synced table with bound parameters", async () => {
    const { ps, calls } = fakePs();
    await createLocalDb(ps).insert("trial_records", { id: "r1", farm_id: "f1", title: "Row 3", note: undefined, quantity: 4 });
    expect(calls).toHaveLength(1);
    expect(calls[0]!.sql).toBe("INSERT INTO trial_records (id, farm_id, title, note, quantity) VALUES (?, ?, ?, ?, ?)");
    expect(calls[0]!.params).toEqual(["r1", "f1", "Row 3", null, 4]);
  });

  it("given an unknown table or a suspicious column name then nothing is executed", async () => {
    const { ps, calls } = fakePs();
    const db = createLocalDb(ps);
    await expect(db.insert("users; DROP TABLE x", { id: "r1" })).rejects.toThrow();
    await expect(db.insert("trial_records", { id: "r1", "title) VALUES (1); --": "x" })).rejects.toThrow();
    expect(calls).toHaveLength(0);
  });

  it("given a stored row when reading by id then it is returned, and null when missing", async () => {
    const { ps, calls } = fakePs();
    const db = createLocalDb(ps);
    expect(await db.getById("trial_records", "r1")).toBeNull();
    ps.rows = [{ id: "r1", title: "x" }];
    expect(await db.getById("trial_records", "r1")).toEqual({ id: "r1", title: "x" });
    expect(calls[0]!.sql).toBe("SELECT * FROM trial_records WHERE id = ?");
    expect(calls[0]!.params).toEqual(["r1"]);
  });

  it("given operations waiting in ps_crud then they are listed for that record only", async () => {
    const { ps, calls } = fakePs();
    ps.rows = [{ id: 1 }];
    const pending = await createLocalDb(ps).pendingCrud("trial_records", "r1");
    expect(pending).toHaveLength(1);
    expect(calls[0]!.sql).toContain("FROM ps_crud");
    expect(calls[0]!.params).toEqual(["trial_records", "r1"]);
  });
});
