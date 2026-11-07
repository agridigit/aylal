# Décisions : F6 — Journal des opérations et registre phyto

## À confirmer

- **Durée de conservation du registre phyto** : le CPS ne fixe aucune durée. Valeur par défaut retenue : **5 ans** à compter de la date de l'opération (`AYLAL_REGISTRY_RETENTION_YEARS=5`, supérieure aux 2-3 ans des référentiels d'export de type GlobalG.A.P.). À confirmer par un juriste (loi 09-08 / CNDP / ONSSA). Pendant la durée, la suppression de compte anonymise les données personnelles et conserve les lignes du registre ; purge par `purge_expired_registry` après échéance.
- **Articulation suppression de compte (30 j) et conservation légale** : anonymisation + export préalable au demandeur, à valider avec la même revue juridique.
- **Source du catalogue PhytoIndex et reconnaissance d'étiquette / dictée** (F5/F7 absents) : ports `LabelRecognizer` et `VoiceParser` avec repli ; fournisseurs à décider.

## Dépendance design

- La porte design (T004) est une validation humaine, non encore donnée. Les écrans dépendent aussi de la fusion de `004-design-system` dans main. F6 ne modifie ni `packages/ui` ni `docs/design/aylal-design-system.md`.
- **Composants demandés à `004-design-system`** : `OperationTypeTile`, `WarningBanner`, `DoseField`, `HarvestDateCard`, `PendingBadge`, `ProductRow`.

## Tests RED des fondations (T005-T022a)

- **Niveau bout en bout** : aucun E2E pour les fondations (garde-fous, règles pures, migration) ; les E2E API de F6 sont portés par T035, T046, T056, T062 (récits). Les fondations sont couvertes en unitaire, intégration et contrat.
- **Contrat `openapi.yaml` invalide en YAML** : la ligne `earliest-harvest` contient `: ` dans un mappage de flux (échec de `yaml.safe_load`) ; T030 doit le corriger pour faire passer T022.
- **T021** : la migration crée 10 tables (7 « de ferme » + `phyto_products`, `phyto_product_uses`, `catalog_versions`), comme dans T024 ; le test vérifie les 10.
- **Lignes produit (`product_lines`, <= 5)** : absentes de `OperationInput` du contrat ; le test T016 les exige dans le corps ; T030 doit les ajouter au contrat.
- **MinIO** : les défauts de développement existants de `docker-compose.yml` (MINIO_ROOT_*) ne sont pas touchés ; T008 exige seulement le refus de démarrage hors dev/test (`require_minio_credentials`) et des variables F6 vides.
- **Contrat PowerSync F6** : fragment non autonome (non validé seul par le service) ; T015 valide les règles réelles `infra/powersync/sync-rules.yaml`.

## Tests RED en contradiction (GREEN des fondations, T023 à T030)

Les tests ci-dessous ne sont pas modifiés ; ils échouent par construction et attendent une décision humaine ou une correction du test.

