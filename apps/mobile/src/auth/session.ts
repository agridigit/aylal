import type { SecureStore } from "./secureStore";

export type SessionTokens = {
  access_token: string;
  refresh_token: string;
  expires_at: string;
  user: { id: string; phone: string; status: string };
  farms: { id: string; role: string }[];
};

const KEY = "session";

/** Session persisted in the secure store: survives restarts until a voluntary logout (R1-A4). */
export function createSession(store: SecureStore) {
  const load = async (): Promise<SessionTokens | null> => {
    const raw = await store.get(KEY);
    if (raw === null) return null;
    try {
      const parsed = JSON.parse(raw) as SessionTokens;
      return parsed && typeof parsed.refresh_token === "string" ? parsed : null;
    } catch {
      return null;
    }
  };
  return {
    load,
    save: (tokens: SessionTokens) => store.set(KEY, JSON.stringify(tokens)),
    clear: () => store.remove(KEY),
    isSignedIn: async () => (await load()) !== null,
  };
}
