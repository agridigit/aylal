import { checkStorage, LOW_STORAGE_BYTES } from "../storageWarning";

describe("low storage warning", () => {
  it("given plenty of free space when saving then no warning", () => {
    expect(checkStorage({ freeBytes: 5 * LOW_STORAGE_BYTES, requiredBytes: 1024 })).toEqual({ level: "ok" });
  });
  it("given free space under the threshold when saving then the farmer is warned before data is lost", () => {
    expect(checkStorage({ freeBytes: LOW_STORAGE_BYTES - 1, requiredBytes: 1024 }).level).toBe("warning");
  });
  it("given not enough space for the entry then the level is blocking and the message key is i18n", () => {
    const r = checkStorage({ freeBytes: 100, requiredBytes: 1024 });
    expect(r.level).toBe("blocking");
    expect(r.messageKey).toMatch(/^[a-z]+(\.[a-zA-Z]+)+$/);
  });
});
