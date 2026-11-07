// Shared tests use the vitest-style `expect(value, message)`; see jest.setup.js.
declare namespace jest {
  interface Expect {
    <T = any>(actual: T, message?: string): JestMatchers<T>;
  }
}
