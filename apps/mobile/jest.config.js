/** Unit tests run in plain Node with injected adapters (no native module needed). */
module.exports = {
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testMatch: ["**/__tests__/**/*.test.ts"],
  transform: { "^.+\\.ts$": ["ts-jest", { tsconfig: "<rootDir>/tsconfig.json", diagnostics: false }] },
  moduleNameMapper: {
    "^@aylal/domain/(.*)$": "<rootDir>/../../packages/domain/src/$1",
    "^@aylal/i18n$": "<rootDir>/../../packages/i18n/src/index.ts",
  },
};
