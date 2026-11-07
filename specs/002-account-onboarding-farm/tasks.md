# Tâches : F1 — Compte, onboarding et ferme

**Branche** : `002-account-onboarding-farm` | **Entrées** : spec.md, plan.md, data-model.md, research.md, contracts/, quickstart.md
**Règle** : test first strict. Dans chaque récit, les tests (unitaires, intégration/contrat, bout en bout) viennent AVANT l'implémentation et DOIVENT échouer (RED, commit `test(002-account-onboarding-farm): red - <sujet>`), puis GREEN, puis REFACTOR. Tout s'exécute dans Docker (`make test-api`, `make test-domain`, `make test-mobile`, `make e2e`).
**Notation** : `[P]` = fichiers différents, sans dépendance. Critères cités : `R<n>-A<m>` = récit n, scénario d'acceptation m de spec.md.
Chemins : API = `services/api/`, domaine = `packages/domain/`, mobile = `apps/mobile/`.

## Phase 1 : Mise en place

- [x] T001 Ajouter `argon2-cffi` à `services/api/pyproject.toml` et `services/workers/pyproject.toml` ; `expo-secure-store`, `expo-location` à `apps/mobile/package.json` ; reconstruire les images Docker.
- [x] T002 [P] Créer les fichiers de clés i18n vides `packages/i18n/locales/{ary,ar,fr}/{auth,onboarding,farm,team,account}.json` et le test de parité des clés `packages/i18n/tests/parity.test.ts`.
- [x] T003 [P] Ajouter la configuration sans secret par défaut dans `services/api/app/config.py` : `AYLAL_JWT_SECRET`, `AYLAL_OTP_PEPPER`, clés passerelle, `AYLAL_ENABLE_TEST_OTP` ; `docker-compose.yml` n'utilise que `${VAR:-}` vide.
- [ ] T004 Porte design (principe 10) : maquettes HD arabe et français validées des écrans P1 E1 à E6, E11, E12 et P2 E7 à E10 dans `docs/design/002-account-onboarding-farm/` ; aucun écran n'est codé avant validation. Les tâches d'écran dépendent de T004.

## Phase 2 : Fondations (bloquent tous les récits)

### Tests RED d'abord

