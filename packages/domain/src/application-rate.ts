export interface RateInput {
  kind: string;
  emitter_flow_lph: number | null;
  emitter_spacing_m: number | null;
  row_spacing_m: number | null;
  pump_flow_m3h: number | null;
  sectors_count: number;
  area_m2: number | null;
}

const pos = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v) && v > 0;

/** mm/h: emitters (L/h over spacing x row spacing) or pump flow over equal sector surfaces; null when not computable. */
export function applicationRate(i: RateInput): { rate_mm_h: number | null } {
  if (pos(i.emitter_flow_lph) && pos(i.emitter_spacing_m) && pos(i.row_spacing_m)) {
    return { rate_mm_h: i.emitter_flow_lph / (i.emitter_spacing_m * i.row_spacing_m) };
  }
  if (pos(i.pump_flow_m3h) && pos(i.area_m2) && pos(i.sectors_count)) {
    return { rate_mm_h: (i.pump_flow_m3h * 1000) / (i.area_m2 / i.sectors_count) };
  }
  return { rate_mm_h: null };
}

/** Minutes = net need / (efficiency x rate), rounded; null without a rate or efficiency. */
export function irrigationMinutes(i: { net_need_mm: number; efficiency: number | null; rate_mm_h: number | null }): { minutes: number | null } {
  if (!pos(i.rate_mm_h) || !pos(i.efficiency)) return { minutes: null };
  return { minutes: Math.round((i.net_need_mm / (i.efficiency * i.rate_mm_h)) * 60) };
}
