import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  framework: "@storybook/react-vite",
  stories: ["../src/components/*.stories.tsx"],
  core: { disableTelemetry: true },
  viteFinal: async (cfg) => {
    cfg.resolve = { ...cfg.resolve, alias: { ...(cfg.resolve?.alias as object), "react-native": "react-native-web" } };
    cfg.define = { ...cfg.define, __DEV__: "true" };
    return cfg;
  },
};
export default config;
