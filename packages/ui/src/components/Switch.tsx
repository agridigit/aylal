import { Pressable, View } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function Switch({ state = "default", label, value = false, onValueChange }: BaseProps & { variant?: "standard"; value?: boolean; onValueChange?: (v: boolean) => void }) {
  const { theme, direction } = useTheme();
  const on = value || state === "active";
  const disabled = state === "disabled" || state === "loading";
  const end = direction === "rtl" ? "flex-start" : "flex-end";
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityState={{ checked: on, disabled }}
      disabled={disabled}
      onPress={() => onValueChange?.(!value)}
      style={{ minHeight: tokens.touchTargetMin, minWidth: tokens.touchTargetMin, justifyContent: "center", opacity: disabled ? tokens.states.disabledOpacity : 1 }}
    >
      <View style={{ width: 52, height: 32, borderRadius: 16, padding: 3, justifyContent: "center", alignItems: on ? end : direction === "rtl" ? "flex-end" : "flex-start", backgroundColor: on ? theme.primary : theme.border, borderWidth: state === "error" ? 2 : 0, borderColor: theme.danger }}>
        <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: on ? theme.onPrimary : theme.surface }} />
      </View>
    </Pressable>
  );
}
