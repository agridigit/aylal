export type RuntimeConfig = {
  e2e: boolean;
  apiUrl: string;
  powersyncUrl: string;
  userId: string | null;
  farmId: string | null;
};

/** Deterministic trial identity of services/api/app/db/seed.py; used by E2E builds only. */
export const E2E_DEFAULTS = {
  // The Android emulator reaches the Docker stack published on the host through 10.0.2.2.
  apiUrl: "http://10.0.2.2:8000/v1",
  powersyncUrl: "http://10.0.2.2:8080",
  userId: "9cd05120-31fa-562e-b8d4-9021646a0145",
  farmId: "236d1fbd-85eb-5bc5-8a71-cde7ad0ba15a",
} as const;

type Env = Record<string, string | undefined>;

/** `env` must be built from literal process.env.EXPO_PUBLIC_* reads so Metro can inline them. */
export function resolveRuntimeConfig(env: Env, extra: { apiUrl: string; powersyncUrl: string }): RuntimeConfig {
  if (env.EXPO_PUBLIC_E2E !== "1") {
    return { e2e: false, apiUrl: extra.apiUrl, powersyncUrl: extra.powersyncUrl, userId: null, farmId: null };
  }
  return {
    e2e: true,
    apiUrl: env.EXPO_PUBLIC_API_URL || E2E_DEFAULTS.apiUrl,
    powersyncUrl: env.EXPO_PUBLIC_POWERSYNC_URL || E2E_DEFAULTS.powersyncUrl,
    userId: E2E_DEFAULTS.userId,
    farmId: E2E_DEFAULTS.farmId,
  };
}
