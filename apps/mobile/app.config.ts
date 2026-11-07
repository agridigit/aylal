type Env = Record<string, string | undefined>;
type Cfg = { plugins?: unknown[]; [k: string]: unknown };

/** Extends app.json. Cleartext HTTP (host Docker stack seen from the emulator) exists in E2E builds only. */
export default function buildConfig({ config }: { config: Cfg }, env: Env = process.env): Cfg {
  const plugins = [...(config.plugins ?? [])];
  if (env.EXPO_PUBLIC_E2E === "1") {
    plugins.push(["expo-build-properties", { android: { usesCleartextTraffic: true } }]);
  }
  return { ...config, plugins };
}
