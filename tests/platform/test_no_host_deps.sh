#!/usr/bin/env bash
# T023 - the repo invokes no host tool other than docker/make (AC1.4, FR-001).
source "$(dirname "$0")/lib.sh"

banned='pnpm|npm|npx|node|yarn|python3?|pip3?|pytest|ruff|mypy|eslint|tsc|mmdc|uv|poetry|gradle|java|adb|jest|vitest'
check() { # file, regex-filter for allowed lines
  while IFS= read -r line; do
    case "$line" in *docker*|*'$(DC)'*|*compose*) continue ;; esac
    if echo "$line" | grep -Eq "(^|[;&|(]|\\$\\(|^[[:space:]]*@?)[[:space:]]*($banned)([[:space:]]|$)"; then
      fail "$1 invokes a host tool outside docker: $line"
    fi
  done < <(grep -vE '^[[:space:]]*#' "$1")
}
check Makefile
for f in scripts/*.sh; do
  # Scripts that run inside a container declare it explicitly.
  grep -q 'AYLAL_IN_CONTAINER' "$f" && continue
  check "$f"
done
# Makefile must at least cover the contract so the check above is meaningful.
grep -q 'test-visual' Makefile || fail "Makefile lacks contract targets (test-visual)"
finish
