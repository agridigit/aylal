import { describe } from "vitest";
import * as mod from "../src/application-rate";
import { runVectors } from "./_f4";

describe("F4 application rate and duration (shared vectors f4_application_rate.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_application_rate.json");
});
