import { View } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function Skeleton({ variant = "line", state = "loading" }: BaseProps & { variant?: "line" | "block" }) {
  const { theme } = useTheme();
  return (
    <View
      accessibilityRole="progressbar"
      style={{
        height: variant === "line" ? 16 : 96, width: "100%", borderRadius: tokens.radius.md, backgroundColor: theme.border,
        opacity: state === "disabled" ? 0.4 : state === "active" ? 0.8 : 0.6,
        borderWidth: state === "error" ? 2 : 0, borderColor: theme.danger,
      }}
    />
  );
}
