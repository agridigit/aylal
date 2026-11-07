export const MOTION = {
  durations: { fast: 200, base: 250, slow: 300 },
  reducedDuration: 0,
} as const;

export function transitionDuration(opts: { reduceMotion: boolean }): number {
  return opts.reduceMotion ? MOTION.reducedDuration : MOTION.durations.base;
}
