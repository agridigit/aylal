export const KEY_NAME = "aylal_db_key";

export type SecureStore = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
};
type KeyDeps = { secureStore: SecureStore; randomBytes: (n: number) => Uint8Array };

const toHex = (b: Uint8Array): string => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");

/** Random 256-bit SQLCipher key, created once and kept in the platform secure store. */
export async function getOrCreateEncryptionKey({ secureStore, randomBytes }: KeyDeps): Promise<string> {
  const existing = await secureStore.getItemAsync(KEY_NAME);
  if (existing) return existing;
  const key = toHex(randomBytes(32));
  await secureStore.setItemAsync(KEY_NAME, key);
  return key;
}

/** Never opens the database without a key: any keystore failure propagates. */
export async function openEncryptedDb<T>(
  deps: KeyDeps & { open: (o: { encryptionKey: string }) => Promise<T> },
): Promise<T> {
  const encryptionKey = await getOrCreateEncryptionKey(deps);
  return deps.open({ encryptionKey });
}
