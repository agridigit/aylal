import { createLocalPin } from "../localPin";
import { createSecureStore } from "../secureStore";

const backend = () => {
  const m = new Map<string, string>();
  return { m, getItemAsync: async (k: string) => m.get(k) ?? null, setItemAsync: async (k: string, v: string) => void m.set(k, v), deleteItemAsync: async (k: string) => void m.delete(k) };
};
const deps = (b = backend()) => ({ b, pin: createLocalPin({ store: createSecureStore(b), hash: async (s: string) => `h:${s.length}:${[...s].reverse().join("")}`, randomSalt: () => "salt" }) });

describe("local 4-digit PIN (R1-A5)", () => {
  it("given a new user then the PIN is optional: not enabled by default", async () => {
    expect(await deps().pin.isEnabled()).toBe(false);
  });
  it("given 4 digits when enabling then the PIN is required afterwards and verifies", async () => {
    const { pin } = deps();
    await pin.enable("1234");
    expect(await pin.isEnabled()).toBe(true);
    expect(await pin.verify("1234")).toBe(true);
    expect(await pin.verify("4321")).toBe(false);
  });
  it.each(["123", "12345", "12a4", "", "١٢٣٤"])("given %p when enabling then it is rejected", async (bad) => {
    const { pin } = deps();
    await expect(pin.enable(bad)).rejects.toThrow();
    expect(await pin.isEnabled()).toBe(false);
  });
  it("given an enabled PIN then only a hash is stored, never the digits", async () => {
    const { b, pin } = deps();
    await pin.enable("1234");
    expect([...b.m.values()].some((v) => v.includes("1234"))).toBe(false);
  });
  it("given the PIN module then it exposes no way to send the PIN to the server", async () => {
    const mod = await import("../localPin");
    expect(Object.keys(mod).filter((k) => /send|upload|sync|fetch/i.test(k))).toEqual([]);
  });
  it("given an enabled PIN when disabling then the app no longer asks for it", async () => {
    const { pin } = deps();
    await pin.enable("1234");
    await pin.disable();
    expect(await pin.isEnabled()).toBe(false);
  });
  it("given an enabled PIN when the app restarts then it is still required", async () => {
    const b = backend();
    await deps(b).pin.enable("1234");
    expect(await deps(b).pin.isEnabled()).toBe(true);
  });
});
