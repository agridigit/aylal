/** In-memory stand-in for the SQLite/PowerSync connection of the F4 view-model tests: inserts and updates enqueue a ps_crud entry
 *  (state "pending") exactly like PowerSync does, and `flush()` plays the replay of the queue against the server (idempotent by id). */
export type Row = Record<string, any>;
export function fakeDb() {
  const tables: Record<string, Record<string, Row>> = {};
  const crud: { table: string; id: string; op: "PUT" | "PATCH" }[] = [];
  return {
    crud,
    tables,
    async insert(table: string, row: Row) {
      (tables[table] ??= {})[row.id] = { ...row };
      crud.push({ table, id: row.id, op: "PUT" });
    },
    async update(table: string, id: string, patch: Row) {
      tables[table][id] = { ...tables[table][id], ...patch };
      crud.push({ table, id, op: "PATCH" });
    },
    async getById(table: string, id: string) {
      return tables[table]?.[id] ?? null;
    },
    async getAll(table: string, where: Row = {}) {
      return Object.values(tables[table] ?? {}).filter((r) => Object.entries(where).every(([k, v]) => r[k] === v));
    },
    async pendingCrud(table: string, id: string) {
      return crud.filter((c) => c.table === table && c.id === id);
    },
    flush(server: Map<string, Row>) {
      for (const c of crud.splice(0)) server.set(c.id, { ...tables[c.table][c.id] });
    },
  };
}
export const ids = (prefix = "00000000-0000-4000-8000-") => {
  let n = 0;
  return () => `${prefix}${String(++n).padStart(12, "0")}`;
};
