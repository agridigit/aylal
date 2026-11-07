/** Map data from the local parcels table (offline first). */
export const STATUS_COLORS = { ok: "#2E6B34", watch: "#F5C26B", act: "#B3261E", unknown: "#9AA0A6" } as const;
export type FieldStatus = keyof typeof STATUS_COLORS;

/** Plain read of parcels: PowerSync forbids joins and sub-queries. */
export const FIELDS_LOCAL_SQL = "SELECT id, name, geometry, status_summary, archived_at FROM parcels WHERE archived_at IS NULL";

export type FieldRow = { id: string; name: string; geometry: unknown; status_summary?: string | null; archived_at?: string | null };
export type FieldFeature = {
  type: "Feature";
  geometry: unknown;
  properties: { id: string; name: string; status: FieldStatus; color: string };
};

function parseGeometry(g: unknown): unknown | null {
  if (typeof g === "string") {
    try {
      return JSON.parse(g);
    } catch {
      return null;
    }
  }
  return g && typeof g === "object" ? g : null;
}

export function buildFieldsGeoJson(rows: readonly FieldRow[]): { type: "FeatureCollection"; features: FieldFeature[] } {
  const features: FieldFeature[] = [];
  for (const r of rows) {
    if (r.archived_at) continue;
    const geometry = parseGeometry(r.geometry);
    if (!geometry) continue;
    const status: FieldStatus = r.status_summary === "ok" || r.status_summary === "watch" || r.status_summary === "act" ? r.status_summary : "unknown";
    features.push({ type: "Feature", geometry, properties: { id: r.id, name: r.name, status, color: STATUS_COLORS[status] } });
  }
  return { type: "FeatureCollection", features };
}
