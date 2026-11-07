import { createTelemetry } from "../telemetry";

const settings = () => {
  const m = new Map<string, string>();
  return { m, get: async (k: string) => m.get(k) ?? null, set: async (k: string, v: string) => void m.set(k, v) };
};

describe("anonymous telemetry", () => {
  it("given a first launch then a random install_id is generated and persisted in app_settings", async () => {
    const s = settings();
    const t = createTelemetry({ settings: s, randomUUID: () => "11111111-1111-4111-8111-111111111111", send: jest.fn() });
    await t.track("app_open", {});
    expect(s.m.get("install_id")).toBe("11111111-1111-4111-8111-111111111111");
  });
  it("given an event then the payload carries no personal data", async () => {
    const send = jest.fn();
    const t = createTelemetry({ settings: settings(), randomUUID: () => "22222222-2222-4222-8222-222222222222", send });
    await t.track("record_saved", { screen: "TrialRecord", email: "a@b.c", name: "Aya", phone: "06", user_id: "u", title: "secret" });
    const payload = send.mock.calls[0][0];
    expect(Object.keys(payload).sort()).toEqual(["event", "install_id", "props"].sort());
    expect(JSON.stringify(payload)).not.toMatch(/a@b\.c|Aya|secret|"user_id"/);
  });
  it("given the farmer disables telemetry then nothing is sent and telemetry_enabled is false", async () => {
    const s = settings();
    const send = jest.fn();
    const t = createTelemetry({ settings: s, randomUUID: () => "33333333-3333-4333-8333-333333333333", send });
    await t.setEnabled(false);
    await t.track("app_open", {});
    expect(send).not.toHaveBeenCalled();
    expect(s.m.get("telemetry_enabled")).toBe("false");
  });
  it("given telemetry re-enabled then events are sent again", async () => {
    const send = jest.fn();
    const t = createTelemetry({ settings: settings(), randomUUID: () => "44444444-4444-4444-8444-444444444444", send });
    await t.setEnabled(false);
    await t.setEnabled(true);
    await t.track("app_open", {});
    expect(send).toHaveBeenCalledTimes(1);
  });
});
