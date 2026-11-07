import { tokens } from "../tokens";

export const STATES = ["default", "active", "disabled", "loading", "error"] as const;
export type ComponentState = (typeof STATES)[number];

export interface CatalogEntry {
  name: string;
  variants: readonly string[];
  interactive: boolean;
  minTouchTarget: number;
}

const entry = (name: string, variants: string[], interactive = false): CatalogEntry => ({
  name, variants, interactive, minTouchTarget: interactive ? tokens.touchTargetMin : 0,
});

export const catalog: readonly CatalogEntry[] = [
  entry("Button", ["primary", "secondary", "danger"], true),
  entry("Text", ["body", "heading", "caption"]),
  entry("Icon", ["info", "warning", "success"]),
  entry("TextField", ["outlined", "filled"], true),
  entry("Card", ["elevated", "outlined"]),
  entry("Skeleton", ["line", "block"]),
  entry("EmptyState", ["illustrated", "plain"]),
  entry("ErrorState", ["inline", "page"]),
  entry("OfflineBanner", ["banner", "compact"]),
  entry("SyncBadge", ["badge", "dot"]),
  entry("Switch", ["standard"], true),
  entry("ListItem", ["simple", "withIcon"], true),
];