1. **`test_f6_registry_retention::test_given_a_sole_owner_deleting_the_account_then_the_registry_is_exported_first_and_kept`** envoie `POST /v1/me/deletion` avec `{}` et attend 202. Le contrat F1 (`test_account_deletion_export::test_given_no_confirmation_when_deleting_then_422_and_nothing_changes`) exige 422 pour `{}` (confirmation explicite obligatoire). Le contrat F1 est conservé. Implémenté : une demande confirmée (`{"confirm": true}`) d'un propriétaire dont la ferme a un registre renvoie `registry_export_id` (et `registry_export_ids`) et met un export complet en file avant l'anonymisation. Le test F6 devrait envoyer `{"confirm": true}`.
2. **`test_migration_0006::test_given_archive_restore_and_merge_then_parcel_archived_at_is_copied_to_operation_parcels`** met à jour `parcels.merged_into`, colonne inexistante (F2 : `merged_into_id`). Aucune colonne d'alias n'est ajoutée. L'archivage et la restauration du test passent ; la fusion (`archived_at` + `merged_into_id`) est couverte par le même trigger `parcels_copy_archived_at`.
3. **`label_photo_key` par la synchro** : `test_f6_sync_authz::test_given_server_owned_fields_when_uploading_then_they_are_ignored` attend que l'opération soit appliquée avec `label_photo_key` ignorée ; `test_f6_object_refs` (T022a, FR-021) attend qu'une clé d'objet fournie par le client soit rejetée (`invalid_object_ref`) et rien d'écrit. T022a est suivi (aucune clé d'objet n'est jamais acceptée d'un client, quel que soit le type d'opération). Le test T012 devrait retirer `label_photo_key` de ses champs « propriété du serveur ».
4. **`test_f6_farm_isolation::test_given_a_non_member_or_unknown_farm_when_calling_any_f6_route_then_404_with_an_identical_body`** génère un nouvel identifiant de job (`uuid.uuid4()`) à chaque appel de `routes(...)` puis indexe les corps de référence par chemin contenant ce job : la clé de la route `GET registry/exports/{job}` n'existe jamais (`KeyError`) quelle que soit l'implémentation. Les 404 sont bien identiques (corps `{"detail":"not_found"}`) ; le test doit réutiliser le même `job` pour les deux appels.

## Choix d'implémentation des fondations

