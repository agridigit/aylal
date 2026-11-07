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
