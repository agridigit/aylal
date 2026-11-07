# Tâches : F6 — Journal des opérations et registre phyto

**Branche** : `005-operations-journal` | **Entrées** : spec.md, plan.md, data-model.md, research.md, contracts/, quickstart.md
**Règle** : test first strict. Dans chaque bloc, les tests RED (unitaire, intégration, contrat, bout en bout) viennent AVANT l'implémentation, DOIVENT échouer (commit `test(005-operations-journal): red - <sujet>`), puis GREEN (`feat(005-operations-journal): green - <sujet>`), puis REFACTOR. Tout s'exécute dans Docker (`make test`, `make test-api`, `make test-mobile`, `make e2e`).
**Notation** : `[P]` = fichiers différents, aucune dépendance en cours. `[USn]` = récit n de spec.md. Critères cités : `Rn-Am` = récit n, scénario d'acceptation m ; `CL` = cas limite ; `G1`..`G6` = garde-fous de plan.md. Identifiants `G<n>-RED` / `G<n>-GREEN` demandés par plan.md.
**Séparation** : les tâches **non-écran** (domaine, API, base, synchro, workers, view models) ne dépendent PAS de la porte design. Les tâches marquées **`[écran]`** dépendent de **T004** (porte design) ET de la **fusion de `004-design-system` dans main** ; aucune ne démarre avant.
**Chemins** : API = `services/api/`, domaine = `packages/domain/`, mobile = `apps/mobile/`, workers = `services/workers/`. Tests : `services/api/tests/{unit,integration,contract,e2e}/`, `packages/domain/tests/`, `apps/mobile/src/**/__tests__/`, `apps/mobile/maestro/`, `tests/platform/`.

## Phase 1 : Mise en place (non-écran sauf T004)

- [ ] T001 Ajouter aux Dockerfiles `services/api/Dockerfile` et `services/workers/Dockerfile` : `reportlab`, `openpyxl`, `arabic-reshaper`, `python-bidi` ; à `apps/mobile/package.json` : `expo-notifications` (locales uniquement), `expo-sharing`, `expo-image-picker` (repli si `expo-camera` absent). Jamais sur l'hôte.
- [ ] T002 [P] Créer les clés i18n vides `packages/i18n/locales/{ary,ar,fr}/{operations,phyto,registry,reminders}.json` et étendre le test de parité `packages/i18n/tests/parity.test.ts`.
- [ ] T003 [P] Créer les squelettes vides de dossiers/modules listés dans plan.md (`services/api/app/operations/`, `packages/domain/vectors/`, `services/workers/tasks/`) sans logique, pour que les tâches RED importent des modules existants.
- [ ] T004 **T-DESIGN-GATE (humain, bloquante pour tout `[écran]`)** : maquettes haute fidélité arabe + français, **validées par un humain** (validation consignée dans `specs/005-operations-journal/decisions.md`), dans `docs/design/005-operations-journal/` pour F6-E1 journal, F6-E2 choix d'icône, F6-E3 formulaire, F6-E4 traitement phyto (produit, dose, avertissements), F6-E5 date de récolte (fiche parcelle), F6-E6 planifiées/rappels (P1), F6-E7 dictée (P1), puis F6-E8 étiquette, F6-E9 validation gestionnaire, F6-E10 historique des corrections, F6-E11 export (P2). Conformes à `docs/design/aylal-design-system.md` (jetons, 4 états, RTL, boutons >= 48 dp, plein soleil). **Dépendance externe** : fusion de la branche `004-design-system` (qui reconstruit `packages/ui`) dans main, vérifiée avant tout écran. F6 ne modifie NI `packages/ui` NI `docs/design/aylal-design-system.md` ; composants manquants (`OperationTypeTile`, `WarningBanner`, `DoseField`, `HarvestDateCard`, `PendingBadge`, `ProductRow`) demandés dans `decisions.md`.

## Phase 2 : Fondations (non-écran, bloquent tous les récits)

### Tests RED d'abord, regroupés par couche

#### Unitaire

