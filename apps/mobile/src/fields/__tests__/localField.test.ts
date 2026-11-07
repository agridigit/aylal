import { PARCEL_COLUMNS } from "../../sync/powersyncSchema";
import { saveDrawnField } from "../fieldStore";

// In-memory stand-in for the PowerSync connection (same shape as sync/__tests__/localStore.test.ts).
function fakeDb() {
  const tables: Record<string, Record<string, any>> = {};
  const crud: { table: string; id: string }[] = [];
  return {
    crud, tables,
    async insert(table: string, row: any) { (tables[table] ??= {})[row.id] = row; crud.push({ table, id: row.id }); },
    async getById(table: string, id: string) { return tables[table]?.[id] ?? null; },
    async pendingCrud(table: string, id: string) { return crud.filter((c) => c.table === table && c.id === id); },
  };
}
const ring: [number, number][] = [[-7.6, 33.57], [-7.599, 33.57], [-7.599, 33.571], [-7.6, 33.571], [-7.6, 33.57]];

describe("field saved locally while offline (R1-A1)", () => {
  it("given the synced parcel columns then the local schema carries the geometry, areas, irrigation, greenhouse and status summary", () => {
    for (const c of ["farm_id", "name", "geometry", "area_calc_ha", "area_declared_ha", "irrigation", "greenhouse", "soil", "status_summary", "source", "gps_accuracy_m"]) {
      expect(Object.keys(PARCEL_COLUMNS)).toContain(c);
    }
  });
  it("given no network when saving a GPS-drawn field then it is stored locally and queued for upload", async () => {
    const db = fakeDb();
    const id = await saveDrawnField(db as never, { farm_id: "f1", name: "Nord", ring, source: "draw_gps", gps_accuracy_m: 6, irrigation: "drip", greenhouse: false });
    const saved = await db.getById("parcels", id);
    expect(saved).toMatchObject({ farm_id: "f1", name: "Nord", source: "draw_gps", irrigation: "drip" });
    expect(JSON.parse(saved.geometry).type).toBe("Polygon");
    expect(await db.pendingCrud("parcels", id)).toHaveLength(1);
  });
  it("given a client that knows an area when saving then the calculated area is not written (server-owned)", async () => {
    const db = fakeDb();
    const id = await saveDrawnField(db as never, { farm_id: "f1", name: "Nord", ring, source: "draw_taps", area_declared_ha: 7.5 });
    const saved = await db.getById("parcels", id);
    expect(saved.area_declared_ha).toBe(7.5);
    expect(saved.area_calc_ha ?? null).toBeNull();
  });
  it("given an invalid drawing when saving then nothing is stored", async () => {
    const db = fakeDb();
    await expect(saveDrawnField(db as never, { farm_id: "f1", name: "X", ring: [[-7.6, 33.57], [-7.599, 33.571], [-7.599, 33.57], [-7.6, 33.571], [-7.6, 33.57]], source: "draw_taps" })).rejects.toThrow(/self_intersection/);
    expect(db.crud).toHaveLength(0);
  });
});
