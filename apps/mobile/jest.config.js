/** Unit tests run in plain Node with injected adapters (no native module needed). */
module.exports = {
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  testMatch: ["**/__tests__/**/*.test.ts"],
  transform: { "^.+\\.ts$": ["ts-jest", { tsconfig: "<rootDir>/tsconfig.json", diagnostics: false }] },
  moduleNameMapper: { "^@aylal/domain/(.*)$": "<rootDir>/../../packages/domain/src/$1" },
};
