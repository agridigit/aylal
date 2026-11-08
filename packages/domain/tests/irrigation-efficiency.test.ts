import { describe } from "vitest";
import * as mod from "../src/irrigation-efficiency";
import { runVectors } from "./_f4";

describe("F4 efficiency (shared vectors f4_efficiency.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_efficiency.json");
});
