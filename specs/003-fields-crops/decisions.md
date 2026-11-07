
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

## Phases 3 à 6 : tests RED non-écran (commit `test(fields-crops): red - field crop irrigation map`)

**Niveaux** : unitaire (domaine TS, miroir Python, mobile `apps/mobile/src/fields/__tests__/`, worker), intégration (`tests/integration`, `tests/contract`), bout en bout service (`tests/e2e`). Le niveau bout en bout mobile (Maestro, émulateur `aylal-2go`) est impossible sans écran : voir ci-dessous.

**Bloquées par T004** (aucun écran codé avant la porte design) : T031, T032, T041, T042, T048, T055 (tests d'écran, Storybook et flux Maestro `field_draw_*.yaml`, `crop_season.yaml`, `field_irrigation.yaml`, `field_map.yaml`). Partie de T036 « tests unitaires UI des composants `CropTile`, `PrecisionMeter`, `MapLegend`, `DrawToolbar` de `packages/ui` » : bloquée par T004 ; seule la partie contrat (`test_crops_seasons_contract.py`) est écrite et cochée. Les tâches d'implémentation d'écran (T033, T043, T049, T056) restent donc bloquées.

**Déjà livré par T016/T017 (`ed0bf6b`), donc verts à l'écriture** (tests de caractérisation, pas de RED) : création/modification/archivage de parcelle, avertissement de chevauchement, 422 croisement / < 3 points / aire nulle / 501 sommets / nom, `area_declared_ha` conservée à part, les cinq modes d'irrigation et la serre (T045, T046), liste de 50 parcelles, ouvrier limité, archivées absentes (T051, T053), culture libre, 403/404 des cultures, campagne initiale et correction de stade conservée, idempotence de la synchro. Le RED porte uniquement sur ce qui manque (liste ci-dessous).

**RED réel (le GREEN doit créer)** :
- API : 422 `outside_morocco` sur REST et sur synchro (T023, T024) ; `area_too_large` > 5 000 ha et `field_limit_reached` à 500 parcelles côté REST ; conflit de synchro des parcelles (`conflict_logged` + ligne `sync_conflicts`, `base_version` lu) ; nombres décimaux (`area_calc_ha`, `area_declared_ha`) sérialisés en nombres JSON et non en chaînes ; seed des 16 cultures avec `photo_key` (`crops/<slug>.webp`) et `stages` non vides, `validated=false` ; `stage_estimated` posé à la création de campagne pour une culture à agronomie.
- Domaine TS et Python : `IRRIGATION_MODES`, `isIrrigationMode`, `irrigation`/`greenhouse`/`areaDeclaredHa` renvoyés par `validateField` (`irrigation_invalid`, `greenhouse_invalid`), `reestimateStage`, `adviceEnabled` (et miroirs `reestimate_stage`, `advice_enabled`, `validate_field`).
- Mobile : `drawSession.ts`, `gpsWalk.ts`, `mapData.ts`, `offlineRegion.ts`, `fieldStore.ts` (`saveDrawnField`), `PARCEL_COLUMNS` dans `src/sync/powersyncSchema.ts`.
- Worker : `services/workers/tasks/build_tiles.py` (`tiles_url`, `build_tiles`, `TilesBaseUrlMissing`), enregistré dans `WorkerSettings.functions`.

**Constat** : `specs/003-fields-crops/contracts/openapi.yaml` n'est pas du YAML valide (`?` non quoté dans un mapping en ligne) ; les tests de contrat le lisent ligne à ligne. T019 doit le corriger puis les tests pourront utiliser `yaml.safe_load`.

**Contrainte PowerSync** : `mapData.test.ts` exige que la requête locale de la carte (`FIELDS_LOCAL_SQL`) soit une lecture de `parcels` sans jointure ni sous-requête ; aucune règle de synchro n'est ajoutée par ces tâches.

**Worker (Docker)** : l'image du worker copie le code (pas de montage) ; reconstruire (`docker compose build worker`) avant `make test-worker` pour voir les nouveaux fichiers de test.
