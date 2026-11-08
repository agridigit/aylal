import { describe } from "vitest";
import * as mod from "../src/et0";
import { runVectors } from "./_f4";

describe("F4 ET0 (FAO-56 eq. 21, 52) (shared vectors f4_et0.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_et0.json");
});
