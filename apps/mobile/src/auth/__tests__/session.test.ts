import { createSession } from "../session";
import { createSecureStore } from "../secureStore";

const backend = () => {
  const m = new Map<string, string>();
  return { getItemAsync: async (k: string) => m.get(k) ?? null, setItemAsync: async (k: string, v: string) => void m.set(k, v), deleteItemAsync: async (k: string) => void m.delete(k) };
};
const tokens = { access_token: "a1", refresh_token: "r1", expires_at: "2026-01-01T00:15:00Z", user: { id: "u1", phone: "+212612345678", status: "pending" }, farms: [] };

describe("session persistence (R1-A4)", () => {
  it("given a signed-in session when the app restarts then the user is still signed in", async () => {
    const b = backend();
    await createSession(createSecureStore(b)).save(tokens);
    const afterRestart = createSession(createSecureStore(b));
    expect(await afterRestart.load()).toEqual(tokens);
    expect(await afterRestart.isSignedIn()).toBe(true);
  });
  it("given no session when loading then the user is signed out", async () => {
    const s = createSession(createSecureStore(backend()));
    expect(await s.load()).toBeNull();
    expect(await s.isSignedIn()).toBe(false);
  });
  it("given a voluntary logout when clearing then nothing remains after restart", async () => {
    const b = backend();
    const s = createSession(createSecureStore(b));
    await s.save(tokens);
    await s.clear();
    expect(await createSession(createSecureStore(b)).isSignedIn()).toBe(false);
  });
  it("given a refresh when saving the new pair then the old refresh token is replaced", async () => {
    const s = createSession(createSecureStore(backend()));
    await s.save(tokens);
    await s.save({ ...tokens, refresh_token: "r2" });
    expect((await s.load())?.refresh_token).toBe("r2");
  });
  it("given corrupted stored data when loading then the session is treated as signed out", async () => {
    const b = backend();
    await b.setItemAsync("aylal_session", "{not json");
    expect(await createSession(createSecureStore(b)).load()).toBeNull();
  });
});
