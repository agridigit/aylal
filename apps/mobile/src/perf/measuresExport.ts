import { verdictFor } from "./metrics";

// Never invent a measure: without a real fps reading on device the verdict is "unmeasured".
export function buildExport(fps: number | null): "unmeasured" | "met" | "not_met" {
  return fps === null ? "unmeasured" : verdictFor("fps", fps);
}
