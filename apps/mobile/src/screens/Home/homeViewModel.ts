import { MIN_TOUCH_TARGET_DP } from "./direction";

export interface HomeInput {
  isLoading: boolean;
  error: Error | null;
  isOffline: boolean;
  itemCount: number;
}
export type HomeState = "loading" | "error" | "empty" | "ready";

export interface HomeBlock {
  component: "Skeleton" | "EmptyState" | "ErrorState" | "OfflineBanner" | "Text";
  messageKey?: string;
  solutionKey?: string;
  illustration?: string;
  action?: { labelKey: string };
}
export interface HomeButton {
  id: string;
  labelKey: string;
  minWidth: number;
  minHeight: number;
}

export function deriveHomeState(i: HomeInput): HomeState {
  if (i.isLoading) return "loading";
  if (i.error) return "error";
  return i.itemCount === 0 ? "empty" : "ready";
}

const button = (id: string, labelKey: string): HomeButton => ({
  id,
  labelKey,
  minWidth: MIN_TOUCH_TARGET_DP,
  minHeight: MIN_TOUCH_TARGET_DP,
});

const LANGUAGE_BUTTONS = ["ary", "ary-Latn", "ar", "fr"].map((l) => button(`lang.${l}`, `lang.${l}`));

export function buildHomeViewModel(i: HomeInput) {
  const state = deriveHomeState(i);
  const showOfflineBanner = i.isOffline;
  const blocks: HomeBlock[] = [];
  if (showOfflineBanner) blocks.push({ component: "OfflineBanner", messageKey: "home.offlineBanner" });
  if (state === "loading") blocks.push({ component: "Skeleton", messageKey: "home.state.loading" });
  else if (state === "error")
    blocks.push({
      component: "ErrorState",
      messageKey: "home.state.error",
      solutionKey: "home.state.errorSolution",
      action: { labelKey: "home.state.retry" },
    });
  else if (state === "empty")
    blocks.push({
      component: "EmptyState",
      messageKey: "home.state.empty",
      illustration: "empty-field",
      action: { labelKey: "home.state.emptyAction" },
    });
  else blocks.push({ component: "Text", messageKey: "home.state.ready" });

  const buttons = [...LANGUAGE_BUTTONS, button("home.speak", "home.speak")];
  if (state === "ready" || state === "empty") buttons.push(button("home.openTrialRecord", "home.openTrialRecord"));
  return { state, showOfflineBanner, blocks, buttons };
}
