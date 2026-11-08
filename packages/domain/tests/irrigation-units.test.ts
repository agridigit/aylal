import { describe } from "vitest";
import * as mod from "../src/irrigation-units";
import { runVectors } from "./_f4";

describe("F4 irrigation units (shared vectors f4_units.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_units.json");
});
