import type { SecureStore } from "./secureStore";

type Deps = {
  store: SecureStore;
  hash: (input: string) => Promise<string>;
  randomSalt: () => string;
};

/** Optional 4-digit PIN kept on the device only: a salted hash in the secure store, never sent anywhere (R1-A5). */
export function createLocalPin({ store, hash, randomSalt }: Deps) {
  const digest = (salt: string, pin: string) => hash(`${salt}:${pin}`);
  return {
    isEnabled: async () => (await store.get("pin_hash")) !== null,
    async enable(pin: string) {
      if (!/^[0-9]{4}$/.test(pin)) throw new Error("pin_invalid");
      const salt = randomSalt();
      await store.set("pin_salt", salt);
      await store.set("pin_hash", await digest(salt, pin));
    },
    async verify(pin: string) {
      const [salt, stored] = [await store.get("pin_salt"), await store.get("pin_hash")];
      return salt !== null && stored !== null && (await digest(salt, pin)) === stored;
    },
    async disable() {
      await store.remove("pin_hash");
      await store.remove("pin_salt");
    },
  };
}
