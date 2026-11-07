# Changelog

Tenu automatiquement par Claude (sous-agent `git-keeper`). Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

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

