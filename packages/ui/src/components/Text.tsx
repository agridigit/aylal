import { Text as RNText } from "react-native";
import { useTheme } from "../theme";
import { tokens } from "../tokens";
import { resolveTextLayout } from "../text-layout";
import type { BaseProps } from "./types";

export function Text({ variant = "body", label, state = "default", locale }: BaseProps & { variant?: "body" | "heading" | "caption"; locale?: string }) {
  const { theme, direction } = useTheme();
  const l = resolveTextLayout({ text: label ?? "", locale: locale ?? (direction === "rtl" ? "ar" : "fr") });
  const size = tokens.typography.scale[variant];
  return (
    <RNText
      style={{
        color: state === "error" ? theme.danger : variant === "caption" ? theme.textMuted : theme.text,
        fontFamily: l.fontFamily, fontSize: size, lineHeight: size * 1.4, textAlign: l.textAlign,
        fontWeight: variant === "heading" ? "600" : "400", opacity: state === "disabled" ? tokens.states.disabledOpacity : 1,
        flexShrink: 1,
      }}
    >
      {state === "loading" ? "…" : label}
    </RNText>
  );
}
