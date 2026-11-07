import { z } from "zod";
import { validateWith, type Verdict } from "./validation/verdict";

export const ConsentGrant = z
  .object({ purpose: z.string().trim().min(1).max(80), text_version: z.string().trim().min(1).max(40) })
  .meta({ title: "ConsentGrant" });

export const validateConsent = (input: unknown): Verdict => validateWith(ConsentGrant, input);
