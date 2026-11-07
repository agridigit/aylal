import { createHash } from "node:crypto";
import { resolveRuntimeConfig, E2E_DEFAULTS } from "../runtimeConfig";

const extra = { apiUrl: "https://proxy/v1", powersyncUrl: "https://proxy/powersync" };

function uuid5(namespace: string, name: string): string {
  const h = createHash("sha1").update(Buffer.concat([Buffer.from(namespace.replace(/-/g, ""), "hex"), Buffer.from(name)])).digest();
  h[6] = (h[6]! & 0x0f) | 0x50;
  h[8] = (h[8]! & 0x3f) | 0x80;
  const x = h.subarray(0, 16).toString("hex");
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
}

describe("runtime configuration", () => {
  it("given a production build then it uses the app config URLs and carries no test identity", () => {
    const c = resolveRuntimeConfig({ EXPO_PUBLIC_API_URL: "http://evil" }, extra);
    expect(c).toEqual({ e2e: false, apiUrl: extra.apiUrl, powersyncUrl: extra.powersyncUrl, userId: null, farmId: null });
  });

  it("given an E2E build without overrides then it targets the host stack through the emulator alias", () => {
    const c = resolveRuntimeConfig({ EXPO_PUBLIC_E2E: "1" }, extra);
    expect(c).toMatchObject({ e2e: true, apiUrl: "http://10.0.2.2:8000/v1", powersyncUrl: "http://10.0.2.2:8080" });
    expect(c.userId).toBe(E2E_DEFAULTS.userId);
    expect(c.farmId).toBe(E2E_DEFAULTS.farmId);
  });

  it("given an E2E build with overrides then the variables win", () => {
    const c = resolveRuntimeConfig({ EXPO_PUBLIC_E2E: "1", EXPO_PUBLIC_API_URL: "http://a/v1", EXPO_PUBLIC_POWERSYNC_URL: "http://p" }, extra);
    expect(c).toMatchObject({ apiUrl: "http://a/v1", powersyncUrl: "http://p" });
  });

  it("given the E2E identity then it equals the deterministic API seed (services/api/app/db/seed.py)", () => {
    const ns = "a71a1000-0000-4000-8000-000000000001";
    expect(E2E_DEFAULTS.userId).toBe(uuid5(ns, "user:trial"));
    expect(E2E_DEFAULTS.farmId).toBe(uuid5(ns, "farm:trial"));
  });
});
