export interface SyncedAlert {
  id: string;
  type: string;
  status: string;
  notify_at: string | null;
  revision: number;
  advice_key: string | null;
}

export interface PlannedNotification {
  alertId: string;
  revision: number;
  at: string;
}

export interface NotificationToSchedule extends PlannedNotification {
  titleKey: string;
  bodyKey: string;
  adviceKey: string | null;
}

/** Local notifications from synced alerts, computed offline; a changed revision replaces the old one. */
export function planAlertNotifications(
  alerts: readonly SyncedAlert[],
  planned: readonly PlannedNotification[],
  now: string,
): { schedule: NotificationToSchedule[]; cancel: string[] } {
  const schedule: NotificationToSchedule[] = [];
  const cancel: string[] = [];
  const byId = new Map(planned.map((p) => [p.alertId, p]));
  for (const a of alerts) {
    const prev = byId.get(a.id);
    const wanted = a.status === "active" && a.notify_at !== null;
    if (!wanted) {
      if (prev !== undefined) cancel.push(a.id);
      continue;
    }
    if (prev !== undefined && prev.revision === a.revision) continue;
    if (prev !== undefined) cancel.push(a.id);
    const at = Date.parse(a.notify_at as string) < Date.parse(now) ? now : (a.notify_at as string);
    schedule.push({
      alertId: a.id,
      revision: a.revision,
      at,
      titleKey: `notification.alert.${a.type}.title`,
      bodyKey: `notification.alert.${a.type}.body`,
      adviceKey: a.advice_key,
    });
  }
  return { schedule, cancel };
}
