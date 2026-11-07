import { useCallback, useEffect, useRef, useState } from "react";
import { TrialRecord } from "../src/screens/TrialRecord/TrialRecord";
import type { TrialSyncState } from "../src/screens/TrialRecord/trialRecordViewModel";
import { getRecordSyncState, saveTrialRecord } from "../src/sync/db";
import { getLocalDb, runtimeConfig } from "../src/sync/powersyncRuntime";
import { useLocale } from "./_layout";

const POLL_MS = 1000;

export default function TrialRecordRoute() {
  const { i18n } = useLocale();
  const [syncState, setSyncState] = useState<TrialSyncState | undefined>(undefined);
  const recordId = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    if (!recordId.current) return;
    setSyncState(await getRecordSyncState(await getLocalDb(), recordId.current));
  }, []);

  useEffect(() => {
    const timer = setInterval(() => void refresh().catch(() => {}), POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const onSave = useCallback(
    async (values: Record<string, string>) => {
      if (!runtimeConfig.farmId) return;
      const quantity = values.quantity ? Number(values.quantity) : null;
      recordId.current = await saveTrialRecord(await getLocalDb(), {
        farm_id: runtimeConfig.farmId,
        title: values.title ?? "",
        note: values.note || null,
        quantity,
      });
      await refresh();
    },
    [refresh],
  );

  return <TrialRecord i18n={i18n} syncState={syncState} onSave={(v) => void onSave(v).catch(() => {})} />;
}
