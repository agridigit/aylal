import { readFileSync } from "node:fs";
import { join } from "node:path";

const pkg = JSON.parse(readFileSync(join(__dirname, "../../../package.json"), "utf8"));

describe("native database configuration", () => {
  it("given the local database then SQLCipher is enabled in the op-sqlite build", () => {
    expect(pkg["op-sqlite"]).toMatchObject({ sqlcipher: true });
  });
  it("given the sync stack then PowerSync and op-sqlite are real dependencies", () => {
    for (const d of ["@powersync/react-native", "@powersync/common", "@op-engineering/op-sqlite", "expo-secure-store", "expo-crypto", "expo-build-properties"]) {
      expect(pkg.dependencies[d]).toBeTruthy();
    }
  });
});
