import { z } from "zod";

export const FarmCreate = z
  .object({ name: z.string().trim().min(1).max(120) })
  .meta({ title: "FarmCreate" });
