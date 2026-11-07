import { View, Text } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import { Button } from "./Button";
import { Icon } from "./Icon";
import type { BaseProps } from "./types";

export function EmptyState({ variant = "illustrated", state = "default", label, actionLabel }: BaseProps & { variant?: "illustrated" | "plain"; actionLabel?: string }) {
  const { theme } = useTheme();
  return (
    <View style={{ alignItems: "center", gap: tokens.space.md, padding: tokens.space.lg, opacity: state === "disabled" ? 0.4 : 1 }}>
      {variant === "illustrated" ? <Icon variant="info" /> : null}
      <Text style={{ color: state === "error" ? theme.danger : theme.text, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.scale.body, textAlign: "center" }}>{state === "loading" ? "…" : label}</Text>
      <Button label={actionLabel} state={state === "loading" ? "loading" : state === "disabled" ? "disabled" : "default"} />
    </View>
  );
}
