import { allocationBreakdown } from "@aylal/domain/allocation";
import { initialStatus, OPERATION_TYPES, type OperationStatus } from "@aylal/domain/operation";
import { LIMITS } from "@aylal/domain/operation-limits";

export interface FormParcel {
  id: string;
  name: string;
  area_ha: number | null;
}
export interface FormDeps {
  today: string;
  newId: () => string;
  parcels: readonly FormParcel[];
  role: string;
}
interface FormState {
  id: string;
  type: string | null;
  performed_on: string | null;
  parcel_ids: string[];
  quantity_total: number | null;
  quantity_unit: string | null;
  product_id: string | null;
  free_product_name: string | null;
  dose: number | null;
  dose_unit: string | null;
  label_photo_id: string | null;
}

/** State of the quick-entry form: only type, parcel and date are required; the status is never part of the input. */
export function createOperationForm(deps: FormDeps) {
  const s: FormState = {
    id: deps.newId(), type: null, performed_on: deps.today, parcel_ids: [], quantity_total: null, quantity_unit: null,
    product_id: null, free_product_name: null, dose: null, dose_unit: null, label_photo_id: null,
  };
  const missing = (): string[] => [
    ...(s.type === null ? ["type"] : []),
    ...(s.parcel_ids.length === 0 ? ["parcel_ids"] : []),
    ...(s.performed_on === null ? ["performed_on"] : []),
  ];
  return {
    types: [...OPERATION_TYPES] as string[],
    state: (): Readonly<FormState> => ({ ...s, parcel_ids: [...s.parcel_ids] }),
    setType(type: string) { s.type = type; },
    setDate(day: string | null) { s.performed_on = day; },
    toggleParcel(id: string) {
      if (s.parcel_ids.includes(id)) s.parcel_ids = s.parcel_ids.filter((p) => p !== id);
      else if (s.parcel_ids.length < LIMITS.parcels) s.parcel_ids = [...s.parcel_ids, id];
    },
    setQuantity(total: number | null, unit: string | null) { s.quantity_total = total; s.quantity_unit = unit; },
    setProduct(productId: string | null, freeName: string | null = null) { s.product_id = productId; s.free_product_name = freeName; },
    setDose(dose: number | null, unit: string | null) { s.dose = dose; s.dose_unit = unit; },
    setLabelPhotoId(id: string | null) { s.label_photo_id = id; },
    missing,
    canSave: () => missing().length === 0,
    suggestions(): string[] {
      if (s.type !== "phyto") return [];
      return [...(s.product_id === null && s.free_product_name === null ? ["product"] : []), ...(s.dose === null ? ["dose"] : [])];
    },
    allocation() {
      if (s.quantity_total === null || s.parcel_ids.length === 0) return [];
      const chosen = deps.parcels.filter((p) => s.parcel_ids.includes(p.id));
      return allocationBreakdown(s.quantity_total, chosen).map((l) => ({ ...l, name: chosen.find((p) => p.id === l.id)?.name ?? "" }));
    },
    statusPreview(): OperationStatus | null {
      return s.performed_on === null ? null : initialStatus(s.performed_on, deps.today, deps.role);
    },
    /** Body sent to the API: only what the person filled in; the server decides status and warnings. */
    toInput(): Record<string, unknown> {
      const out: Record<string, unknown> = { id: s.id, type: s.type, performed_on: s.performed_on, parcel_ids: [...s.parcel_ids] };
      const optional: [string, unknown][] = [
        ["quantity_total", s.quantity_total], ["quantity_unit", s.quantity_unit], ["product_id", s.product_id],
        ["free_product_name", s.free_product_name], ["dose", s.dose], ["dose_unit", s.dose_unit], ["label_photo_id", s.label_photo_id],
      ];
      for (const [k, v] of optional) if (v !== null) out[k] = v;
      return out;
    },
  };
}
