import { uploadBatch, type CrudEntry } from "./connector";

export type PsCrudEntry = {
  clientId: number;
  op: "PUT" | "PATCH" | "DELETE";
  table: string;
  id: string;
  opData?: Record<string, unknown>;
};
export type CrudTx = { crud: PsCrudEntry[]; complete(): Promise<void> };
type CrudSource = { getNextCrudTransaction(): Promise<CrudTx | null> };

type Deps = {
  apiUrl: string;
  powersyncUrl: string;
  /** null in production builds: there is no test identity, so no dev token is requested. */
  userId: string | null;
  fetchImpl?: typeof fetch;
};

const ACKNOWLEDGED = new Set(["applied", "duplicate", "conflict_logged"]);

/** Stable op id per queue entry: same entry -> same id on every retry (server answers "duplicate"). */
export function opIdFor(recordId: string, clientId: number): string {
  const hex = recordId.replace(/-/g, "").toLowerCase();
  const tail = (clientId >>> 0).toString(16).padStart(8, "0");
  const h = `${hex.slice(0, 24)}${tail}`;
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function toEntry(e: PsCrudEntry): CrudEntry {
  const { farm_id, ...data } = e.opData ?? {};
  return {
    id: opIdFor(e.id, e.clientId),
    op: e.op,
    table: e.table,
    record_id: e.id,
    farm_id: farm_id as string | undefined,
    base_version: 0,
    data,
  };
}

export function createConnector({ apiUrl, powersyncUrl, userId, fetchImpl = fetch }: Deps) {
  async function token(): Promise<{ token: string; expiresAt: Date | undefined }> {
    if (!userId) throw new Error("no credentials available");
    const res = await fetchImpl(`${apiUrl}/auth/dev-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (!res.ok) throw new Error(`token request failed: ${res.status}`);
    const body = (await res.json()) as { token: string; expires_at?: string };
    const exp = body.expires_at ? new Date(body.expires_at) : undefined;
    return { token: body.token, expiresAt: exp && !Number.isNaN(exp.getTime()) ? exp : undefined };
  }

  return {
    async fetchCredentials() {
      const t = await token();
      return { endpoint: powersyncUrl, token: t.token, expiresAt: t.expiresAt };
    },
    /** Any failure or non-acknowledged op throws: the transaction stays in ps_crud and is retried. */
    async uploadData(db: CrudSource): Promise<void> {
      const tx = await db.getNextCrudTransaction();
      if (!tx) return;
      const entries = tx.crud.map(toEntry);
      const results = await uploadBatch(apiUrl, (await token()).token, entries, fetchImpl);
      for (const e of entries) {
        const r = results.find((x) => x.op_id === e.id);
        if (!r || !ACKNOWLEDGED.has(r.status)) throw new Error(`upload not acknowledged: ${e.id} ${r?.status ?? "missing"}`);
      }
      await tx.complete();
    },
  };
}
