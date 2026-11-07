import { transitionDuration } from "@aylal/ui/motion";

const ITEMS = ["fade", "slide", "scale"] as const;
const COMPONENTS = ["Button", "Card", "Skeleton", "SyncBadge"] as const;

export function buildShowcase(i: { reduceMotion: boolean }) {
  const durationMs = transitionDuration({ reduceMotion: i.reduceMotion });
  return {
    animated: !i.reduceMotion,
    animations: ITEMS.map((name) => ({ name, durationMs })),
    components: COMPONENTS.map((name) => ({ name, source: "@aylal/ui" as const })),
  };
}
