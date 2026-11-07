import { MIN_TOUCH_TARGET_DP } from "../Home/direction";

export type TrialSyncState = "pending" | "conflict" | "synced";

export function buildTrialRecordViewModel(input: { syncState: TrialSyncState }) {
  return {
    titleKey: "trialRecord.title",
    fields: [
      { id: "title", testId: "trialRecord.title", labelKey: "trialRecord.fields.title" },
      { id: "note", testId: "trialRecord.note", labelKey: "trialRecord.fields.note" },
      { id: "quantity", testId: "trialRecord.quantity", labelKey: "trialRecord.fields.quantity" },
    ],
    saveButton: {
      testId: "trialRecord.save",
      labelKey: "trialRecord.save",
      minWidth: MIN_TOUCH_TARGET_DP,
      minHeight: MIN_TOUCH_TARGET_DP,
    },
    syncIndicator: {
      // The "not sent" warning stays visible until the server confirms (conflicts need acknowledgement).
      visible: input.syncState !== "synced",
      testId: `sync.indicator.${input.syncState}`,
      labelKey: `trialRecord.sync.${input.syncState}`,
    },
  };
}
