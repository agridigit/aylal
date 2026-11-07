# AYLAL — toutes les commandes passent par Docker Compose
DC := docker compose
.PHONY: up down logs build test test-api test-domain test-mobile test-unit test-integration test-pyramid e2e e2e-api lint typecheck coverage check diagrams docs-index loop report clean

up:            ## démarre toute la plateforme
	$(DC) up -d --build
down:
	$(DC) down
logs:
	$(DC) logs -f --tail=100
build:
	$(DC) build

test: test-api test-domain test-mobile   ## tous les tests unitaires et d'intégration
test-api:
	$(DC) --profile test run --rm api-test
test-domain:
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test
test-mobile:
	$(DC) --profile test run --rm js-test pnpm --filter mobile test
test-unit:     ## tests unitaires seuls
	$(DC) --profile test run --rm api-test pytest -q tests/unit
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test -- tests/unit
test-integration: ## tests d'intégration seuls (dont contrats)
	$(DC) --profile test run --rm api-test pytest -q tests/integration tests/contract
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test -- tests/integration
test-pyramid:  ## chaque module a ses tests unitaires, d'intégration et de bout en bout
	bash scripts/check-test-pyramid.sh
e2e: e2e-api   ## tous les tests de bout en bout
	$(DC) --profile e2e run --rm e2e
e2e-api:
	$(DC) --profile test run --rm api-test pytest -q tests/e2e
lint:
	$(DC) --profile test run --rm js-test pnpm -r lint
	$(DC) --profile test run --rm api-test ruff check .
typecheck:
	$(DC) --profile test run --rm js-test pnpm -r typecheck
	$(DC) --profile test run --rm api-test mypy app
coverage:
	$(DC) --profile test run --rm api-test pytest --cov=app --cov-fail-under=80
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test -- --coverage
check: test-pyramid lint typecheck test coverage diagrams   ## porte de qualité utilisée par la boucle

diagrams:      ## rend docs/**/diagrams/*.mmd en SVG + PNG
	bash scripts/render-diagrams.sh
docs-index:
	bash scripts/docs-index.sh

loop:          ## boucle Spec Kit autonome sur toutes les fonctionnalités
	bash scripts/speckit-loop.sh
report:
	bash scripts/report.sh
clean:
	$(DC) down -v --remove-orphans
