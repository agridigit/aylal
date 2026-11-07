import { Pressable, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import { Icon } from "./Icon";
import type { BaseProps } from "./types";

export function ListItem({ variant = "simple", state = "default", label, onPress }: BaseProps & { variant?: "simple" | "withIcon"; onPress?: () => void }) {
  const { theme } = useTheme();
  const disabled = state === "disabled" || state === "loading";
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={{
        minHeight: tokens.touchTargetMin, flexDirection: "row", alignItems: "center", gap: tokens.space.md, paddingHorizontal: tokens.space.md,
        borderBottomWidth: 1, borderColor: state === "error" ? theme.danger : theme.border,
        backgroundColor: state === "active" ? theme.border : "transparent", opacity: disabled ? tokens.states.disabledOpacity : 1,
      }}
    >
      {variant === "withIcon" ? <Icon variant="info" /> : null}
      <Text style={{ flexShrink: 1, color: state === "error" ? theme.danger : theme.text, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.body, textAlign: "start" }}>{state === "loading" ? "…" : label}</Text>
    </Pressable>
  );
}
