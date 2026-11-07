#!/usr/bin/env bash
# T095 - a standard module (8 diagrams) renders SVG+PNG in under 2 minutes (SC-010).
source "$(dirname "$0")/lib.sh"
need_dockerfile
mkmod duration; valid_fixtures
for i in 1 2 3 4; do printf 'flowchart LR\n  A%s --> B%s\n' $i $i > "$MOD/diagrams/extra$i.mmd"; done
start=$(date +%s)
make diagrams >/dev/null 2>&1 || fail "make diagrams failed"
el=$(( $(date +%s) - start ))
[ "$el" -lt 120 ] || fail "rendering took ${el}s (>= 120s)"
[ "$(find "$MOD/img" -type f | wc -l | tr -d ' ')" -eq 16 ] || fail "expected 16 images"
finish
