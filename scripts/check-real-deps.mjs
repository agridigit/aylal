// Guard against "facade" apps: every external module imported by a JS/TS workspace package
// must be declared in its package.json, apps/mobile must be a real Expo/React Native app,
// and no source file may stub a native library with `declare module "<lib>"`.
// Run inside the js-test container: node scripts/check-real-deps.mjs
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = process.cwd();
const errors = [];
const SKIP_DIRS = new Set(["node_modules", "android", "ios", "dist", "coverage", "storybook-static", "test-results", ".expo"]);
const BUILTIN = /^(node:|fs$|path$|os$|url$|crypto$|child_process$|util$|events$|stream$)/;
const NATIVE_STUB = /^(react-native|expo|@expo\/|@powersync\/|@op-engineering\/|react-native-)/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name) || name.startsWith(".")) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx|js|jsx|mjs)$/.test(name)) out.push(p);
  }
  return out;
}

const pkgName = (spec) => (spec.startsWith("@") ? spec.split("/").slice(0, 2).join("/") : spec.split("/")[0]);

const workspaces = ["apps", "packages"].flatMap((d) =>
  existsSync(d) ? readdirSync(d).map((n) => join(d, n)).filter((p) => existsSync(join(p, "package.json"))) : [],
);

for (const ws of workspaces) {
  const pkg = JSON.parse(readFileSync(join(ws, "package.json"), "utf8"));
  const declared = new Set(
    ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"].flatMap((k) => Object.keys(pkg[k] ?? {})),
  );
  declared.add(pkg.name);
  const files = walk(ws).filter((f) => !/(\.config\.|babel\.config|jest\.setup)/.test(f));
  for (const f of files) {
    const src = readFileSync(f, "utf8");
    const specs = [
      ...src.matchAll(/(?:import|export)\s[^'"]*?from\s+['"]([^'"]+)['"]/g),
      ...src.matchAll(/import\s+['"]([^'"]+)['"]/g),
      ...src.matchAll(/require\(\s*['"]([^'"]+)['"]\s*\)/g),
      ...src.matchAll(/import\(\s*['"]([^'"]+)['"]\s*\)/g),
    ].map((m) => m[1]);
    for (const s of specs) {
      if (s.startsWith(".") || s.startsWith("/") || BUILTIN.test(s)) continue;
      const name = pkgName(s);
      if (!declared.has(name)) errors.push(`${relative(ROOT, f)} : « ${name} » importé mais absent de ${ws}/package.json`);
    }
    for (const m of src.matchAll(/declare\s+module\s+['"]([^'"]+)['"]/g)) {
      if (NATIVE_STUB.test(m[1])) errors.push(`${relative(ROOT, f)} : stub interdit de la bibliothèque native « ${m[1]} » (installer la vraie dépendance)`);
    }
  }
}

const mobile = "apps/mobile/package.json";
if (existsSync(mobile)) {
  const pkg = JSON.parse(readFileSync(mobile, "utf8"));
  const deps = pkg.dependencies ?? {};
  for (const required of ["expo", "react", "react-native", "expo-router"]) {
    if (!deps[required]) errors.push(`${mobile} : dépendance d'exécution « ${required} » manquante (app mobile non constructible)`);
  }
}

const unique = [...new Set(errors)];
if (unique.length) {
  for (const e of unique) console.error(`DEPS ✗ ${e}`);
  process.exit(1);
}
console.log("DEPS ✓ dépendances réelles déclarées, aucun stub natif");
