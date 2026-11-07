#!/usr/bin/env bash
# T022 - a deliberately failing test makes `make test` exit != 0 and its name appears in the output (AC1.3).
source "$(dirname "$0")/lib.sh"

tmp="services/api/tests/tmp_deliberate_failure"
mkdir -p "$tmp"
trap 'rm -rf "$ROOT/$tmp"' EXIT
cat > "$tmp/test_deliberate_failure_marker.py" <<'PY'
def test_deliberate_failure_marker_xyz():
    assert False, "deliberate failure"
PY
out="$(make test 2>&1)"; rc=$?
[ $rc -ne 0 ] || fail "make test returned 0 despite a failing test"
echo "$out" | grep -q 'test_deliberate_failure_marker_xyz' || fail "failing test name not present in make test output"
echo "$out" | grep -Eq 'FAILED|failed' || fail "make test output does not say FAILED"
finish
