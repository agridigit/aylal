import { createContext, useContext, type ReactNode } from "react";
import { tokens, type Theme, type ThemeName } from "./tokens";

export type Direction = "ltr" | "rtl";
interface Ctx { name: ThemeName; theme: Theme; direction: Direction }

const ThemeContext = createContext<Ctx>({ name: "light", theme: tokens.themes.light, direction: "ltr" });

export function ThemeProvider(p: { name: ThemeName; direction: Direction; children: ReactNode }) {
  return <ThemeContext.Provider value={{ name: p.name, theme: tokens.themes[p.name], direction: p.direction }}>{p.children}</ThemeContext.Provider>;
}
export const useTheme = () => useContext(ThemeContext);
