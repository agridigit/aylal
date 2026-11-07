import { getOrCreateEncryptionKey, openEncryptedDb, KEY_NAME } from "../encryptionKey";

const memoryStore = () => {
  const m = new Map<string, string>();
  return { m, getItemAsync: async (k: string) => m.get(k) ?? null, setItemAsync: async (k: string, v: string) => void m.set(k, v) };
};
const counter = (start: number) => (n: number) => Uint8Array.from({ length: n }, (_, i) => (start + i) % 256);

describe("database encryption key", () => {
  it("given a first launch when opening then a random 256-bit key is stored in secure storage", async () => {
    const store = memoryStore();
    const key = await getOrCreateEncryptionKey({ secureStore: store, randomBytes: counter(1) });
    expect(key).toMatch(/^[0-9a-f]{64}$/);
    expect(store.m.get(KEY_NAME)).toBe(key);
  });
  it("given a later launch then the same key is reused, not regenerated", async () => {
    const store = memoryStore();
    const a = await getOrCreateEncryptionKey({ secureStore: store, randomBytes: counter(1) });
    const b = await getOrCreateEncryptionKey({ secureStore: store, randomBytes: counter(99) });
    expect(b).toBe(a);
  });
  it("given two installs then their keys differ", async () => {
    const a = await getOrCreateEncryptionKey({ secureStore: memoryStore(), randomBytes: counter(1) });
    const b = await getOrCreateEncryptionKey({ secureStore: memoryStore(), randomBytes: counter(50) });
    expect(a).not.toBe(b);
  });
  it("given the key when opening the database then it is opened encrypted with that key", async () => {
    const store = memoryStore();
    const open = jest.fn(async (_o: { encryptionKey: string }) => ({}));
    await openEncryptedDb({ secureStore: store, randomBytes: counter(1), open });
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ encryptionKey: store.m.get(KEY_NAME) }));
  });
  it("given a key in secure storage that cannot be read then the database is not opened in clear", async () => {
    const open = jest.fn();
    const broken = { getItemAsync: async () => { throw new Error("keystore"); }, setItemAsync: async () => {} };
    await expect(openEncryptedDb({ secureStore: broken, randomBytes: counter(1), open })).rejects.toThrow();
    expect(open).not.toHaveBeenCalled();
  });
});
