import Constants from "expo-constants";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { PowerSyncDatabase, Schema, Table, column } from "@powersync/react-native";
import type { LocalDb } from "./db";
import { openEncryptedDb } from "./encryptionKey";
import { createLocalDb } from "./powersyncAdapter";
import { createConnector } from "./powersyncConnector";
import { TRIAL_RECORD_COLUMNS } from "./powersyncSchema";
import { resolveRuntimeConfig, type RuntimeConfig } from "./runtimeConfig";

// Literal reads so Metro inlines the EXPO_PUBLIC_* values at build time.
const extra = (Constants.expoConfig?.extra ?? {}) as { apiUrl: string; powersyncUrl: string };
export const runtimeConfig: RuntimeConfig = resolveRuntimeConfig(
  {
    EXPO_PUBLIC_E2E: process.env.EXPO_PUBLIC_E2E,
    EXPO_PUBLIC_API_URL: process.env.EXPO_PUBLIC_API_URL,
    EXPO_PUBLIC_POWERSYNC_URL: process.env.EXPO_PUBLIC_POWERSYNC_URL,
  },
  extra,
);

const schema = new Schema({
  trial_records: new Table(
    Object.fromEntries(Object.entries(TRIAL_RECORD_COLUMNS).map(([name, type]) => [name, column[type]])),
  ),
});

let opening: Promise<LocalDb> | null = null;

/** Opens the SQLCipher database once, then keeps it synced (retries on its own while offline). */
export function getLocalDb(): Promise<LocalDb> {
  opening ??= openEncryptedDb({
    secureStore: SecureStore,
    randomBytes: (n) => Crypto.getRandomBytes(n),
    open: async ({ encryptionKey }) => {
      const ps = new PowerSyncDatabase({
        schema,
        database: { dbFilename: "aylal.db", sqliteOptions: { encryptionKey } },
      });
      await ps.init();
      const connector = createConnector({
        apiUrl: runtimeConfig.apiUrl,
        powersyncUrl: runtimeConfig.powersyncUrl,
        userId: runtimeConfig.userId,
      });
      void ps.connect({
        fetchCredentials: () => connector.fetchCredentials(),
        uploadData: (database) => connector.uploadData(database as never),
      });
      return createLocalDb(ps as never);
    },
  }).catch((e) => {
    opening = null;
    throw e;
  });
  return opening;
}