- [x] T005 [P] **G3-RED plafonds (unitaire)** : vecteur `packages/domain/vectors/f6_limits.json` + `packages/domain/tests/operation-limits.test.ts` + miroir `services/api/tests/unit/test_f6_operation_limits.py` : <= 50 parcelles, <= 5 lignes produit, lot <= 100, note <= 500, produit libre/opérateur <= 80, dose `0 < x <= 100000` et <= 3 décimales, `limit` <= 200 (défaut 50), `performed_on` entre 2000-01-01 et +2 ans, export <= 10 000 lignes et <= 5 ans, <= 20 000 opérations/ferme/an, <= 500 planifiées.
- [x] T006 [P] **G1-RED matrice de rôles (unitaire)** : vecteur `packages/domain/vectors/f6_roles.json` + `packages/domain/tests/roles.test.ts` (étendu, assertions existantes inchangées) + `services/api/tests/unit/test_f6_roles_matrix.py` : owner/manager/worker x `operation.create|read|mark_done|cancel|validate|correct`, `registry.read|export`, `phyto_product.create_free`, suppression physique = jamais.
- [x] T007 [P] RED règles de domaine partagées : vecteurs `packages/domain/vectors/f6_{allocation,units,status_machine}.json`, tests `packages/domain/tests/{allocation,units,operation}.test.ts` et miroir `services/api/tests/unit/test_f6_domain_rules.py` (répartition au prorata de surface, somme = total, arrondi 3 décimales ; conversion d'unités affichée ; transitions d'état du data-model : planned/done/pending_validation/validated/cancelled).
- [x] T008 [P] **G4-RED configuration et Maroc (unitaire)** `services/api/tests/unit/test_f6_config.py` : aucun secret par défaut (`${VAR:-}` vides dans `docker-compose.yml`), démarrage refusé hors dev/test si identifiants MinIO absents, `AYLAL_VISION_URL`/`AYLAL_NLU_URL` vides = fonctions indisponibles (pas d'URL en dur), `AYLAL_REGISTRY_RETENTION_YEARS=5` par défaut, **allowlist** : le code F6 n'appelle aucun domaine étranger.
- [x] T009 [P] **G5-RED IP de confiance (unitaire)** `services/api/tests/unit/test_f6_client_ip.py` : `X-Forwarded-For` ignoré si le pair socket n'est pas dans `AYLAL_TRUSTED_PROXIES` (en-tête falsifié), pris en compte si le pair est fiable (saut le plus à droite non fiable) ; les tests F1 existants restent inchangés et verts.

#### Intégration

- [x] T010 [P] **G1-RED 404 inter-ferme** `services/api/tests/integration/test_f6_farm_isolation.py` : pour CHAQUE route F6 (opérations, lignes, produits libres, registre, export, rappels, corrections), non-membre, membre retiré, ferme inexistante et ferme supprimée (`farms.deleted_at`) -> **404 de corps identique** ; opération d'une autre ferme -> 404 (chargement avec `farm_id` dans le WHERE) ; FK composites `(farm_id, parcel_id)`, `(farm_id, operation_id)` refusent une référence inter-ferme.
- [x] T011 [P] **G1-RED 403 par rôle et visibilité ouvrier** `services/api/tests/integration/test_f6_role_authz.py` : ouvrier -> 403 sur `validate`, `correct`, `registry.read`, `registry.export`, annulation d'une opération d'autrui ; ouvrier sur parcelle non attribuée ou archivée -> 404 ; owner/manager OK ; statut forcé `pending_validation` (ou `planned`) pour l'ouvrier ; aucune ligne de registre synchronisée vers l'ouvrier ; aucune route de suppression physique.
- [x] T012 [P] **G1-RED synchro scopée** `services/api/tests/integration/test_f6_sync_authz.py` : `/v1/sync/upload` -> lot entier refusé 403 si une opération viole le rôle (rien d'écrit) ; non-membre 404 ; champs serveur (`farm_id` existant, `status` hors transition, `author_id`, `warnings`, `validated_by`, `registry_*`, `parcel_archived_at`) ignorés/rejetés ; ferme/parcelle créée plus tôt dans le même lot prise en compte.
- [x] T013 **G1-RED parité de tous les chemins** `services/api/tests/integration/test_f6_path_parity.py` : même matrice paramétrée (rôle x ferme x parcelle attribuée/archivée/supprimée x action) exécutée contre REST, `sync/operations.py`, `accounts/export.py`, `accounts/purge.py`, export de registre et calcul DAR, statuts identiques exigés ; **test d'inventaire** qui échoue si une route/table F6 n'est pas dans la matrice.
- [x] T014 [P] **G1-RED parcelle archivée masquée à l'ouvrier PARTOUT** `services/api/tests/integration/test_f6_archived_parcel_hidden.py` : ouvrier, parcelle archivée -> absente en REST (liste, détail, journal, DAR), en relecture/écriture `/v1/sync/upload`, dans l'export de compte de l'ouvrier et le calcul DAR ; archiver retire les lignes `operation_parcels` du seau ouvrier à la synchro suivante ; propriétaire/gestionnaire : l'opération archivée/fusionnée reste **lisible** dans journal et registre (CL).
- [x] T015 [P] **G2-RED règles PowerSync valides** `tests/platform/test_f6_sync_rules_valid.sh` + cas F6 dans `scripts/validate-sync-rules.sh` et `scripts/validate-sync-rules.mjs` : `infra/powersync/sync-rules.yaml` accepté par le service, **aucune jointure, aucune sous-requête, aucun `IN (...)`** ; seau ouvrier par requête de paramètres à deux colonnes (`parcel_id`, `user_id`) ; seau catalogue global sans paramètre ; `parcel_archived_at IS NULL` pour l'ouvrier ; `registry_entries` absent des seaux ouvrier. Doit échouer avant les règles.
- [x] T016 [P] **G3-RED plafonds avant travail coûteux** `services/api/tests/integration/test_f6_limits_enforced.py` : taille de corps lue d'abord (413/422 immédiat, parsing/I/O/rendu jamais atteints : espions) ; 51 parcelles, 6 lignes produit, note 501 car., dose hors bornes -> 422 ; lot sync de 101 opérations -> 413 `batch_too_large` **avant toute écriture** ; photo d'étiquette > 3 Mo ou type non JPEG/WebP (signature) refusée ; pagination `limit` 201 -> 422, jamais de liste non bornée.
- [x] T017 [P] **G3-RED quotas sous verrou** `services/api/tests/integration/test_f6_quota_race.py` : 2 requêtes concurrentes pour chaque quota (opérations/ferme/an, planifiées <= 500, 1 export actif par ferme, <= 10 exports/h) via REST ET `sync/operations.py` : un seul passe ; verrou `pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` puis comptage puis écriture dans la même transaction ; idempotence par `applied_ops`.
- [x] T018 [P] **G4-RED registre immuable** `services/api/tests/integration/test_f6_registry_immutable.py` : `UPDATE`/`DELETE` SQL direct sur `registry_entries` et `operation_corrections` échoue (`registry_append_only`), le rôle applicatif n'a pas `UPDATE`/`DELETE` (GRANT) ; aucune route REST/synchro ne modifie/supprime ; une **correction insère un `reversal` puis une `application` corrigée** (annulation = `reversal` seul), vue `registry_current` n'expose que les écritures non annulées, ligne de correction (auteur, date, avant/après) ; snapshot figé (nom de parcelle, culture, surface, produit, matière active, DAR, dose max, unité, opérateur, avertissements, version du catalogue) identique après purge de la parcelle ou mise à jour du catalogue ; `retain_until = performed_on + 5 ans`.
- [x] T019 [P] **G4-RED conservation et suppression de compte** `services/api/tests/integration/test_f6_registry_retention.py` : suppression de compte avant échéance -> registre conservé, opérateur anonymisé (« opérateur supprimé », aucun téléphone), registre exporté au demandeur d'abord si unique propriétaire ; `purge_expired_registry` ne supprime rien avant `retain_until`, supprime après ; l'anonymisation ne passe que par `anonymize_registry_operator` ; registre inclus dans l'export de compte JSON.
- [x] T020 [P] **G5-RED limiteur Redis et 429** `services/api/tests/integration/test_f6_rate_limit.py` : analyse dictée (<= 60/h/utilisateur), étiquette (<= 20/h), export (<= 10/h/ferme) et upload photo -> 429 avec `Retry-After` ; en-tête `X-Forwarded-For` falsifié depuis un pair non fiable ne change pas la clé de limite ; depuis un proxy fiable il est pris en compte.
- [x] T021 [P] RED migration réversible `0006_operations_journal` `services/api/tests/integration/test_migration_0006.py` : up/down, 7 tables, FK composites, `CHECK (product_id IS NULL OR free_product_name IS NULL)`, `performed_on` borné, index unique partiel `export_jobs` (1 job `queued|running`/ferme), triggers append-only, trigger de recopie `parcel_archived_at` (archivage, restauration, fusion), non-régression F0-F2.

#### Contrat

- [x] T022 [P] RED contrat `services/api/tests/contract/test_f6_openapi_sync.py` : `specs/005-operations-journal/contracts/openapi.yaml` == schéma généré par l'API (routes `operations`, `phyto_products`, `registry`, export), schémas Pydantic générés depuis Zod à jour (`test_generated_schema_fresh.py` étendu).

- [x] T022a [P] **G1-RED références d'objets / IDOR (intégration + contrat)** `services/api/tests/integration/test_f6_object_refs.py` + `services/api/tests/contract/test_f6_object_key_schema.py` : sur **REST (`POST/PATCH operations`), `/v1/sync/upload` ET export (`POST registry/exports`, `GET exports/{job_id}`)** : (a) `label_photo_id` émis pour la ferme B présenté dans la ferme A -> 422 `invalid_object_ref` ; id d'un autre utilisateur -> 422 ; id inconnu ou déjà consommé -> 422 ; (b) clé brute forgée (`label_photo_key`, `file_keys`, `../`, `farms/{autre_ferme}/labels/{uuid}`, URL `http(s)://`) dans un corps -> 422 (champ refusé, jamais écrite, aucune lecture d'objet) ; via sync : résultat d'op en erreur, rien écrit ; (c) job d'export de la ferme B demandé via la ferme A -> 404, URL signée jamais renvoyée ; accès à l'objet toujours scopé ferme (404 inter-ferme) ; (d) `label_photo_key` et `file_keys` absents des réponses, du schéma OpenAPI d'entrée (`pattern` `ServerObjectKey` en `readOnly`) et des règles PowerSync ; (e) `CHECK` de motif en base. DOIT échouer avant T024/T036/T037/T049/T073.

- FR-021 est couvert par T022a.

### Implémentation GREEN (ordre : domaine, base, garde-fous)

- [x] T023 **GREEN domaine** : règles Zod dans `packages/domain/src/{operation,operation-limits,allocation,units,registry}.ts` + `packages/domain/src/roles.ts` (étendu), vecteurs partagés, génération JSON Schema -> Pydantic, miroirs `services/api/app/domain/{operation_rules.py,allocation.py,units.py,operation_limits.py}` et rôles dans `services/api/app/domain/roles.py` ; fait passer T005, T006, T007.
- [x] T024 **GREEN migration** `services/api/alembic/versions/0006_operations_journal.py` + 10 modèles (dont `label_uploads`) dans `services/api/app/db/models.py` (colonnes et contraintes **telles que dans data-model.md**, dont `note <= 500`, `operator_name <= 80`, `free_product_name <= 80`, `entry_kind IN (application, reversal)`) ; triggers append-only, GRANT sans UPDATE/DELETE, fonctions `SECURITY DEFINER` `anonymize_registry_operator` et purge après `retain_until`, trigger de recopie `parcel_archived_at` ; fixtures de test seulement ; fait passer T021 et la part base de T022a (table `label_uploads`, `CHECK` de motif).
- [x] T025 **G1-GREEN accès scopé et parité** : `services/api/app/operations/access.py` (prédicats `visible_lines(role, user_id)` et `authorize(ops)`), appelé par `services/api/app/routers/operations.py`, `services/api/app/sync/operations.py`, `services/api/app/accounts/export.py`, `services/api/app/accounts/purge.py`, l'export de registre et le calcul DAR ; toutes les routes `/v1/farms/{farm_id}/…` via `farm_context`/`require(action)` ; fait passer T010, T011, T012, T013, T014.
- [x] T026 **G2-GREEN règles PowerSync** : règles F6 dans `infra/powersync/sync-rules.yaml` (colonnes dénormalisées `farm_id`, `parcel_id`, `author_id`, `parcel_archived_at` + en-tête d'opération dans `operation_parcels`), cas dans `scripts/validate-sync-rules.sh`, trigger serveur de recopie ; fait passer T015 et la partie seau de T014 (`scripts/validate-sync-rules.sh` vert, inclus dans `make check`).
- [x] T027 **G3-GREEN plafonds et quotas** : application des plafonds avant tout parsing lourd/I/O/rendu dans `services/api/app/routers/operations.py` et `services/api/app/sync/operations.py` ; helper de verrou et de quota dans `services/api/app/operations/service.py` (verrou puis comptage puis écriture, même transaction, y compris chemin synchro) ; fait passer T016, T017.
- [x] T028 **G4-GREEN registre réglementaire** : `services/api/app/operations/registry.py` (écritures `application`/`reversal` compensatoires, snapshot, `retain_until`), `services/workers/tasks/purge_expired_registry.py`, extension de `services/api/app/accounts/{export.py,purge.py}` (anonymisation, export préalable), config `AYLAL_REGISTRY_RETENTION_YEARS`, `AYLAL_VISION_URL`, `AYLAL_NLU_URL` dans `services/api/app/config.py` et `docker-compose.yml` (`${VAR:-}` vides) ; fait passer T008, T018, T019.
- [x] T029 **G5-GREEN IP de confiance et limiteur** : extraire `client_ip()` de `services/api/app/routers/auth.py` vers `services/api/app/auth/client_ip.py` (comportement inchangé) ; limiteur Redis partagé `services/api/app/auth/rate_limit.py` ; fait passer T009, T020 ; tests F1 verts.
- [x] T030 **GREEN contrat** : `specs/005-operations-journal/contracts/openapi.yaml` synchronisé, squelettes de routeurs `services/api/app/routers/{operations,phyto_products,registry}.py` enregistrés ; fait passer T022.
- [ ] T031 REFACTOR fondations : dédupliquer sans changer le comportement, tous les tests T005-T022a verts (`refactor(005-operations-journal): foundations`).
- [x] T031a **Durcissement-RED conservation** (sécurité) : `services/api/tests/unit/test_f6_retention_rule.py` (`retain_until(performed_on, *, recorded_on, years=None)` = max(performed_on, recorded_on) + années) et `services/api/tests/integration/test_f6_retention_hardening.py` (opération antidatée de 10 ans, chaîne annulation/correction au `retain_until` le plus long, `purge_expired_registry` ne supprime aucune entrée d'une chaîne dont un membre n'est pas expiré, ni une ligne enregistrée aujourd'hui).
- [x] T031b **Durcissement-RED visibilité non-staff** (sécurité) : `services/api/tests/integration/test_f6_nonstaff_line_visibility.py` (mark_done / cancel REST et rejeu de `put` par la synchro : 404 tant que TOUTES les lignes ne sont pas visibles du non-staff, rien n'est écrit ni au registre).
- [x] T031c **Durcissement-RED anonymisation du compte supprimé** (sécurité) : `services/workers/tests/integration/test_f6_anonymise_account_data.py` (`SqlAccountRepo` réel : `registry_entries` par `recorded_by`/`operator_user_id`, `operations` par `author_id`/`operator_user_id`, `operation_corrections` par `author_id` perdent `operator_name` et identifiants de `note` ; produit, dose, dates conservés ; lignes des autres utilisateurs intactes).
- [x] T031d **Durcissement-GREEN** : `registry.retain_until(..., recorded_on=)` avec la date serveur `recorded_at` et plus long `retain_until` de la chaîne (reversal/correction) ; `purge_expired_registry` filtré par chaîne et par `GREATEST(retain_until, recorded_at + durée)` ; `access.can_see` (non-staff) = toutes les lignes visibles, appliqué à `service.transition` et à `sync/operations.authorize` (put sur opération existante) ; migration 0007 : `anonymize_registry_operator` étendue à `recorded_by`, garde `corrections_guard` ouverte sous `aylal.registry_maintenance` pour l'anonymisation des corrections, anonymisation des `operations`, appelée par `SqlAccountRepo.purge_deleted_accounts` ; fait passer T031a à T031c.
- [x] T031e **Durcissement-RED portée de l'anonymisation** (sécurité) : `services/workers/tests/integration/test_f6_anonymise_scope.py` (SQL réel : supprimer un AUTEUR/`recorded_by` laisse intacts `operator_user_id`/`operator_name` d'un opérateur distinct encore actif, mais met `author_id`/`recorded_by` à NULL et efface la note écrite par l'auteur ; supprimer l'OPÉRATEUR l'anonymise (« opérateur supprimé ») en gardant la note, l'auteur et `recorded_by` de l'autre ; ligne sans lien inchangée ; contenu réglementaire conservé ; exemption de `registry_guard`/`corrections_guard` étroite : UPDATE direct, autre colonne ou autre rôle refusé) ; `test_f6_anonymise_account_data.py` aligné au minimum (voir decisions.md).
- [x] T031f **Durcissement-GREEN portée de l'anonymisation** : migration `0008` : `anonymize_registry_operator` ne touche l'opérateur que si `operator_user_id = p_user` ; `author_id`/`recorded_by` (registry_entries, operations, operation_corrections) deviennent NULLables et sont mis à NULL quand ils valent `p_user` ; note d'opération effacée seulement si `author_id = p_user` ; `registry_guard`/`corrections_guard` autorisent en maintenance uniquement `operator_*` et `recorded_by` (resp. `author_id` et `before`/`after`) ; adapter modèles, accès/synchro (auteur NULL) et `downgrade` ; fait passer T031e.
- [x] T031g **Durcissement-RED revue 3** (sécurité) : `services/workers/tests/integration/test_f6_anonymise_corrections_complete.py` (SQL réel : corrections `note` d'un autre sur une opération dont `author_id` = compte supprimé, correction `note` suivant celle du compte supprimé, corrections `operator_name` d'une opération dont le compte supprimé fut un opérateur antérieur (historique du registre) : `before`/`after` effacés ; corrections d'autres personnes sur opérations sans lien et champ `dose` intacts) ; `services/api/tests/integration/test_f6_reschedule_quota.py` (report vers l'année N+1 pleine : 20 000 opérations ou 500 planifiées -> 413 quota, deux reports concurrents -> un seul passe, même année ou place disponible -> 200) ; `services/api/tests/integration/test_f6_server_season.py` (REST et `/v1/sync/upload` : `season_id` d'une autre parcelle/ferme/inconnue -> 422 `invalid_season` / `rejected`, campagne serveur utilisée pour le décompte ET la ligne de registre, par parcelle).
- [ ] T031h **Durcissement-GREEN revue 3** : migration `0009` (`anonymize_registry_operator` : efface `before`/`after` des corrections `note`/`operator_name` de toute opération dont le compte fut auteur, auteur d'une correction `note` ou opérateur, y compris historique du registre) ; `service.reschedule` : `lock_farm` + `check_quotas` au changement d'année ; `season_id` dérivé côté serveur (campagne active de chaque parcelle à `performed_on`), validé s'il est fourni (422 `invalid_season`), utilisé pour `_applications_so_far` et `registry` ; fait passer T031g.

## Phase 3 : Récit 1 — Enregistrer une opération par son icône (P1) [US1]

**Test indépendant** : une opération de chaque type, avec et sans réseau. **Dépend de** : Phase 2.

### Tests RED d'abord

- [x] T032 [P] [US1] RED unitaire R1-A1, R1-A3 : `packages/domain/tests/allocation.test.ts` (étendu : prorata, affichage de la répartition) et `apps/mobile/src/operations/__tests__/operationFormViewModel.test.ts` (seuls type, parcelle, date obligatoires ; répartition affichée ; 9 types).
- [x] T033 [P] [US1] RED intégration R1-A1, R1-A2, R1-A3, R1-A5 : `services/api/tests/integration/test_f6_operations_create.py` (création minimale 3 champs, 9 types, répartition au prorata, journal chronologique paginé, `applied_ops` idempotent) et `services/api/tests/integration/test_f6_offline_sync.py` (30 jours hors ligne, aucune perte, conflit champ par champ : deux versions dans `operation_corrections`, CL).
- [x] T034 [P] [US1] RED contrat R1 : `services/api/tests/contract/test_f6_operations_contract.py` (`POST/GET /v1/farms/{farm_id}/operations`, schémas et codes de `contracts/openapi.yaml`).
- [x] T035 [US1] RED bout en bout (API) R1-A2 : `services/api/tests/e2e/test_f6_offline_operations_e2e.py` (pile Docker complète : saisie locale -> `/v1/sync/upload` -> `operation_parcels` côté lecture, sans perte ; SC-004 : file de 30 jours d'opérations hors ligne (FR-016) rejouée sans perte ni doublon, idempotence par id client ; FR-015 : les opérations `done` sont lisibles par un point de lecture stable pour F8/F4, les `planned`/`cancelled` exclues).

### Implémentation GREEN (non-écran)

- [x] T036 [US1] GREEN création et lecture : `services/api/app/operations/service.py` (création, répartition, statut initial, éligibilité de rôle), `services/api/app/routers/operations.py` ; fait passer T033, T034.
- [x] T037 [US1] GREEN synchro écriture/lecture : `services/api/app/sync/operations.py` (`authorize` + `apply` via `access.py`, quota sous verrou, conflits champ par champ ; résolution de `label_photo_id` sur (id, farm_id, user_id), aucune clé client lue) ; fait passer T035 et T022a (voie sync).
- [x] T038 [P] [US1] GREEN view models mobiles : `apps/mobile/src/operations/viewModels/operationForm.ts`, `journal.ts` (SQLite local, indicateur « à envoyer ») ; fait passer T032.
- [ ] T039 [US1] REFACTOR récit 1.

### Écrans (dépendent de T004 + fusion 004-design-system)

- [ ] T040 [US1] [écran] RED Jest/RNTL R1 (4 états + RTL + trois langues, SC-007) : `apps/mobile/src/screens/{OperationTypePicker,OperationForm,OperationJournal}/__tests__/*.test.tsx` ; Maestro `apps/mobile/maestro/operation_quick.yaml` (RED, chronométrage R1-A4, SC-001 < 15 s).
- [ ] T041 [US1] [écran] GREEN F6-E2 `apps/mobile/src/screens/OperationTypePicker/`, F6-E3 `apps/mobile/src/screens/OperationForm/`, F6-E1 `apps/mobile/src/screens/OperationJournal/` (composants `packages/ui` uniquement, aucun texte en dur) ; fait passer T040.

## Phase 4 : Récit 2 — Traitement phyto avec contrôles (P1) [US2]

**Test indépendant** : traitements conformes et non conformes. **Dépend de** : Phase 2, Récit 1.

### Tests RED d'abord

- [x] T042 [P] [US2] RED unitaire R2-A3, R2-A4, R2-A5, R2-A7 + CL : vecteur `packages/domain/vectors/f6_phyto_controls.json`, `packages/domain/tests/phyto-controls.test.ts`, miroir `services/api/tests/unit/test_f6_phyto_controls.py` (avertissements `not_authorized_for_crop`, `dose_above_max`, `max_applications_reached`, `dar_unknown`, `free_product_unchecked` ; jamais bloquant ; contrôle par parcelle sur cultures différentes ; produit/dose jamais exigés ; conversion d'unité).
- [x] T043 [P] [US2] RED intégration R2-A1, R2-A3 à R2-A7 : `services/api/tests/integration/test_f6_phyto_controls.py` (le serveur **recalcule** et ignore les avertissements du client ; décompte par campagne et par produit ; avertissements conservés dans `registry_entries` ; produit libre « non contrôlé ») et `services/api/tests/integration/test_f6_catalog.py` (recherche par nom avec matière active, homologation expirée cachée mais conservée, date de version du catalogue).
- [x] T044 [P] [US2] RED contrat R2 : `services/api/tests/contract/test_f6_phyto_contract.py` (`/v1/phyto-products`, `/v1/farms/{farm_id}/phyto-products/free`, analyse d'étiquette).
- [x] T045 [P] [US2] RED intégration R2-A2 (port `LabelRecognizer`) : `services/api/tests/integration/test_f6_label_port.py` (`AYLAL_VISION_URL` vide -> indisponible, repli par nom ; reconnaissance proposée à confirmation, jamais enregistrée seule ; photo <= 3 Mo, signature JPEG/WebP).
- [x] T046 [US2] RED bout en bout (API) SC-002 : `services/api/tests/e2e/test_f6_phyto_warnings_e2e.py` (dose > max, culture non autorisée, applications max : 3 avertissements dans le registre).

### Implémentation GREEN (non-écran)

- [x] T047 [US2] GREEN contrôles : `packages/domain/src/phyto-controls.ts`, `services/api/app/domain/phyto_controls.py`, intégration dans `services/api/app/operations/service.py` et `registry.py` ; fait passer T042, T043 (partie avertissements), T046.
- [ ] T048 [P] [US2] GREEN catalogue : `services/api/app/routers/phyto_products.py`, `services/workers/tasks/import_phyto_catalog.py` (import mensuel, `catalog_versions`, budget <= 3 Mo compressé) ; fait passer T043 (catalogue), T044.
- [x] T049 [P] [US2] GREEN étiquette : `services/api/app/operations/label.py` (port `LabelRecognizer`, repli ; clé générée serveur `farms/{farm_id}/labels/{uuid}`, émission de `label_photo_id`, vérification ferme + utilisateur, purge à 24 h) ; fait passer T045 et T022a (voie REST).
- [x] T050 [P] [US2] GREEN local : `apps/mobile/src/operations/localControls.ts`, `catalogCache.ts` (< 50 ms, date du catalogue) avec tests Jest `apps/mobile/src/operations/__tests__/localControls.test.ts` écrits avant (RED).
- [ ] T051 [US2] REFACTOR récit 2.

### Écrans (dépendent de T004 + fusion 004-design-system)

- [ ] T052 [US2] [écran] RED F6-E4 `apps/mobile/src/screens/PhytoTreatment/__tests__/*.test.tsx`, F6-E8 `apps/mobile/src/screens/LabelScan/__tests__/*.test.tsx` (4 états, RTL, trois langues) ; Maestro `apps/mobile/maestro/phyto_warning.yaml` (RED).
- [ ] T053 [US2] [écran] GREEN `apps/mobile/src/screens/PhytoTreatment/`, `apps/mobile/src/screens/LabelScan/` ; fait passer T052.

## Phase 5 : Récit 3 — Date de récolte au plus tôt (P1) [US3]

**Test indépendant** : plusieurs traitements aux DAR différents. **Dépend de** : Récit 2.

- [x] T054 [P] [US3] RED unitaire R3-A1 à R3-A4 : vecteur `packages/domain/vectors/f6_harvest_date.json`, `packages/domain/tests/harvest-date.test.ts`, miroir `services/api/tests/unit/test_f6_harvest_date.py` (DAR le plus long restant, plusieurs produits, aucun traitement = « récoltable dès maintenant », ignore les écritures annulées du registre).
- [x] T055 [P] [US3] RED intégration R3-A4 : `services/api/tests/integration/test_f6_harvest_date.py` (correction ou annulation -> recalcul via `registry_current` ; ouvrier : parcelle archivée/non attribuée -> 404, parité T013) et contrat `services/api/tests/contract/test_f6_harvest_contract.py`.
- [x] T056 [US3] RED e2e (API) SC-003 : `services/api/tests/e2e/test_f6_harvest_date_e2e.py` (DAR 21 j -> J+21 ; deux produits -> le plus long).
- [x] T057 [US3] GREEN : `packages/domain/src/harvest-date.ts`, `services/api/app/domain/harvest_date.py`, route DAR dans `services/api/app/routers/operations.py`, calcul local `apps/mobile/src/operations/viewModels/harvestDate.ts` ; fait passer T054 à T056.
- [ ] T058 [US3] [écran] RED puis GREEN F6-E5 `apps/mobile/src/screens/HarvestDate/` (+ `__tests__`, Maestro `apps/mobile/maestro/harvest_date.yaml`), 4 états, RTL ; dépend de T004 + fusion 004.

## Phase 6 : Récit 4 — Planifier et être rappelé (P1) [US4]

**Test indépendant** : planifier pour demain, rappel, passage à « faite ». **Dépend de** : Récit 1.

- [x] T059 [P] [US4] RED unitaire R4-A1, R4-A4 : `packages/domain/tests/operation.test.ts` (date future -> `planned`, « en retard » dérivé, report/réaliser/annuler) et `apps/mobile/src/operations/__tests__/reminders.test.ts` (notifications locales programmées hors ligne, aucune dépendance push tiers).
- [x] T060 [P] [US4] RED intégration R4-A1, R4-A3, R4-A4 : `services/api/tests/integration/test_f6_planned.py` (planifiée, `mark_done` -> `done` compté dans journal, DAR et coûts, annulation, plafond 500 planifiées, ouvrier : ses propres planifiées seulement) et `services/api/tests/integration/test_f6_mark_overdue.py` (worker `mark_overdue_operations`).
- [x] T061 [P] [US4] RED contrat R4 : `services/api/tests/contract/test_f6_planned_contract.py`.
- [x] T062 [US4] RED e2e (API) R4-A2, R4-A3 : `services/api/tests/e2e/test_f6_planned_e2e.py`.
- [x] T063 [US4] GREEN : transitions dans `services/api/app/operations/service.py`, `services/workers/tasks/mark_overdue_operations.py`, `apps/mobile/src/operations/reminders.ts` ; fait passer T059 à T062.
- [ ] T064 [US4] [écran] RED puis GREEN F6-E6 `apps/mobile/src/screens/PlannedOperations/` (+ `__tests__`, Maestro `apps/mobile/maestro/planned_reminder.yaml`) ; dépend de T004 + fusion 004.

## Phase 7 : Récit 5 — Dicter une opération (P1) [US5]

**Test indépendant** : phrases en darija, arabe, français. **Dépend de** : Récits 1 et 2.

- [x] T065 [P] [US5] RED unitaire R5-A1 à R5-A4 : vecteur `packages/domain/vectors/f6_dictation.json`, `packages/domain/tests/dictation-parse.test.ts` (pré-remplissage, champs ambigus signalés sans être devinés, phrase non comprise -> formulaire vide, sans confirmation rien n'est enregistré).
- [x] T066 [P] [US5] RED intégration R5 : `services/api/tests/integration/test_f6_dictation.py` (texte <= 500 car., audio jamais envoyé, port `VoiceParser` indisponible -> repli, limite 60/h/utilisateur, aucune opération créée par l'analyse) et contrat `services/api/tests/contract/test_f6_dictation_contract.py`.
- [x] T067 [US5] RED e2e (API) R5-A4 : `services/api/tests/e2e/test_f6_dictation_e2e.py`.
- [ ] T068 [US5] GREEN : `packages/domain/src/dictation-parse.ts`, `services/api/app/operations/parse.py` (port `VoiceParser`), route d'analyse ; fait passer T065 à T067.
- [ ] T069 [US5] [écran] RED puis GREEN F6-E7 `apps/mobile/src/screens/Dictation/` (+ `__tests__`, Maestro `apps/mobile/maestro/dictation.yaml`), confirmation obligatoire ; dépend de T004 + fusion 004.

## Phase 8 : Récit 6 — Exporter le registre (P2) [US6]

**Test indépendant** : exporter une parcelle puis la ferme. **Dépend de** : Phase 2 (G4), Récit 2.

- [x] T070 [P] [US6] RED unitaire R6-A1, R6-A4 : `services/api/tests/unit/test_f6_registry_columns.py` (mêmes colonnes PDF/XLSX : date, parcelle, culture, produit, matière active, dose, surface, opérateur, avertissements, « non contrôlé », écritures corrigées ; empreinte SHA-256 en pied).
- [x] T071 [P] [US6] RED intégration R6-A1 à R6-A5, SC-005 : `services/api/tests/integration/test_f6_registry_export.py` (période/parcelle, <= 10 000 lignes, <= 5 ans, 1 export actif/ferme, 403 ouvrier, 404 inter-ferme, URL signée courte MinIO) et contrat `services/api/tests/contract/test_f6_registry_contract.py`.
- [x] T072 [US6] RED e2e (API) : `services/api/tests/e2e/test_f6_registry_export_e2e.py` (worker, PDF et XLSX produits, 10 000 lignes < 60 s).
- [ ] T073 [US6] GREEN : `services/api/app/operations/export_job.py`, `services/workers/tasks/build_registry_export.py`, `services/api/app/routers/registry.py`, `apps/mobile/src/operations/share.ts` ; clés d'export générées serveur, URL signée après contrôle ferme ; fait passer T070 à T072 et T022a (voie export).
- [ ] T074 [US6] [écran] RED puis GREEN F6-E11 `apps/mobile/src/screens/RegistryExport/` (+ `__tests__`, Maestro `apps/mobile/maestro/registry_export.yaml`), partage WhatsApp ; dépend de T004 + fusion 004.

## Phase 9 : Récit 7 — Validation par le gestionnaire (P2) [US7]

**Test indépendant** : un ouvrier saisit, un gestionnaire valide ou corrige. **Dépend de** : Phase 2 (G1, G4), Récit 1.

- [x] T075 [P] [US7] RED intégration R7-A1 à R7-A4 : `services/api/tests/integration/test_f6_validation_corrections.py` (ouvrier -> `pending_validation` avec opérateur ouvrier ; validation manager/owner ; ouvrier 403 ; correction -> `reversal` + `application` et historique auteur/date/avant/après ; l'ouvrier ne voit que ses lignes) et contrat `services/api/tests/contract/test_f6_validation_contract.py`.
- [x] T076 [US7] RED e2e (API) : `services/api/tests/e2e/test_f6_worker_validation_e2e.py`.
- [ ] T077 [US7] GREEN : routes validate/correct/corrections dans `services/api/app/routers/operations.py`, `services/api/app/operations/service.py` ; fait passer T075, T076.
- [ ] T078 [US7] [écran] RED puis GREEN F6-E9 `apps/mobile/src/screens/ManagerValidation/`, F6-E10 `apps/mobile/src/screens/CorrectionHistory/` (+ `__tests__`, Maestro `apps/mobile/maestro/worker_validation.yaml`) ; dépend de T004 + fusion 004.

## Phase finale : Finition

- [ ] T079 Revue transverse non-écran : couverture >= 80 % du code métier F6, `scripts/check-test-pyramid.sh` vert (unitaire, intégration, contrat, e2e présents pour chaque récit P1), aucun `// eslint-disable`, aucune chaîne en dur.
- [ ] T080 **`make check` vert** (tests, lint, `scripts/validate-sync-rules.sh`, contrats, budget APK, parité i18n) ; les tâches `[écran]` bloquées par T004/004 sont signalées dans `decisions.md` si non terminées.
- [ ] T081 **Documentation de fin de module (/aylal.docs)** : `docs/modules/005-operations-journal/{ingenieur.md,agriculteur.fr.md,agriculteur.ar.md}`, `diagrams/*.mmd` (flowchart, sequenceDiagram, erDiagram, stateDiagram-v2 des transitions), rendus `img/*.svg` et `img/*.png` via `make diagrams`, image ET bloc de code source intégrés.

## Dépendances et exécution

- Phase 1 -> Phase 2 (RED T005-T022a [P] possibles ensemble, GREEN T023 -> T024 -> T025..T030) -> récits P1 (R1 d'abord ; R2 -> R3 ; R4 et R5 après R1) -> P2 (R6, R7).
- T004 (porte design + fusion 004) bloque UNIQUEMENT les tâches `[écran]` : T040, T041, T052, T053, T058, T064, T069, T074, T078. Tout le reste progresse sans elle.
- MVP : Phases 1-2 + Récit 1 non-écran, puis Récit 2.

## Récits reportés (P3)

Aucun récit P3 dans la spec : rien n'est reporté. Hors périmètre rappelé : certification officielle, paie, coûts F8, bilan hydrique F4, recommandation de traitement F5.
