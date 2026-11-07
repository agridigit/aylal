#!/usr/bin/env bash
# T094 - a second run is identical: same checksums and "0 fichier rendu" (AC5.3).
source "$(dirname "$0")/lib.sh"
need_dockerfile
mkmod repro; valid_fixtures
make diagrams >/dev/null 2>&1 || fail "first make diagrams failed"
sum1="$(find "$MOD/img" -type f | sort | xargs shasum 2>/dev/null)"
[ -n "$sum1" ] || fail "no images produced on first run"
out="$(make diagrams 2>&1)"; rc=$?
[ $rc -eq 0 ] || fail "second make diagrams failed"
echo "$out" | grep -q '0 fichier rendu' || fail "second run did not report '0 fichier rendu'"
sum2="$(find "$MOD/img" -type f | sort | xargs shasum 2>/dev/null)"
[ "$sum1" = "$sum2" ] || fail "checksums differ between runs"
finish
