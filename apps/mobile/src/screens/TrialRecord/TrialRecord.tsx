import { useState } from "react";
import { View } from "react-native";
import { Button, SyncBadge, Text, TextField } from "@aylal/ui";
import type { I18n } from "@aylal/i18n";
import { buildTrialRecordViewModel, type TrialSyncState } from "./trialRecordViewModel";

interface TrialRecordProps {
  i18n: I18n;
  /** Undefined until a record has been saved: the indicator is then hidden. */
  syncState?: TrialSyncState;
  onSave: (values: Record<string, string>) => void;
}

export function TrialRecord({ i18n, syncState, onSave }: TrialRecordProps) {
  const vm = buildTrialRecordViewModel({ syncState: syncState ?? "pending" });
  const [values, setValues] = useState<Record<string, string>>({});
  function t(key: string) {
    return i18n.t(key);
  }
  return (
    <View style={{ flex: 1, gap: 16, padding: 16 }}>
      <Text variant="heading" label={t(vm.titleKey)} locale={i18n.locale} />
      {vm.fields.map((f) => (
        <TextField
          key={f.id}
          testID={f.testId}
          label={t(f.labelKey)}
          onChangeText={(text) => setValues((v) => ({ ...v, [f.id]: text }))}
        />
      ))}
      {syncState ? (
        <View testID={vm.syncIndicator.testId}>
          <SyncBadge label={t(vm.syncIndicator.labelKey)} state={vm.syncIndicator.visible ? "loading" : "default"} />
        </View>
      ) : null}
      <View testID={vm.saveButton.testId} style={{ minWidth: vm.saveButton.minWidth, minHeight: vm.saveButton.minHeight }}>
        <Button label={t(vm.saveButton.labelKey)} onPress={() => onSave(values)} />
      </View>
    </View>
  );
}
