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
