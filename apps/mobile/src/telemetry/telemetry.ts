export type Settings = { get(k: string): Promise<string | null>; set(k: string, v: string): Promise<void> };
type Deps = { settings: Settings; randomUUID: () => string; send: (payload: Payload) => unknown };
type Payload = { event: string; install_id: string; props: Record<string, string | number | boolean> };

/** Only these non-personal props may leave the device. */
const ALLOWED_PROPS = new Set(["screen", "locale", "theme", "app_version", "duration_ms"]);

export function createTelemetry({ settings, randomUUID, send }: Deps) {
  async function installId(): Promise<string> {
    const existing = await settings.get("install_id");
    if (existing) return existing;
    const id = randomUUID();
    await settings.set("install_id", id);
    return id;
  }
  return {
    async setEnabled(enabled: boolean): Promise<void> {
      await settings.set("telemetry_enabled", String(enabled));
    },
    async track(event: string, props: Record<string, unknown>): Promise<void> {
      if ((await settings.get("telemetry_enabled")) === "false") return;
      const safe: Payload["props"] = {};
      for (const [k, v] of Object.entries(props)) {
        if (ALLOWED_PROPS.has(k) && ["string", "number", "boolean"].includes(typeof v)) safe[k] = v as never;
      }
      await send({ event, install_id: await installId(), props: safe });
    },
  };
}
