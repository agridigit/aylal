
## T003 : refus de démarrer sans AYLAL_TILES_BASE_URL

Les tests F1 existants (`test_auth_hardening_config.py`, `test_f1_secrets_config.py`) exigent que `get_settings()` réussisse en prod avec seulement les secrets forts ; un refus dans `get_settings()` les casserait (et ils ne sont pas modifiables). Décision : `get_settings()` lit la variable (vide par défaut), et `require_tiles_base_url(settings)` refuse hors dev/test si elle est absente ; elle est appelée par le démarrage des routes carte (récit 4). À confirmer à la revue.

## T005 à T007b : niveaux de test

Ces tâches sont des tests d'intégration (PostgreSQL réel, API réelle) : `services/api/tests/integration/test_f2_*.py` et `tests/platform/test_f2_sync_rules_valid.sh` (service PowerSync). Le niveau unitaire de la matrice des rôles est porté par T011 (`test_f2_roles_matrix.py`), et le bout en bout par T026 et les récits suivants (pile Docker complète) : écrits dans ces tâches pour ne pas dupliquer les mêmes assertions.

## Règles PowerSync F2 : colonnes dénormalisées

Le service PowerSync refuse jointures, sous-requêtes et listes `IN (...)`. Le contrat `contracts/powersync-sync-rules.yaml` est réécrit : l'ouvrier est borné par le paramètre `worker_parcels.parcel_id` ; les enfants de parcelle (`seasons`, `field_blocks`) portent `parcel_archived_at`, copie de `parcels.archived_at` posée/remise à NULL par le serveur (archivage, restauration) dans la même transaction. Le GREEN doit donc ajouter cette colonne dans la migration `0004`.

## T013 : `crops.farm_id` sans clé étrangère vers `farms`

Un `TRUNCATE farms CASCADE` (fixtures d'intégration, `tests/conftest.py`) viderait aussi `crops` et détruirait le référentiel des 16 cultures (lignes `farm_id IS NULL`). `crops.farm_id` reste donc une colonne simple ; le contrôle d'appartenance est fait par l'API (`farm_id` dans toutes les clauses WHERE) et la purge de ferme (F1, à étendre) supprime explicitement les cultures libres. `seasons.crop_id` référence `crops(id)` (le contrôle « référentiel ou culture de la ferme » est dans l'API, un FK composite ne pouvant pas exprimer `farm_id NULL`).

## T018 : pas de seau « référentiel des cultures » dans `infra/powersync/sync-rules.yaml`

Le service PowerSync refuse un seau sans paramètre cohérent avec `farm_id` (`farm_id = bucket.farm_id OR farm_id IS NULL` rejeté : « Left and right sides of OR must use the same parameters »), et les tests F1 existants (`test_worker_visibility.py`) exigent que tout seau soit filtré par rôle/appartenance. Le contrat F2 proposait `crops_reference` sans paramètre : non retenu. Les 16 cultures du référentiel (lignes `farm_id IS NULL`) sont lues via `GET /v1/crops` et embarquées dans l'application ; seules les cultures libres de la ferme sont synchronisées (seaux gestionnaire et `farm_worker_farm`). Le contrat F1 `specs/001-foundations/contracts/powersync-sync-rules.yaml` est resynchronisé sur l'infra (test `tests/contract/test_powersync_rules.py`). À confirmer à la revue (T018).
