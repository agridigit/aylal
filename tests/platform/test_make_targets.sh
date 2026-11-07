#!/usr/bin/env bash
# T020 - every target of contracts/make-targets.md exists and behaves as documented (FR-003).
source "$(dirname "$0")/lib.sh"

targets="up down test test-api test-domain test-mobile test-visual e2e lint typecheck coverage check diagrams report apk-size"
for t in $targets; do
  out="$(make -n "$t" 2>&1)" || { fail "make target '$t' missing or not runnable (make -n failed)"; continue; }
  echo "$out" | grep -Eq 'docker|bash scripts/' || fail "make target '$t' does not go through docker or a script"
done

make -n up 2>&1 | grep -q -- '--wait' || fail "make up must run 'docker compose up -d --build --wait'"
make -n up 2>&1 | grep -q -- '--build' || fail "make up must use --build"

for dep in test-api test-domain test-mobile; do
  grep -Eq "^test:.*\b$dep\b" Makefile || fail "make test must depend on $dep"
done
for dep in lint typecheck test coverage test-visual apk-size diagrams e2e; do
  grep -Eq "^check:.*(^|[ :])$dep( |$)" Makefile || fail "make check must depend on $dep"
done
grep -q 'update-visual' Makefile || fail "make update-visual missing"
grep -q 'KVM' Makefile || fail "make e2e must print an explicit message when KVM is absent"
grep -q 'E2E_SKIP' Makefile || fail "make e2e must honour E2E_SKIP=1"
grep -q 'STRICT' Makefile || fail "make report must honour STRICT=1"
finish
