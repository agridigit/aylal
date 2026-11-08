/** T060 (US3) - R3-A4, SC-002: an irrigation recorded offline is kept locally, marked "to send" (pending badge), counted at once in the
 *  local balance, replayed without duplicate; recording from the advice is one gesture. Modules do not exist yet (imported in each test).
 *  Time is injected: no wall clock, no sleep. */
import { fakeDb, ids } from "./_fakeDb";

const loadBadge = async () => await import("../pendingBadge");
const loadRecord = async () => await import("../viewModels/record");
const advice = { parcel_id: "p1", for_date: "2026-06-04", kind: "irrigate", total_minutes: 120, sectors: [{ sector_no: 1, minutes: 60 }, { sector_no: 2, minutes: 60 }] };
const clockAt = (iso: string) => ({ now: () => new Date(iso) });
const deps = (db = fakeDb()) => ({ db, newId: ids(), farmId: "farm-1", role: "owner", clock: clockAt("2026-06-04T01:00:00Z") });

describe("record irrigation view model (offline)", () => {
  it("given the advice of the day when the farmer confirms done then one local row is saved with the advised duration, dated on the local day, marked pending", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = deps();
    const out = await createRecordViewModel(d).recordFromAdvice(advice, 1);
    expect(await d.db.getById("irrigation_events", out.id)).toMatchObject({ parcel_id: "p1", farm_id: "farm-1", duration_min: 60, sector_no: 1, performed_on: "2026-06-04" });
    expect(out.pending).toBe(true);
  });

  it("given the advice when recording then it takes a single gesture and no network round trip (SC-002: far under 15 s)", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = deps();
    const network = jest.fn();
    const out = await createRecordViewModel({ ...d, fetch: network } as never).recordFromAdvice(advice, 1);
    expect(out.gestures).toBe(1);
    expect(network).not.toHaveBeenCalled();
  });

  it("given a duration entry when recording then the volume is derived locally from the installation", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = { ...deps(), system: { rate_mm_h: 4, efficiency: 0.9, area_m2: 5000, sectors_count: 1 } };
    const out = await createRecordViewModel(d).recordByDuration({ parcel_id: "p1", duration_min: 60, performed_on: "2026-06-04" });
    expect(out.volume_m3).toBeCloseTo(20, 1);
  });

  it("given a volume entry when recording then the duration is derived locally", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = { ...deps(), system: { rate_mm_h: 4, efficiency: 0.9, area_m2: 5000, sectors_count: 1 } };
    const out = await createRecordViewModel(d).recordByVolume({ parcel_id: "p1", volume_m3: 20, performed_on: "2026-06-04" });
    expect(out.duration_min).toBe(60);
  });

  it("given an incoherent entry when recording then the field and an i18n key come back and nothing is queued", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = deps();
    const out = await createRecordViewModel(d).recordByDuration({ parcel_id: "p1", duration_min: 2000, performed_on: "2026-06-04" });
    expect(out.ok).toBe(false);
    expect(out.errors[0]).toMatchObject({ field: "duration_min" });
    expect(out.errors[0].i18n_key).toMatch(/^irrigation\./);
    expect(d.db.crud).toEqual([]);
  });

  it("given an irrigation recorded offline when reading the local balance then it is already counted", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = { ...deps(), system: { rate_mm_h: 4, efficiency: 0.9, area_m2: 5000, sectors_count: 1 } };
    const vm = createRecordViewModel(d);
    const before = vm.localAppliedMm("p1", "2026-06-04");
    await vm.recordByDuration({ parcel_id: "p1", duration_min: 60, performed_on: "2026-06-04" });
    expect(vm.localAppliedMm("p1", "2026-06-04") - before).toBeCloseTo(3.6, 1);
  });

  it("given an offline cancellation then the local row is cancelled and not deleted", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = deps();
    const vm = createRecordViewModel(d);
    const out = await vm.recordFromAdvice(advice, 1);
    await vm.cancel(out.id);
    expect((await d.db.getById("irrigation_events", out.id)).status).toBe("cancelled");
  });
});

describe("pending badge (R3-A4)", () => {
  it("given a local irrigation waiting for upload when reading the badge then it is pending with the i18n label key", async () => {
    const { createRecordViewModel } = await loadRecord();
    const { createPendingBadge } = await loadBadge();
    const d = deps();
    const out = await createRecordViewModel(d).recordFromAdvice(advice, 1);
    const badge = createPendingBadge({ db: d.db });
    expect(await badge.forRecord(out.id)).toEqual({ pending: true, label_key: "irrigation.pending_upload" });
    expect(await badge.count("irrigation_events")).toBe(1);
  });

  it("given the queue replayed twice when reading the badge then the record is no longer pending and the server holds it once", async () => {
    const { createRecordViewModel } = await loadRecord();
    const { createPendingBadge } = await loadBadge();
    const d = deps();
    const out = await createRecordViewModel(d).recordFromAdvice(advice, 1);
    const server = new Map();
    d.db.flush(server);
    d.db.flush(server);
    expect(server.size).toBe(1);
    expect(await createPendingBadge({ db: d.db }).forRecord(out.id)).toEqual({ pending: false, label_key: null });
  });

  it("given 30 offline days of irrigation when replayed after reconnection then every record is sent exactly once (SC-005)", async () => {
    const { createRecordViewModel } = await loadRecord();
    const d = deps();
    const vm = createRecordViewModel(d);
    for (let day = 1; day <= 30; day++) await vm.recordFromAdvice({ ...advice, for_date: `2026-05-${String(day).padStart(2, "0")}` }, 1);
    const server = new Map();
    d.db.flush(server);
    d.db.flush(server);
    expect(server.size).toBe(30);
  });
});
