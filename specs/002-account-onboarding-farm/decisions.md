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
- Durcissement supply-chain : `pnpm.onlyBuiltDependencies = ["esbuild"]` (seul paquet avec script d'installation dans l'arbre) dans `package.json` racine (pnpm 9.15 ne lit pas la clé de `pnpm-workspace.yaml`).

## Constats de sécurité ouverts (revue automatique après 3d929ee, 2026-11-07)
À traiter en test first (RED puis GREEN) avant fusion de F1 :
1. OTP `/v1/auth/otp/request` (services/api/app/routers/auth.py) : le verrou (`failed_attempts`/`locked_until`) est porté par le challenge ; un nouveau challenge repart à 0 → contournement du verrouillage. Reporter ou compter les échecs par téléphone sur une fenêtre, invalider les challenges précédents, limiter le débit par téléphone et par IP (délai de renvoi, plafond horaire).
2. OTP `/v1/auth/otp/verify` : course TOCTOU sur le compteur d'échecs. Verrouiller la ligne (`with_for_update()`) ou incrémenter atomiquement par UPDATE conditionnel ; marquer « consommé » par UPDATE conditionnel.
3. services/api/app/auth/access.py : une ferme supprimée (`Farm.deleted_at`) reste accessible. Joindre `Farm`, exiger `deleted_at IS NULL` dans `farm_role`/`farm_context`/`authorize`, et refuser les écritures dans `sync/admin._farm`.
