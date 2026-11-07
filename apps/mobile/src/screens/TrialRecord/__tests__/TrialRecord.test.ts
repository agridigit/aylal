import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { flattenKeys, LOCALES, resources } from "@aylal/i18n";
import { TRIAL_RECORD_TEXT_KEYS } from "../keys";
import { buildTrialRecordViewModel } from "../trialRecordViewModel";

describe("TrialRecord screen (T059, AC3.1, AC3.2)", () => {
  it("Given a record saved offline, When pending, Then the not-sent indicator is visible", () => {
    const vm = buildTrialRecordViewModel({ syncState: "pending" });
    expect(vm.syncIndicator).toMatchObject({ visible: true, testId: "sync.indicator.pending" });
    expect(vm.syncIndicator.labelKey).toBeTruthy();
  });

  it("Given a conflict not yet acknowledged, Then the indicator stays visible", () => {
    expect(buildTrialRecordViewModel({ syncState: "conflict" }).syncIndicator.visible).toBe(true);
  });

  it("Given the server confirmed, When synced, Then the indicator disappears", () => {
    expect(buildTrialRecordViewModel({ syncState: "synced" }).syncIndicator.visible).toBe(false);
  });

  it("Given the form, Then the Maestro ids exist and the save button is at least 48 dp", () => {
    const vm = buildTrialRecordViewModel({ syncState: "synced" });
    expect(vm.fields.map((f) => f.testId)).toContain("trialRecord.title");
    expect(vm.saveButton.testId).toBe("trialRecord.save");
    expect(vm.saveButton.minHeight).toBeGreaterThanOrEqual(48);
    expect(vm.saveButton.minWidth).toBeGreaterThanOrEqual(48);
  });

  it("Given every locale, When reading the screen keys, Then all exist", () => {
    for (const l of LOCALES) {
      const flat = flattenKeys(resources[l]);
      for (const k of TRIAL_RECORD_TEXT_KEYS) expect(flat[k]?.trim(), `${l}:${k}`).toBeTruthy();
    }
  });

  it("Given the screen sources, When scanning, Then no hard-coded visible text", () => {
    const dir = join(__dirname, "..");
    const files = readdirSync(dir).filter((f) => f.endsWith(".tsx"));
    expect(files.length).toBeGreaterThan(0);
    for (const f of files) expect(readFileSync(join(dir, f), "utf8"), f).not.toMatch(/>\s*[A-Za-zÀ-ɏ؀-ۿ][^<>{}]*</);
  });
});
