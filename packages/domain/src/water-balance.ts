export interface BalanceDay {
  day: string;
  et0_mm: number;
  kc: number;
  rain_eff_mm: number;
  irrigation_net_mm: number;
  moisture_depletion_mm?: number | null;
}

/** Replays the daily balance: D = clamp(D_prev + ETc - rain - irrigation, 0, TAW); a measurement replaces the day's depletion. */
export function replayBalance(i: { taw_mm: number | null; initial_depletion_mm: number; days: BalanceDay[] }): {
  days: { day: string; etc_mm: number; depletion_mm: number }[] | null; unavailable_reason?: string;
} {
  if (typeof i.taw_mm !== "number") return { days: null, unavailable_reason: "no_soil_reserve" };
  const taw = i.taw_mm;
  let d = i.initial_depletion_mm;
  const days = i.days.map((x) => {
    const etc = x.et0_mm * x.kc;
    d = typeof x.moisture_depletion_mm === "number" ? x.moisture_depletion_mm : d + etc - x.rain_eff_mm - x.irrigation_net_mm;
    d = Math.min(taw, Math.max(0, d));
    return { day: x.day, etc_mm: etc, depletion_mm: d };
  });
  return { days };
}
