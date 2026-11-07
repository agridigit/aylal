# Tâches : F2 — Parcelles et cultures

**Branche** : `003-fields-crops` | **Entrées** : spec.md, plan.md, data-model.md, research.md, contracts/, quickstart.md
**Règle** : test first strict. Dans chaque récit, les tests (unitaires, intégration/contrat, bout en bout) viennent AVANT l'implémentation et DOIVENT échouer (RED, commit `test(003-fields-crops): red - <sujet>`), puis GREEN (`feat(...): green - <sujet>`), puis REFACTOR. Tout s'exécute dans Docker (`make test-api`, `make test-domain`, `make test-mobile`, `make e2e`).
**Notation** : `[P]` = fichiers différents, sans dépendance. Critères cités : `R<n>-A<m>` = récit n, scénario d'acceptation m de spec.md ; `CL` = cas limite. `[écran]` = tâche d'écran, **dépendante de T004** (porte design). Les tâches non-écran ne dépendent pas de T004.
**Chemins** : API = `services/api/`, domaine = `packages/domain/`, mobile = `apps/mobile/`, workers = `services/workers/`.

## Phase 1 : Mise en place (non-écran)

- [x] T001 Ajouter à `apps/mobile/package.json` : `@maplibre/maplibre-react-native`, `expo-document-picker`, `@tmcw/togeojson`, `shpjs`, `proj4`, `pmtiles` (les trois derniers servent R7 reporté : ne les ajouter que si utiles aux tests de non-appel réseau ; sinon omettre) ; `shapely` dans `services/api/pyproject.toml` seulement si un vecteur l'exige ; reconstruire les images Docker.
- [x] T002 [P] Créer les fichiers de clés i18n vides `packages/i18n/locales/{ary,ar,fr}/{fields,crops,seasons,map}.json` et étendre le test de parité `packages/i18n/tests/parity.test.ts`.
- [x] T003 [P] Configuration sans secret : `AYLAL_TILES_BASE_URL` dans `services/api/app/config.py` et `docker-compose.yml` (`${VAR:-}` vide) ; test dans `services/api/tests/unit/test_f2_config.py` écrit avant : aucun identifiant MinIO ni URL de tuiles externe codé en dur, refus de démarrer hors dev/test si absents (garde-fou n°5).
- [ ] T004 **Porte design « T004-like »** (principe 10, comme F1/T004) : maquettes HD arabe et français, validées par l'humain, des écrans P1 F2-E1 carte, F2-E2 dessin (touches et GPS, précision, croisement expliqué visuellement), F2-E3 fiche et formulaire, F2-E4 liste illustrée des cultures, et P2 F2-E5 découpage/fusion, F2-E6 campagnes et historique, F2-E8 parcelles archivées, dans `docs/design/003-fields-crops/` ; chaque écran avec 4 états (chargement, vide, erreur, hors ligne) et miroir RTL ; composants `CropTile`, `PrecisionMeter`, `MapLegend`, `DrawToolbar` demandés au design system par une note dans `specs/003-fields-crops/decisions.md` (sans modifier `docs/design/aylal-design-system.md`). **Aucun écran n'est codé avant cette validation : toutes les tâches `[écran]` en dépendent.** (F2-E7 import : reporté, pas de maquette.)

## Phase 2 : Fondations (non-écran, bloquent tous les récits)

### Tests RED d'abord