- `operations.product_lines jsonb` (ajout à `data-model.md`) porte les lignes produit (<= 5) ; le registre écrit une entrée par parcelle et par ligne.
- Dépassement de quota (annuel 20 000, planifiées 500) : 413 `operations_quota_exceeded` / `planned_quota_exceeded` (contrat), par opération `rejected` sur la synchro.
- Une opération sur une parcelle archivée est refusée (404) pour tous les rôles ; la lecture de l'historique reste ouverte au staff.
- Photo d'étiquette : le serveur enregistre `label_uploads` (clé générée `farms/{farm}/labels/{uuid}`, usage unique, 24 h) ; l'écriture de l'objet dans MinIO et la reconnaissance (`AYLAL_VISION_URL`) sont câblées par T049 ; sans reconnaisseur la route répond 503 `label_unavailable` avec le `label_photo_id`.
- Dictée (`/operations/parse`) : limiteur Redis 60/h/utilisateur actif ; l'analyse elle-même (`AYLAL_NLU_URL`) est câblée par l'histoire de dictée (503 `parse_unavailable` d'ici là).
- Export de registre : limite de 10 par heure et par ferme et un seul job actif comptés en base sous le verrou de ferme ; la construction des fichiers et l'URL signée viennent de T073.
- Les fonctions SQL `anonymize_registry_operator` et `purge_expired_registry` positionnent `aylal.registry_maintenance` (local à la transaction) ; même alors, le trigger ne laisse changer que `operator_name` / `operator_user_id` (UPDATE) ou supprimer (DELETE, filtré sur `retain_until`).
5. **`test_worker_visibility::test_given_the_general_buckets_then_no_one_gets_a_row_of_a_removed_member_and_workers_are_not_in_a_staff_bucket`** (F1, T065) exige que tout seau dont le nom ne contient pas « worker » ait un paramètre `farm_members ... removed_at IS NULL ... role != 'worker'`. Or `tests/platform/test_f6_sync_rules_valid.sh` (T015) exige un seau global `phyto_catalog` sans aucun paramètre (référentiel lisible par tous, ouvrier compris). Les deux exigences sont incompatibles : le seau `phyto_catalog` est livré sans paramètre (T015, spec F6) et le test F1 doit exclure explicitement le seau global du référentiel.

Le contrat `specs/001-foundations/contracts/powersync-sync-rules.yaml` est resynchronisé avec `infra/powersync/sync-rules.yaml` (test d'identité `test_powersync_rules`) ; la route `earliest-harvest` est documentée dans le contrat F2 car le test de contrat F2 exige que toute route servie sous `/v1/farms/{farm_id}/fields` y figure.

## Corrections de tests RED contradictoires (décision : contradiction établie avec la spec)

Aucune assertion de sécurité n'est affaiblie ; chaque correction est minimale. Source de vérité entre parenthèses.

1. `test_f6_registry_retention` (sole owner) : avant `json={}` -> après `json={"confirm": True}`. Raison : `{}` doit renvoyer 422 (confirmation explicite, contrat F1 `test_account_deletion_export`). Les assertions (202, `registry_export_id`, registre conservé) sont inchangées.
2. `test_migration_0006` (archive/restore/merge) : avant `UPDATE parcels SET ... merged_into=$2` -> après `merged_into_id=$2`. Raison : la colonne F2 s'appelle `merged_into_id`. Assertions inchangées.
3. `test_f6_sync_authz::...server_owned_fields...ignored` : avant `label_photo_key="farms/x/labels/y"` envoyé et `label_photo_key IS NULL` vérifié -> après le champ n'est plus envoyé. Raison : T022a / FR-021 (`test_f6_object_refs`) rejette toute clé d'objet fournie par le client (`invalid_object_ref`, rien d'écrit) ; T022a prime. Le rejet reste testé par `test_f6_object_refs`.
4. `test_f6_farm_isolation::...identical_body` : avant `uuid.uuid4()` à chaque appel de `routes(...)` -> après un seul `job` réutilisé. Raison : les clés de référence contiennent le chemin du job. Assertions (404, corps identique) inchangées.
5. `test_worker_visibility::...general_buckets...` (F1) : avant tout seau hors « worker » exige le paramètre `farm_members` -> après liste blanche nommée `GLOBAL_CATALOG_BUCKETS = {"phyto_catalog"}` ; pour ces seaux on exige AU CONTRAIRE l'absence de paramètre et de `farm_id`/`user_id` dans les requêtes. Raison : T015 / spec F6 imposent un référentiel global sans paramètre. Tout autre seau reste soumis aux trois exigences d'origine.

## Durcissement du registre (T031a à T031d)

- Choix : un non-staff ne peut agir (mark_done, cancel, rejeu synchro d'une opération existante) que si TOUTES les lignes de l'opération lui sont visibles (assignées, non archivées, siennes) ; sinon 404 et rien n'est écrit. Pas d'écriture partielle au registre.
- Conservation : `retain_until = max(performed_on, date serveur recorded_at) + registry_retention_years` ; une opération antidatée ne raccourcit pas la conservation ; reversals et corrections gardent le plus long `retain_until` de la chaîne.
- Anonymisation : `operation_corrections` est aujourd'hui sans exception de maintenance (`corrections_guard`) ; le GREEN doit l'ouvrir uniquement à `aylal.registry_maintenance`. `recorded_by` (uuid sans FK) reste en place dans le registre (garde : seuls `operator_name`/`operator_user_id` changent) ; seul le nom opérateur est effacé.
- Niveau bout en bout non écrit : ces trois constats sont des invariants de base de données et d'accès couverts en intégration sur PostgreSQL réel (l'anonymisation tourne dans le worker, hors pile HTTP) ; les parcours HTTP de bout en bout restent portés par les tâches e2e des récits (T035, T076). Pas de test synchro de `mark_done`/`cancel` : la synchro n'expose pas ces transitions (le patch est réservé au staff, 403) ; le rejeu d'un `put` est le seul chemin d'écriture non-staff sur une opération existante.
- Note outillage : l'image `worker` embarque ses tests (pas de bind mount) ; `bash scripts/dc.sh build worker` avant de lancer un nouveau test worker.
- Purge (0007) : `purge_expired_registry(p_today, p_years DEFAULT 5)` travaille par chaîne (application + reversals qui la désignent). Une ligne « héritée » (`retain_until <= performed_on + années`) garde en plus le plancher `recorded_at + années` ; une ligne dont `retain_until` dépasse déjà ce calcul est respectée telle quelle.
