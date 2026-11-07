import { z } from "zod";

export const TrialRecordCreate = z
  .object({
    title: z.string().trim().min(1).max(120),
    note: z.string().max(2000).nullable().optional(),
    quantity: z.number().min(0).max(1_000_000).nullable().optional(),
  })
  .meta({ title: "TrialRecordCreate" });
