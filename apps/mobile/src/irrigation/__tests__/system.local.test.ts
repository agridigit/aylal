/** T049 (US1) - R1-A4: the installation is described offline, kept locally as "pending", and replayed without loss.
 *  The view model does not exist yet: imported inside each test (the failure is the missing feature). */
import { fakeDb, ids } from "./_fakeDb";

const load = async () => await import("../viewModels/system");
const DRIP = { kind: "drip", sectors_count: 2, emitter_flow_lph: 4, emitter_spacing_m: 0.5, row_spacing_m: 2 };

describe("system view model (offline, R1-A4)", () => {
  it("given no network when the farmer describes the system then it is saved locally with a client uuid and marked pending", async () => {
    const { createSystemViewModel } = await load();
    const db = fakeDb();
    const vm = createSystemViewModel({ db, newId: ids(), farmId: "farm-1" });
    const out = await vm.save("parcel-1", DRIP);
    expect(out.ok).toBe(true);
    expect(await db.getById("irrigation_systems", out.id)).toMatchObject({ parcel_id: "parcel-1", farm_id: "farm-1", kind: "drip", sectors_count: 2 });
    expect(await vm.syncState(out.id)).toBe("pending");
  });

  it("given a described system when reading it back then the default efficiency of the type is shown as a default", async () => {
    const { createSystemViewModel } = await load();
    const vm = createSystemViewModel({ db: fakeDb(), newId: ids(), farmId: "farm-1" });
    const out = await vm.save("parcel-1", DRIP);
    expect(await vm.read("parcel-1")).toMatchObject({ id: out.id, efficiency_effective: 0.9, efficiency_is_default: true });
  });

  it("given a system described by the pump flow when saving offline then it is accepted", async () => {
    const { createSystemViewModel } = await load();
    const vm = createSystemViewModel({ db: fakeDb(), newId: ids(), farmId: "farm-1" });
    expect((await vm.save("parcel-1", { kind: "gravity", sectors_count: 1, pump_flow_m3h: 8 })).ok).toBe(true);
  });

  it("given an incoherent value when saving then the field and an i18n key are returned and nothing is queued", async () => {
    const { createSystemViewModel } = await load();
    const db = fakeDb();
    const vm = createSystemViewModel({ db, newId: ids(), farmId: "farm-1" });
    const out = await vm.save("parcel-1", { ...DRIP, emitter_spacing_m: 0 });
    expect(out.ok).toBe(false);
    expect(out.errors[0]).toMatchObject({ field: "emitter_spacing_m" });
    expect(out.errors[0].i18n_key).toMatch(/^irrigation\./);
    expect(db.crud).toEqual([]);
  });

  it("given a system already described when modifying it then the same id is updated (one active system per parcel)", async () => {
    const { createSystemViewModel } = await load();
    const db = fakeDb();
    const vm = createSystemViewModel({ db, newId: ids(), farmId: "farm-1" });
    const first = await vm.save("parcel-1", DRIP);
    const second = await vm.save("parcel-1", { ...DRIP, emitter_flow_lph: 8 });
    expect(second.id).toBe(first.id);
    expect((await db.getAll("irrigation_systems", { parcel_id: "parcel-1" })).length).toBe(1);
  });

  it("given 30 offline days of edits when the queue is replayed twice then nothing is lost and nothing is duplicated (SC-005)", async () => {
    const { createSystemViewModel } = await load();
    const db = fakeDb();
    const vm = createSystemViewModel({ db, newId: ids(), farmId: "farm-1" });
    for (let day = 1; day <= 30; day++) await vm.save(`parcel-${day % 3}`, { ...DRIP, emitter_flow_lph: 4 + day });
    const server = new Map();
    db.flush(server);
    db.flush(server);
    expect(server.size).toBe(3);
    expect([...server.values()].map((r) => r.emitter_flow_lph).sort()).toEqual([32, 33, 34]);
  });

  it("given the view model when sending the record then no server-owned field is part of the row", async () => {
    const { createSystemViewModel } = await load();
    const db = fakeDb();
    const out = await createSystemViewModel({ db, newId: ids(), farmId: "farm-1" }).save("parcel-1", DRIP);
    const row = await db.getById("irrigation_systems", out.id);
    expect(Object.keys(row)).not.toEqual(expect.arrayContaining(["server_version", "efficiency_effective", "application_rate_mm_h"]));
  });
});
