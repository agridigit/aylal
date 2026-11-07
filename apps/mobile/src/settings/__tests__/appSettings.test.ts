import { createAppSettings, type KeyValueStore } from "../appSettings";

function memoryStore(): KeyValueStore {
  const m = new Map<string, string>();
  return { get: async (k) => m.get(k) ?? null, set: async (k, v) => void m.set(k, v) };
}

describe("appSettings", () => {
  it("falls back to device locale then fr, and theme system", async () => {
    const s = createAppSettings(memoryStore());
    expect(await s.getLocale("de-DE")).toBe("fr");
    expect(await s.getLocale("ar")).toBe("ar");
    expect(await s.getTheme()).toBe("system");
  });
  it("persists locale and theme", async () => {
    const s = createAppSettings(memoryStore());
    await s.setLocale("ary");
    await s.setTheme("dark");
    expect(await s.getLocale("fr")).toBe("ary");
    expect(await s.getTheme()).toBe("dark");
  });
  it("ignores invalid stored values", async () => {
    const store = memoryStore();
    await store.set("locale", "xx");
    await store.set("theme", "pink");
    const s = createAppSettings(store);
    expect(await s.getLocale("fr")).toBe("fr");
    expect(await s.getTheme()).toBe("system");
  });
});
