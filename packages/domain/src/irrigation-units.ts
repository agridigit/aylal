type N = number | null;
const pos = (v: N | undefined): v is number => typeof v === "number" && Number.isFinite(v) && v > 0;

/** Duration to volume (m3) and net depth (mm); nothing is invented without a rate or a surface. */
export function fromDuration(i: { minutes: number; rate_mm_h: N; area_m2: N; efficiency: N }): { volume_m3: N; net_mm: N } {
  if (!pos(i.rate_mm_h) || !pos(i.area_m2)) return { volume_m3: null, net_mm: null };
  const gross = (i.rate_mm_h * i.minutes) / 60;
  return { volume_m3: (gross * i.area_m2) / 1000, net_mm: pos(i.efficiency) ? gross * i.efficiency : null };
}

/** Inverse of fromDuration. */
export function fromVolume(i: { volume_m3: number; rate_mm_h: N; area_m2: N; efficiency: N }): { minutes: N; net_mm: N } {
  if (!pos(i.area_m2)) return { minutes: null, net_mm: null };
  const gross = (i.volume_m3 * 1000) / i.area_m2;
  const net = pos(i.efficiency) ? gross * i.efficiency : null;
  return { minutes: pos(i.rate_mm_h) ? Math.round((gross / i.rate_mm_h) * 60) : null, net_mm: net };
}
