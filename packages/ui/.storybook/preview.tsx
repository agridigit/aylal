import type { Preview } from "@storybook/react";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/600.css";
import { ThemeProvider, type Direction } from "../src/theme";
import { tokens, type ThemeName } from "../src/tokens";

const preview: Preview = {
  globalTypes: {
    theme: { description: "Thème", toolbar: { title: "Thème", items: ["light", "dark", "sun"], dynamicTitle: true } },
    direction: { description: "Sens", toolbar: { title: "Sens", items: ["ltr", "rtl"], dynamicTitle: true } },
  },
  initialGlobals: { theme: "light", direction: "ltr" },
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story, ctx) => {
      const name = (ctx.globals.theme ?? "light") as ThemeName;
      const direction = (ctx.globals.direction ?? "ltr") as Direction;
      return (
        <ThemeProvider name={name} direction={direction}>
          <div
            dir={direction}
            style={{ boxSizing: "border-box", width: 360, minHeight: 240, padding: 16, background: tokens.themes[name].background, fontFamily: direction === "rtl" ? tokens.typography.fontFamilyArabic : tokens.typography.fontFamily }}
          >
            <Story />
          </div>
        </ThemeProvider>
      );
    },
  ],
};
export default preview;
