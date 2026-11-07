import { createActiveFarm, filterByFarm } from "../activeFarm";

const mem = () => {
  const m = new Map<string, string>();
  return { get: async (k: string) => m.get(k) ?? null, set: async (k: string, v: string) => void m.set(k, v), remove: async (k: string) => void m.delete(k) };
};
const farms = [{ id: "f1", role: "owner" }, { id: "f2", role: "worker" }];

describe("active farm (R5-A1, R5-A2)", () => {
  it("given two farms and no choice when resolving then the first farm is active", async () => {
    expect((await createActiveFarm(mem()).resolve(farms))?.id).toBe("f1");
  });
  it("given a chosen farm when the app restarts then the same farm is active", async () => {
    const s = mem();
    await createActiveFarm(s).set("f2");
    expect((await createActiveFarm(s).resolve(farms))?.id).toBe("f2");
  });
  it("given a stored farm the user no longer belongs to when resolving then it falls back to a member farm", async () => {
    const s = mem();
    await createActiveFarm(s).set("gone");
    expect((await createActiveFarm(s).resolve(farms))?.id).toBe("f1");
  });
  it("given no farm when resolving then nothing is active", async () => {
    expect(await createActiveFarm(mem()).resolve([])).toBeNull();
  });
  it("given rows of several farms when filtering then only the active farm rows remain, offline included", () => {
    const rows = [{ id: "r1", farm_id: "f1" }, { id: "r2", farm_id: "f2" }, { id: "r3", farm_id: "f1" }];
    expect(filterByFarm(rows, "f1").map((r) => r.id)).toEqual(["r1", "r3"]);
    expect(filterByFarm(rows, null)).toEqual([]);
  });
});
