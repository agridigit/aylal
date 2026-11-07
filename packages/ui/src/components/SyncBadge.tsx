import { View, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function SyncBadge({ variant = "badge", state = "default", label }: BaseProps & { variant?: "badge" | "dot" }) {
  const { theme } = useTheme();
  const color = state === "error" ? theme.danger : state === "loading" ? theme.warning : state === "disabled" ? theme.border : theme.success;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: tokens.space.xs, opacity: state === "active" ? 0.85 : 1 }}>
      <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: color }} />
      {variant === "badge" ? <Text style={{ color: theme.text, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.caption }}>{label}</Text> : null}
    </View>
  );
}
