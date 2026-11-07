/** Local reminders only: notifications are scheduled on the device, never through a push provider or the network. */
export interface ReminderOperation {
  id: string;
  performed_on: string;
  status: string;
  type: string;
  parcel_name?: string;
}
export interface LocalScheduler {
  scheduleLocal(n: { id: string; at: Date; title: string; data: Record<string, string> }): Promise<void>;
  cancel(id: string): Promise<void>;
}

const MAX_SCHEDULED = 500;
const REMINDER_HOUR = 8;

export function createReminders(scheduler: LocalScheduler, now: () => Date = () => new Date()) {
  const known = new Set<string>();

  const at = (day: string): Date => {
    const [y = 0, m = 1, d = 1] = day.split("-").map(Number);
    return new Date(y, m - 1, d, REMINDER_HOUR, 0, 0);
  };
  const due = (op: ReminderOperation): Date | null => {
    if (op.status !== "planned") return null;
    const when = at(op.performed_on);
    return when.getTime() > now().getTime() ? when : null;
  };

  async function cancel(id: string): Promise<void> {
    known.delete(id);
    await scheduler.cancel(id);
  }
  async function schedule(op: ReminderOperation): Promise<void> {
    const when = due(op);
    if (when === null) return;
    known.add(op.id);
    await scheduler.scheduleLocal({
      id: op.id,
      at: when,
      title: "reminders.planned_operation",
      data: { operation_id: op.id, type: op.type, ...(op.parcel_name ? { parcel_name: op.parcel_name } : {}) },
    });
  }
  async function reschedule(op: ReminderOperation): Promise<void> {
    await cancel(op.id);
    await schedule(op);
  }
  async function syncAll(ops: readonly ReminderOperation[]): Promise<void> {
    const wanted = ops
      .filter((o) => due(o) !== null)
      .sort((a, b) => a.performed_on.localeCompare(b.performed_on) || a.id.localeCompare(b.id))
      .slice(0, MAX_SCHEDULED);
    const keep = new Set(wanted.map((o) => o.id));
    for (const id of [...known]) if (!keep.has(id)) await cancel(id);
    for (const op of wanted) await reschedule(op);
  }
  return { schedule, reschedule, cancel, syncAll };
}
