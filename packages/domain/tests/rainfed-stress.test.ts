import { describe } from "vitest";
import * as mod from "../src/rainfed-stress";
import { runVectors } from "./_f4";

describe("F4 rainfed stress (shared vectors f4_stress.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_stress.json");
});
