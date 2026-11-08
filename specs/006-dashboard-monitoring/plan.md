# Plan d'implémentation : F3 — Tableau de bord et monitoring

**Branche** : `006-dashboard-monitoring` | **Date** : 2026-11-07 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F3 + CPS sections 4, 6, 8, 15, 16, 17, 19 + constitution + livrables F0/F1/F2/F6 fusionnés (`farm_context`/`require`, `app/domain/roles.py`, `worker_parcels`, `/v1/sync/upload`, `parcels.archived_at`, `seasons.stage_*`, `operation_parcels`, `app/auth/client_ip.py` + `AYLAL_TRUSTED_PROXIES`, `app/operations/body_limit.py`, verrou `pg_advisory_xact_lock`, `label_uploads` (modèle d'objet opaque), `infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`, `accounts/export.py`, `accounts/purge.py`, workers Arq).

## Résumé

F3 ajoute le **tableau de bord** (météo J+7, liste des parcelles par état), les **alertes météo par culture et par stade**, la **vigueur satellite** (carte + courbe + comparaison N-1), les **zones à vérifier** (détection, guidage GPS hors ligne, observation rattachée), l'**état résumé en couleur** par parcelle et le **résumé vocal**. Approche :
- toute règle (seuils, sévérité, état, tri, détection d'anomalie, fiabilité d'imagerie, calendrier de notification) dans `packages/domain` (Zod -> JSON Schema -> Pydantic, **vecteurs JSON partagés TS/Python**) ; le serveur calcule et fait foi, le mobile affiche et recompose le résumé vocal localement ;
- **état de parcelle = modèle de lecture dénormalisé** (`parcel_status`) recalculé par worker à chaque signal ; sources = **registre d'adaptateurs** (météo, vigueur, F6 « opérations en retard » disponible ; F4/F5 absents = ignorés sans erreur, FR-013) ;
- **un seul module d'accès** `app/monitoring/access.py` (`visible_parcels(ctx)`) appelé par REST, synchro, export, purge, agrégats, caches, workers de notification : parité de garde entre chemins frères ;
- **sources externes derrière des passerelles configurables, vides par défaut** (météo, imagerie, push) : rien n'est envoyé hors Maroc, rien n'est inventé (« non disponible ») ;
- notifications : **locales** (programmées sur l'appareil à partir des alertes synchronisées, hors ligne) + push optionnel via passerelle auto-hébergée ; **voix = synthèse native de l'appareil**, aucun TTS étranger. Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x strict, Python 3.13.
**Dépendances** : celles de F0-F2/F6. Ajouts API/worker : `numpy`, `rasterio` (+ GDAL dans l'image worker) et `shapely` (déjà présent via géométrie F2 si oui) pour statistiques zonales NDVI/NDMI et détection de zones ; `Pillow` (rendu PNG de la carte de vigueur). Ajouts mobiles : `expo-speech` (voix native), `expo-notifications` (locales, déjà F6), `expo-location` (guidage), MapLibre déjà présent (fonds mis en cache, F2). Aucun SaaS étranger, aucune clé FCM/Google.
**Stockage** : PostgreSQL 16 + PostGIS (10 tables nouvelles, migration `0010_dashboard_monitoring`, numéro à recaler sur le prochain libre au moment de fusionner), SQLite local PowerSync, MinIO (cartes de vigueur, rasters de tuile, photos d'observation), Redis/Arq (météo, imagerie, détection, états, notifications).
**Tests** : pytest (unit, integration, contrat, e2e), Vitest (domain + vecteurs), Jest + RNTL (view models, écrans), Maestro (parcours).
**Plateforme** : Android 9+, 2 Go RAM ; API Linux conteneurisée.
**Performance** : tableau de bord affiché < 2 s depuis SQLite (200 parcelles) ; SC-001 30 s ; historique 12 mois d'une nouvelle parcelle < 10 min dans 95 % des cas (SC-002) ; liste des états recalculée < 5 min après un signal ; sync initiale du suivi ≤ 1 Mo par ferme de 50 parcelles ; budget app < 40 Mo inchangé (aucune bibliothèque de graphes lourde : courbe en SVG/Skia).
**Contraintes** : hors ligne complet (données datées partout) ; hébergement Maroc ; gratuit ; 4 états + RTL par écran.
**Échelle** : 8 écrans (F3-E1 à F3-E8), ~14 routes, 10 tables, 1 migration, 6 tâches workers.

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| I Agriculteur d'abord | OK | Couleur + phrase + icône, tri rouge puis orange, voix |
| II Hors ligne | OK | Dernières données datées ; alertes -> notifications locales ; guidage cap/distance sans réseau |
| III Gratuit/sobre | OK | Sentinel-2 et météo gratuits via passerelles ; pas de push tiers payant ; TTS natif |
| IV Données à l'utilisateur | OK | Tables F3 ajoutées à l'export de compte et à la purge (garde-fou G1) |
| V Conseil prudent | OK | Doute = orange ; imagerie peu fiable signalée ; sources expliquées ; seuils validés agronomie |
| VI Logique unique | OK | `packages/domain` + vecteurs partagés |
| VII Petits téléphones | OK | Séries plafonnées, cartes PNG pré-rendues serveur, pas de raster sur l'appareil |
| VIII/XI Test first | OK | RED -> GREEN -> REFACTOR, un test par critère P1 |
| IX i18n | OK | Clés `ary/ar/fr` : `dashboard`, `weather`, `alerts`, `vigor`, `zones`, `status`, `summary` ; « vigueur » / « humidité des plantes » seuls mots affichés |
| X Design | OK sous condition | Porte design T004-like (G7) |
| XII Docker | OK | Aucun service permanent nouveau ; worker existant ; GDAL dans l'image worker |
| XIII Maroc | OK sous condition | Garde-fou G5 : passerelles Maroc/configurables, aucune géométrie ni donnée personnelle sortante |
| XIV Documentation | OK | `docs/modules/006-dashboard-monitoring/` en fin de fonctionnalité |
| XV Seuils | OK | SC-001 à SC-007 mesurés en recette ; couverture domaine >= 80 % |

## Garde-fous obligatoires (leçons F0–F6)

Chaque point = **une tâche RED puis une tâche GREEN** dans `tasks.md` (`G<n>-RED` / `G<n>-GREEN`, avant les tâches de récit qui en dépendent).

### G1 — Accès scopé, rôles, parité de tous les chemins
- **404 inter-ferme = 404 ferme inconnue** : toutes les routes `/v1/farms/{farm_id}/…` passent par `farm_context`/`require(action)` ; non-membre, membre retiré, ferme inexistante ou **supprimée** (`farms.deleted_at`) -> **404** de corps identique (`{"detail":"not_found"}`). Toute lecture (alerte, zone, scène, point de vigueur, état, résumé) filtre `farm_id` dans le WHERE ; clés étrangères composites `(farm_id, parcel_id)`.
- **Matrice des droits** (`roles.py` + `roles.ts`, vecteur `f3_roles.json`) ; CPS §6 : l'ouvrier ne voit que ses parcelles, aucun montant ; §8 muet sur les rôles -> clarification de la spec (propriétaire/gestionnaire = toutes ; ouvrier = attribuées).

| Action | owner | manager | worker |
| --- | --- | --- | --- |
| `dashboard.read`, `weather.read` | oui | oui | oui (liste/agrégats **limités à ses parcelles**) |
| `status.read`, `alert.read`, `vigor.read`, `zone.read` | toutes | toutes | **attribuées et non archivées** |
| `zone.observe` (observation rattachée) | oui | oui | oui, parcelles attribuées seulement |
| `zone.dismiss`, `alert.dismiss` | oui | oui | **403** |
| `imagery.reprocess` | oui | oui | **403** |
| `summary.read`, `summary.settings` (les siens) | oui | oui | oui, **calculé sur sa portée** |
| `monitoring.read_cost` | — | — | aucun champ financier dans F3 |

  Ouvrier sur parcelle **non attribuée**, **archivée** ou inexistante : **404** identique ; parcelle attribuée mais action de gestion : **403**. Ferme supprimée : 404 pour tous.
- **Archivée masquée PARTOUT** : un seul prédicat `visible_parcels(ctx)` (SQL) : `farm_id = :farm AND archived_at IS NULL` (+ `id IN worker_parcels` pour l'ouvrier). Il est appelé par : REST (dashboard, états, alertes, zones, vigueur, comparaison), `sync/monitoring.py` (écriture d'observation), règles PowerSync (`parcel_archived_at IS NULL`), `accounts/export.py` (export de l'ouvrier ; le staff retrouve l'historique archivé en lecture seule), `accounts/purge.py`, **agrégats** (compteurs, tri, résumé vocal), workers de notification (destinataires **et** parcelles par destinataire), caches. Pour owner/manager, la **fiche historique** d'une parcelle archivée reste lisible en lecture seule (vigueur) mais n'apparaît ni dans le tableau de bord, ni dans les agrégats, ni ne génère d'alerte (FR-019).
- **Parité des chemins frères** : un **test de parité paramétré** exécute la même matrice (rôle × ferme {propre, autre, inconnue, supprimée} × parcelle {attribuée, non attribuée, archivée, inconnue} × chemin {REST, sync upload, export, résumé, agrégat}) et exige des statuts/contenus identiques ; un **test d'inventaire** échoue si une route, une table ou une tâche worker F3 n'apparaît pas dans la matrice.
- **Synchro** : le lot `/v1/sync/upload` est refusé entier (403) si une écriture viole le rôle ; non-membre -> 404 ; champs serveur (`farm_id` d'un enregistrement existant, `author_id`, `photo_key`, `status` de zone, `parcel_archived_at`) ignorés/rejetés.

### G2 — Agrégats sans fuite
Tout total, compte, moyenne ou rang est **calculé sur la portée de l'appelant** : `SELECT … FROM parcel_status WHERE <visible_parcels>`. Aucun compteur n'est lu d'une table de ferme (`farms.area_ha`, nombre total de parcelles) ni d'un cache partagé. Le résumé (`counts.red/orange/green`, surface, moyenne de vigueur) d'un ouvrier est identique à celui calculé à la main sur ses seules parcelles ; la réponse ne contient aucun champ « total ferme ». Tests : ferme à 10 parcelles dont 3 attribuées à l'ouvrier, une rouge invisible -> compteurs, moyennes, `ETag`, ordre, résumé vocal et notification de l'ouvrier ne changent pas quand une parcelle invisible change d'état (invariance), et un ouvrier sans parcelle voit 0 partout (pas 404, pas de total ferme). **Clé de cache** : `dash:{farm_id}:{role}:{user_id si worker}:{sha256(ids visibles triés)}:{data_version}` ; le staff partage par ferme+rôle+empreinte ; invalidation par `data_version` de la ferme. Test : deux rôles/portées distincts ne partagent jamais une entrée.

### G3 — PowerSync : ni jointure ni sous-requête
Le service refuse jointures et sous-requêtes (`infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`). Chaque table synchronisée porte **dénormalisés** : `farm_id`, `parcel_id`, `parcel_archived_at` (posé par triggers serveur à l'archivage/restauration/fusion, comme `operation_parcels`), `user_id` pour le résumé vocal (un destinataire par ligne), et les libellés/clés i18n utiles (`crop_slug`, `reason_key`, `reason_params`). **Seaux par utilisateur** : tout seau paramétré par l'utilisateur (`user_summaries`, `farm_worker_weather`, `farm_worker_monitoring`) est soumis à l'appartenance ACTIVE (`farm_members ... removed_at IS NULL`, ou `worker_parcels` purgé à la sortie) et filtre ses données par `(farm_id, user_id)` ; jamais par `request.user_id()` seul. Retrait d'un membre, changement de rôle et suppression/purge de ferme purgent `daily_summaries` et `notification_prefs` dans la même transaction (REST, synchro et export refusent ensuite : 404). Le seau ouvrier réutilise la requête de paramètres à une colonne (`parcel_id`) sans sous-requête ; la météo (niveau ferme, sans parcelle) a son propre seau ouvrier par `farm_id`. **Colonnes explicites** (jamais `SELECT *`) : `photo_key`, `map_key`, `raster_key` ne sont jamais synchronisés. Voir [contracts/powersync-sync-rules.yaml](contracts/powersync-sync-rules.yaml). RED = étendre `validate-sync-rules.sh` + `tests/platform/test_powersync_rules_valid.sh` (échec attendu) ; GREEN = colonnes, triggers de recopie, règles. Test d'intégration : archiver une parcelle retire ses lignes (états, alertes, zones, points) du seau ouvrier **et** du seau staff (hors historique de vigueur).

### G4 — Plafonds avant tout calcul coûteux, quotas et verrous par ferme
Contrôles **avant** parsing lourd, I/O réseau, lecture de raster ou rendu (taille de corps lue d'abord : 413/422 immédiat, `body_limit.py`). Constantes dans `app/domain/monitoring_limits.py` + `monitoring-limits.ts` (vecteur `f3_limits.json`) :

| Ressource | Plafond |
| --- | --- |
| Parcelles par page de tableau de bord | `limit` ≤ 100 (défaut 50), curseur ; parcelles suivies par ferme ≤ plafond F2 (traitement imagerie jamais au-delà de 200) |
| Fenêtre de série de vigueur | ≤ 24 mois ; ≤ 400 points par réponse ; comparaison N-1 ≤ 2 × 200 points alignés |
| Prévision météo | 8 jours (J0 + 7) ; refus de tout autre horizon |
| Alertes actives par ferme | ≤ 1 000 ; par parcelle ≤ 20 (écrasement du plus ancien résolu, jamais d'insertion non bornée) |
| Zones ouvertes | ≤ 5 par parcelle, ≤ 200 par ferme ; polygone ≤ 200 sommets |
| Observations de zone | note ≤ 500 car. ; 1 photo ≤ 3 Mo (JPEG/WebP, signature vérifiée) ; ≤ 20 par zone ; ≤ 2 000 par ferme et par an |
| Lot `/v1/sync/upload` | ≤ 100 opérations (413 `batch_too_large` avant toute écriture) |
| Traitement initial d'une parcelle | 1 backfill actif par parcelle ; ≤ 5 jobs d'imagerie simultanés par ferme ; retraitement manuel ≤ 3 par parcelle et par jour |
| Passerelle météo | 1 appel par cellule 0,1° et par 3 h (verrou Redis) ; budget global journalier configurable ; pas d'appel déclenché par une requête utilisateur (lecture cache seulement) |
| Passerelle imagerie | téléchargement par **tuile** (pas par parcelle) ; taille de raster ≤ 500 Mo par scène ; fenêtre ≤ 12 mois à l'initialisation |
| Débit | limiteur Redis par IP/utilisateur/ferme (G6) ; 429 `Retry-After` |

**Quotas sous verrou** : création d'observation et de job de retraitement -> `SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` (clé identique à `fields/service.py` et F6), comptage, écriture dans la même transaction, **y compris sur le chemin synchro**. Test de course à 2 requêtes concurrentes par quota, REST et synchro. Idempotence par `applied_ops` (acquis F0). Les workers prennent un verrou consultatif par ferme (`monitoring:{farm}`) pour qu'un recalcul d'états n'entre pas en concurrence avec lui-même. Tests RED : refus des dépassements **avant** tout appel passerelle/lecture de raster (espion sur l'adaptateur : zéro appel).

### G5 — Sources externes : Maroc, donnée minimale, dégradation honnête
- **Passerelles configurables, URLs vides par défaut** : `AYLAL_WEATHER_URL`, `AYLAL_IMAGERY_URL`, `AYLAL_PUSH_URL`, `AYLAL_EXTERNAL_ALLOWED_HOSTS` (liste blanche, vide = tout refusé). Vide ou hôte hors liste -> la fonction répond `availability: "unavailable"` avec `reason` (`gateway_not_configured`, `gateway_unreachable`, `stale`) ; **jamais de valeur inventée, interpolée ou par défaut**. Hors dev/test, un hôte hors liste explicite refuse le démarrage ; la liste doit nommer des hôtes hébergés au Maroc (ou un maître hôte AYLAL) — documenté dans `contracts/external-gateways.md`.
- **Minimisation sortante** : météo -> uniquement `{lat_r, lon_r}` arrondis à 0,1° (~11 km, cellule partagée entre fermes) et dates ; **ni identifiant de ferme/utilisateur, ni nom, ni numéro, ni géométrie de parcelle**. Imagerie -> uniquement un identifiant de **tuile publique** (MGRS) et une date ; les statistiques zonales (NDVI/NDMI) sont calculées **dans le worker au Maroc** sur le raster rapatrié : la géométrie de la ferme ne quitte jamais le serveur. Push -> charge utile sans donnée personnelle : `{device_token, alert_id opaque, locale}` ; le texte est composé sur l'appareil par clés i18n. Tests : adaptateur espion + schéma d'allowlist de charge utile (clés exactes) ; test de configuration sans valeur secrète par défaut ; test d'inventaire d'imports (aucun SDK d'un fournisseur étranger).
- **Aucun secret par défaut** : `docker-compose.yml` utilise `${VAR:-}` vides pour toutes les clés de passerelle ; démarrage refusé hors dev/test si une URL est fournie sans clé requise ; aucune clé en dépôt.
- **Image satellite** : si la couverture sans nuage de la parcelle < 80 % la scène est enregistrée `rejected_cloud` (jamais affichée), la dernière scène valide reste servie avec sa date (FR-007, SC-004) ; test paramétré 79,9 / 80,0 %.
- **Fraîcheur** : toute donnée servie porte `observed_at`/`fetched_at` ; la météo plus vieille que 24 h est marquée `stale` côté serveur et côté mobile.

### G6 — Identifiants d'objets, URL signées, X-Forwarded-For
- **Le client n'envoie JAMAIS une clé de stockage ni une URL** : cartes de vigueur et photos sont référencées par des identifiants **opaques émis par le serveur** (`scene_id`, `map_id`, `photo_id`). `GET …/vigor/scenes/{scene_id}/map` résout `(scene_id, farm_id, parcel_id)` après contrôle de visibilité, puis renvoie une **URL signée MinIO de 15 min** ; scène d'une autre ferme/parcelle invisible -> 404 identique. `POST …/zones/{id}/observations/photo` stocke sous `farms/{farm_id}/zone-photos/{uuid}` (clé serveur) et renvoie un `photo_id` lié à `(farm_id, user_id)`, usage unique, 24 h (même mécanisme que `label_uploads`) ; `photo_key`/`map_key` dans un corps -> champ refusé (`extra=forbid`) ; inconnu/autre ferme/autre utilisateur/consommé => 422 `invalid_object_ref` identique (pas d'oracle). Même règle sur REST et `/v1/sync/upload`. Les règles PowerSync n'exposent aucune clé. Tests : forgerie de clé, IDOR inter-ferme, expiration.
- **X-Forwarded-For** : `client_ip()` (`app/auth/client_ip.py`) uniquement ; l'en-tête n'est lu que si le pair de la socket appartient à `AYLAL_TRUSTED_PROXIES`, saut le plus à droite non fiable, sinon pair direct. Le limiteur Redis partagé s'applique aux routes F3 coûteuses (photo, retraitement, séries, comparaison, résumé). Tests : en-tête falsifié depuis un pair non fiable ignoré ; depuis un proxy fiable pris en compte ; 429 + `Retry-After`.

### G7 — Écrans et porte design
Les écrans suivent `docs/design/aylal-design-system.md` (jetons, 4 états, RTL, ≥ 48 dp, plein soleil ; la couleur d'état n'est jamais seule : icône + phrase). **Porte design T004-like** : tâche `T-DESIGN-GATE` = maquettes haute fidélité arabe + français validées par un humain dans `docs/design/006-dashboard-monitoring/` pour F3-E1 tableau de bord, F3-E2 météo 7 jours, F3-E3 alertes, F3-E4 fiche vigueur (carte + courbe), F3-E5 détail de l'état, F3-E6 zone à vérifier + guidage (P1) ; F3-E7 comparaison N-1, F3-E8 résumé vocal (P2). **Aucun code d'écran avant cette validation** ; toutes les tâches `[écran]` en dépendent, **ainsi que de la fusion de `004-design-system` dans main** (qui reconstruit `packages/ui`). **F3 ne modifie ni `packages/ui` ni `docs/design/*`** : les composants manquants (`StatusBadge`, `WeatherDayCard`, `AlertRow`, `VigorChart`, `VigorMapOverlay`, `ZoneGuidanceCard`, `StaleDataBanner`) sont demandés par une note dans `specs/006-dashboard-monitoring/decisions.md`. La logique hors écran (domaine, API, workers, view models) n'est pas bloquée.

## Structure du projet

### Documentation

```text
specs/006-dashboard-monitoring/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/ (openapi.yaml, powersync-sync-rules.yaml, external-gateways.md)
└── tasks.md   # produit par /speckit-tasks
docs/design/006-dashboard-monitoring/   # maquettes HD ar + fr (porte design, avant tout écran)
```

### Code source (réutilise F0-F6, ajoute seulement ce qui est requis)

```text
packages/domain/src/{weather-thresholds,alert-rules,vigor,anomaly,parcel-status,status-sources,imagery-reliability,notification-schedule,voice-summary,monitoring-limits,guidance}.ts
packages/domain/src/roles.ts (étendu)
packages/domain/vectors/f3_{roles,limits,alert_rules,parcel_status,anomaly,cloud_rule,reliability,notify_schedule,summary,guidance}.json   # partagés TS/Python
packages/i18n/locales/{ary,ar,fr}/{dashboard,weather,alerts,vigor,zones,status,summary}.json
services/api/app/domain/{weather_thresholds.py,alert_rules.py,vigor.py,anomaly.py,parcel_status.py,imagery_reliability.py,notification_schedule.py,monitoring_limits.py}   # miroirs Python
services/api/app/monitoring/{access.py,service.py,status_sources.py,gateways.py,weather.py,imagery.py,zones.py,cache.py,uploads.py}
services/api/app/routers/{dashboard.py,alerts.py,vigor.py,zones.py,summary.py}
services/api/app/sync/monitoring.py                      # authorize + apply (observations de zone), même access.py
services/api/app/db/models.py (+ 10 modèles)
services/api/alembic/versions/0010_dashboard_monitoring.py   # tables, triggers de recopie parcel_archived_at, seuils de FIXTURE seulement
services/api/app/accounts/{export.py,purge.py} (étendus)
services/workers/tasks/{refresh_weather.py,evaluate_alerts.py,ingest_imagery.py,backfill_parcel_vigor.py,detect_zones.py,recompute_status.py,send_daily_summary.py,import_crop_thresholds.py}
infra/powersync/sync-rules.yaml (étendu) ; scripts/validate-sync-rules.* (cas F3)
apps/mobile/src/screens/{Dashboard,Weather7Days,Alerts,ParcelVigor,StatusDetail,ZoneGuidance,YearCompare,VoiceSummary}/
apps/mobile/src/monitoring/{viewModels,staleness.ts,alertNotifications.ts,voiceSummary.ts,guidance.ts}
apps/mobile/maestro/{dashboard_30s,weather_offline,frost_alert,vigor_cloud,zone_guidance,status_detail,year_compare,voice_summary,worker_scope}.yaml
```

**Décision de structure** : pas de nouveau service Docker permanent ; le worker existant exécute les tâches ; GDAL ajouté au Dockerfile worker (jamais sur l'hôte) ; `make` inchangé (nouveaux tests découverts par les cibles actuelles).

## Ordre de livraison (pour `tasks`)

1. Fondations non-écran : G1-G6 (RED puis GREEN), migration, domaine + vecteurs, adaptateurs de passerelle (stubs de test).
2. Récits P1 non-écran : R1 (météo, cache, hors ligne), R2 (alertes par stade, dédoublonnage, gel < 18 h), R3 (scènes, règle 80 %, fiabilité, backfill < 10 min), R4 (zones, guidage domaine), R5 (état, sources, tri).
3. `T-DESIGN-GATE` (humain) + fusion 004 puis écrans P1 ; puis P2 : R6 (comparaison N-1), R7 (résumé vocal).
4. Documentation `docs/modules/006-dashboard-monitoring/`.
