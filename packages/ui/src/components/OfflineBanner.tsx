import { View, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function OfflineBanner({ variant = "banner", state = "default", label }: BaseProps & { variant?: "banner" | "compact" }) {
  const { theme } = useTheme();
  return (
    <View accessibilityRole="alert" style={{ paddingVertical: variant === "banner" ? tokens.space.md : tokens.space.xs, paddingHorizontal: tokens.space.md, backgroundColor: state === "error" ? theme.danger : theme.warning, borderRadius: tokens.radius.sm, opacity: state === "disabled" ? 0.4 : state === "active" ? 0.85 : 1 }}>
      <Text style={{ color: theme.surface, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.caption, fontWeight: "600" }}>{state === "loading" ? "…" : label}</Text>
    </View>
  );
}
