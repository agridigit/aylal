#!/usr/bin/env bash
# Test pyramid gate: every code module has unit + integration tests; every app/service has e2e tests;
# every feature branch adds or changes tests at all three levels.
# Conventions:
#   unit        : <module>/tests/unit/**   (TS legacy: <module>/tests/*.test.ts counts as unit)
#   integration : <module>/tests/integration/**  (services: tests/contract/** also counts)
#   apps (mobile): tests live next to code in src/**/__tests__ ; Maestro flows in maestro/
#   e2e         : services/<s>/tests/e2e/**, apps/mobile/maestro/** (Maestro), apps/{web,desktop}/e2e/** (Playwright)
set -u
cd "$(git rev-parse --show-toplevel)"
fail=0
err(){ echo "PYRAMIDE ✗ $*" >&2; fail=1; }
has(){ [ -n "$(find "$@" -type f \( -name '*.test.ts' -o -name '*.test.tsx' -o -name '*.spec.ts' -o -name 'test_*.py' -o -name '*_test.py' -o -name '*.yaml' -o -name '*.yml' \) -not -path '*/node_modules/*' 2>/dev/null | head -1)" ]; }

for m in packages/* services/* apps/*; do
  [ -d "$m" ] || continue
  # only modules that contain production code
  [ -d "$m/src" ] || [ -d "$m/app" ] || continue
  has "$m/tests/unit" || { [ -d "$m/tests" ] && has "$m/tests" -maxdepth 1; } || { [ "${m#apps/}" != "$m" ] && has "$m/src"; } || err "$m : aucun test unitaire ($m/tests/unit/)"
  has "$m/tests/integration" "$m/tests/contract" || { [ "${m#apps/}" != "$m" ] && has "$m/src"; } || err "$m : aucun test d'intégration ($m/tests/integration/)"
  case "$m" in
    services/*) has "$m/tests/e2e" || err "$m : aucun test de bout en bout ($m/tests/e2e/)";;
    apps/*)     has "$m/e2e" "$m/maestro" || err "$m : aucun test de bout en bout ($m/e2e/)";;
  esac
done

# Feature branch: code changes must come with tests at all three levels.
branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ] && git rev-parse -q --verify main >/dev/null; then
  changed="$(git diff --name-only main...HEAD; git diff --name-only HEAD; git ls-files --others --exclude-standard)"
  prod="$(printf '%s\n' "$changed" | grep -E '^(apps|packages|services)/[^/]+/(src|app)/' || true)"
  if [ -n "$prod" ]; then
    printf '%s\n' "$changed" | grep -qE '/tests/unit/|^packages/[^/]+/tests/[^/]+\.test\.tsx?$|^apps/[^/]+/src/(.+/)?__tests__/[^/]+\.test\.tsx?$' || err "branche $branch : code modifié sans test unitaire"
    printf '%s\n' "$changed" | grep -qE '/tests/(integration|contract)/|/__tests__/integration/' || err "branche $branch : code modifié sans test d'intégration"
    printf '%s\n' "$changed" | grep -qE '/tests/e2e/|^apps/[^/]+/(e2e|maestro)/'                || err "branche $branch : code modifié sans test de bout en bout"
  fi
fi

[ $fail -eq 0 ] && echo "PYRAMIDE ✓ unitaires, intégration et bout en bout présents"
exit $fail
