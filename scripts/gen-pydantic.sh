#!/usr/bin/env bash
# Zod -> JSON Schema -> Pydantic, entirely through Docker.
set -euo pipefail
cd "$(dirname "$0")/.."
bash "$(git rev-parse --show-toplevel)/scripts/dc.sh" --profile test run --rm js-test sh -c "pnpm install --frozen-lockfile=false >/dev/null && pnpm --filter @aylal/domain export-schema"
rm -rf services/api/app/generated/schema
mkdir -p services/api/app/generated/schema
cp packages/domain/schema/*.json services/api/app/generated/schema/
bash "$(git rev-parse --show-toplevel)/scripts/dc.sh" --profile test run --rm api-test python -m app.generated.check_fresh --write
