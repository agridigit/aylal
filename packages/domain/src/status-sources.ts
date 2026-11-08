import type { StatusSignal } from "./parcel-status";

export type SourceReader = () => StatusSignal[] | "unavailable";

/**
 * Registry of status sources (FR-013): a source that is not registered (F4, F5 before they exist), reports
 * "unavailable" or throws contributes nothing, without error. Order follows the registry.
 */
export function collectSignals(registry: Record<string, SourceReader | undefined>): StatusSignal[] {
  const out: StatusSignal[] = [];
  for (const read of Object.values(registry)) {
    if (read === undefined) continue;
    try {
      const signals = read();
      if (signals !== "unavailable") out.push(...signals);
    } catch {
      continue;
    }
  }
  return out;
}
