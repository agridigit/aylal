/** FAO-56 eq. 21 (extraterrestrial radiation) and eq. 52 (Hargreaves-Samani). */
const GSC = 0.082; // MJ m-2 min-1
const RAD = Math.PI / 180;

export function extraterrestrialRadiation(i: { lat: number; doy: number }): { ra_mj_m2_day: number } {
  const phi = i.lat * RAD;
  const dr = 1 + 0.033 * Math.cos((2 * Math.PI * i.doy) / 365);
  const delta = 0.409 * Math.sin((2 * Math.PI * i.doy) / 365 - 1.39);
  const ws = Math.acos(Math.max(-1, Math.min(1, -Math.tan(phi) * Math.tan(delta))));
  const ra = ((24 * 60) / Math.PI) * GSC * dr * (ws * Math.sin(phi) * Math.sin(delta) + Math.cos(phi) * Math.cos(delta) * Math.sin(ws));
  return { ra_mj_m2_day: ra };
}

export function hargreavesEt0(i: { tmin: number; tmax: number; lat: number; doy: number }): { et0_mm: number } {
  const ra = extraterrestrialRadiation(i).ra_mj_m2_day;
  const range = Math.max(0, i.tmax - i.tmin);
  const et0 = 0.0023 * ((i.tmax + i.tmin) / 2 + 17.8) * Math.sqrt(range) * ra * 0.408;
  return { et0_mm: Math.max(0, et0) };
}

type N = number | null | undefined;
/** Gateway ET0 wins (zero is a value); otherwise Hargreaves; otherwise nothing. */
export function resolveEt0(i: { gateway_et0_mm: N; tmin: N; tmax: N; lat: number; doy: number }): {
  et0_mm: number | null; method: "gateway" | "hargreaves" | null; unavailable_reason?: string;
} {
  if (typeof i.gateway_et0_mm === "number") return { et0_mm: i.gateway_et0_mm, method: "gateway" };
  if (typeof i.tmin === "number" && typeof i.tmax === "number") {
    return { et0_mm: hargreavesEt0({ tmin: i.tmin, tmax: i.tmax, lat: i.lat, doy: i.doy }).et0_mm, method: "hargreaves" };
  }
  return { et0_mm: null, method: null, unavailable_reason: "no_weather" };
}
