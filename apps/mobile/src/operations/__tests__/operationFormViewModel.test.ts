import { OPERATION_TYPES } from "@aylal/domain/operation";
import { createOperationForm } from "../viewModels/operationForm";

const parcels = [
  { id: "p1", name: "Haut", area_ha: 1 },
  { id: "p2", name: "Bas", area_ha: 3 },
];
const make = (over = {}) => createOperationForm({ today: "2026-11-07", newId: () => "11111111-1111-4111-8111-111111111111", parcels, role: "owner", ...over });

describe("operation form view model (R1-A1, R1-A3)", () => {
  it("given the form when listing the types then the nine operation icons are offered", () => {
    expect(make().types).toEqual([...OPERATION_TYPES]);
    expect(make().types).toHaveLength(9);
  });

  it("given an empty form when checking then only the type and the parcel are missing, the date defaulting to today", () => {
    const f = make();
    expect(f.missing()).toEqual(["type", "parcel_ids"]);
    expect(f.canSave()).toBe(false);
    expect(f.state().performed_on).toBe("2026-11-07");
  });

  it("given a type, a parcel and a date when saving then no other field is required", () => {
    const f = make();
    f.setType("irrigation");
    f.toggleParcel("p1");
    expect(f.missing()).toEqual([]);
    expect(f.canSave()).toBe(true);
    expect(f.toInput()).toEqual({ id: "11111111-1111-4111-8111-111111111111", type: "irrigation", performed_on: "2026-11-07", parcel_ids: ["p1"] });
  });

  it("given the date cleared when checking then the date becomes required", () => {
    const f = make();
    f.setType("other");
    f.toggleParcel("p1");
    f.setDate(null);
    expect(f.missing()).toEqual(["performed_on"]);
    expect(f.canSave()).toBe(false);
  });

  it("given a phyto treatment without product or dose when saving then it is still allowed and the missing items are only suggested", () => {
    const f = make();
    f.setType("phyto");
    f.toggleParcel("p1");
    expect(f.canSave()).toBe(true);
    expect(f.suggestions()).toEqual(["product", "dose"]);
  });

  it("given a toggled parcel when toggling it again then it is removed, and more than 50 parcels are refused", () => {
    const f = make();
    f.toggleParcel("p1");
    f.toggleParcel("p1");
    expect(f.state().parcel_ids).toEqual([]);
    const many = Array.from({ length: 51 }, (_, i) => ({ id: `p${i}`, name: `P${i}`, area_ha: 1 }));
    const g = make({ parcels: many });
    many.forEach((p) => g.toggleParcel(p.id));
    expect(g.state().parcel_ids).toHaveLength(50);
  });

  it("given a quantity over two parcels when displaying then the split by area is shown and adds up", () => {
    const f = make();
    f.setType("fertilization");
    f.toggleParcel("p1");
    f.toggleParcel("p2");
    f.setQuantity(10, "kg");
    expect(f.allocation()).toEqual([
      { id: "p1", name: "Haut", share: 2.5, percent: 25 },
      { id: "p2", name: "Bas", share: 7.5, percent: 75 },
    ]);
    expect(f.toInput()).toMatchObject({ quantity_total: 10, quantity_unit: "kg" });
  });

  it("given no quantity when displaying then there is no allocation", () => {
    const f = make();
    f.toggleParcel("p1");
    expect(f.allocation()).toEqual([]);
  });

  it("given a future date when previewing then the status is planned; today it follows the role", () => {
    const owner = make();
    owner.setDate("2026-11-09");
    expect(owner.statusPreview()).toBe("planned");
    owner.setDate("2026-11-07");
    expect(owner.statusPreview()).toBe("validated");
    expect(make({ role: "worker" }).statusPreview()).toBe("pending_validation");
  });

  it("given a form when building the input then it never carries a status, a warning or a storage key", () => {
    const f = make();
    f.setType("phyto");
    f.toggleParcel("p1");
    f.setLabelPhotoId("22222222-2222-4222-8222-222222222222");
    const input = f.toInput() as Record<string, unknown>;
    expect(input.label_photo_id).toBe("22222222-2222-4222-8222-222222222222");
    for (const k of ["status", "warnings", "label_photo_key", "file_keys", "url"]) expect(input).not.toHaveProperty(k);
  });
});
