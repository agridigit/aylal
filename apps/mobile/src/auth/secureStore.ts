export type SecureBackend = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
};

export type SecureStore = {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
};

const PREFIX = "aylal_";

/** Namespaced wrapper over the OS keystore (expo-secure-store injected); errors always propagate. */
export function createSecureStore(backend: SecureBackend): SecureStore {
  return {
    get: (key) => backend.getItemAsync(PREFIX + key),
    set: (key, value) => backend.setItemAsync(PREFIX + key, value),
    remove: (key) => backend.deleteItemAsync(PREFIX + key),
  };
}
