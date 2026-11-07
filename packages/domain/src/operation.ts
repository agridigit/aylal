import { z } from "zod";
import { DOSE_UNITS } from "./units";

export const OPERATION_TYPES = [
  "phyto", "fertilization", "irrigation", "tillage", "sowing_planting", "pruning", "weeding", "harvest", "other",
] as const;
export const OPERATION_STATUSES = ["planned", "done", "pending_validation", "validated", "cancelled"] as const;
export type OperationStatus = (typeof OPERATION_STATUSES)[number];
export type OperationAction = "mark_done" | "validate" | "cancel" | "correct";

const STAFF = ["owner", "manager"];

/** Next status of an operation, or null when the action is not allowed from this state for this role. */
export function nextStatus(from: string, action: string, role: string): OperationStatus | null {
  const staff = STAFF.includes(role);
  switch (action) {
    case "mark_done":
      return from === "planned" ? (staff ? "validated" : "pending_validation") : null;
    case "validate":
      return from === "pending_validation" && staff ? "validated" : null;
    case "cancel":
      if (from === "planned") return "cancelled";
      return staff && ["done", "pending_validation", "validated"].includes(from) ? "cancelled" : null;
    case "correct":
      return staff && ["done", "pending_validation", "validated"].includes(from) ? (from as OperationStatus) : null;
    default:
      return null;
  }
}

/** Status at creation: future date -> planned; otherwise done, validated at once for staff. */
export function initialStatus(performedOn: string, today: string, role: string): OperationStatus {
  if (performedOn > today) return "planned";
  return STAFF.includes(role) ? "validated" : "pending_validation";
}

/** Derived, never stored: a planned operation whose date has passed. */
export function isOverdue(status: string, performedOn: string, today: string): boolean {
  return status === "planned" && performedOn < today;
}

const ProductLine = z
  .object({
    product_id: z.uuid().nullable().optional(),
    free_product_name: z.string().min(1).max(80).nullable().optional(),
    dose: z.number().gt(0).max(100000).nullable().optional(),
    dose_unit: z.enum(DOSE_UNITS).nullable().optional(),
  })
  .strict()
  .meta({ title: "ProductLine" });

/** Body of an operation (REST and sync). No storage key exists here: photos are named by `label_photo_id`. */
export const OperationInput = z
  .object({
    id: z.uuid(),
    type: z.enum(OPERATION_TYPES).meta({ title: "OperationType" }),
    performed_on: z.iso.date(),
    parcel_ids: z.array(z.uuid()).min(1).max(50),
    product_id: z.uuid().nullable().optional(),
    free_product_name: z.string().min(1).max(80).nullable().optional(),
    product_lines: z.array(ProductLine).max(5).optional(),
    dose: z.number().gt(0).max(100000).nullable().optional(),
    dose_unit: z.enum(DOSE_UNITS).nullable().optional().meta({ title: "DoseUnit" }),
    quantity_total: z.number().gt(0).max(100000).nullable().optional(),
    quantity_unit: z.string().min(1).max(20).nullable().optional(),
    operator_name: z.string().max(80).nullable().optional(),
    note: z.string().max(500).nullable().optional(),
    season_id: z.uuid().nullable().optional(),
    label_photo_id: z.uuid().nullable().optional(),
    status: z.enum(OPERATION_STATUSES).nullable().optional().meta({ title: "IgnoredStatus", description: "Ignored: the server decides the status." }),
  })
  .strict()
  .meta({ title: "OperationInput" });
