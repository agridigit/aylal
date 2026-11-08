export interface BadgeDb {
  pendingCrud(table: string, id: string): Promise<unknown[]>;
  getAll(table: string, where?: Record<string, unknown>): Promise<Record<string, any>[]>;
}

/** "To send" badge of a local record, from the upload queue. */
export function createPendingBadge(deps: { db: BadgeDb }) {
  return {
    async forRecord(id: string, table = "irrigation_events"): Promise<{ pending: boolean; label_key: string | null }> {
      const pending = (await deps.db.pendingCrud(table, id)).length > 0;
      return { pending, label_key: pending ? "irrigation.pending_upload" : null };
    },
    async count(table: string): Promise<number> {
      const rows = await deps.db.getAll(table);
      let n = 0;
      for (const r of rows) if ((await deps.db.pendingCrud(table, r.id)).length > 0) n += 1;
      return n;
    },
  };
}
