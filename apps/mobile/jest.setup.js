/** Vitest-style `expect(value, message)` is used by shared tests; Jest's expect accepts one argument only. */
const jestExpect = global.expect;
const expectWithMessage = (actual) => jestExpect(actual);
Object.assign(expectWithMessage, jestExpect);
global.expect = expectWithMessage;
