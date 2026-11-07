# Plan d'implémentation : F2 — Parcelles et cultures

**Branche** : `003-fields-crops` | **Date** : 2026-11-07 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F2 + CPS sections 4, 7, 15, 16, 17, 19 + constitution + livrables F0/F1 fusionnés (`farm_context`, rôles `owner/manager/worker`, `worker_parcels`, sync par rôle, `/v1/sync/upload`, jetons de design)

## Résumé

F2 transforme la table F0 `parcels` en **Field** complet (géométrie, surface calculée + déclarée, irrigation, serre, sol, archivage 90 j) et ajoute **crops** (référentiel de 16 cultures + cultures libres privées à la ferme), **seasons** (campagnes, une active par parcelle et par culture), **field_blocks** (blocs/secteurs) et la commande de fusion. Approche :
- toute règle (aire, croisement, chevauchement, contenance des blocs, règles de campagne, estimation de stade, parcelle peu adaptée à l'imagerie) dans `packages/domain` (Zod -> JSON Schema -> Pydantic, vecteurs JSON partagés) et recalculée par le serveur, qui fait foi (aire serveur par PostGIS `geography`) ;
- API sous `/v1/farms/{farm_id}/fields|seasons|crops`, toujours derrière `farm_context`/`require(action)` ; écritures hors ligne par `/v1/sync/upload` avec le même contrôle de rôle ;
- dessin par touches (carte MapLibre) ou GPS (`expo-location`, précision affichée, simplification Douglas-Peucker) ; carte de toutes les parcelles (GeoJSON local, couleur neutre si état inconnu) ;
- import KML/Shapefile **analysé sur l'appareil** (aucun fichier envoyé), revalidé par le serveur à la synchro ;
- fonds de carte et satellite servis par l'infrastructure AYLAL au Maroc (PMTiles dans MinIO derrière Caddy), jamais par un tiers. Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x strict, Python 3.13.
**Dépendances** : celles de F0/F1. Ajouts mobiles minimaux : `@maplibre/maplibre-react-native` (déjà imposé par la stack), `expo-location` (déjà F1), `expo-document-picker`, `@tmcw/togeojson` (KML), `shpjs` + `proj4` (Shapefile zip + reprojection), `pmtiles` (protocole de tuiles). Ajouts API : aucun parseur de fichier ; `shapely` uniquement si un test de vecteur l'exige (sinon PostGIS suffit). Aucun SaaS étranger.
**Stockage** : PostgreSQL 16 + PostGIS (`parcels`, `field_blocks` en `geometry(Polygon,4326)`, index GiST), SQLite local (PowerSync), MinIO (PMTiles, photos de cultures), Redis (inchangé).
**Tests** : pytest (unit, integration, contrat, e2e), Vitest (domain, vecteurs partagés), Jest + RNTL (écrans, view models), Maestro (parcours E2E).
**Plateforme** : Android 9+, 2 Go de RAM ; API Linux conteneurisée.
**Type** : monorepo mobile + API + workers.
**Performance** : carte de 50 parcelles < 2 s sur Android d'entrée de gamme (SC-004) ; aire à 1 % près (SC-003, tolérance de vecteur 0,5 %) ; première parcelle < 3 min (SC-001) ; 100 % des croisements détectés avant enregistrement (SC-005) ; 30 jours hors ligne sans perte (SC-002) ; photos de cultures embarquées en vignettes WebP < 400 Ko au total (app < 40 Mo).
**Contraintes** : hors ligne complet (création, modification, découpe, fusion, archivage, restauration) ; hébergement Maroc ; gratuit ; 4 états et RTL par écran.
**Échelle** : 8 écrans (F2-E1 à F2-E8), ~22 routes, 5 tables nouvelles + extension de `parcels`, 1 migration (`0004_fields_crops`).

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| I Agriculteur d'abord | OK | Dessin guidé par illustrations, cultures en photos, voix sur chaque écran, un objectif par écran |
| II Hors ligne | OK | Toutes les opérations écrivent en local (PowerSync) ; fusion par commande idempotente rejouée au retour du réseau ; conflits sans perte (`sync_conflicts`) |
| III Gratuit/sobre | OK | Pas de fournisseur de cartes payant : PMTiles auto-hébergés, zones téléchargées en Wi-Fi ou à la demande ; GeoJSON local |
| IV Données à l'utilisateur | OK | Parcelles, campagnes, blocs et cultures libres ajoutés à l'export et à la purge de compte/ferme |
| V Conseil prudent | OK | Culture libre sans coefficients : conseils désactivés ; valeurs de stade du référentiel marquées « non validées » tant que l'agronome ne les a pas validées |
| VI Logique unique | OK | `packages/domain` + schémas générés + vecteurs partagés TS/Python |
| VII Petits téléphones | OK | Simplification des tracés, ≤ 500 sommets par parcelle, couches vectorielles simples, mesure SC-004 |
| VIII/XI Test first | OK | RED -> GREEN -> REFACTOR, un test par critère P1 |
| IX i18n | OK | Clés `ary`, `ar`, `fr` (`fields`, `crops`, `seasons`, `map`), aucune chaîne en dur |
| X Design | OK | Porte design : maquettes HD arabe + français validées avant tout écran (tâche de porte, comme F1/T004) |
| XII Docker | OK | Aucun service nouveau ; générateur de tuiles et tests dans les conteneurs existants |
| XIII Maroc | OK sous condition | Tuiles, satellite, photos et API hébergés au Maroc ; l'app n'appelle aucun serveur de cartes étranger (test d'allowlist) ; emprise des parcelles limitée au Maroc |
| XV Seuils | OK | Mesures SC-001 à SC-004 prévues en recette |

### Garde-fous obligatoires (leçons F0/F1)

1. **Accès toujours scopé à la ferme, 404 inter-ferme.** Toutes les routes passent par `farm_context(farm_id)` / `require(action)` (`app/auth/farm_context.py`). Non-membre (ou membre retiré) = **404** identique à « ferme inexistante ». Les objets enfants (parcelle, bloc, campagne, culture libre) sont **toujours chargés avec `farm_id` dans la clause WHERE** ; une parcelle d'une autre ferme dans l'URL donne 404 même si l'ID existe. Clés étrangères **composites** `(farm_id, field_id)`, `(farm_id, crop_id)` en base pour interdire toute référence inter-ferme. Tests inter-ferme obligatoires sur **chaque** route (matrice route x rôle x ferme).
2. **403 par rôle ; ouvrier limité à ses parcelles.** Matrice `app/domain/roles.py` + `roles.ts` étendue (`field.create|update|archive|restore|merge|split`, `season.manage|stage_correct`, `crop.create_custom` = owner/manager ; `field.read` = owner/manager + ouvrier **si la parcelle figure dans `worker_parcels`**). Décision : un ouvrier qui lit/écrit une parcelle **non attribuée** reçoit **404** (invisible, aucune fuite d'existence) ; sur une parcelle attribuée, toute action de gestion donne **403**. La liste des parcelles, des campagnes et des blocs est filtrée en SQL par `worker_parcels` (jamais en post-filtrage mémoire). Les règles PowerSync ouvrier reprennent la même restriction (liste blanche de colonnes) et exigent en plus, pour tout enfant de parcelle (campagnes, blocs), que la parcelle parente soit attribuée ET non archivée (`field_id IN (SELECT id FROM parcels WHERE farm_id = bucket.farm_id AND archived_at IS NULL AND …)`) : parcelle archivée = plus aucune donnée synchronisée ni lisible par l'ouvrier.
3. **Même contrôle sur la synchro.** `/v1/sync/upload` applique à chaque opération sur `parcels`, `seasons`, `field_blocks`, `crops` (personnalisées), `field_commands` le même `authorize` que REST (rôle + appartenance + visibilité ouvrier) ; un ouvrier : 403 pour tout le lot, rien d'écrit ; non-membre : 404. Le client ne fixe jamais `farm_id` d'un enregistrement existant, `area_calc_ha`, `status_summary`, `created_by`, `archived_at` hors action autorisée : champs serveur ignorés/rejetés. Lever la limite F1 « ferme créée dans le même lot » : `authorize` tient compte des fermes créées plus tôt dans le lot par le même utilisateur (parcours : première ferme + première parcelle hors ligne).
4. **Parcelle ou ferme supprimée = 404.** Toute requête joint `farms.deleted_at IS NULL` (clôture du constat F1 n° 3, dans `farm_role`/`farm_context`/`authorize`) et `parcels.archived_at IS NULL` sur les routes normales : une parcelle archivée répond 404 sur sa fiche, ses blocs et ses campagnes ; seules `GET .../fields/archived` et `POST .../restore` la voient (owner/manager, ≤ 90 j). Après purge définitive : 404 partout, y compris restauration. Aucune écriture (REST ou synchro) sur une ferme ou parcelle supprimée.
5. **Aucun secret par défaut.** F2 n'introduit aucun secret. Les identifiants MinIO du bucket de tuiles/photos viennent de l'environnement existant (`${VAR:-}` vide dans `docker-compose.yml`, refus de démarrer hors dev/test si absents). Aucune clé de fournisseur de cartes (il n'y en a pas). Un test de configuration vérifie qu'aucune valeur d'identifiant ni URL de tuiles externe n'est codée en dur.
6. **Aucune donnée hors Maroc.** Les géométries sont des données personnelles : hébergées au Maroc, jamais envoyées à un tiers. Le style de carte de l'app ne référence que `AYLAL_TILES_BASE_URL` (test d'allowlist sur le style et sur le code mobile : aucun domaine tiers de tuiles/géocodage). Import de fichier analysé localement, jamais téléversé. Géométrie dont le centroïde sort de l'emprise du Maroc : 422 `outside_morocco`.
7. **Entrées bornées** : ≥ 3 sommets distincts, ≤ 500 sommets, aire > 0 et ≤ 5 000 ha, ≤ 500 parcelles par ferme, nom ≤ 80 car., variété ≤ 80 car. ; validation Zod côté client et Pydantic + PostGIS (`ST_IsValid`, `ST_IsSimple`) côté serveur.

## Structure du projet

### Documentation

```text
specs/003-fields-crops/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/ (openapi.yaml, geometry-rules.md, powersync-sync-rules.yaml)
└── tasks.md   # produit par /speckit-tasks
docs/design/003-fields-crops/   # maquettes HD ar + fr (porte design, avant tout écran)
```

### Code source (réutilise F0/F1, ajoute seulement ce qui est requis)

```text
packages/domain/src/{geometry,area,overlap,field,crop,season,phenology,block,merge,field-import}.ts   # règles + Zod
packages/domain/vectors/f2_{area,self_intersection,overlap,season_rules,merge,import}.json           # partagés TS/Python
packages/i18n/locales/{ary,ar,fr}/{fields,crops,seasons,map}.json
packages/ui/src/components/{CropTile,PrecisionMeter,MapLegend,DrawToolbar}/   # demandés au design system (voir Porte design)
services/api/app/domain/{geometry.py,season_rules.py,field_rules.py}          # miroirs Python
services/api/app/routers/{fields.py,seasons.py,blocks.py,crops.py}
services/api/app/sync/fields.py                                               # authorize + apply pour les nouvelles tables
services/api/app/db/models.py (+ Crop, Season, FieldBlock, FieldCommand ; Parcel étendu)
services/api/alembic/versions/0004_fields_crops.py                            # + seed des 16 cultures
services/api/app/accounts/export.py (étendu) ; purge (étendue)
services/workers/tasks/{purge_archived_fields.py,build_tiles.py}
infra/powersync/sync-rules.yaml (étendu) ; infra/tiles/ (pmtiles Maroc, script de génération Docker)
apps/mobile/src/screens/{FieldMap,FieldDraw,FieldForm,CropPicker,SplitMerge,Seasons,FieldImport,ArchivedFields}/
apps/mobile/src/fields/{drawSession.ts,gpsWalk.ts,mapStyle.ts,import/{kml,shapefile}.ts,offlineRegion.ts}
apps/mobile/maestro/{field_draw_taps,field_draw_gps,crop_season,field_map,split_merge,import_file}.yaml
```

**Décision de structure** : pas de nouveau service Docker ; le worker existant exécute les tâches ; le générateur de tuiles est un job `make tiles` dans l'image worker. Cibles `Makefile` existantes inchangées (nouveaux tests découverts par les cibles actuelles ; ajout de `make tiles` seulement).

## Porte design (obligatoire, comme F1/T004)

Aucun écran F2 n'est codé avant validation humaine des maquettes haute fidélité, arabe et français, dans `docs/design/003-fields-crops/` : F2-E1 carte des parcelles, F2-E2 dessin (touches et GPS, précision, croisement expliqué visuellement), F2-E3 fiche et formulaire, F2-E4 liste illustrée des cultures (P1) ; puis F2-E5 découpage/fusion, F2-E6 campagnes et historique, F2-E8 archivées (P2) ; F2-E7 import (P3). Chaque écran : 4 états (chargement, vide, erreur, hors ligne) et miroir RTL. Les écrans sont composés **uniquement** de composants de `packages/ui` et de jetons du design system (`docs/design/aylal-design-system.md`, source de vérité). Les composants manquants (`CropTile`, `PrecisionMeter`, `MapLegend`, `DrawToolbar`) sont demandés au design system par une note dans `specs/003-fields-crops/decisions.md` ; le fichier du design system n'est pas modifié par cette fonctionnalité. Les tâches d'écran dépendent de la tâche de porte. La logique hors écran (domaine, API, synchro, view models) n'est pas bloquée.

## Vérification de la constitution (après conception)

Inchangé : OK. Écarts signalés à `tasks` :
- migration `0004` : `parcels.vigor` (F0) devient nullable ; `status_summary` (écrit par F3 côté serveur) le remplace pour la carte ; non-régression des tests ACL/sync F0-F1 ;
- clôture du constat F1 n° 3 (`deleted_at`) et de la limite « ferme créée dans le même lot » comme prérequis RED du récit 1 ;
- points ouverts non bloquants : source des photos de cultures sous licence libre, validation agronomique des seuils de stade, orthophoto satellite Maroc (mosaïque Sentinel-2 en 10 m par défaut), emprise exacte du Maroc (HCP). Chacun est isolé derrière une donnée de référentiel ou un port.

## Suivi de complexité

Aucune violation.
