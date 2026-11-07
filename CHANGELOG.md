# Changelog

Tenu automatiquement par Claude (sous-agent `git-keeper`). Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [0.1.1] - 2026-11-07 — hotfix App mobile réelle et e2e Android sur émulateur macOS
### Corrections
- e2e: no host python/openssl, measures extraction never fails the run; untrack .coverage
- platform: make up applies database migrations before the API starts
- platform: API e2e tests run only through make e2e-api, after make up
- platform: one compose project per branch, shared build caches
- api: isolate integration tests in a throw-away database per session
- mobile: green - map and showcase routes, home.root, provisional emulator measures export
- mobile: valid PowerSync sync rules and e2e stack bootstrap (secret, seed) before Maestro
- mobile: green - PowerSync/SQLCipher local db, connector, trial record route, e2e stack wiring
- mobile: green - real Expo SDK 58 app, APK builds and home flow passes on emulator
### Technique
- mobile: classify schema contract test as integration; pyramid gate recognises app test layout
- build: skip APK rebuild when its inputs are unchanged
- mobile: provisional emulator measures (startup, map, fps)
- mobile: red - measure session and E2E local parcels
- mobile: red - real PowerSync adapter, connector, runtime config and app config
- mobile: add PowerSync, op-sqlite and build-properties dependencies
- hotfix: red - real mobile deps guard and Android e2e on macOS emulator

Documentation du module : [specs/001-foundations/decisions.md](specs/001-foundations/decisions.md) (section « Hotfix android-e2e »)

## [0.1.0] - 2026-11-07 — F0 Fondations : monorepo, Docker, CI, design system, i18n, synchronisation hors ligne
### Ajouts
- foundations: green - repo skeleton, shared validation, platform docker
- foundations: green - offline sync, auth hardening, design system
- foundations: green - mobile home, mobile shell, diagrams, device measures
### Corrections
- foundations: correctif sécurité (IDOR, JWT) et dev-token activé uniquement pour les cibles de test
- foundations: lint, typecheck et pyramid gate
- foundations: apk-size rapporte honnêtement « non mesuré » (limite connue : taille APK non mesurée, blocage documenté)
### Documentation
- foundations: spec, plan, tâches, décisions, quickstart, matrice de traçabilité
- 001-foundations: documentation ingénieur et agriculteur
- foundations: raison du blocage F0 (apk-size non mesuré) consignée
### Technique
- tests red de chaque lot, tests unitaires/intégration/e2e obligatoires par module
- chore(loop), chore(git): pipeline et versionnement local
- build: montage du domaine dans api-test, ignore du store pnpm

Documentation du module : [docs/modules/001-foundations/](docs/modules/001-foundations/)

