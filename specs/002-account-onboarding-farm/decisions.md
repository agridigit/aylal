# Décisions F1 (tests RED fondations)

- T005 : `AYLAL_OTP_PEPPER` (>= 32 car.) devient obligatoire hors dev/test, comme `AYLAL_JWT_SECRET`. Le test F0 `test_given_prod_env_when_secret_is_strong_then_settings_load` (test_auth_hardening_config.py) n'a plus de pepper : il devra fournir `AYLAL_OTP_PEPPER` au GREEN T016 (écart contraint par contracts/auth-otp.md, non une triche).
- T007 : `tests/conftest.py` (`make_farm`, TABLES) et les anciens tests F0 utilisant `editor`/`viewer` devront être migrés vers `manager`/`worker` au GREEN T014 (la migration 0002 change la contrainte de rôle) ; `farms` gagnera des colonnes NOT NULL (owner_id...), `make_farm` sera adapté alors.
- T008a : une écriture de synchro d'un ouvrier sur une table d'administration renvoie HTTP 403 pour tout le lot (rien d'écrit) ; non-membre : 404. Le test F0 « farm_members -> 422 » sera remplacé quand `Op.table` accepte ces tables (T012b).
- Corps REST supposés : `PUT .../parcels` `{"parcel_ids": [...]}`, `POST .../invitations` `{"phone","role"}`, `PATCH .../members/{id}` `{"role"}`.
- Niveau E2E : reporté au récit 1 (T025) ; aucune pile de bout en bout propre aux fondations.

# Décisions GREEN fondations (T012-T016)

- Contradiction F0 / F1 (CPS section 6) : le renommage des rôles `editor`->`manager`, `viewer`->`worker` impose d'adapter les anciens tests F0 (test_acl, test_acl_conflict_ack, test_conflicts, test_idempotency, test_offline_30_days, test_validation_server, e2e) et `tests/conftest.py` (TABLES). Seules les valeurs de rôle ont changé, aucune assertion de comportement. `test_auth_hardening_config.py` : ajout de `AYLAL_OTP_PEPPER` aux deux tests « prod, secret fort » (déjà annoncé en T005).
- Le test F0 « farm_members -> 422 » reste valide sans modification : `farm_members` est maintenant accepté par `Op.table`, mais une écriture sans `user_id` ou avec un rôle hors `manager|worker` donne 422 après le contrôle de rôle.
- Écarts au data-model : `farms.owner_id` et `farms.location` restent nullables en base (lignes F0, fixtures) et sont imposés par l'API et la synchro ; pas de FK vers `users` pour `farm_members.user_id`, `farms.owner_id`, `invitations.invited_by` (la synchro peut créer une ferme avant la ligne `users`). `parcels` gagne `UNIQUE (farm_id, id)` pour la FK composite de `worker_parcels`.
- Référentiel géo (T015) : la migration charge 12 régions / 12 provinces / 12 communes avec des boîtes englobantes approximatives autour des villes principales. L'import officiel HCP/ANCFCC reste à faire (source à valider, R5).
- `/v1/dev-token` : le filtrage lit `AYLAL_ENV` brut, sans `get_settings()`, pour rester 404 hors dev/test même sans poivre OTP.
- OTP : verrou et code haché (Argon2id + poivre) en place ; limites d'envoi (60 s, 5/h) et tâche d'envoi Arq reportées au récit 1 ; `/v1/auth/refresh` et `/logout` aussi.
- Le démarrage de l'API appelle `get_settings()` (lifespan) : refus de démarrer si secret/poivre faibles ou `AYLAL_ENABLE_TEST_OTP=1` hors dev/test.
- Durcissement supply-chain : `pnpm.onlyBuiltDependencies = ["esbuild"]` (seul paquet avec script d'installation dans l'arbre) dans `package.json` racine.

## Constats de sécurité ouverts (revue automatique après 3d929ee, 2026-11-07)
À traiter en test first (RED puis GREEN) avant fusion de F1 :
1. OTP `/v1/auth/otp/request` (services/api/app/routers/auth.py) : le verrou (`failed_attempts`/`locked_until`) est porté par le challenge ; un nouveau challenge repart à 0 → contournement du verrouillage. Reporter ou compter les échecs par téléphone sur une fenêtre, invalider les challenges précédents, limiter le débit par téléphone et par IP (délai de renvoi, plafond horaire).
2. OTP `/v1/auth/otp/verify` : course TOCTOU sur le compteur d'échecs. Verrouiller la ligne (`with_for_update()`) ou incrémenter atomiquement par UPDATE conditionnel ; marquer « consommé » par UPDATE conditionnel.
3. services/api/app/auth/access.py : une ferme supprimée (`Farm.deleted_at`) reste accessible. Joindre `Farm`, exiger `deleted_at IS NULL` dans `farm_role`/`farm_context`/`authorize`, et refuser les écritures dans `sync/admin._farm`.
- Limite connue OTP : le verrou vit sur chaque défi ; tant qu'il est actif, `/otp/request` n'envoie rien et le conserve, mais une nouvelle demande après 1-2 échecs (hors verrou) remet le compteur à zéro. À fermer avec la limite d'envoi du récit 1.
- Limite connue synchro : `authorize` s'exécute avant toute opération ; un même lot qui crée une ferme puis écrit une opération d'administration sur cette ferme (ex. invitation en file hors ligne) reçoit 404 pour tout le lot. À traiter aux récits 1/4 (scinder le lot côté client ou autoriser selon les créations du lot).

## Niveaux de test des constats de sécurité 2 (T075 à T077)
- Unitaire : non applicable. Le comportement testé vit dans des transactions SQL (verrou de ligne, UPDATE conditionnel, jointure `Farm`) et dans le routage HTTP ; la politique pure (`otp_policy`) est déjà couverte. E2E : couvert par l'intégration sur PostgreSQL réel via ASGI ; pas de parcours utilisateur nouveau.
- Seuils de limitation fixés par les tests (à respecter au GREEN) : 429 avec `Retry-After` pour un renvoi immédiat ; plafond horaire par téléphone atteint avant 10 envois espacés de 2 min ; plafond horaire par IP atteint avant 60 envois vers des numéros distincts.

# Décisions tests RED récit 1 (T019 à T026)

- T027 (écrans E2/E3) et T028 (Maestro signup_login) : bloquées par T004 (porte design, validation humaine des maquettes non levée). Non écrites.
- Contrats posés par les tests, à respecter au GREEN : `app/auth/sessions.py` (`TokenRecord`, `hash_token`, `new_token`, `evaluate` -> `rotate|reuse|revoked`, `revoke_family`, `rotate`), `otp_policy.is_expired/attempts_left`, `otp.codes_equal` (via `hmac.compare_digest`), `POST /v1/auth/refresh` `{"refresh_token"}` (200 même forme que verify, 401 si inconnu/réutilisé + famille révoquée), `POST /v1/auth/logout` `{"refresh_token"}` + Bearer (204, révoque la famille de cet appareil seulement), erreurs `detail` en objet `{"code": ...}` (422 `phone_invalid`), jeton d'accès de 15 min (`expires_at`), `services/workers/tasks/send_otp.py` (`deliver_otp(phone, code, channel, senders)`, `DeliveryFailed`, `ForeignNumber`, tâche `send_otp` dans `WorkerSettings.functions`), `apps/mobile/src/auth/{secureStore,session,localPin}.ts` (fabriques `createSecureStore(backend)` préfixe `aylal_`, `createSession(store)`, `createLocalPin({store,hash,randomSalt})`).
- E2E T025 : exige `AYLAL_ENV=test` et `AYLAL_ENABLE_TEST_OTP=1` sur la pile ; le GREEN ajoute cet export au Makefile (cibles e2e-api).
- Niveaux : T019/T020/T026 unitaires, T021/T022/T024 intégration/contrat, T023 intégration worker (faux adaptateurs du port, sans réseau), T025 E2E service. Le mobile n'a pas d'intégration propre (écrans bloqués par T004).

# Décisions tests RED récits 2, 3, 4 (T033 à T050)

- Bloquées par T004 (porte design non levée), non écrites : T034 (écran E1 langue), T036 (Maestro language_choice), T041 (écrans E4/E5), T042 partie Maestro (consent_profile.yaml), T049 (écran E6), T050 partie Maestro (onboarding.yaml). Aucune logique mobile hors écran n'est spécifiée pour ces récits : pas de test mobile unitaire/intégration.
- Déjà verts (code livré avec les fondations/F0) : T045 (vecteurs domaine), T046, T047, une partie de T048 (`POST/GET /v1/farms`, sync `farms` put, `/v1/geo/*`). Tests ajoutés quand même pour couvrir R4-A1/A2/A3/A5 ; seules les nouveautés échouent.
- Contrats posés par les tests, à respecter au GREEN :
  - i18n : `LANGUAGE_OPTIONS` (`code` ary|ar|fr, `label`, `spokenText`, `speechLocale`, `dir`), `applyLanguage(i18n, code) -> {locale, rtl}` (rejette une langue inconnue), clés `onboarding.language.*` (dont `title`) dans les 4 locales.
  - domaine : `CONSENT_PURPOSE_DATA_POLICY`, `hasActiveConsent(grants, purpose, version)`; `PROFILE_FIELDS = ["display_name","language"]` et `validateProfile` refuse tout champ inconnu (erreur sur le champ); `farmUploadState(id, pendingIds) -> "pending_upload"|"synced"`.
  - API : `GET/PATCH /v1/me` (PATCH `language` seul autorisé sans consentement; `display_name` sans consentement `data_policy` actif -> 403 `{"code":"consent_required"}`; champs inconnus -> 422; le profil complet passe `status` à `active`), `POST/GET /v1/me/consents` (201, 422 sans version), `DELETE /v1/me/consents/{purpose}` (204, pose `withdrawn_at`), `app/accounts/purge.py::purge_pending_accounts(session, now) -> int` (users `pending`, > 24 h, sans consentement actif, sans nom ni ferme).
  - worker : `tasks/purge_deleted_accounts.py` avec `PENDING_TTL = 24 h` et `purge_pending(ctx, now=None)` (appelle `ctx["repo"].purge_pending_accounts(now)`), enregistrée dans `WorkerSettings.cron_jobs` (horaire). L'adaptateur SQL réel du port est du GREEN (le conteneur worker n'a pas de base en test).
  - OpenAPI : `contracts/openapi.yaml` contient déjà `/v1/me*`; l'app doit les exposer.