- [x] T005 [P] RED sécurité-configuration : refus de démarrer hors dev/test sans secret, secret faible ou OTP de test activé, dans `services/api/tests/unit/test_f1_secrets_config.py` et `services/api/tests/integration/test_test_otp_gating.py` (garde-fou F0 n°1 ; FR-027).
- [x] T006 [P] **RED accès inter-ferme (404)** dans `services/api/tests/integration/test_farm_isolation.py` : pour CHAQUE route `/v1/farms/{farm_id}/...` (détail, patch, members, members/{id}, members/{id}/parcels, invitations, invitations/{id}), un utilisateur non membre reçoit **404 identique** à une ferme inexistante (corps et en-têtes comparés, pas de 403) ; membre au rôle insuffisant reçoit 403 ; un objet enfant (invitation, membre) d'une autre ferme adressé via sa propre ferme reçoit 404. Doit échouer avant T012 (FR-021, garde-fou F0 n°2).
- [x] T007 [P] RED non-régression ACL F0 après migration des rôles `editor->manager`, `viewer->worker` : étendre `services/api/tests/integration/test_acl.py` et `test_acl_conflict_ack.py` sans modifier leurs assertions existantes (noter tout écart dans `specs/002-account-onboarding-farm/decisions.md`).
- [x] T008a [P] **RED autorisation d'écriture par rôle** : un ouvrier reçoit 403 sur `PUT /v1/farms/{farm_id}/members/{user_id}/parcels` (REST) ET lors d'un `/v1/sync/upload` contenant une écriture sur `worker_parcels`, `farm_members`, `farms` ou `invitations` (rien n'est écrit) ; gestionnaire et propriétaire acceptés pour l'attribution ; non-membre/autre ferme -> 404, dans `services/api/tests/integration/test_admin_write_authz.py` (FR-021, FR-022, garde-fou n°3). Doit échouer avant T012b.
- [x] T008 [P] RED rôle lu en base à chaque requête (jeton périmé après retrait ou changement de rôle) dans `services/api/tests/integration/test_role_from_db.py` (R6-A4, R6-A5, garde-fou n°3).
- [x] T009 [P] RED règles de domaine partagées : format de numéro marocain, politique OTP (3 échecs, 5 min), rôles et droits, validation ferme/consentement/profil dans `packages/domain/tests/{phone,otp-policy,roles,farm,consent,onboarding}.test.ts` ; vecteurs partagés TS/Python dans `services/api/tests/unit/test_f1_shared_vectors.py`.
- [x] T010 [P] RED migration réversible `0002_account_farm` (up/down, index unique partiel un seul `owner`, FK composites `worker_parcels`) dans `services/api/tests/integration/test_migration_0002.py`.
- [x] T011 [P] RED référentiel géo et point-dans-commune (`/v1/geo/*`, 404 hors Maroc) dans `services/api/tests/integration/test_geo_locate.py` et `services/api/tests/unit/test_geo_point_in_commune.py` (R4-A2).

### Implémentation

- [x] T012 Dépendance unique `farm_context(farm_id, user)` : rôle lu en base, 404 non-membre, 403 rôle insuffisant dans `services/api/app/auth/farm_context.py` et `services/api/app/auth/access.py` ; fait passer T006 pour les routes existantes.
- [x] T012b Contrôle de rôle d'écriture commun REST et synchro : appliquer `farm_context` et la matrice de rôles dans `services/api/app/routers/sync.py` (chaque opération vers une table d'administration de ferme) et sur la route des parcelles ; fait passer T008a ; exception : la création d'une ferme par son futur propriétaire (R4-A3) reste permise via synchro.
- [x] T013 Règles Zod dans `packages/domain/src/{phone,otp-policy,roles,farm,consent,onboarding}.ts` puis génération JSON Schema -> Pydantic (chaîne F0) ; miroir `services/api/app/domain/{roles.py,otp_policy.py}`.
- [x] T014 Migration `services/api/alembic/versions/0002_account_farm.py` et modèles dans `services/api/app/db/models.py` (tables du data-model, migration des rôles F0).
- [x] T015 [P] Référentiel géo : import régions/provinces/communes, module `services/api/app/geo/`, routeur `services/api/app/routers/geo.py`.
- [x] T016 [P] Configuration et refus de démarrer (T005) dans `services/api/app/config.py`.
- [ ] T017 Règles de synchro PowerSync étendues par rôle (liste blanche, ouvrier sans table financière) dans `infra/powersync/sync-rules.yaml` conformes à `specs/002-account-onboarding-farm/contracts/powersync-sync-rules.yaml`, avec test `services/api/tests/integration/test_sync_rules_roles.py` écrit avant (RED puis GREEN).
- [ ] T018 [P] Contrat : synchroniser `specs/002-account-onboarding-farm/contracts/openapi.yaml` avec l'API réelle, test `services/api/tests/contract/test_f1_openapi_sync.py` écrit avant.

**Point de contrôle** : T005 à T011 (dont T008a) verts, `make test-api` et `make test-domain` verts.

## Phase 3 : Récit 1 — Inscription par téléphone et code (P1)

### Tests RED
- [ ] T019 [P] Unitaires : génération, hachage argon2 + pepper, expiration, comparaison à temps constant, compteur d'échecs et verrou dans `services/api/tests/unit/test_otp.py` (R1-A1, R1-A2).
- [ ] T020 [P] Unitaires : rotation des jetons, détection de réutilisation (famille révoquée) dans `services/api/tests/unit/test_sessions.py` (R1-A4).
- [ ] T021 [P] Intégration : `POST /v1/auth/otp/request` (202, 422, 429 quota) et `verify` (200, 400, 410, 423 après 3 échecs, verrou 5 min côté serveur, compte non dupliqué) dans `services/api/tests/integration/test_auth_otp.py` (R1-A1, A2, A3).
- [ ] T022 [P] Intégration : `refresh` (rotation, 401 sur réutilisation) et `logout` dans `services/api/tests/integration/test_auth_session.py` (R1-A4).
- [ ] T023 [P] Intégration worker : port `OtpSender`, canal au choix puis repli sur l'autre, aucun appel hors Maroc, dans `services/workers/tests/integration/test_send_otp.py`.
- [ ] T024 [P] Contrat `/v1/auth/*` dans `services/api/tests/contract/test_auth_contract.py`.
- [ ] T025 [P] E2E service : inscription complète puis retour d'un utilisateur existant dans `services/api/tests/e2e/test_signup_login_e2e.py` (R1-A1, A3).
- [ ] T026 [P] Mobile unitaires : `session.ts` (persistance après redémarrage), `secureStore.ts`, `localPin.ts` (4 chiffres, haché, jamais envoyé au serveur, optionnel) dans `apps/mobile/src/auth/__tests__/` (R1-A4, R1-A5).
- [ ] T027 [P] Mobile écrans : E2 numéro et E3 code avec 4 états et RTL (ordre des cases) dans `apps/mobile/src/screens/{Phone,Code}/__tests__/` (R1-A2).
- [ ] T028 [P] E2E mobile Maestro : `apps/mobile/e2e/` ou `apps/mobile/maestro/signup_login.yaml` (R1-A1, A3, A4, A5).

