type N = number | null | undefined;
export interface SystemInput {
  kind: string; sectors_count?: N; pump_flow_m3h?: N; emitter_flow_lph?: N; emitter_spacing_m?: N; row_spacing_m?: N; efficiency?: N;
}
export interface FieldError { field: string; code: string; i18n_key: string }

const err = (field: string, code: string): FieldError => ({ field, code, i18n_key: `irrigation.system.${field}.${code}` });
const given = (v: N): v is number => v !== null && v !== undefined;
const bad = (v: N) => given(v) && !(Number.isFinite(v) && v > 0);

/** R1-A2/A5: a system is described by the pump flow or (drip only) by emitters and spacings; a field that is given must be > 0; no flow is never invented. */
export function validateIrrigationSystem(i: SystemInput): { valid: boolean; errors: any[] } {
  const errors: FieldError[] = [];
  for (const f of ["emitter_flow_lph", "emitter_spacing_m", "row_spacing_m", "pump_flow_m3h", "sectors_count"] as const) {
    if (bad(i[f])) errors.push(err(f, "must_be_positive"));
  }
  if (given(i.efficiency) && !(i.efficiency > 0 && i.efficiency <= 1)) errors.push(err("efficiency", "out_of_range"));
  if (!given(i.pump_flow_m3h) && (i.kind !== "drip" || !given(i.emitter_flow_lph))) errors.push(err("pump_flow_m3h", "flow_required"));
  else if (!given(i.pump_flow_m3h)) {
    if (!given(i.emitter_spacing_m)) errors.push(err("emitter_spacing_m", "required"));
    if (!given(i.row_spacing_m)) errors.push(err("row_spacing_m", "required"));
  }
  return { valid: errors.length === 0, errors };
}
