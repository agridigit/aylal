/** T058 (US3) - recording an irrigation: duration <-> volume (R3-A2), the caps (24 h, 24 per day and sector, 400 days back) and the
 *  non blocking `possible_duplicate` (decisions point 12). New file (the shared-vector files are not extended). The validator does not
 *  exist yet: imported inside each test. */
import { describe, expect, it } from "vitest";
import { fromDuration, fromVolume } from "../src/irrigation-units";

const load = async () => await import("../src/irrigation-event");
const OK = { duration_min: 60, volume_m3: null, performed_on: "2026-06-03", today: "2026-06-04", slot_count: 0, area_ha: 1 };

describe("F4 US3 duration and volume (R3-A2) on the shared units", () => {
  const sys = { rate_mm_h: 4, area_m2: 5000, efficiency: 0.9 };
  it("given a duration when converting then the volume comes from the installation (60 min, 4 mm/h, 5000 m2 = 20 m3)", () => {
    expect(fromDuration({ minutes: 60, ...sys }).volume_m3).toBeCloseTo(20, 2);
  });
  it("given a volume when converting then the duration is the inverse and the round trip is stable", () => {
    const v = fromDuration({ minutes: 90, ...sys }).volume_m3 as number;
    expect(fromVolume({ volume_m3: v, ...sys }).minutes).toBe(90);
  });
  it("given an installation without a rate when converting a volume then no duration is invented", () => {
    expect(fromVolume({ volume_m3: 10, rate_mm_h: null, area_m2: 5000, efficiency: 0.9 }).minutes).toBeNull();
  });
});

describe("F4 US3 event validation and caps", () => {
  it("given a coherent duration entry when validating then it is valid and not a duplicate", async () => {
    const { validateIrrigationEvent } = await load();
    expect(validateIrrigationEvent(OK)).toMatchObject({ valid: true, errors: [], possible_duplicate: false });
  });

  it("given both a duration and a volume when validating then exactly one is required", async () => {
    const { validateIrrigationEvent } = await load();
    const out = validateIrrigationEvent({ ...OK, volume_m3: 5 });
    expect(out.valid).toBe(false);
    expect(out.errors[0].code).toBe("exactly_one_of_duration_or_volume");
  });

  it("given neither a duration nor a volume when validating then it is refused", async () => {
    const { validateIrrigationEvent } = await load();
    expect(validateIrrigationEvent({ ...OK, duration_min: null }).valid).toBe(false);
  });

  it.each([[1440, true], [1441, false], [0, false]])("given a duration of %s min when validating then valid is %s (24 h cap)", async (minutes, valid) => {
    const { validateIrrigationEvent } = await load();
    expect(validateIrrigationEvent({ ...OK, duration_min: minutes }).valid).toBe(valid);
  });

  it.each([["2026-06-04", true], ["2026-06-05", false], ["2025-04-30", true], ["2025-04-29", false]])(
    "given a date %s with today 2026-06-04 when validating then valid is %s (no future, at most 400 days back)", async (day, valid) => {
      const { validateIrrigationEvent } = await load();
      expect(validateIrrigationEvent({ ...OK, performed_on: day }).valid).toBe(valid);
    });

  it("given 24 events already on the day and sector when validating then the 25th is refused with the quota code", async () => {
    const { validateIrrigationEvent } = await load();
    const out = validateIrrigationEvent({ ...OK, slot_count: 24 });
    expect(out.valid).toBe(false);
    expect(out.errors[0].code).toBe("events_per_day_sector");
  });

  it("given a volume above 1000 m3 per hectare when validating then it is refused", async () => {
    const { validateIrrigationEvent } = await load();
    expect(validateIrrigationEvent({ ...OK, duration_min: null, volume_m3: 1001, area_ha: 1 }).valid).toBe(false);
    expect(validateIrrigationEvent({ ...OK, duration_min: null, volume_m3: 1000, area_ha: 1 }).valid).toBe(true);
  });

  it("given one event already on the same day and sector when validating then it stays valid but is flagged possible_duplicate (never blocks)", async () => {
    const { validateIrrigationEvent } = await load();
    expect(validateIrrigationEvent({ ...OK, slot_count: 1 })).toMatchObject({ valid: true, possible_duplicate: true });
  });

  it("given an error when validating then the field and an i18n key are returned", async () => {
    const { validateIrrigationEvent } = await load();
    const e = validateIrrigationEvent({ ...OK, performed_on: "2026-06-05" }).errors[0];
    expect(e.field).toBe("performed_on");
    expect(e.i18n_key).toMatch(/^irrigation\./);
  });
});
