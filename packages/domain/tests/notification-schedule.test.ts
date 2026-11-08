import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { frostNotifyAt } from "../src/notification-schedule";

const v = JSON.parse(readFileSync(new URL("../vectors/f3_notify_schedule.json", import.meta.url), "utf-8"));

describe("F3 frost notification schedule (SC-003)", () => {
  for (const c of v.cases) {
    it(`given ${c.name}`, () => {
      const out = frostNotifyAt(c.forecast_day, c.first_seen_at, c.notify_hour);
      expect(new Date(out.notifyAt).toISOString()).toBe(new Date(c.notify_at).toISOString());
      expect(out.late).toBe(c.late);
    });
  }
});
