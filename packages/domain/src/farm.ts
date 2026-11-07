import { z } from "zod";
import { validateWith, type Verdict } from "./validation/verdict";

export const FarmRegistration = z
  .object({
    name: z.string().trim().min(1).max(120),
    location: z.object({ lat: z.number().min(-90).max(90), lon: z.number().min(-180).max(180) }),
    area_ha: z.number().min(0).optional(),
  })
  .meta({ title: "FarmRegistration" });

export const validateFarm = (input: unknown): Verdict => validateWith(FarmRegistration, input);

/** A farm still in the local upload queue is shown as "pending upload". */
export function farmUploadState(farmId: string, pendingIds: readonly string[]): "pending_upload" | "synced" {
  return pendingIds.includes(farmId) ? "pending_upload" : "synced";
}
