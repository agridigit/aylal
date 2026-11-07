export type CrudEntry = {
  id: string;
  op: "PUT" | "PATCH" | "DELETE";
  table: string;
  record_id: string;
  farm_id?: string;
  base_version: number;
  data?: Record<string, unknown>;
};

const KIND = { PUT: "put", PATCH: "patch", DELETE: "delete" } as const;

/** Sends the ps_crud queue to POST /v1/sync/upload; an entry leaves the queue only once acknowledged. */
export async function uploadBatch(
  apiUrl: string,
  token: string,
  entries: CrudEntry[],
  fetchImpl: typeof fetch = fetch,
): Promise<{ op_id: string; status: string }[]> {
  const ops = entries.map((e) => ({
    op_id: e.id,
    table: e.table,
    kind: KIND[e.op],
    record_id: e.record_id,
    farm_id: e.farm_id,
    base_version: e.base_version,
    fields: e.data ?? {},
  }));
  const res = await fetchImpl(`${apiUrl}/sync/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ ops }),
  });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  return (await res.json()).results;
}
