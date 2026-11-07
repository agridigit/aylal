import { View, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import { Button } from "./Button";
import { Icon } from "./Icon";
import type { BaseProps } from "./types";

export function ErrorState({ variant = "inline", state = "default", label, solutionLabel, actionLabel }: BaseProps & { variant?: "inline" | "page"; solutionLabel?: string; actionLabel?: string }) {
  const { theme } = useTheme();
  return (
    <View accessibilityRole="alert" style={{ alignItems: variant === "page" ? "center" : "flex-start", gap: tokens.space.sm, padding: tokens.space.md, opacity: state === "disabled" ? 0.4 : 1 }}>
      <Icon variant="warning" state="error" />
      <Text style={{ color: theme.danger, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.body, fontWeight: "600" }}>{label}</Text>
      <Text style={{ color: theme.textMuted, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.caption }}>{solutionLabel}</Text>
      <Button variant="secondary" label={actionLabel} state={state === "loading" ? "loading" : state === "active" ? "active" : state === "disabled" ? "disabled" : "default"} />
    </View>
  );
}
