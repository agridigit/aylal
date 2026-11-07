#!/usr/bin/env bash
# T102 - `make report` aggregates measure JSON into mesures.md with a verdict per threshold (AC6.4, SC-011).
source "$(dirname "$0")/../platform/lib.sh"
MODNAME="999-tmp-report"; MOD="docs/modules/$MODNAME"
rm -rf "$ROOT/$MOD"; mkdir -p "$ROOT/$MOD/measures"; trap 'rm -rf "$ROOT/$MOD"' EXIT
mj() { printf '{"metric":"%s","value":%s,"unit":"%s","threshold":%s,"device":"android-2gb","date":"2026-11-07","verdict":"%s","build":"b1"}\n' "$1" "$2" "$3" "$4" "$5" > "$MOD/measures/$1.json"; }
mj startup_ms 2500 ms 3000 met
mj map_open_ms 1800 ms 2000 met
mj fps 60 fps 60 met
mj apk_size_mb 38 MB 40 met
mj daily_traffic_mb 4 MB 5 met

MODULE=$MODNAME STRICT=1 make report >/dev/null 2>&1; rc=$?
[ $rc -eq 0 ] || fail "STRICT=1 failed although every threshold is met"
out="$MOD/mesures.md"
[ -f "$out" ] || fail "$out not generated"
for m in startup_ms map_open_ms fps apk_size_mb daily_traffic_mb; do grep -q "$m" "$out" 2>/dev/null || fail "metric $m missing from mesures.md"; done
[ "$(grep -ci 'non tenu' "$out" 2>/dev/null)" = "0" ] || fail "unexpected 'non tenu'"
grep -qi 'tenu' "$out" 2>/dev/null || fail "no 'tenu' verdict"

mj startup_ms 3500 ms 3000 not_met
MODULE=$MODNAME make report >/dev/null 2>&1 || fail "non-strict report must succeed with a non tenu"
grep -qi 'non tenu' "$out" 2>/dev/null || fail "'non tenu' verdict missing"
grep -qi 'réexamen' "$out" 2>/dev/null || fail "non tenu must mention the technical re-examination"
MODULE=$MODNAME STRICT=1 make report >/dev/null 2>&1 && fail "STRICT=1 must fail on non tenu"
finish
