# Décisions : 001-foundations

## Récit 3 (RED) : choix de test
- Refus d'accès à l'envoi : le contrat `/sync/upload` ne définit pas de 403 ; un refus est donc un résultat par opération (`status: rejected`, `error.code: forbidden`), HTTP 200. Le 403/404 HTTP ne s'applique qu'à `/sync/conflicts/{id}/acknowledge`.
- Seuil de stockage faible (`LOW_STORAGE_BYTES`) : valeur choisie au GREEN dans `storageWarning.ts`, les tests la lisent via l'export.
- Les tests d'intégration serveur montent le dépôt en lecture seule sur `/repo` dans `api-test` (contrats, `infra/powersync`) et dépendent du service `proxy` (TLS).
- Maestro (T049) et Jest mobile (T044-T048) ne peuvent pas tourner tant que `apps/mobile` n'existe pas (T057) ; l'échec RED est l'absence du module.

## Phase 6 RED : écarts de forme des tests mobiles
- Les tests Jest `Home.*` sont écrits en `.test.ts` (et non `.tsx`) : `apps/mobile/jest.config.js` n'exécute que `*.test.ts` en environnement node, sans bibliothèque de rendu React Native. Les règles (RTL, états, zones tactiles, clés i18n) sont testées via des modèles de vue purs et une analyse statique des sources `.tsx`. Le GREEN doit mapper `@aylal/i18n` dans `moduleNameMapper`.
- Intégration de l'accueil : complétude des locales contre les clés réellement utilisées (Home, TrialRecord). E2E : Maestro (T084), exécutable seulement sur émulateur.
