#!/usr/bin/env bash
# Shared helpers for platform contract tests (run from repo root, host needs only bash, make, docker).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 2
FAILS=0
fail() { echo "FAIL: $*" >&2; FAILS=$((FAILS + 1)); }
finish() { if [ "$FAILS" -gt 0 ]; then echo "$FAILS assertion(s) failed" >&2; exit 1; fi; echo "OK"; }
