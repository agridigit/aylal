import type { LocalDb } from "./db";

/** The slice of PowerSyncDatabase used by the app; the real one is injected, tests pass a double. */
export interface PowerSyncLike {
  execute(sql: string, params?: unknown[]): Promise<unknown>;
  getOptional<T = Record<string, any>>(sql: string, params?: unknown[]): Promise<T | null>;
  getAll<T = Record<string, any>>(sql: string, params?: unknown[]): Promise<T[]>;
}

const TABLES = new Set(["trial_records"]);
const IDENTIFIER = /^[a-z_][a-z0-9_]*$/;

function assertTable(table: string): void {
  if (!TABLES.has(table)) throw new Error(`unknown table: ${table}`);
}

/** LocalDb over PowerSync: inserts go through the synced view, so PowerSync enqueues them in ps_crud. */
export function createLocalDb(ps: PowerSyncLike): LocalDb {
  return {
    async insert(table, row) {
      assertTable(table);
      const columns = Object.keys(row);
      for (const c of columns) if (!IDENTIFIER.test(c)) throw new Error(`invalid column: ${c}`);
      const marks = columns.map(() => "?").join(", ");
      await ps.execute(
        `INSERT INTO ${table} (${columns.join(", ")}) VALUES (${marks})`,
        columns.map((c) => row[c] ?? null),
      );
    },
    async getById(table, id) {
      assertTable(table);
      return ps.getOptional(`SELECT * FROM ${table} WHERE id = ?`, [id]);
    },
    async pendingCrud(table, id) {
      assertTable(table);
      return ps.getAll(
        "SELECT id FROM ps_crud WHERE json_extract(data, '$.type') = ? AND json_extract(data, '$.id') = ?",
        [table, id],
      );
    },
  };
}
