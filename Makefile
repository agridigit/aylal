# AYLAL — toutes les commandes passent par Docker Compose (contrat : specs/001-foundations/contracts/make-targets.md)
DC := bash scripts/dc.sh
# ex. make test-api ARGS=tests/unit/test_x.py — cibler un fichier pendant une tâche
ARGS ?=
# Maestro est téléchargé à la construction de l'image e2e uniquement (jamais un défaut d'exécution).
# Outils en ligne de commande Android, téléchargés à la construction de l'image android-build uniquement.
export ANDROID_CMDLINE_URL ?= https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip
export MAESTRO_URL ?= https://github.com/mobile-dev-inc/maestro/releases/latest/download/maestro.zip
.PHONY: up down logs build apk e2e-mobile test-deps check-cached e2e-cached test test-api test-domain test-mobile test-visual update-visual test-unit test-integration test-pyramid e2e e2e-api lint typecheck coverage apk-size check diagrams docs-index loop report clean

up:            ## démarre toute la plateforme et attend que tout soit sain
	@$(DC) up -d --build --wait || { echo "make up: service non sain :" >&2; $(DC) ps -a --format '{{.Service}} {{.State}} {{.Health}}' | grep -v 'running healthy' | grep -v 'exited' >&2; $(DC) ps -a --format '{{.Service}} {{.State}} {{.Health}}' | grep 'exited' | grep -v ' 0$$' >&2; exit 1; }
down:
	$(DC) down
logs:
	$(DC) logs -f --tail=100
build:
	$(DC) build

test: test-api test-domain test-mobile   ## tous les tests unitaires et d'intégration
# l'e2e passe par le proxy vers l'API de la pile : route dev-token activée pour les tests uniquement (env dev/test)
test test-api e2e-api coverage test-integration check: export AYLAL_ENABLE_DEV_TOKEN=1
test-api:
	$(DC) --profile test run --rm api-test pytest -q --ignore=tests/e2e $(ARGS)
	$(DC) run --rm --no-deps worker pytest -q
test-domain:
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test -- $(ARGS)
test-mobile:
	$(DC) --profile test run --rm js-test pnpm --filter mobile test
test-visual:   ## captures Storybook 3 thèmes x 2 sens contre les références
	$(DC) --profile visual run --rm visual
update-visual: ## régénère les références (revue obligatoire)
	$(DC) --profile visual run --rm visual pnpm --filter @aylal/ui test:visual --update-snapshots catalog.spec.ts
test-unit:     ## tests unitaires seuls
	$(DC) --profile test run --rm api-test pytest -q -n auto tests/unit $(ARGS)
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test -- tests/unit --passWithNoTests
test-integration: ## tests d'intégration seuls (dont contrats)
	$(DC) --profile test run --rm api-test pytest -q tests/integration tests/contract /repo/tests/contract
	$(DC) --profile test run --rm js-test pnpm -r --filter "./packages/**" test -- tests/integration --passWithNoTests
	$(DC) --profile test run --rm js-test pnpm --filter mobile test -- __tests__/integration
test-pyramid:  ## chaque module a ses tests unitaires, d'intégration et de bout en bout
	bash scripts/check-test-pyramid.sh
e2e: e2e-api   ## bout en bout : API + mobile (Maestro sur émulateur ; macOS : émulateur natif, voir scripts/e2e-mobile.sh)
	bash scripts/e2e-mobile.sh
e2e-mobile:    ## bout en bout mobile seul
	bash scripts/e2e-mobile.sh
apk:           ## construit l'APK release arm64 dans Docker -> apps/mobile/dist/app-release.apk
	bash scripts/build-apk.sh
test-deps:     ## refuse une app « façade » : dépendances réelles déclarées, aucun stub natif
	$(DC) --profile test run --rm --no-deps js-test node scripts/check-real-deps.mjs
e2e-api: export AYLAL_ENV=test
e2e-api: export AYLAL_ENABLE_TEST_OTP=1
e2e-api:
	$(MAKE) up
	$(DC) --profile test run --rm api-test pytest -q tests/e2e
lint:
	$(DC) --profile test run --rm js-test pnpm -r lint
	$(DC) --profile test run --rm api-test ruff check .
typecheck:
	$(DC) --profile test run --rm js-test pnpm -r typecheck
	$(DC) --profile test run --rm api-test mypy app
coverage:      ## seuil 80 % pytest et Vitest
	$(DC) --profile test run --rm api-test pytest --ignore=tests/e2e --cov=app --cov-fail-under=80
	$(DC) --profile test run --rm js-test pnpm -r --filter @aylal/domain test -- --coverage
apk-size:      ## APK release <= 40 Mo
	bash scripts/check-apk-size.sh
check: test-deps test-pyramid lint typecheck test coverage test-visual apk-size diagrams e2e   ## porte de qualité utilisée par la boucle
check-cached:  ## make check, sauté si déjà vert sur le même commit (docs seules -> diagrams)
	bash scripts/cached-gate.sh check check diagrams
e2e-cached:    ## make e2e, sauté si déjà vert sur le même code
	bash scripts/cached-gate.sh e2e e2e

diagrams:      ## rend docs/**/diagrams/*.mmd en SVG + PNG
	bash scripts/render-diagrams.sh
docs-index:
	bash scripts/docs-index.sh

loop:          ## boucle Spec Kit autonome sur toutes les fonctionnalités
	bash scripts/speckit-loop.sh
report:        ## STRICT=1 : échec si un seuil est non tenu
	STRICT=$(STRICT) bash scripts/report.sh
clean:
	$(DC) down -v --remove-orphans
