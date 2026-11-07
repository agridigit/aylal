import { TextInput, View, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import type { BaseProps } from "./types";

export function TextField({ variant = "outlined", state = "default", label, placeholder, value }: BaseProps & { variant?: "outlined" | "filled"; placeholder?: string; value?: string }) {
  const { theme } = useTheme();
  const disabled = state === "disabled" || state === "loading";
  const border = state === "error" ? theme.danger : state === "active" ? theme.focus : theme.border;
  return (
    <View style={{ gap: tokens.space.xs }}>
      <Text style={{ color: state === "error" ? theme.danger : theme.textMuted, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.caption }}>{label}</Text>
      <TextInput
        editable={!disabled}
        defaultValue={value}
        placeholder={placeholder}
        placeholderTextColor={theme.textMuted}
        accessibilityLabel={label}
        style={{
          minHeight: tokens.touchTargetMin, paddingHorizontal: tokens.space.md, borderRadius: tokens.radius.md,
          borderWidth: state === "active" || state === "error" ? 3 : 1, borderColor: border, color: theme.text,
          backgroundColor: variant === "filled" ? theme.surface : "transparent", textAlign: "start",
          fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.body,
          opacity: disabled ? tokens.states.disabledOpacity : 1,
        }}
      />
    </View>
  );
}