### Implémentation
- [x] T029 `services/api/app/auth/otp.py`, `services/api/app/auth/sessions.py`, `services/api/app/routers/auth.py` (Redis pour compteurs d'envoi, PostgreSQL pour défis).
- [x] T030 [P] Worker `services/workers/tasks/send_otp.py` avec port `OtpSender` et adaptateur de passerelle isolé (R3 de research.md).
- [x] T031 [P] Mobile : `apps/mobile/src/auth/{session.ts,secureStore.ts,localPin.ts}`.
- [ ] T032 Mobile : écrans `apps/mobile/src/screens/Phone/`, `apps/mobile/src/screens/Code/` avec composants `packages/ui` et clés i18n `auth.json`.

## Phase 4 : Récit 2 — Choix de la langue avec voix (P1)

### Tests RED
- [x] T033 [P] Unitaires i18n : trois langues, RTL pour `ary` et `ar`, application immédiate dans `packages/i18n/tests/language.test.ts` (R2-A2, R2-A3).
- [ ] T034 [bloquée par T004] [P] Mobile écran E1 : trois options lisibles à voix haute, aucune présélection si langue inconnue, 4 états, miroir RTL, dans `apps/mobile/src/screens/Language/__tests__/` (R2-A1, R2-A2).
- [x] T035 [P] Intégration : `PATCH /v1/me` enregistre la langue sur le compte dans `services/api/tests/integration/test_me_language.py` (R2-A3).
- [ ] T036 [bloquée par T004] [P] E2E mobile : `apps/mobile/maestro/language_choice.yaml` (R2-A1 à A3).

### Implémentation
- [ ] T037 `apps/mobile/src/screens/Language/`, `services/api/app/routers/me.py` (langue), textes `packages/i18n/locales/*/onboarding.json`.

## Phase 5 : Récit 3 — Consentement et profil minimal (P1)

### Tests RED
- [x] T038 [P] Unitaires domaine : consentement versionné, profil limité nom/surnom + langue, aucun champ superflu dans `packages/domain/tests/consent.test.ts` et `onboarding.test.ts` (R3-A2, R3-A3).
- [x] T039 [P] Intégration : `POST/GET /v1/me/consents`, `DELETE /v1/me/consents/{purpose}`, compte `pending` purgé après 24 h sans consentement et sans autre donnée que le numéro dans `services/api/tests/integration/test_consent.py` (R3-A2, FR-012).
- [x] T040 [P] Worker : `services/workers/tests/integration/test_purge_pending.py`.
- [ ] T041 [bloquée par T004] [P] Mobile écrans E4 et E5 : politique lisible à voix haute hors ligne, blocage sans consentement, enregistrement local puis synchro, 4 états, RTL, dans `apps/mobile/src/screens/{Consent,Profile}/__tests__/` (R3-A1 à A3).
- [x] T042 [P] E2E service `services/api/tests/e2e/test_consent_profile_e2e.py` et mobile `apps/mobile/maestro/consent_profile.yaml`. (partie service ; Maestro bloquée par T004)

### Implémentation
- [x] T043 `services/api/app/routers/me.py` (profil, consentements), worker de purge dans `services/workers/tasks/purge_deleted_accounts.py`.
- [ ] T044 `apps/mobile/src/screens/{Consent,Profile}/`, textes `onboarding.json`.

## Phase 6 : Récit 4 — Création de la ferme (P1)

### Tests RED
- [x] T045 [P] Unitaires domaine : nom et emplacement requis, surface facultative dans `packages/domain/tests/farm.test.ts` (R4-A1, A5).
- [x] T046 [P] Intégration : `POST /v1/farms` (201, 422), propriétaire unique, commune déduite du point, `GET /v1/farms` avec rôle, dans `services/api/tests/integration/test_farms_create.py` (R4-A1, A2).
- [x] T047 [P] Intégration hors ligne : ferme créée localement puis synchronisée, indicateur « en attente d'envoi » (UUID client) dans `services/api/tests/integration/test_farm_offline_sync.py` (R4-A3).
- [x] T048 [P] Contrat `/v1/farms`, `/v1/geo/*` dans `services/api/tests/contract/test_farms_contract.py`.
- [ ] T049 [bloquée par T004] [P] Mobile écran E6 : position, carte, repli liste hiérarchique, ferme hors ligne, 4 états, RTL, dans `apps/mobile/src/screens/FarmCreate/__tests__/` (R4-A2, A3, A5).
- [x] T050 [P] E2E mobile parcours complet langue -> numéro -> code -> consentement -> surnom -> ferme en moins de 2 min et moins de 200 Ko : `apps/mobile/maestro/onboarding.yaml` (R4-A4, SC) ; E2E service `services/api/tests/e2e/test_onboarding_e2e.py`. (partie service ; Maestro bloquée par T004)

### Implémentation
- [x] T051 `services/api/app/routers/farms.py` (création, liste, détail via `farm_context`), `services/api/app/geo/`.
- [ ] T052 `apps/mobile/src/screens/FarmCreate/`, textes `farm.json`.

## Phase 7 : Récit 8 — Suppression du compte et export (P1)

### Tests RED
- [x] T053 [P] Unitaires : calcul de la date limite à 30 jours, règles propriétaire avec membres dans `services/api/tests/unit/test_account_deletion.py` (R8-A1, A3).
- [x] T054 [P] Intégration : `POST /v1/me/deletion` (202, déconnexion, révocation des jetons, date limite renvoyée), purge effective par worker, `POST /v1/me/export` (202, contenu complet) dans `services/api/tests/integration/test_account_deletion_export.py` (R8-A1, A2, FR-026).
- [ ] T055 [bloquée par T004] [P] Mobile écran E12 : avertissement propriétaire avec membres avant confirmation, 4 états, RTL, dans `apps/mobile/src/screens/DeleteAccount/__tests__/` (R8-A3).
- [x] T056 [P] E2E : `services/api/tests/e2e/test_account_deletion_e2e.py` (Maestro `delete_account.yaml` bloqué par T004, voir decisions.md) (R8-A1 à A3).

### Implémentation
- [x] T057 `services/api/app/routers/account.py`, `services/workers/tasks/purge_deleted_accounts.py`, export asynchrone.
- [ ] T058 `apps/mobile/src/screens/DeleteAccount/`, `apps/mobile/src/screens/Settings/` (langue, code d'accès, déconnexion, E11 ; tests écrits avant dans `apps/mobile/src/screens/Settings/__tests__/`), textes `account.json`.

**Point de contrôle P1** : tous les scénarios P1 couverts par au moins un test, `make test` vert.

## Phase 8 : Récit 5 — Plusieurs fermes (P2)

### Tests RED
- [x] T059 [P] Intégration : seconde ferme, ferme active, fermes d'un membre avec rôle dans `services/api/tests/integration/test_multi_farm.py` (R5-A1, A3).
- [ ] T060 [bloquée par T004] [P] Mobile E7 : sélecteur, isolation des données entre fermes y compris hors ligne, 4 états, RTL, dans `apps/mobile/src/screens/FarmSwitcher/__tests__/` (R5-A2).
- [ ] T061 [bloquée par T004] [P] E2E : `apps/mobile/maestro/multi_farm.yaml` (R5-A1 à A3).

### Implémentation
- [ ] T062 `apps/mobile/src/screens/FarmSwitcher/` et filtrage local par `farm_id`.

## Phase 9 : Récit 6 — Invitation et rôles (P2)

### Tests RED
- [x] T063 [P] Unitaires : matrice des droits propriétaire/gestionnaire/ouvrier, gestionnaire sans suppression de ferme ni changement de propriétaire, propriétaire non retirable, dans `packages/domain/tests/roles.test.ts` et `services/api/tests/unit/test_roles.py` (R6-A2, FR-022).
- [x] T064 [P] Intégration : invitation (201, 409, 422, expiration 30 j), honorée à l'inscription du numéro, annulation, changement de rôle, retrait immédiat, attribution de parcelles, dans `services/api/tests/integration/test_invitations_members.py` (R6-A2 à A5).
- [x] T065 [P] Intégration : ouvrier ne voit que ses parcelles et aucun champ financier (API et règles PowerSync) dans `services/api/tests/integration/test_worker_visibility.py` (R6-A1).
- [x] T066 [P] Contrat invitations et membres dans `services/api/tests/contract/test_team_contract.py`.
- [ ] T067 [bloquée par T004] [P] Mobile E8, E9, E10 : équipe, invitation, accès parcelles, actions en attente hors ligne, 4 états, RTL, dans `apps/mobile/src/screens/{Team,Invite,WorkerAccess}/__tests__/`.
- [x] T068 [P] E2E : `services/api/tests/e2e/test_team_e2e.py` (Maestro `team_invite.yaml` bloqué par T004, voir decisions.md) (R6-A1 à A5).

### Implémentation
- [x] T069 `services/api/app/routers/{members.py,invitations.py}`, `services/workers/tasks/expire_invitations.py`, `infra/powersync/sync-rules.yaml`.
- [ ] T070 `apps/mobile/src/screens/{Team,Invite,WorkerAccess}/`, textes `team.json`.

## Phase 10 : Finition

- [ ] T071 REFACTOR sans changement de comportement, commit `refactor(002-account-onboarding-farm): ...`.
- [ ] T072 [P] Vérifier couverture du code métier >= 80 % (`make coverage`) et captures de référence arabe/français (`make test-visual`).
- [ ] T073 `make check` vert (lint, typecheck, tests, couverture, visuel, taille APK, diagrammes, e2e).
- [ ] T074 Documentation de fin de module (`/aylal.docs`) : `docs/modules/002-account-onboarding-farm/{ingenieur.md,agriculteur.fr.md,agriculteur.ar.md,diagrams/*.mmd,img/*}`, rendus par `make diagrams`.

## Durcissement authentification 2 (constats de sécurité, decisions.md)

- [x] T075 [P] RED intégration : verrou OTP par téléphone sur fenêtre, ancien défi invalidé, délai de renvoi, plafonds horaires téléphone/IP (429), dans `services/api/tests/integration/test_otp_hardening.py`.
- [x] T076 [P] RED intégration : atomicité du compteur d'échecs et de la consommation (20 vérifications parallèles), dans `services/api/tests/integration/test_otp_atomicity.py`.
- [x] T077 [P] RED intégration : ferme supprimée -> 404 REST et refus sync/admin, dans `services/api/tests/integration/test_deleted_farm_access.py`.
- [x] T078 GREEN : `routers/auth.py` (échecs par téléphone, invalidation, limites 429, UPDATE conditionnel / `with_for_update`), `auth/access.py`, `auth/farm_context.py`, `sync/admin.py` (`Farm.deleted_at IS NULL`).
- [x] T079 [P] RED intégration : IP cliente derrière proxy (`AYLAL_TRUSTED_PROXIES`, vide = en-têtes ignorés ; seaux distincts par client ; IP inconnue = pas de seau partagé), dans `services/api/tests/integration/test_otp_ratelimit_hardening.py`.
- [x] T080 [P] RED intégration : concurrence sur `/request` (plafond horaire et délai de 60 s jamais contournés), même fichier.
- [x] T081 GREEN : `routers/auth.py` + `config.py` (IP de confiance via X-Real-IP/X-Forwarded-For, `pg_advisory_xact_lock(hashtext(phone))` avant les lectures).

## Dépendances

Phase 1 -> Phase 2 (T006 et T008a RED avant T012 et T012b) -> Récit 1 -> Récits 2, 3 -> Récit 4 -> Récit 8 -> P2 (Récits 5, 6) -> Phase 10. T004 précède tout écran. Dans chaque récit : RED -> GREEN. Les tâches [P] d'un même bloc de tests s'exécutent en parallèle.

## Reportés (P3, exclus)

- Récit 7 — Changement de téléphone et restauration (E13, R7-A1, R7-A2) : reporté ; la restauration de base reste couverte par la reconnexion R1-A3.