- [x] T005 [P] **RED accès inter-ferme (404)** dans `services/api/tests/integration/test_f2_farm_isolation.py` : pour CHAQUE route F2 (`/v1/farms/{farm_id}/fields`, `fields/archived`, `fields/{id}`, `fields/{id}/restore`, `fields/merge`, `fields/{id}/blocks`, `blocks/{id}`, `fields/{id}/seasons`, `seasons/{id}`, `farms/{id}/crops`, `/v1/crops?farm_id=`), un non-membre reçoit un **404 identique** (corps et en-têtes comparés) à une ferme inexistante, jamais 403 ; une parcelle, un bloc, une campagne ou une culture libre d'une autre ferme adressé via sa propre ferme reçoit 404 ; `crop_id` d'une autre ferme dans un POST de campagne : 404 ; `survivor_id`/`merged_ids` d'une autre ferme : 404 ; ferme supprimée (`deleted_at`) : 404 (garde-fous n°1 et n°4). Doit échouer avant T016.
- [x] T006 [P] **RED autorisation par rôle (403) et visibilité ouvrier (404)** dans `services/api/tests/integration/test_f2_role_authz.py` : un ouvrier reçoit **403** sur toute action de gestion (créer/modifier/archiver/restaurer/fusionner/découper une parcelle, démarrer/clôturer une campagne, corriger le stade, créer une culture libre) sur une parcelle **attribuée** ; reçoit **404** (pas 403) sur toute lecture ou écriture d'une parcelle **non attribuée** (fiche, blocs, campagnes) et sur `fields/archived` ; sa liste ne contient que ses parcelles ; owner et manager acceptés ; rôle lu en base à chaque requête (jeton périmé après changement de rôle) (garde-fou n°2, FR-020). Doit échouer avant T016.
- [x] T007 [P] **RED même contrôle sur la synchro** dans `services/api/tests/integration/test_f2_sync_authz.py` : `/v1/sync/upload` avec une opération sur `parcels`, `seasons`, `field_blocks`, `crops` personnalisées ou `field_commands` -> ouvrier : 403 pour tout le lot, rien d'écrit ; non-membre : 404 ; objet d'une autre ferme : 404 ; champs serveur (`farm_id` d'un enregistrement existant, `area_calc_ha`, `status_summary`, `created_by`, `archived_at` hors action autorisée) ignorés ou rejetés ; écriture sur ferme supprimée ou parcelle archivée refusée (garde-fous n°3 et n°4). Doit échouer avant T017.
- [x] T007b [P] **RED ouvrier assigné + parcelle archivée** dans `services/api/tests/integration/test_f2_worker_archived_field.py` : ouvrier attribué à une parcelle, puis parcelle archivée (ou ferme supprimée) -> REST : 404 sur fiche, blocs, campagnes et liste (parcelle absente) ; règles PowerSync ouvrier (`seasons`, `field_blocks`, tout enfant de parcelle) ne renvoient plus aucune ligne, y compris l'historique de campagnes ; après restauration par un gestionnaire, les données réapparaissent ; `/v1/sync/upload` refuse toute écriture (FR-020, garde-fous n°2 et n°4). Doit échouer avant T015, T018 et T061.
- [x] T008 [P] RED non-régression F0/F1 après migration `0004` (`parcels.vigor` nullable, `deleted_at` joint dans `farm_role`/`farm_context`/`authorize`) : étendre sans modifier les assertions existantes `services/api/tests/integration/test_acl.py`, `test_acl_conflict_ack.py`, `test_farm_isolation.py`, `test_admin_write_authz.py`, et ajouter `services/api/tests/integration/test_deleted_farm_404.py` (clôture du constat F1 n° 3 ; limite « ferme créée dans le même lot »).
- [x] T009 [P] RED règles de domaine partagées dans `packages/domain/tests/{geometry,area,overlap,field,crop,season,phenology,block,merge}.test.ts` ; vecteurs `packages/domain/vectors/f2_{area,self_intersection,overlap,season_rules,merge}.json` ; test miroir Python `services/api/tests/unit/test_f2_shared_vectors.py` (aire à 0,5 % près, bornes ≥ 3 et ≤ 500 sommets, ≤ 5 000 ha, ≤ 500 parcelles/ferme, noms ≤ 80 car.).
- [x] T010 [P] RED migration réversible `0004_fields_crops` (up/down, PostGIS, index GiST, FK composites `(farm_id, …)`, index unique partiel `(field_id, crop_id) WHERE ended_at IS NULL`, CHECK `planting_year`/`sowing_date`, seed des 16 cultures) dans `services/api/tests/integration/test_migration_0004.py`.
- [x] T011 [P] RED matrice de rôles étendue (`field.*`, `season.*`, `crop.create_custom`) : vecteurs partagés dans `packages/domain/tests/roles.test.ts` et `services/api/tests/unit/test_f2_roles_matrix.py`.

### Implémentation

- [x] T012 Règles Zod dans `packages/domain/src/{geometry,area,overlap,field,crop,season,phenology,block,merge}.ts`, génération JSON Schema -> Pydantic (chaîne F0), miroirs `services/api/app/domain/{geometry.py,season_rules.py,field_rules.py}` ; fait passer T009 et T011.
- [x] T013 Migration `services/api/alembic/versions/0004_fields_crops.py` (extension de `parcels`, tables `crops`, `seasons`, `field_blocks`, `field_commands`, seed des 16 cultures) et modèles dans `services/api/app/db/models.py` ; fait passer T010 et T008 (partie migration).
- [x] T014 Étendre `services/api/app/domain/roles.py` et `packages/domain/src/roles.ts` (matrice F2 : écritures owner/manager ; lecture ouvrier limitée à `worker_parcels`) ; fait passer T011.
- [x] T015 `farm_context`/`authorize` : jointure `farms.deleted_at IS NULL` et `parcels.archived_at IS NULL`, chargement des objets enfants toujours avec `farm_id` dans la clause WHERE, visibilité ouvrier (404) dans `services/api/app/auth/farm_context.py` et `services/api/app/auth/access.py`, y compris pour blocs et campagnes dont la parcelle parente est archivée ; fait passer T008 (`deleted_farm_404`) et T007b (partie REST).
- [x] T016 Squelette des routeurs `services/api/app/routers/{fields.py,seasons.py,blocks.py,crops.py}` derrière `farm_context`/`require(action)` ; fait passer **T005 (404 inter-ferme)** et **T006 (403 par rôle, 404 non attribuée)** une fois les routes alimentées par les récits.
- [x] T017 Autorisation de synchro `services/api/app/sync/fields.py` (`authorize` + `apply` pour `parcels`, `seasons`, `field_blocks`, `crops`, `field_commands`, champs serveur ignorés) branchée dans `services/api/app/routers/sync.py` ; fait passer **T007**.
- [x] T018 [P] Règles de synchro PowerSync étendues (parcelles, campagnes, blocs, cultures ; ouvrier : ses parcelles seulement) dans `infra/powersync/sync-rules.yaml` conformes à `specs/003-fields-crops/contracts/powersync-sync-rules.yaml` (enfants de parcelle ouvrier filtrés sur parcelle parente non archivée), tests `services/api/tests/integration/test_f2_sync_rules_roles.py` et T007b écrits avant.
- [ ] T019 [P] Contrat : synchroniser `specs/003-fields-crops/contracts/openapi.yaml` avec l'API réelle, test `services/api/tests/contract/test_f2_openapi_sync.py` écrit avant.
- [ ] T020 [P] Garde-fou Maroc : test d'allowlist `services/api/tests/unit/test_f2_no_foreign_tiles.py` et `apps/mobile/src/fields/__tests__/mapStyle.allowlist.test.ts` (style de carte et code mobile ne référencent que `AYLAL_TILES_BASE_URL`, aucun domaine tiers de tuiles/géocodage), puis `apps/mobile/src/fields/mapStyle.ts` ; emprise Maroc : 422 `outside_morocco` testé dans `services/api/tests/integration/test_f2_outside_morocco.py` (garde-fou n°6).

**Point de contrôle** : T005 à T011 verts (sauf routes alimentées par les récits), `make test-api` et `make test-domain` verts.

## Phase 3 : Récit 1 — Dessiner une parcelle (P1)

### Tests RED (non-écran)
- [x] T021 [P] Unitaires domaine : aire, croisement, simplification Douglas-Peucker (≤ 500 sommets), < 3 points, surface nulle, chevauchement (avertissement non bloquant), surface déclarée distincte de la calculée, dans `packages/domain/tests/{area,geometry,overlap}.test.ts` et `services/api/tests/unit/test_f2_geometry.py` (R1-A2, R1-A3, R1-A5, CL).
- [x] T022 [P] Unitaires mobile : `apps/mobile/src/fields/__tests__/{drawSession,gpsWalk}.test.ts` (touches, tour GPS, précision, reprise/correction, signal faible) (R1-A1, R1-A4, CL).
- [x] T023 [P] Intégration API `services/api/tests/integration/test_fields_create.py` : `POST /v1/farms/{farm_id}/fields` (201 + surface serveur PostGIS, `warnings` chevauchement, 422 croisement/< 3 points/aire nulle/`outside_morocco`, `area_calc_ha` client ignoré, `area_declared_ha` conservée à part) ; `PATCH` et archivage (R1-A2 à A5, CL).
- [x] T024 [P] Intégration synchro hors ligne `services/api/tests/integration/test_fields_offline_sync.py` : parcelle GPS créée hors ligne puis rejouée via `/v1/sync/upload`, surface recalculée par le serveur, idempotence, conflit sans perte (`sync_conflicts`) (R1-A1, CL).
- [x] T025 [P] Contrat `services/api/tests/contract/test_fields_contract.py` (schémas `fields`, `geometry-rules.md`).
- [x] T026 [P] E2E service `services/api/tests/e2e/test_field_draw_e2e.py` : créer par touches puis par GPS, vérifier surface, croisement refusé, synchro au retour du réseau (R1-A1 à A5).

### Implémentation (non-écran)
- [ ] T027 `services/api/app/routers/fields.py` (create, patch, archive) et règles serveur ; fait passer T023 ; alimente T005, T006.
- [ ] T028 [P] `services/api/app/sync/fields.py` (apply `parcels`) ; fait passer T024.
- [ ] T029 [P] Mobile : `apps/mobile/src/fields/{drawSession.ts,gpsWalk.ts}` (expo-location, précision, simplification) ; fait passer T022.
- [ ] T030 [P] i18n `packages/i18n/locales/{ary,ar,fr}/fields.json` (dessin, erreurs de croisement, précision GPS).

### Écrans (dépendent de T004)
- [ ] T031 [écran] [P] [dépend de T004] Tests RED écrans F2-E2 dessin : touches et GPS, `PrecisionMeter`, explication visuelle du croisement, 4 états, miroir RTL, dans `apps/mobile/src/screens/FieldDraw/__tests__/` (R1-A3, R1-A4, CL).
- [ ] T032 [écran] [P] [dépend de T004] Test RED Maestro `apps/mobile/maestro/field_draw_taps.yaml` et `field_draw_gps.yaml` (R1-A1 à A5).
- [ ] T033 [écran] [dépend de T004, T031, T029, T036 (composants)] Écran `apps/mobile/src/screens/FieldDraw/` avec `packages/ui` (`DrawToolbar`, `PrecisionMeter`) et clés i18n `fields.json` ; fait passer T031 et T032.

## Phase 4 : Récit 2 — Nommer la parcelle et choisir sa culture (P1)

### Tests RED (non-écran)
- [x] T034 [P] Unitaires domaine : cycle pérenne (année de plantation) vs annuelle (date de semis), exclusivité des deux, estimation de stade, correction jamais écrasée par la réestimation, culture libre sans coefficients (conseils désactivés), dans `packages/domain/tests/{crop,season,phenology}.test.ts` et `services/api/tests/unit/test_f2_season_rules.py` (R2-A3, R2-A4, R2-A5).
- [x] T035 [P] Intégration API `services/api/tests/integration/test_crops.py` : `GET /v1/crops` renvoie les 16 cultures du référentiel avec photo, `POST /v1/farms/{farm_id}/crops` (culture libre privée à la ferme, 201 ; 403 ouvrier ; 404 non membre ; 422), culture libre invisible des autres fermes ; campagne initiale avec variété facultative, 422 dates incohérentes avec le cycle ; `PATCH` stade corrigé conservé, dans `services/api/tests/integration/test_season_stage.py` (R2-A1 à A5).
- [x] T036 [P] Contrat `services/api/tests/contract/test_crops_seasons_contract.py` ; unitaires UI des composants `packages/ui/src/components/{CropTile,PrecisionMeter,MapLegend,DrawToolbar}/__tests__/` (écrits seulement après T004 pour l'aspect visuel, la logique d'état avant).
- [x] T037 [P] E2E service `services/api/tests/e2e/test_crop_choice_e2e.py` : une parcelle pour chacune des 16 cultures et une culture libre (R2-A1 à A5).

### Implémentation (non-écran)
- [ ] T038 `services/api/app/routers/crops.py` et routes de campagne initiale dans `services/api/app/routers/seasons.py` ; fait passer T035 ; alimente T005, T006.
- [ ] T039 [P] Seed des 16 cultures (valeurs de stade marquées « non validées ») dans `services/api/alembic/versions/0004_fields_crops.py` et photos WebP < 400 Ko au total dans `apps/mobile/assets/crops/` ; `packages/i18n/locales/{ary,ar,fr}/crops.json`.
- [ ] T040 [P] `services/api/app/sync/fields.py` (apply `seasons`, `crops` libres).

### Écrans (dépendent de T004)
- [ ] T041 [écran] [P] [dépend de T004] Tests RED écrans F2-E3 fiche/formulaire et F2-E4 liste illustrée : 16 cultures avec photo, culture libre, variété facultative, année ou date selon le cycle, correction de stade, 4 états, RTL, dans `apps/mobile/src/screens/{FieldForm,CropPicker}/__tests__/` (R2-A1 à A5).
- [ ] T042 [écran] [P] [dépend de T004] Test RED Maestro `apps/mobile/maestro/crop_season.yaml` (R2-A1 à A5).
- [ ] T043 [écran] [dépend de T004, T041, T036] Écrans `apps/mobile/src/screens/FieldForm/`, `apps/mobile/src/screens/CropPicker/` avec `CropTile`.

## Phase 5 : Récit 3 — Irrigation et serre (P1)

### Tests RED (non-écran)
- [x] T044 [P] Unitaires domaine : cinq modes d'irrigation + non renseigné, serre booléen, `imagery_suitable` (< 0,3 ha ou serre) dans `packages/domain/tests/field.test.ts` (R3-A1, R3-A2, CL).
- [x] T045 [P] Intégration API `services/api/tests/integration/test_field_irrigation.py` : chaque mode et serre oui/non enregistrés et relus à la création et à la modification ; 422 mode inconnu (R3-A1, R3-A2).
- [x] T046 [P] E2E service `services/api/tests/e2e/test_irrigation_greenhouse_e2e.py` (R3-A1, R3-A2).

### Implémentation (non-écran)
- [ ] T047 Champs `irrigation`, `greenhouse`, `soil` dans `services/api/app/routers/fields.py` et schémas ; fait passer T044 à T046 ; clés i18n dans `fields.json`.

### Écrans (dépendent de T004)
- [ ] T048 [écran] [P] [dépend de T004] Tests RED écran F2-E3 (sélecteur d'irrigation et serre visibles sur la fiche, 4 états, RTL) dans `apps/mobile/src/screens/FieldForm/__tests__/irrigation.test.tsx` et Maestro `apps/mobile/maestro/field_irrigation.yaml` (R3-A1, R3-A2).
- [ ] T049 [écran] [dépend de T004, T048, T043] Sélecteur d'irrigation/serre dans `apps/mobile/src/screens/FieldForm/`.

## Phase 6 : Récit 4 — Carte de toutes les parcelles (P1)

### Tests RED (non-écran)
- [x] T050 [P] Unitaires mobile : GeoJSON local de toutes les parcelles, couleur par `status_summary` (`ok`/`watch`/`act`), couleur neutre distincte si NULL, parcelles chargées disponibles hors ligne, dans `apps/mobile/src/fields/__tests__/{mapData,offlineRegion}.test.ts` (R4-A1, R4-A2, R4-A4).
- [x] T051 [P] Intégration API `services/api/tests/integration/test_fields_list.py` : liste complète pour owner/manager (50 parcelles), ouvrier limité à ses parcelles (dupliqué volontairement avec T006 côté données), `status_summary` NULL -> champ nul ; archivées et ferme supprimée absentes (R4-A1, R4-A2).
- [x] T052 [P] Mesure SC-004 (RED, seuil initial) : `apps/mobile/src/fields/__tests__/map_perf.test.ts` — rendu de 50 parcelles < 2 s (mesure notée au gabarit de recette) (R4-A1).
- [x] T053 [P] E2E service `services/api/tests/e2e/test_field_map_e2e.py` : ferme de 50 parcelles, liste et fiche (R4-A1, R4-A3).

### Implémentation (non-écran)
- [ ] T054 `GET /v1/farms/{farm_id}/fields` et `GET .../fields/{field_id}` dans `services/api/app/routers/fields.py` ; `apps/mobile/src/fields/{mapData.ts,offlineRegion.ts}` ; `infra/tiles/` et tâche `services/workers/tasks/build_tiles.py` + cible `make tiles` ; clés `map.json`.

### Écrans (dépendent de T004)
- [ ] T055 [écran] [P] [dépend de T004] Tests RED écran F2-E1 carte : toutes les parcelles colorées, couleur neutre, ouverture de la fiche au toucher, hors ligne, `MapLegend`, 4 états, RTL, dans `apps/mobile/src/screens/FieldMap/__tests__/` et Maestro `apps/mobile/maestro/field_map.yaml` (R4-A1 à A4).
- [ ] T056 [écran] [dépend de T004, T055, T054] Écran `apps/mobile/src/screens/FieldMap/` (MapLibre, `MapLegend`).

## Phase 7 : Récit 5 — Découper ou fusionner (P2)

### Tests RED (non-écran)
- [ ] T057 [P] Unitaires domaine : bloc contenu dans la parcelle (tolérance 1 %), pas de chevauchement entre blocs, surface cumulée de fusion, fusion de campagnes de même culture active, contiguïté, dans `packages/domain/tests/{block,merge}.test.ts` (R5-A1, R5-A2).
- [ ] T058 [P] Intégration API `services/api/tests/integration/test_blocks.py` (201, 422 `block_outside_field`/`block_overlap`, 404 bloc d'une autre parcelle ou ferme, 403 ouvrier) et `test_field_merge.py` (surface cumulée, parcelle fusionnée archivée avec `merged_into_id`, campagnes conservées, 422 `merge_not_contiguous`, 404 inter-ferme, idempotence de la commande `field_commands`) (R5-A1, R5-A2).
- [ ] T059 [P] E2E service `services/api/tests/e2e/test_split_merge_e2e.py` : découper puis fusionner, vérifier surfaces et rattachements, rejeu hors ligne (R5-A1, R5-A2).

### Implémentation (non-écran)
- [ ] T060 `services/api/app/routers/blocks.py`, route `POST .../fields/merge`, `services/api/app/sync/fields.py` (`field_blocks`, `field_commands`).
- [ ] T061 [P] Archivage 90 jours : `GET .../fields/archived`, `POST .../restore`, `services/workers/tasks/purge_archived_fields.py` ; tests écrits avant dans `services/api/tests/integration/test_field_archive_restore.py` (restaurable ≤ 90 j, 404 après purge, 404 pour l'ouvrier) et `services/workers/tests/integration/test_purge_archived_fields.py` (CL).
- [ ] T062 [P] Export et purge de compte/ferme étendus (`services/api/app/accounts/export.py`) ; test écrit avant `services/api/tests/integration/test_f2_export_purge.py` (ouvrier : ses parcelles seulement).

### Écrans (dépendent de T004)
- [ ] T063 [écran] [P] [dépend de T004] Tests RED écrans F2-E5 découpage/fusion et F2-E8 archivées (4 états, RTL) dans `apps/mobile/src/screens/{SplitMerge,ArchivedFields}/__tests__/` et Maestro `apps/mobile/maestro/split_merge.yaml` (R5-A1, R5-A2, CL).
- [ ] T064 [écran] [dépend de T004, T063, T060, T061] Écrans `apps/mobile/src/screens/SplitMerge/` et `apps/mobile/src/screens/ArchivedFields/`.

## Phase 8 : Récit 6 — Nouvelle campagne (P2)

### Tests RED (non-écran)
- [ ] T065 [P] Unitaires domaine : une seule campagne active par parcelle et par culture, rotation (clôture de la précédente), cultures associées simultanées, dans `packages/domain/tests/season.test.ts` et `services/api/tests/unit/test_f2_season_rules.py` (R6-A1 à A3).
- [ ] T066 [P] Intégration API `services/api/tests/integration/test_seasons_rotation.py` : rotation avec `close_ids` (précédente clôturée et consultable), 409 `season_already_active` pour la même culture, deux cultures actives simultanées, 403 ouvrier, 404 campagne d'une autre parcelle ou ferme ; index unique partiel respecté sous concurrence (R6-A1 à A3).
- [ ] T067 [P] E2E service `services/api/tests/e2e/test_seasons_e2e.py` : enchaîner deux campagnes, consulter la première (R6-A1 à A3).

### Implémentation (non-écran)
- [ ] T068 Rotation, clôture et historique dans `services/api/app/routers/seasons.py` et `services/api/app/domain/season_rules.py` ; clés `seasons.json` (R6).

### Écrans (dépendent de T004)
- [ ] T069 [écran] [P] [dépend de T004] Tests RED écran F2-E6 campagnes et historique (blocage explicité de la double campagne, 4 états, RTL) dans `apps/mobile/src/screens/Seasons/__tests__/` et Maestro `apps/mobile/maestro/seasons.yaml` (R6-A1 à A3).
- [ ] T070 [écran] [dépend de T004, T069, T068] Écran `apps/mobile/src/screens/Seasons/`.

## Phase 8b : Plafond de ressources géométriques (correctif sécurité DoS)

- [ ] T075 [P] Tests RED unitaires : longueur BRUTE de l'anneau > MAX_VERTICES+1 refusée `too_many_vertices` avant `self_crossings` ; total de sommets d'un import > 20 000 -> `too_many_vertices_total`, dans `services/api/tests/unit/test_f2_geometry_resource_cap.py` et `packages/domain/tests/geometry-resource-cap.test.ts`.
- [ ] T076 GREEN : contrôle de longueur brute dans `validate_ring`/`validateRing` avant déduplication et crossings ; constante `MAX_IMPORT_VERTICES_TOTAL = 20000` et erreur `too_many_vertices_total` dans `import_features`/`importFeatures` (`services/api/app/domain/geometry.py`, `packages/domain/src/geometry.ts`).
- [ ] T077 [P] Tests RED intégration `services/api/tests/integration/test_f2_geometry_resource_cap.py` et E2E `services/api/tests/e2e/test_geometry_resource_cap_e2e.py` : POST parcelle et sync put avec anneau géant -> 422 / opération non appliquée, rapide, sans timeout.
- [x] T078 Les routes parcelles et la synchro refusent déjà un anneau géant (`check_polygon` plafonne la longueur brute, 422 `geometry_vertices`) ; T077 est donc un test de non-régression (déjà vert), aucun code requis.

## Phase 9 : Finition

- [ ] T071 REFACTOR global (commit `refactor(003-fields-crops): ...`) : retirer `parcels.vigor` après migration des lecteurs F0, supprimer les doublons, tests toujours verts.
- [ ] T072 Mesures de recette SC-001 à SC-004 dans le gabarit de recette (première parcelle < 3 min, 30 jours hors ligne, aire à 1 %, carte 50 parcelles < 2 s) ; couverture du code métier ≥ 80 %.
- [ ] T073 `make check` vert (lint, typecheck, tests, couverture, visuel, taille APK < 40 Mo, diagrammes, e2e).
- [ ] T074 Documentation de fin de module (`/aylal.docs`) : `docs/modules/003-fields-crops/{ingenieur.md,agriculteur.fr.md,agriculteur.ar.md,diagrams/*.mmd,img/*}`, rendus par `make diagrams`.

## Dépendances

- T004 (porte design) bloque **toutes** les tâches `[écran]` : T031 à T033, T041 à T043, T048 à T049, T055 à T056, T063 à T064, T069 à T070. Les tâches non-écran de chaque récit avancent sans attendre T004.
- Dans chaque récit : tests RED -> implémentation -> écrans (tests écran avant écran).
- T005, T006, T007, T007b (RED inter-ferme/rôles/synchro) précèdent T015 à T018 et chaque route de récit ; T005 et T006 restent rouges jusqu'à ce que toutes les routes existent, puis doivent être verts avant T073.
- T033 dépend des composants `packages/ui` (T036) ; T012 et T013 précèdent tous les récits.
- Ordre : Phase 3 à 6 (P1) puis Phase 7 et 8 (P2).

## Reportés (P3, exclus)

- Récit 7 — Importer des parcelles depuis un fichier KML/Shapefile (P3) : écran F2-E7, `apps/mobile/src/fields/import/{kml,shapefile}.ts`, `vectors/f2_import.json`. Reporté ; le plan prévoit une analyse sur l'appareil sans téléversement lorsqu'il sera repris.