- Niveaux : T033/T038/T045 unitaires; T035/T039/T046/T047/T048 intégration/contrat; T040 intégration worker (port factice); T042/T050 E2E service (pile Docker, `AYLAL_ENABLE_TEST_OTP=1`).

# Décisions tests RED récits 8, 5, 6 (T053 à T068)

- Bloquées par T004 (porte design non levée), non écrites : T055 (écran E12), T056 partie Maestro (delete_account.yaml), T060 (écran E7 ; la logique hors écran est couverte par `apps/mobile/src/farms/__tests__/activeFarm.test.ts`), T061 (multi_farm.yaml), T067 (écrans E8/E9/E10 et actions en attente hors ligne), T068 partie Maestro (team_invite.yaml).
- Déjà verts (routes livrées avec les fondations) : une partie de T063/T064/T066 (matrice, cartes `/members`, `/invitations`, 403/404/409/422) et T059. Seules les nouveautés échouent : honorer l'invitation à la connexion, expiration, suppression, export, règles de rôle supplémentaires, règles PowerSync par rôle.
- Contrats posés par les tests, à respecter au GREEN :
  - API : `POST /v1/me/deletion` `{"confirm": true}` (sans confirmation 422) -> 202 `{deletion_requested_at, deletion_deadline}` (+30 j), `users.status='deletion_requested'`, tous les jetons de rafraîchissement révoqués, jeton d'accès refusé ensuite (401, `current_user` vérifie le statut). `GET /v1/me/deletion/impact` -> `{"owned_farms":[{farm_id,name,other_members}]}` (propriétaire avec autres membres actifs seulement). `POST /v1/me/export` -> 202 `{export_id}` ; `app/accounts/export.py::build_export(session, user_id) -> {profile{phone,display_name,language}, consents[], farms[{id,role}], records[]}` limité à l'utilisateur, sans hachages ni donnée d'autrui. Ajouter `/v1/me/deletion/impact` à `contracts/openapi.yaml`.
  - Domaine Python `app/domain/account_deletion.py` (`DELETION_GRACE_DAYS`, `deletion_deadline`, `deletion_impact`), `app/domain/roles.py` (`INVITABLE_ROLES`, `can_remove_member`, `can_assign_parcels_to`) ; miroirs TS `packages/domain/src/account-deletion.ts` et `roles.ts`.
  - Invitations : « jeton à usage unique » = l'invitation liée au numéro vérifié par OTP, consommée une fois (`status='accepted'`) ; pas de jeton exposé dans la réponse (champs limités à id, phone, role, status, expires_at). Honorée à `otp/verify` (nouveau compte ou compte existant) si `pending` et non expirée ; ni annulée ni expirée ; un membre retiré ne la réactive pas. Rôle `owner` jamais invitable (422), numéros non marocains refusés (422).
  - Worker : `tasks/purge_deleted_accounts.py` (`DELETION_GRACE` 30 j, `purge_deleted(ctx, now=None)`, `SqlAccountRepo.purge_deleted_accounts(now)` : supprime utilisateur, jetons, consentements, appartenances ; ferme sans autre membre actif marquée `deleted_at` ; ferme partagée conservée), `tasks/expire_invitations.py` (`expire_invitations(ctx, now=None)`, `SqlInvitationRepo.expire_invitations(now)`), les deux dans `functions` et `cron_jobs`.
  - PowerSync `infra/powersync/sync-rules.yaml` : seaux par rôle (staff owner/manager avec `removed_at IS NULL`, ouvrier restreint à `worker_parcels`, aucun champ financier, pas de `SELECT *` sur farms/farm_members/invitations/users).
  - Mobile : `apps/mobile/src/farms/activeFarm.ts` (`createActiveFarm(store{get,set,remove})` avec `set`, `resolve(farms)` retombant sur une ferme membre, `filterByFarm(rows, farmId|null)`).
