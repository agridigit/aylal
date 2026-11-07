#!/usr/bin/env bash
# T092 - flowchart, sequenceDiagram, erDiagram, stateDiagram-v2 each yield an SVG and a PNG in img/ (AC5.1, FR-025).
source "$(dirname "$0")/lib.sh"
need_dockerfile
mkmod render; valid_fixtures
out="$(make diagrams 2>&1)"; rc=$?
[ $rc -eq 0 ] || fail "make diagrams failed on valid diagrams: $out"
for n in flow seq er state; do
  [ -s "$MOD/img/$n.svg" ] || fail "missing $MOD/img/$n.svg"
  [ -s "$MOD/img/$n.png" ] || fail "missing $MOD/img/$n.png"
done
head -c 4 "$MOD/img/flow.png" 2>/dev/null | LC_ALL=C grep -aq PNG || fail "flow.png is not a PNG"
LC_ALL=C grep -aq '<svg' "$MOD/img/flow.svg" 2>/dev/null || fail "flow.svg is not an SVG"
finish
