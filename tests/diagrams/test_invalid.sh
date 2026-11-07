#!/usr/bin/env bash
# T093 - an invalid .mmd makes `make diagrams` fail and name the faulty file (AC5.2).
source "$(dirname "$0")/lib.sh"
need_dockerfile
mkmod invalid; valid_fixtures
printf 'flowchart TD\n  A --> [[[ broken(((\n' > "$MOD/diagrams/broken_diagram.mmd"
out="$(make diagrams 2>&1)"; rc=$?
[ $rc -ne 0 ] || fail "make diagrams returned 0 despite an invalid diagram"
echo "$out" | grep -q "$MOD/diagrams/broken_diagram.mmd" || fail "output does not name the faulty file path"
finish
