import { View, Text } from "react-native";
import { useTheme } from "../theme";
import type { BaseProps } from "./types";

const GLYPH = { info: "i", warning: "!", success: "✓" } as const;

export function Icon({ variant = "info", state = "default" }: BaseProps & { variant?: keyof typeof GLYPH }) {
  const { theme } = useTheme();
  const color = state === "error" ? theme.danger : variant === "warning" ? theme.warning : variant === "success" ? theme.success : theme.primary;
  return (
    <View style={{ width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: color, alignItems: "center", justifyContent: "center", opacity: state === "disabled" ? 0.4 : 1 }}>
      <Text style={{ color, fontSize: 14, fontWeight: "700" }}>{GLYPH[variant]}</Text>
    </View>
  );
}
