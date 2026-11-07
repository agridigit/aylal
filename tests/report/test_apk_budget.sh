#!/usr/bin/env bash
# Documented APK budget override: default 40 MB never weakened; override is explicit, bounded and branch-scoped.
source "$(dirname "$0")/../platform/lib.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
S=scripts/in-container/apk-size.sh
truncate -s 30M "$T/ok.apk"; truncate -s 45M "$T/mid.apk"; truncate -s 41M "$T/big.apk"
mkdir -p "$T/specs/feat"
printf '## Dérogation\nraison\n' > "$T/specs/feat/decisions.md"
run() { APK_PATH="$1" APK_BRANCH="${BR:-feat}" SPECS_DIR="$T/specs" MEASURE_OUT="$T/m.json" bash "$S" >"$T/out" 2>&1; }
env_file() { printf 'APK_LIMIT_MB=%s\nAPK_BUDGET_REASON="%s"\nDECISION_REF=%s\n' "$1" "$2" "$3" > "$T/specs/feat/apk-budget.env"; }
ref="$T/specs/feat/decisions.md"

# default unchanged without file
rm -f "$T/specs/feat/apk-budget.env"
run "$T/mid.apk" && fail "45 MB must fail with default 40 MB"
grep -q 'DÉROGATION' "$T/out" && fail "no derogation message without file"

# valid derogation accepted and displayed
env_file 52 "MapLibre natif" "$ref"
run "$T/mid.apk" || fail "45 MB must pass under valid 52 MB derogation"
grep -q "DÉROGATION: limite 52 Mo au lieu de 40 Mo — MapLibre natif — $ref" "$T/out" || fail "derogation line missing"
grep -q 'DÉROGATION' "$T/m.json" || fail "derogation missing from measure JSON"
grep -q '"threshold": *52' "$T/m.json" || fail "threshold must be 52"
truncate -s 53M "$T/over.apk"
run "$T/over.apk" && fail "53 MB must fail even with 52 MB derogation"

# invalid derogations refused (even for a small APK)
env_file 52 "" "$ref"; run "$T/ok.apk" && fail "missing reason must be refused"
env_file 52 "x" ""; run "$T/ok.apk" && fail "missing ref must be refused"
printf '# rien\n' > "$T/nosec.md"
env_file 52 "x" "$T/nosec.md"; run "$T/ok.apk" && fail "ref without Dérogation section must be refused"
env_file 52 "x" "$T/absent.md"; run "$T/ok.apk" && fail "absent ref file must be refused"
env_file 61 "x" "$ref"; run "$T/ok.apk" && fail ">60 MB must be refused"
env_file 60 "x" "$ref"; run "$T/ok.apk" || fail "60 MB is the allowed maximum"
env_file 39 "x" "$ref"; run "$T/ok.apk" && fail "limit below 40 must be refused"
env_file abc "x" "$ref"; run "$T/ok.apk" && fail "non numeric limit must be refused"

# other branch ignores the file
env_file 52 "x" "$ref"
BR=main run "$T/mid.apk" && fail "other branch must keep 40 MB"
grep -q 'DÉROGATION' "$T/out" && fail "other branch must not show derogation"

# report.sh shows derogation in mesures.md
R="$T/repo"; mkdir -p "$R/docs/modules/m/measures" "$R/scripts"; cp scripts/report.sh "$R/scripts/"
env_file 52 "MapLibre natif" "$ref"
run "$T/mid.apk"; cp "$T/m.json" "$R/docs/modules/m/measures/apk_size_mb.json"
(cd "$R" && git init -q . && MODULE=m bash scripts/report.sh >/dev/null 2>&1)
grep -q 'DÉROGATION: limite 52 Mo au lieu de 40 Mo — MapLibre natif' "$R/docs/modules/m/mesures.md" || fail "mesures.md must show derogation"
finish
