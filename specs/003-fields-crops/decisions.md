
## T003 : refus de démarrer sans AYLAL_TILES_BASE_URL

Les tests F1 existants (`test_auth_hardening_config.py`, `test_f1_secrets_config.py`) exigent que `get_settings()` réussisse en prod avec seulement les secrets forts ; un refus dans `get_settings()` les casserait (et ils ne sont pas modifiables). Décision : `get_settings()` lit la variable (vide par défaut), et `require_tiles_base_url(settings)` refuse hors dev/test si elle est absente ; elle est appelée par le démarrage des routes carte (récit 4). À confirmer à la revue.

## T005 à T007b : niveaux de test

Ces tâches sont des tests d'intégration (PostgreSQL réel, API réelle) : `services/api/tests/integration/test_f2_*.py` et `tests/platform/test_f2_sync_rules_valid.sh` (service PowerSync). Le niveau unitaire de la matrice des rôles est porté par T011 (`test_f2_roles_matrix.py`), et le bout en bout par T026 et les récits suivants (pile Docker complète) : écrits dans ces tâches pour ne pas dupliquer les mêmes assertions.

## Règles PowerSync F2 : colonnes dénormalisées

Le service PowerSync refuse jointures, sous-requêtes et listes `IN (...)`. Le contrat `contracts/powersync-sync-rules.yaml` est réécrit : l'ouvrier est borné par le paramètre `worker_parcels.parcel_id` ; les enfants de parcelle (`seasons`, `field_blocks`) portent `parcel_archived_at`, copie de `parcels.archived_at` posée/remise à NULL par le serveur (archivage, restauration) dans la même transaction. Le GREEN doit donc ajouter cette colonne dans la migration `0004`.
