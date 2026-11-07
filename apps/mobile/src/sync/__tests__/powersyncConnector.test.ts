import { createConnector, opIdFor, type CrudTx } from "../powersyncConnector";

const API = "http://api.test/v1";
const PS = "http://ps.test";
const USER = "9cd05120-31fa-562e-b8d4-9021646a0145";
const RID = "11111111-2222-4333-8444-555555555555";

const put = (clientId: number) => ({
  clientId,
  op: "PUT" as const,
  table: "trial_records",
  id: RID,
  opData: { farm_id: "f1", title: "Essai", quantity: 2 },
});
const tx = (...crud: ReturnType<typeof put>[]): CrudTx & { completed: number } => {
  const t = { crud, completed: 0, async complete() { t.completed++; } };
  return t;
};
const dbWith = (t: CrudTx | null) => ({ getNextCrudTransaction: async () => t });
const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body }) as Response;

describe("PowerSync connector", () => {
  it("given the E2E identity when fetching credentials then it asks the API dev token and points at PowerSync", async () => {
    const fetchImpl = jest.fn(async () => json({ token: "jwt", expires_at: "2030-01-01T00:00:00+00:00" }));
    const c = createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: fetchImpl as any });
    const creds = await c.fetchCredentials();
    expect(fetchImpl).toHaveBeenCalledWith(`${API}/auth/dev-token`, expect.objectContaining({ method: "POST", body: JSON.stringify({ user_id: USER }) }));
    expect(creds).toMatchObject({ endpoint: PS, token: "jwt" });
  });

  it("given no network when fetching credentials then it fails so PowerSync retries", async () => {
    const c = createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: (async () => { throw new TypeError("Network request failed"); }) as any });
    await expect(c.fetchCredentials()).rejects.toThrow();
  });

  it("given no identity (production build) when fetching credentials then no token is requested", async () => {
    const fetchImpl = jest.fn();
    const c = createConnector({ apiUrl: API, powersyncUrl: PS, userId: null, fetchImpl: fetchImpl as any });
    await expect(c.fetchCredentials()).rejects.toThrow();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("given a queued creation when uploading then the entry leaves ps_crud only after the server acknowledged it", async () => {
    const calls: string[] = [];
    const fetchImpl = jest.fn(async (url: string, init: any) => {
      calls.push(url);
      if (url.endsWith("/auth/dev-token")) return json({ token: "jwt", expires_at: "x" });
      const op = JSON.parse(init.body).ops[0];
      return json({ results: [{ op_id: op.op_id, status: "applied", server_version: 1 }] });
    });
    const t = tx(put(7));
    const c = createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: fetchImpl as any });
    await c.uploadData(dbWith(t));
    const body = JSON.parse((fetchImpl.mock.calls.find((x) => x[0].endsWith("/sync/upload")) as any)[1].body);
    expect(body.ops[0]).toMatchObject({ table: "trial_records", kind: "put", record_id: RID, farm_id: "f1", base_version: 0, fields: { title: "Essai", quantity: 2 } });
    expect(body.ops[0].fields).not.toHaveProperty("farm_id");
    expect(body.ops[0].op_id).toBe(opIdFor(RID, 7));
    expect(t.completed).toBe(1);
  });

  it("given a replay answered duplicate then it is acknowledged too", async () => {
    const fetchImpl = async (url: string, init: any) =>
      url.endsWith("/auth/dev-token") ? json({ token: "jwt", expires_at: "x" }) : json({ results: [{ op_id: JSON.parse(init.body).ops[0].op_id, status: "duplicate" }] });
    const t = tx(put(1));
    await createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: fetchImpl as any }).uploadData(dbWith(t));
    expect(t.completed).toBe(1);
  });

  it("given a network or server failure when uploading then the entry stays queued", async () => {
    const t = tx(put(1));
    const down = createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: (async () => { throw new TypeError("Network request failed"); }) as any });
    await expect(down.uploadData(dbWith(t))).rejects.toThrow();
    const err = createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: (async (u: string) => (u.endsWith("/auth/dev-token") ? json({ token: "j", expires_at: "x" }) : json({}, 500))) as any });
    await expect(err.uploadData(dbWith(t))).rejects.toThrow();
    expect(t.completed).toBe(0);
  });

  it("given an op the server did not acknowledge or rejected then the entry stays queued", async () => {
    const t = tx(put(1));
    const answer = (results: unknown[]) => async (u: string) => (u.endsWith("/auth/dev-token") ? json({ token: "j", expires_at: "x" }) : json({ results }));
    for (const results of [[], [{ op_id: opIdFor(RID, 1), status: "rejected" }]]) {
      const c = createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: answer(results) as any });
      await expect(c.uploadData(dbWith(t))).rejects.toThrow();
    }
    expect(t.completed).toBe(0);
  });

  it("given nothing queued then nothing is sent", async () => {
    const fetchImpl = jest.fn();
    await createConnector({ apiUrl: API, powersyncUrl: PS, userId: USER, fetchImpl: fetchImpl as any }).uploadData(dbWith(null));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("given the same entry when retried then the op id is identical, and distinct for another entry", () => {
    expect(opIdFor(RID, 3)).toBe(opIdFor(RID, 3));
    expect(opIdFor(RID, 3)).not.toBe(opIdFor(RID, 4));
    expect(opIdFor(RID, 3)).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });
});