- Intégration réelle SqlAccountRepo / SqlInvitationRepo : `services/workers/tests/integration/test_sql_account_repo.py` contre la base de la pile (migrée par `migrate`), lignes créées et nettoyées par le test ; saute (skip) si la base est injoignable (limite : `make test-api` démarre la base via api-test avant le worker). Ce test échoue aussi à l'import tant que `expire_invitations` n'existe pas.
- Hors périmètre de ces tests : données de `trial_records` écrites par l'utilisateur supprimé (anonymisation à décider au GREEN, notée ici) ; hébergement Maroc : aucune donnée sortante (aucun test réseau).

# Décisions GREEN récits 8, 5, 6 (T057, T062, T069)

- `infra/powersync/sync-rules.yaml` : le seau personnel `farm_data` (test F0 T037) devient le seau du personnel (propriétaire/gestionnaire, `removed_at IS NULL`) et `farm_worker` est ajouté pour l'ouvrier. Le contrat `specs/001-foundations/contracts/powersync-sync-rules.yaml` est aligné (le test d'identité T037 reste inchangé). Pas de seau `user_own` : les tests T065 exigent `farm_members` dans les paramètres de tout seau non ouvrier.
- `current_user` vérifie `users.status` avec sa propre session (une session partagée ouvrirait la transaction que `sync/upload` démarre) ; un utilisateur absent de la table reste accepté (fixtures F0).
- `POST /v1/me/export` renvoie l'`export_id` ; la génération asynchrone côté worker et la livraison du fichier restent à faire (`build_export` est prêt). Les enregistrements `trial_records` de l'utilisateur supprimé sont conservés (pas de FK), anonymisation à décider.
