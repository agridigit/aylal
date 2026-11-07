# Tâches : F0 — Fondations techniques d'AYLAL

**Branche** : `001-foundations` | **Entrées** : [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [research.md](research.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

## Règles d'exécution

- **Test first strict** (constitution VIII/XI, CLAUDE.md) : dans chaque récit, les tâches de test (contrat, unitaires, intégration, E2E) viennent AVANT l'implémentation. Une tâche de test cite le critère couvert (`AC<récit>.<n>` = scénario d'acceptation de la spec, `FR-xxx`, `SC-xxx`).
- Cycle par récit : RED (tests écrits et lancés, ils DOIVENT échouer, commit `test(foundations): red - <sujet>`) -> GREEN (minimum de code, commit `feat(foundations): green - <sujet>`) -> REFACTOR (commit `refactor(foundations): ...`). Interdit de modifier un test pour le faire passer (sauf contradiction avec la spec, notée dans `specs/001-foundations/decisions.md`).
- Tout s'exécute dans Docker (`make ...` ou `docker compose ...`) ; rien n'est installé sur l'hôte ; toute dépendance va dans le Dockerfile concerné.
- `[P]` = fichiers différents et aucune dépendance vis-à-vis d'une tâche non terminée. `[USn]` = récit n de la spec.
- Récits P1 : US1, US2, US3, US4. Récits P2 : US5, US6. Aucun récit P3 (voir « Reportés »). Ordre des P1 par dépendance : US1 -> US3 -> US4 -> US2.
- Les noms de services et les cibles `make` sont ceux de [contracts/make-targets.md](contracts/make-targets.md) ; ne pas renommer l'existant.

## Phase 1 : Socle du dépôt (sans récit)

- [x] T001 Créer le monorepo pnpm : `package.json`, `pnpm-workspace.yaml`, `tsconfig.base.json` (TypeScript strict), `.dockerignore`, `.gitignore` complété à la racine
- [x] T002 [P] Créer les squelettes d'espaces `apps/web/{README.md,package.json}` et `apps/desktop/{README.md,package.json}` (FR-005)
- [x] T003 [P] Créer `.env.example` et `.env.test` (secrets factices, aucun domaine externe, `scram-sha-256`) à la racine
- [x] T004 [P] Créer `infra/docker/js.Dockerfile` (Node + pnpm, lockfile figé) pour domain, i18n, ui, mobile (Jest), Storybook
- [x] T005 [P] Créer `services/api/Dockerfile` et `services/api/pyproject.toml` (Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, pytest-cov, Ruff, mypy)
- [x] T006 [P] Créer `services/workers/Dockerfile` et `services/workers/pyproject.toml` (Python 3.13, Arq, pytest)
- [x] T007 [P] Créer `infra/docker/e2e.Dockerfile`, `infra/docker/android-build.Dockerfile`, `infra/docker/visual.Dockerfile` (Playwright), `infra/caddy/Caddyfile` (TLS interne), `infra/minio/init.sh`, `infra/powersync/config.yaml`

## Phase 2 : Fondations bloquantes (sans récit)

**Bloque tous les récits.** Contient la validation partagée (FR-016, AC3.5) car API, mobile et domaine en dépendent.

### Tests d'abord (RED)

- [ ] T008 [P] Écrire les vecteurs partagés `packages/domain/vectors/trial_record.json` et `packages/domain/vectors/parcel.json` (title 1..120 après trim, quantity >= 0 et <= 1 000 000, note <= 2000, vigor dans [0,1], geometry polygone fermé valide ; cas valides et invalides) (AC3.5, FR-016)
- [ ] T009 [P] Écrire le test Vitest `packages/domain/tests/validation.test.ts` qui joue tous les vecteurs de T008 contre les schémas Zod (AC3.5)
- [ ] T010 [P] Écrire le test Vitest `packages/domain/tests/conflict.test.ts` : résolution champ par champ par ordre d'arrivée serveur, indépendante de l'horloge appareil, valeur écartée journalisée (AC3.4, cas limite horloge décalée, R6)
- [ ] T011 [P] Écrire le test pytest `services/api/tests/unit/test_shared_validation.py` qui joue les mêmes vecteurs (T008) contre les modèles Pydantic générés et vérifie l'identité des verdicts avec TS (AC3.5)
- [ ] T012 [P] Écrire le test de contrat `services/api/tests/contract/test_generated_schema_fresh.py` : les JSON Schema et modèles dans `services/api/app/generated/` correspondent à la sortie de l'export Zod (échec si périmés) (FR-016)
- [ ] T013 Lancer `docker compose run --rm js-test` et `api-test` : T009 à T012 DOIVENT échouer ; commit `test(foundations): red - shared validation`

### Implémentation (GREEN)

- [x] T014 Créer `packages/domain/package.json`, `packages/domain/tsconfig.json`, `packages/domain/vitest.config.ts` (seuil de couverture 80 % bloquant)
- [x] T015 [P] Implémenter les schémas Zod dans `packages/domain/src/schemas/trial_record.ts`, `parcel.ts`, `farm.ts` avec les contraintes de data-model.md citées : « title obligatoire après trim, 1..120 », « note <= 2000 », « quantity >= 0, <= 1 000 000 », « vigor dans [0,1] », « geometry polygone fermé valide »
- [x] T016 [P] Implémenter la résolution de conflits pure dans `packages/domain/src/conflict.ts` (champ par champ, ordre d'arrivée serveur, `field_versions`, jamais `updated_at`)
- [x] T017 Implémenter l'export JSON Schema `packages/domain/src/export-json-schema.ts` et le script `scripts/gen-pydantic.sh` générant `services/api/app/generated/*.py` (via conteneur)
- [x] T018 Implémenter l'enveloppe de validation Python `services/api/app/domain/validation.py` utilisant les modèles générés
- [x] T019 Commit `feat(foundations): green - shared validation` ; REFACTOR éventuel `refactor(foundations): shared validation`

**Point de contrôle** : validation partagée verte en TS et Python.

## Phase 3 : Récit 1 — Plateforme et tests dans Docker (P1)

**Objectif** : `make up` puis `make check` sur machine avec Docker seul. **Test indépendant** : voir spec Récit 1.

### Tests d'abord (RED)

- [x] T020 [P] [US1] Test de contrat `tests/platform/test_make_targets.sh` : vérifie l'existence et le comportement documenté de chaque cible de [contracts/make-targets.md](contracts/make-targets.md) (`up`, `down`, `test`, `test-api`, `test-domain`, `test-mobile`, `test-visual`, `e2e`, `lint`, `typecheck`, `coverage`, `check`, `diagrams`, `report`, `apk-size`) (FR-003)
- [x] T021 [P] [US1] Test d'intégration `tests/platform/test_services_healthy.sh` : après `make up`, les services `db`, `redis`, `minio`, `powersync`, `api`, `worker`, `proxy` sont `healthy` ; sinon le service non sain est nommé (AC1.1, FR-002)
- [x] T022 [P] [US1] Test d'intégration `tests/platform/test_failing_test_named.sh` : un test volontairement en échec dans un répertoire temporaire fait retourner un code != 0 à `make test` et son nom figure dans la sortie (AC1.3)
- [x] T023 [P] [US1] Test `tests/platform/test_no_host_deps.sh` : le dépôt n'invoque aucun outil hôte hors `docker`/`make` (analyse des cibles du `Makefile` et des scripts) (AC1.4, FR-001)
- [x] T024 [P] [US1] Test `tests/platform/test_coverage_gate.sh` : une couverture simulée < 80 % fait échouer `make coverage` (FR-004)
- [x] T025 [P] [US1] Test pytest `services/api/tests/contract/test_health_contract.py` : `GET /v1/health` conforme à `contracts/openapi.yaml` (AC1.1)
- [x] T026 [P] [US1] Test pytest `services/workers/tests/test_health_task.py` : la tâche de santé Arq répond (AC1.1)
- [x] T027 [P] [US1] Test `tests/platform/test_no_foreign_defaults.sh` : échec si un domaine ou service externe hors Maroc (Firebase, EAS, CDN de polices) est configuré par défaut (FR-019, R17)
- [x] T028 [US1] Lancer ces tests : ils DOIVENT échouer ; commit `test(foundations): red - platform`

### Implémentation (GREEN)

- [x] T029 [US1] Compléter `docker-compose.yml` : services `db` (PostgreSQL 16 + PostGIS, `wal_level=logical`, `scram-sha-256`), `redis`, `minio`, `minio-init`, `powersync`, `api`, `worker`, `proxy`, `storybook`, profils `test` (`api-test`, `js-test`, `visual`) et `e2e`, chacun avec `healthcheck` et `depends_on: condition: service_healthy` (AC1.1, FR-002)
- [x] T030 [P] [US1] Implémenter `services/api/app/main.py`, `services/api/app/config.py`, `services/api/app/routers/health.py` (`/v1/health`, schéma de openapi.yaml)
- [x] T031 [P] [US1] Implémenter `services/workers/worker.py` et la tâche de santé
- [x] T032 [US1] Compléter `Makefile` : cibles de make-targets.md, `make up` = `docker compose up -d --build --wait` nommant le service non sain, `make test` = `test-api` + `test-domain` + `test-mobile` nommant le test fautif, `make check` (lint, typecheck, test, coverage, test-visual, apk-size, diagrams, e2e), message explicite si KVM absent sauf `E2E_SKIP=1` (AC1.2, AC1.3, R9)
- [x] T033 [P] [US1] Implémenter `scripts/check-apk-size.sh` (seuil 40 Mo, R18) et brancher `make apk-size`
- [x] T034 [P] [US1] Configurer Ruff/mypy dans `services/api/pyproject.toml`, ESLint dans `eslint.config.js` racine, seuil `--cov-fail-under=80` pytest et seuils Vitest (FR-004)
- [ ] T035 [US1] Commit `feat(foundations): green - platform` ; REFACTOR `refactor(foundations): platform`

**Point de contrôle** : `make up` sain, `make test` nomme un test en échec.

## Phase 4 : Récit 3 — Synchronisation hors ligne sans perte (P1)

**Objectif** : donnée créée hors ligne, envoyée sans perte ni doublon, conflits sans perte silencieuse, chiffrement. **Test indépendant** : voir spec Récit 3.

### Tests d'abord (RED)

- [x] T036 [P] [US3] Test de contrat `services/api/tests/contract/test_openapi_sync.py` : jeton d'essai et envoi de synchronisation conformes à `contracts/openapi.yaml` (AC3.2)
- [x] T037 [P] [US3] Test de contrat `tests/contract/test_powersync_rules.py` : `infra/powersync/sync-rules.yaml` identique à `contracts/powersync-sync-rules.yaml` et filtre par ferme/membre (AC3.2, FR-018)
- [x] T038 [P] [US3] Test pytest `services/api/tests/integration/test_acl.py` : refus 403 hors ferme ; `viewer` ne peut pas écrire ; `editor`/`owner` peuvent ; `farm_members` en lecture seule (FR-018, R8)
- [x] T039 [P] [US3] Test pytest `services/api/tests/integration/test_idempotency.py` : un `op_id` rejoué renvoie le résultat enregistré dans `applied_ops` sans réappliquer ; coupure en plein envoi sans doublon (cas limite, AC3.2) [FR-013]
- [x] T040 [P] [US3] Test pytest `services/api/tests/integration/test_conflicts.py` : même champ modifié par deux appareils -> règle d'ordre d'arrivée, ligne dans `sync_conflicts` (`discarded_value`, `kept_value`, `base_version`, `server_version`), `has_conflict = true` jusqu'à acquittement ; horloge décalée sans effet (AC3.4) [FR-015]
- [x] T040a [P] [US3] Test pytest `services/api/tests/integration/test_acl_conflict_ack.py` : `POST /v1/sync/conflicts/{id}/acknowledge` par un membre `editor`/`owner` de la ferme du conflit -> 204 ; par un utilisateur d'une AUTRE ferme (ou non membre) -> 404 (jamais 403, corps identique à un id inexistant) ; `viewer` de la bonne ferme -> 403 ; sans jeton -> 401 ; le conflit reste non acquitté après un refus (FR-018, sécurité inter-ferme)
- [x] T041 [P] [US3] Test pytest `services/api/tests/integration/test_validation_server.py` : rejet par le serveur des entrées que les vecteurs T008 déclarent invalides (AC3.5)
- [x] T042 [P] [US3] Test pytest `services/api/tests/integration/test_offline_30_days.py` : 1 000 enregistrements créés et modifiés sur 30 jours simulés, reconnexion, 0 perte, 0 doublon (AC3.3, SC-005) [FR-012]
- [x] T043 [P] [US3] Test pytest `services/api/tests/integration/test_encryption.py` : `scram-sha-256` actif, accès TLS via `proxy`, refus du clair (AC3.6, FR-017)
- [x] T044 [P] [US3] Test Jest `apps/mobile/src/sync/__tests__/localStore.test.ts` : saisie sans réseau enregistrée localement, état `pending` dérivé de `ps_crud` (AC3.1, FR-014)
- [x] T045 [P] [US3] Test Jest `apps/mobile/src/sync/__tests__/syncState.test.ts` : transitions `pending -> synced`, `pending -> conflict`, `conflict -> synced`, `synced -> pending` ; « non envoyé » visible tant que non acquitté (AC3.2, cas limite changement de téléphone)
- [x] T046 [P] [US3] Test Jest `apps/mobile/src/sync/__tests__/encryptionKey.test.ts` : clé SQLCipher aléatoire au premier lancement stockée dans le stockage sécurisé, base ouverte chiffrée (AC3.6, R7)
- [x] T047 [P] [US3] Test Jest `apps/mobile/src/sync/__tests__/storageWarning.test.ts` : avertissement avant perte de saisie si stockage presque plein (cas limite)
- [x] T048 [P] [US3] Test Jest `apps/mobile/src/telemetry/__tests__/telemetry.test.ts` : télémétrie anonyme (`install_id` aléatoire, sans donnée personnelle) et désactivable (FR-020)
- [x] T049 [P] [US3] Test E2E Maestro `apps/mobile/maestro/offline_sync.yaml` : mode avion -> saisie -> « non envoyé » -> retour réseau -> indicateur disparu (AC3.1, AC3.2)
- [x] T050 [US3] Lancer pytest et Jest : T036 à T048 et T040a DOIVENT échouer ; commit `test(foundations): red - offline sync`

### Implémentation (GREEN)

- [x] T051 [US3] Créer les modèles SQLAlchemy `services/api/app/db/models.py` (farms, farm_members, parcels, trial_records avec `server_version`, `field_versions`, `has_conflict`, `deleted_at`, applied_ops, sync_conflicts) selon data-model.md
- [x] T052 [US3] Créer la migration `services/api/alembic/versions/0001_initial.py` (PostGIS, index GiST sur `parcels.geometry`, publication logique pour PowerSync)
- [x] T053 [P] [US3] Implémenter `services/api/app/auth/` : jeton d'essai et contrôle ferme/rôle (`owner`/`editor`/`viewer`) (FR-018)
- [x] T054 [US3] Implémenter `services/api/app/sync/apply.py` (envoi idempotent via `applied_ops`, validation partagée, résolution de `packages/domain` répliquée selon R6, écriture `sync_conflicts`) et `services/api/app/routers/sync.py` (dont `POST /sync/conflicts/{id}/acknowledge` : résolution du conflit vers `sync_conflicts.farm_id`, contrôle membre `editor`/`owner` de cette ferme, 404 si autre ferme, fait passer T040a)
- [x] T055 [P] [US3] Créer `infra/powersync/sync-rules.yaml` (copie conforme du contrat) et brancher `powersync` dans `docker-compose.yml`
- [x] T056 [P] [US3] Implémenter la graine déterministe `services/api/app/db/seed.py` (compte d'essai, 1 ferme, 50 parcelles)
- [x] T057 [US3] Créer le shell mobile `apps/mobile/{package.json,app.json,babel.config.js,jest.config.js}` et `apps/mobile/src/sync/{db.ts,connector.ts,syncState.ts,encryptionKey.ts,storageWarning.ts}` (PowerSync + SQLCipher, expo-secure-store)
- [x] T058 [P] [US3] Implémenter `apps/mobile/src/telemetry/telemetry.ts` (anonyme, désactivable, `telemetry_enabled`)
- [x] T059 [P] [US3] Implémenter l'écran de saisie d'essai `apps/mobile/src/screens/TrialRecord/` avec indicateur « non envoyé » (clés i18n uniquement, composants de `packages/ui` une fois US4 disponible, voir Dépendances)
- [x] T060 [US3] Commit `feat(foundations): green - offline sync` ; REFACTOR `refactor(foundations): offline sync`

**Point de contrôle** : 1 000 enregistrements / 30 jours : 0 perte, 0 doublon.

## Phase 5 : Récit 4 — Design system et catalogue (P1)

**Objectif** : jetons 3 thèmes, composants de base (~12), Storybook, captures de référence. **Test indépendant** : voir spec Récit 4.

### Tests d'abord (RED)

- [ ] T061 [P] [US4] Test de contrat Vitest `packages/ui/tests/tokens.schema.test.ts` : les jetons de chaque thème (clair, sombre, plein soleil) valident `contracts/design-tokens.schema.json` ; espacements multiples de 4 px ; polices IBM Plex Sans / IBM Plex Sans Arabic (AC4.1, FR-021)
- [ ] T062 [P] [US4] Test Vitest `packages/ui/tests/contrast.test.ts` : contraste texte/fond >= 7:1 pour le texte courant du thème plein soleil (AC4.2)
- [ ] T063 [P] [US4] Test Vitest `packages/ui/tests/motion.test.ts` : durées de transition 200 à 300 ms ; supprimées ou réduites si « réduire les animations » est actif (AC4.6, FR-024)
- [ ] T064 [P] [US4] Test Vitest `packages/ui/tests/stories-coverage.test.ts` : chaque composant exporté a une story par variante et par état (défaut, actif, désactivé, chargement, erreur) (AC4.3, FR-022)
- [ ] T065 [P] [US4] Test Vitest `packages/ui/tests/touch-target.test.ts` : tout composant interactif a une zone tactile >= 48 dp (AC2.5, FR-010)
- [ ] T066 [P] [US4] Test Playwright `packages/ui/visual/catalog.spec.ts` : captures Storybook 3 thèmes x 2 sens (LTR/RTL) de chaque composant contre `packages/ui/visual/__screenshots__/` ; une modification involontaire est détectée (AC4.1, AC4.4, AC4.5, SC-007) [FR-023]
- [ ] T067 [P] [US4] Test Playwright `packages/ui/visual/regression-detect.spec.ts` : une altération volontaire d'un composant fait échouer `make test-visual` (AC4.5)
- [ ] T068 [P] [US4] Test Vitest `packages/ui/tests/long-text.test.ts` : texte long (fr) et court (ar) sans débordement ni troncature illisible (cas limite)
- [ ] T069 [US4] Lancer : T061 à T068 DOIVENT échouer ; commit `test(foundations): red - design system`

### Implémentation (GREEN)

- [x] T070 [US4] Créer `packages/ui/package.json` et `packages/ui/src/tokens/{light,dark,sun}.ts`, `index.ts` (couleurs, typographie, espacement grille 4 px, rayons, ombres, états, mouvement), polices Plex en sous-ensemble embarquées localement (R10, R18)
- [x] T071 [P] [US4] Implémenter `packages/ui/src/motion.ts` (200-300 ms, réduction système)
- [x] T072 [P] [US4] Implémenter les composants de base dans `packages/ui/src/components/` : `Button`, `Text`, `Icon`, `TextField`, `Card`, `Skeleton`, `EmptyState`, `ErrorState`, `OfflineBanner`, `SyncBadge`, `Switch`, `ListItem` (variantes, états, RTL, zone tactile 48 dp)
- [x] T073 [US4] Écrire les stories `packages/ui/src/components/*.stories.tsx` et configurer Storybook `packages/ui/.storybook/` (barre d'outils thème et sens, react-native-web), service `storybook`
- [x] T074 [P] [US4] Configurer Playwright dans `infra/docker/visual.Dockerfile` et `packages/ui/visual/playwright.config.ts` ; cibles `make test-visual` / `make update-visual`
- [x] T075 [US4] Générer les références initiales (`make update-visual`) et les relire ; commit `feat(foundations): green - design system` ; REFACTOR `refactor(foundations): design system`

**Point de contrôle** : catalogue complet, captures de référence versionnées.

## Phase 6 : Récit 2 — App mobile : accueil trilingue RTL à 4 états (P1)

**Objectif** : écran d'accueil < 3 s, 3 langues (+ graphie latine), miroir RTL, 4 états, lecture vocale. **Test indépendant** : voir spec Récit 2.

### Tests d'abord (RED)

- [x] T076 [P] [US2] Test Vitest `packages/i18n/tests/completeness.test.ts` : toutes les clés présentes en `ary`, `ary-Latn`, `ar`, `fr`, aucune valeur vide ; échec nommant la clé manquante (AC2.2, SC-004, cas limite clé manquante)
- [x] T077 [P] [US2] Test Vitest `packages/i18n/tests/fallback.test.ts` : langue d'appareil non prise en charge -> repli `fr` ; changement de langue à tout moment (cas limite, FR-007)
- [x] T078 [P] [US2] Test Jest `apps/mobile/src/screens/Home/__tests__/Home.i18n.test.tsx` : tous les textes de l'accueil dans chaque langue, aucun texte en dur (analyse de chaînes littérales), aucune clé manquante (AC2.2)
- [x] T079 [P] [US2] Test Jest `apps/mobile/src/screens/Home/__tests__/Home.rtl.test.tsx` : `ar` et `ary` en graphie arabe -> `I18nManager.isRTL`, direction de lecture, icônes directionnelles et alignements en miroir ; `ary-Latn` et `fr` en LTR (AC2.3, FR-008)
- [x] T080 [P] [US2] Test Jest `apps/mobile/src/screens/Home/__tests__/Home.states.test.tsx` : états chargement (squelette), vide (illustration + action), erreur (message + solution), hors ligne (indicateur) ; jamais d'écran vide (AC2.4, FR-009)
- [x] T081 [P] [US2] Test Jest `apps/mobile/src/screens/Home/__tests__/Home.touch.test.tsx` : chaque bouton >= 48 dp (AC2.5, FR-010)
- [x] T082 [P] [US2] Test Jest `apps/mobile/src/voice/__tests__/speak.test.ts` : lecture vocale du contenu dans la langue choisie via la synthèse de l'appareil (FR-011, R13)
- [x] T083 [P] [US2] Test Jest `apps/mobile/src/perf/__tests__/startupMark.test.ts` : la marque de démarrage est émise à l'affichage de l'accueil (AC2.1)
- [x] T084 [P] [US2] Test E2E Maestro `apps/mobile/maestro/home_languages.yaml` : ouverture < 3 s, bascule darija/arabe/français, les 4 états atteignables (AC2.1 à AC2.4)
- [x] T085 [US2] Lancer : T076 à T083 DOIVENT échouer ; commit `test(foundations): red - home screen`

### Implémentation (GREEN)

- [x] T086 [US2] Créer `packages/i18n/package.json`, `packages/i18n/src/index.ts` (i18next, repli `fr`) et `packages/i18n/locales/{ary,ary-Latn,ar,fr}.json` selon `contracts/i18n-contract.md` (textes provisoires mais complets)
- [x] T087 [US2] Implémenter l'écran `apps/mobile/src/screens/Home/` (4 états via `packages/ui`, RTL, sélecteur de langue, bouton de lecture vocale) et `apps/mobile/app/_layout.tsx`, `apps/mobile/app/index.tsx` [FR-006]
- [x] T088 [P] [US2] Implémenter `apps/mobile/src/voice/speak.ts` (expo-speech)
- [x] T089 [P] [US2] Implémenter `apps/mobile/src/perf/startupMark.ts` (Hermes, marque de démarrage)
- [x] T090 [P] [US2] Implémenter la persistance de `locale`/`theme` dans `app_settings` : `apps/mobile/src/settings/appSettings.ts`
- [x] T091 [US2] Commit `feat(foundations): green - home screen` ; REFACTOR `refactor(foundations): home screen`

**Point de contrôle** : accueil validé en 4 langues, 4 états, RTL.

## Phase 7 : Récit 5 — Diagrammes `make diagrams` (P2)

### Tests d'abord (RED)

- [x] T092 [P] [US5] Test `tests/diagrams/test_render.sh` : des `.mmd` de `flowchart`, `sequenceDiagram`, `erDiagram`, `stateDiagram-v2` produisent un SVG et un PNG chacun dans `img/` du module (AC5.1, FR-025)
- [x] T093 [P] [US5] Test `tests/diagrams/test_invalid.sh` : un `.mmd` invalide fait échouer `make diagrams` en nommant le fichier fautif (AC5.2)
- [x] T094 [P] [US5] Test `tests/diagrams/test_reproducible.sh` : second lancement identique (sommes de contrôle égales, « 0 fichier rendu ») (AC5.3)
- [x] T095 [P] [US5] Test `tests/diagrams/test_duration.sh` : module standard rendu en moins de 2 minutes (SC-010)
- [x] T096 [US5] Lancer : DOIVENT échouer ; commit `test(foundations): red - diagrams`

### Implémentation (GREEN)

- [x] T097 [US5] Créer `infra/docker/mermaid.Dockerfile` et compléter `scripts/render-diagrams.sh` (rendu SVG + PNG, ignore les rendus à jour, nomme le fichier invalide) ; brancher `make diagrams`
- [x] T098 [P] [US5] Ajouter les fixtures `tests/diagrams/fixtures/{valid,invalid}/*.mmd`
- [x] T099 [US5] Commit `feat(foundations): green - diagrams` ; REFACTOR `refactor(foundations): diagrams`

## Phase 8 : Récit 6 — Prototype et mesures sur Android 2 Go (P2)

### Tests d'abord (RED)

- [ ] T100 [P] [US6] Test Jest `apps/mobile/src/screens/Map/__tests__/Map.test.tsx` : carte rendue depuis 50 parcelles en cache local avec vigueur, sans réseau (AC6.2, FR-027)
- [ ] T101 [P] [US6] Test Jest `apps/mobile/src/perf/__tests__/metrics.test.ts` : la sortie de mesure respecte `{metric, value, unit, threshold, device, date, verdict, build}` (data-model) (FR-028)
- [ ] T102 [P] [US6] Test `tests/report/test_report.sh` : `make report` génère `docs/modules/001-foundations/mesures.md`, verdict « tenu »/« non tenu » par seuil (démarrage 3 s, carte 2 s, 60 i/s, 40 Mo, 5 Mo/jour) ; `STRICT=1` échoue sur « non tenu » ; un « non tenu » mentionne le réexamen du choix technique (AC6.4, SC-011)
- [ ] T103 [P] [US6] Test Jest `apps/mobile/src/screens/Showcase/__tests__/Showcase.test.tsx` : écran animé du design system, respecte « réduire les animations » (AC6.3, FR-024)
- [ ] T104 [P] [US6] Test Jest `apps/mobile/src/perf/__tests__/trafficBudget.test.ts` : trafic d'une session type < 5 Mo/jour (SC-006)
- [ ] T105 [US6] Lancer : DOIVENT échouer ; commit `test(foundations): red - prototype`

### Implémentation (GREEN)

- [ ] T106 [US6] Implémenter `apps/mobile/src/screens/Map/` (MapLibre RN, 50 parcelles, vigueur, tuiles et polices locales)
- [ ] T107 [P] [US6] Implémenter `apps/mobile/src/screens/Showcase/` (écran animé Reanimated, composants `packages/ui`)
- [ ] T108 [P] [US6] Implémenter `apps/mobile/src/perf/metrics.ts` (démarrage, ouverture carte, images/s, trafic) et l'écran « Mesures » en build dev
- [ ] T109 [US6] Compléter `scripts/report.sh` (agrégation JSON -> `mesures.md`, comparaison aux seuils de la section 15 du CPS, `STRICT=1`)
- [ ] T110 [US6] Exécuter le protocole sur l'Android 2 Go de référence, déposer les JSON dans `docs/modules/001-foundations/measures/`, lancer `make report` ; tout « non tenu » ouvre un réexamen noté dans `specs/001-foundations/decisions.md` (AC6.1 à AC6.4, SC-002, SC-003, SC-008)
- [ ] T111 [US6] Commit `feat(foundations): green - prototype` ; REFACTOR `refactor(foundations): prototype`

## Phase 9 : Finition et transversal (sans récit)

- [ ] T112 [P] Vérifier la couverture >= 80 % du code métier (`packages/domain`, `services/api/app/domain`) via `make coverage` (SC-009, FR-004)
- [ ] T113 [P] Vérifier que chaque critère d'acceptation P1 (AC1.x à AC4.x) a au moins un test automatisé : matrice de traçabilité `specs/001-foundations/traceability.md` (SC-009)
- [ ] T114 [P] Passer `quickstart.md` en entier sur un clone propre (Docker seul) et corriger les écarts
- [ ] T115 **make check vert** : lancer `make check` (lint, typecheck, test, coverage, test-visual, apk-size, diagrams, e2e ou `E2E_SKIP=1` avec avertissement et justification en CI Linux/KVM) ; tout échec est corrigé, jamais contourné en modifiant un test [SC-001]
- [ ] T116 **Documentation de fin de module (/aylal.docs)** : exécuter `/aylal.docs` pour produire `docs/modules/001-foundations/{ingenieur.md,agriculteur.fr.md,agriculteur.ar.md}`, `diagrams/*.mmd` (flowchart, sequenceDiagram, erDiagram, stateDiagram-v2), `img/*.svg` et `img/*.png` via `make diagrams`, chaque doc intégrant l'image ET le bloc de code source ; mettre à jour `CHANGELOG.md` (FR-026)

## Dépendances

- Phase 1 -> Phase 2 -> Phases récits. Phase 2 (validation partagée) bloque US1 à US6.
- US1 (plateforme) avant tout test d'intégration Docker (US3, US4, US5, US6).
- US3 avant US2 (l'accueil et le shell mobile s'appuient sur `apps/mobile` créé en T057). US4 avant US2 (composants UI) ; T059 (écran de saisie) est finalisé avec les composants de US4.
- US5 et US6 (P2) après tous les P1 ; US6 dépend de US3 (sync), US4 (écran animé), US2 (marque de démarrage).
- T115 après toutes les tâches de code ; T116 en dernier.

## Exécution parallèle (exemples)

- Phase 2 : T008, T009, T010, T011, T012 ensemble (fichiers distincts).
- US1 : T020 à T027 ensemble ; T030, T031, T033, T034 ensemble.
- US3 : T036 à T049 ensemble (tests) ; T053, T055, T056, T058 ensemble.
- US4 : T061 à T068 ensemble ; T071, T072, T074 ensemble.
- US2 : T076 à T084 ensemble ; T088, T089, T090 ensemble.

## Stratégie

MVP = Phases 1, 2 et US1 (plateforme saine et porte de qualité), puis US3 (cœur « aucune donnée perdue »), US4, US2 pour compléter les P1, puis US5 et US6 (P2), puis Phase 9.

## Reportés (récits P3)

Aucun récit P3 n'existe dans la spec F0. Restent hors périmètre (reportés) : cibles iOS, contenu fonctionnel de `apps/web` et `apps/desktop` (squelettes seulement), modèles vocaux darija hébergés au Maroc (F7), authentification par téléphone et code à usage unique (F1), choix final de l'hébergeur au Maroc, maquettes haute fidélité et tests avec 5 agriculteurs, relecture des textes par un locuteur natif.

## Totaux

117 tâches : Setup 7, Fondations 12, US1 16, US3 26, US4 15, US2 16, US5 8, US6 12, Finition 5.
