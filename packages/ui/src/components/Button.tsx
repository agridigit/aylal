import { Pressable, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function Button({ variant = "primary", state = "default", label, onPress }: BaseProps & { variant?: "primary" | "secondary" | "danger"; onPress?: () => void }) {
  const { theme } = useTheme();
  const disabled = state === "disabled" || state === "loading";
  const bg = variant === "primary" ? theme.primary : variant === "danger" ? theme.danger : "transparent";
  const fg = variant === "secondary" ? theme.primary : variant === "danger" ? theme.surface : theme.onPrimary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled, busy: state === "loading" }}
      disabled={disabled}
      onPress={onPress}
      style={{
        minHeight: tokens.touchTargetMin, minWidth: tokens.touchTargetMin, paddingHorizontal: tokens.space.md,
        borderRadius: tokens.radius.md, alignItems: "center", justifyContent: "center", backgroundColor: bg,
        borderWidth: variant === "secondary" ? 2 : state === "error" ? 2 : 0, borderColor: state === "error" ? theme.danger : theme.primary,
        opacity: disabled ? tokens.states.disabledOpacity : state === "active" ? tokens.states.activeOpacity : 1,
        outlineStyle: "solid", outlineWidth: state === "active" ? 3 : 0, outlineColor: theme.focus,
      }}
    >
      <Text style={{ color: fg, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.body, fontWeight: "600" }}>
        {state === "loading" ? "…" : label}
      </Text>
    </Pressable>
  );
}
