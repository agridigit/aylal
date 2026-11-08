import { z } from "zod";

/** Observation attached to an attention zone (REST and sync). No storage key exists here: a photo is named by `photo_id`. */
export const ObservationInput = z
  .object({
    id: z.uuid(),
    note: z.string().max(500),
    photo_id: z.uuid().nullable().optional(),
  })
  .strict()
  .meta({ title: "ObservationInput" });
