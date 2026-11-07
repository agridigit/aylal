#!/usr/bin/env bash
# Shared helpers for diagram tests. Each test uses its own throwaway module under docs/modules/.
source "$(dirname "${BASH_SOURCE[0]}")/../platform/lib.sh"
# usage: mkmod <name>  -> sets MOD (module dir), cleans it on exit
mkmod() { MOD="docs/modules/999-tmp-$1"; rm -rf "$ROOT/$MOD"; mkdir -p "$ROOT/$MOD/diagrams"; trap 'rm -rf "$ROOT/$MOD"' EXIT; }
valid_fixtures() {
  printf 'flowchart TD\n  A[Start] --> B[End]\n' > "$MOD/diagrams/flow.mmd"
  printf 'sequenceDiagram\n  A->>B: hello\n' > "$MOD/diagrams/seq.mmd"
  printf 'erDiagram\n  FARM ||--o{ PLOT : has\n' > "$MOD/diagrams/er.mmd"
  printf 'stateDiagram-v2\n  [*] --> Idle\n  Idle --> Busy\n' > "$MOD/diagrams/state.mmd"
}
need_dockerfile() { [ -f infra/docker/mermaid.Dockerfile ] || fail "infra/docker/mermaid.Dockerfile missing"; }
