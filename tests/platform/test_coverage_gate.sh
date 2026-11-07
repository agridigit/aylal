#!/usr/bin/env bash
# T024 - coverage below 80 % makes `make coverage` fail (FR-004).
source "$(dirname "$0")/lib.sh"

grep -q -- '--cov-fail-under=80' Makefile services/api/pyproject.toml || fail "pytest 80 % gate not configured"
grep -Rqs 'thresholds' packages/domain/vitest.config.* || fail "Vitest coverage thresholds not configured"

f="services/api/app/tmp_uncovered_for_gate.py"
trap 'rm -f "$ROOT/$f"' EXIT
{ echo "def uncovered(x):"; for i in $(seq 1 3000); do echo "    x = x + $i"; done; echo "    return x"; } > "$f"
out="$(make coverage 2>&1)"; rc=$?
[ $rc -ne 0 ] || fail "make coverage returned 0 with simulated coverage < 80 %"
echo "$out" | grep -Eq 'Required test coverage of 80' || fail "failure is not the 80 % coverage gate"
finish
