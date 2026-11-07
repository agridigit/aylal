import buildConfig from "../../../app.config";

const base: any = { name: "AYLAL", slug: "aylal", plugins: ["expo-router", "expo-secure-store"] };
const cleartext = (cfg: any) => (cfg.plugins as any[]).find((p) => Array.isArray(p) && p[0] === "expo-build-properties");

describe("Expo app config", () => {
  it("given a production build then cleartext traffic is never enabled", () => {
    const cfg = buildConfig({ config: base }, {});
    expect(cleartext(cfg)).toBeUndefined();
    expect(cfg.plugins).toEqual(base.plugins);
  });

  it("given an E2E build then cleartext traffic is enabled for the host stack only", () => {
    const cfg = buildConfig({ config: base }, { EXPO_PUBLIC_E2E: "1" });
    expect(cleartext(cfg)[1]).toEqual({ android: { usesCleartextTraffic: true } });
    expect(cfg.plugins).toContain("expo-router");
  });
});
