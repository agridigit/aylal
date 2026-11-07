import { createSecureStore } from "../secureStore";

const backend = () => {
  const m = new Map<string, string>();
  return { m, getItemAsync: async (k: string) => m.get(k) ?? null, setItemAsync: async (k: string, v: string) => void m.set(k, v), deleteItemAsync: async (k: string) => void m.delete(k) };
};

describe("secure store wrapper", () => {
  it("given a value when stored then it is read back and namespaced under aylal_", async () => {
    const b = backend();
    const s = createSecureStore(b);
    await s.set("refresh_token", "abc");
    expect(await s.get("refresh_token")).toBe("abc");
    expect([...b.m.keys()]).toEqual(["aylal_refresh_token"]);
  });
  it("given a missing key when read then null", async () => {
    expect(await createSecureStore(backend()).get("x")).toBeNull();
  });
  it("given a stored value when removed then it is gone", async () => {
    const s = createSecureStore(backend());
    await s.set("k", "v");
    await s.remove("k");
    expect(await s.get("k")).toBeNull();
  });
  it("given a keystore failure when reading then the error propagates (never a silent empty value)", async () => {
    const broken = { ...backend(), getItemAsync: async () => { throw new Error("keystore"); } };
    await expect(createSecureStore(broken).get("k")).rejects.toThrow("keystore");
  });
});
