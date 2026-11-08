/** Morocco has a permanent UTC+1 offset for this rule (the notification hour is local). */
const MOROCCO_OFFSET_H = 1;
const LATEST_HOUR = 18;

function localHourUtc(day: string, hour: number): number {
  return Date.parse(`${day}T00:00:00Z`) + (hour - MOROCCO_OFFSET_H) * 3_600_000;
}

function eveBefore(day: string): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10);
}

/**
 * When to notify a frost forecast: the evening before at `notifyHour` (capped at 18:00 Morocco time). Seen later,
 * it is immediate; `late` when it was first seen after 18:00 the evening before.
 */
export function frostNotifyAt(forecastDay: string, firstSeenAt: string, notifyHour: number): { notifyAt: string; late: boolean } {
  const eve = eveBefore(forecastDay);
  const target = localHourUtc(eve, Math.min(notifyHour, LATEST_HOUR));
  const seen = Date.parse(firstSeenAt);
  if (seen <= target) return { notifyAt: new Date(target).toISOString(), late: false };
  return { notifyAt: new Date(seen).toISOString(), late: seen > localHourUtc(eve, LATEST_HOUR) };
}
