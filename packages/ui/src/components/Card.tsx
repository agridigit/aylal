import type { ReactNode } from "react";
import { View } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function Card({ variant = "elevated", state = "default", children }: BaseProps & { variant?: "elevated" | "outlined"; children?: ReactNode }) {
  const { theme } = useTheme();
  return (
    <View
      style={{
        padding: tokens.space.md, borderRadius: tokens.radius.lg, backgroundColor: theme.surface,
        borderWidth: variant === "outlined" || state === "error" || state === "active" ? 2 : 0,
        borderColor: state === "error" ? theme.danger : state === "active" ? theme.focus : theme.border,
        boxShadow: variant === "elevated" ? tokens.shadow.md : tokens.shadow.none,
        opacity: state === "disabled" ? tokens.states.disabledOpacity : 1,
      }}
    >
      {children}
    </View>
  );
}
