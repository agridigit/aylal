# Plan d'implémentation : F4 — Irrigation et bilan hydrique

**Branche** : `007-irrigation-water-balance` | **Date** : 2026-11-08 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F4 + CPS sections 4, 9, 15, 16, 17, 19 + constitution + livrables F0/F1/F2/F3/F6 fusionnés (`farm_context`/`require`, `app/domain/roles.py`, `worker_parcels`, `/v1/sync/upload` + `applied_ops`, `parcels.archived_at`, `seasons`, `crops.stages`, `operations`/`operation_parcels`, `farm_weather` + passerelle météo `app/monitoring/gateways.py`, registre de sources d'état `status_sources.py` (table `irrigation_plans` déjà attendue par F3), `app/monitoring/access.py` (`visible_parcels`), `app/auth/client_ip.py` + `AYLAL_TRUSTED_PROXIES`, `app/operations/body_limit.py`, verrou `pg_advisory_xact_lock`, `infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`, `accounts/export.py`/`purge.py`).

## Résumé

F4 ajoute la **description de l'installation**, le **bilan hydrique journalier** (FAO-56), le **conseil du jour** (durée par secteur, report pour pluie > 10 mm, confiance + hypothèses), l'**enregistrement d'une irrigation en un geste** (c'est une opération F6, pas un second registre), le **suivi de consommation** (m³, m³/ha), l'**analyse d'eau** (fraction de lessivage) et le **point d'accueil** d'une mesure externe (F9). Approche :
- **toute règle** (efficience, débit par m², ET0, pluie efficace, bilan, durée, lessivage, report, confiance, stress pluvial, conversions durée/volume) dans `packages/domain` (TS, source de vérité, Zod -> JSON Schema -> Pydantic) avec miroir `services/api/app/domain/` et **vecteurs JSON partagés TS/Python** (`f4_*.json`) ; le serveur calcule et fait foi, le mobile **recalcule localement** le bilan à partir de SQLite (FR-016, SC-005) ;
- **aucune valeur agronomique inventée** : Kc par stade, profondeur racinaire, fraction d'épuisement, réserve utile par texture, tolérance à la salinité, méthode de pluie efficace, seuil « stress » vivent dans des **référentiels vides à la livraison** (comme `crop_weather_thresholds` en F3), chargés par `import_irrigation_params` depuis un fichier validé par l'agronomie (`validated_by`, `source`). Les migrations ne contiennent que des fixtures de test. Référentiel manquant -> conseil `unavailable` avec raison, jamais une valeur par défaut. Seules constantes fixées par le CPS : efficiences 90/75/60 %, report si pluie > 10 mm / 24 h ;
- **météo/ET0** : lues dans `farm_weather` (F3), alimentée par la passerelle Maroc existante ; ET0 = valeur de la passerelle si fournie, sinon Hargreaves-Samani (FAO-56 éq. 52) calculé localement depuis Tmin/Tmax et le rayonnement extraterrestre (éq. 21, latitude de la ferme arrondie à 0,1°) ; passerelle vide -> « non disponible » ;
- **conseil = lecture dénormalisée** `irrigation_plans` (recalculée par worker la nuit puis à chaque météo reçue ; **prête avant 7 h heure locale de la ferme**), consommée par F3 via `status_sources` (`irrigation_need`) ;
- **un seul module d'accès** `app/irrigation/access.py` qui délègue à `visible_parcels(ctx)` de F3 : REST, synchro, export, purge, agrégats, caches, workers de calcul et de rappel : parité de garde. Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x strict, Python 3.13.
**Dépendances** : celles de F0-F3/F6. **Aucune nouvelle dépendance serveur** (calcul en Python pur + `zoneinfo`) ; mobile : `expo-speech` (déjà présent, F3) pour la lecture vocale du conseil. Aucune bibliothèque de graphes (courbes en SVG/Skia, APK).
**Stockage** : PostgreSQL 16 + PostGIS, **8 tables nouvelles** (`irrigation_systems`, `irrigation_system_versions`, `irrigation_events`, `irrigation_applied`, `water_analyses`, `water_balance_days`, `irrigation_plans`, `moisture_corrections`) + 3 référentiels (`crop_irrigation_params`, `soil_textures`, `irrigation_params`) + `irrigation_notification_log` ; migration `0012_irrigation_water_balance` (numéro provisoire, à recaler à la fusion) ; SQLite local PowerSync ; Redis/Arq.
**Tests** : pytest (unit, integration, contrat, e2e), Vitest (domain + vecteurs), Jest + RNTL, Maestro.
**Plateforme** : Android 9+, 2 Go RAM ; API Linux conteneurisée.
**Performance** : bilan d'une parcelle sur 400 jours recalculé < 50 ms (domaine) ; écran conseil < 2 s depuis SQLite ; enregistrement d'une irrigation < 15 s (SC-002) ; sync initiale F4 <= 300 Ko par ferme de 50 parcelles ; budget APK < 40 Mo (voir G9).
**Contraintes** : hors ligne complet (30 jours simulés, SC-005) ; hébergement Maroc ; gratuit ; 4 états + RTL par écran.
**Échelle** : 5 écrans (F4-E1 à F4-E5), ~16 routes, 12 tables, 1 migration, 3 tâches workers.

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| I Agriculteur d'abord | OK | Une phrase (« irriguer 2 h 30 »), icônes, lecture vocale native, saisie en un geste |
| II Hors ligne | OK | Bilan recalculé sur SQLite ; irrigation locale marquée « à envoyer » ; id client = idempotence |
| III Gratuit/sobre | OK | Calcul en Python pur, aucun service payant ; passerelle météo existante |
| IV Données à l'utilisateur | OK | Tables F4 dans export et purge (G1) |
| V Conseil prudent | OK | Confiance + hypothèses en un clic ; valeurs manquantes = indisponible ; pas de valeur inventée (G5) |
| VI Logique unique | OK | `packages/domain` + vecteurs partagés |
| VII Petits téléphones | OK | Séries bornées, aucun calcul lourd, pas de nouvelle lib |
| VIII/XI Test first | OK | RED -> GREEN -> REFACTOR ; un test par critère P1 |
| IX i18n | OK | Clés `ary/ar/fr` : `irrigation`, `advice`, `waterbalance`, `wateranalysis` |
| X Design | OK sous condition | Porte design T004-like (G8) |
| XII Docker | OK | Aucun service permanent nouveau ; worker existant |
| XIII Maroc | OK | G5 : passerelles Maroc configurables, aucune géométrie exacte ni donnée personnelle sortante |
| XIV Documentation | OK | `docs/modules/007-irrigation-water-balance/` en fin de fonctionnalité |
| XV Seuils | OK | SC-001 à SC-007 mesurés en recette ; couverture domaine >= 80 % |

## Garde-fous obligatoires (leçons F0–F3, F6)

Chaque point = **une tâche RED puis une tâche GREEN** dans `tasks.md` (`G<n>-RED` / `G<n>-GREEN`, avant les tâches de récit qui en dépendent).

### G1 — Accès scopé, rôles, parité de tous les chemins
- **404 inter-ferme = 404 ferme inconnue** : toutes les routes `/v1/farms/{farm_id}/…` passent par `farm_context`/`require(action)` ; non-membre, membre retiré (`removed_at IS NOT NULL`), ferme inexistante ou **supprimée** (`farms.deleted_at`) -> **404** de corps identique `{"detail":"not_found"}`. Toute lecture filtre `farm_id` dans le WHERE ; clés étrangères composites `(farm_id, parcel_id)`.
- **Matrice des droits** (`roles.py` + `roles.ts`, vecteur `f4_roles.json`). CPS §6 : l'ouvrier ne voit que ses parcelles attribuées, aucun montant ; CPS §9 muet sur les rôles -> déduit de §6/§16 (voir decisions « À confirmer »).

| Action | owner | manager | worker |
| --- | --- | --- | --- |
| `irrigation_system.read` | oui | oui | oui, parcelles attribuées non archivées |
| `irrigation_system.write` | oui | oui | **403** |
| `advice.read` (conseil, hypothèses, stress pluvial) | toutes | toutes | attribuées non archivées |
| `irrigation.record` (enregistrer une irrigation) | oui | oui | oui, attribuées seulement |
| `irrigation.correct` (corriger/annuler la sienne) | toutes | toutes | **les siennes** (`author_id`) |
| `consumption.read` (m³, m³/ha) | toutes | toutes | agrégat de **ses parcelles visibles**, toutes sources d'apport |
| `water_analysis.read`/`write` | oui | oui | **403** |
| `moisture.ingest` (F9) | service interne | service interne | aucune route |

  Ouvrier sur parcelle **non attribuée**, **archivée** ou inexistante : **404** identique ; parcelle attribuée mais action de gestion : **403**. Ferme supprimée : 404 pour tous.
- **Archivée masquée PARTOUT** : un seul prédicat `visible_parcels(ctx)` (celui de F3, `VISIBLE_PARCELS_SQL`) : `farm_id = :farm AND archived_at IS NULL` (+ `id IN worker_parcels` pour l'ouvrier). Appelé par : REST (installation, conseil, historique, consommation, analyses), `sync/irrigation.py` (écritures), règles PowerSync (`parcel_archived_at IS NULL`), `accounts/export.py` (l'ouvrier n'exporte pas l'archivé ; le staff retrouve l'historique en lecture seule), `accounts/purge.py`, **calculs de bilan** (le worker `compute_irrigation_plans` ne calcule ni ne notifie une parcelle archivée ; l'agrégat de consommation de l'ouvrier l'exclut), **rappels du matin** (`send_irrigation_reminders`) et la source d'état F3 `irrigation_need`.
- **Parité des chemins frères** : un **test de parité paramétré** exécute la même matrice (rôle × ferme {propre, autre, inconnue, supprimée} × parcelle {attribuée, non attribuée, archivée, inconnue} × chemin {REST, sync upload, export, conseil, agrégat de consommation, rappel}) et exige statuts/contenus identiques ; un **test d'inventaire** échoue si une route, une table, une règle de synchro ou une tâche worker F4 n'apparaît pas dans la matrice.
- **Appartenance ACTIVE** : tout seau paramétré par l'utilisateur ou tout calcul par destinataire (`irrigation_notification_log`, rappels, seau `own`) exige `farm_members.removed_at IS NULL` (rejoué à chaque lecture/génération). **Purge** à la sortie d'un membre, au changement de rôle et à la suppression de ferme : `purge_member_irrigation` (journal de notifications, préférences de rappel) et `purge_farm_irrigation` (clés d'objet : aucune en F4) ; à la **sortie d'un membre** les événements restent (registre de la ferme) et `author_id` n'est **pas** modifié ; l'**anonymisation de l'auteur n'a lieu qu'à la suppression du COMPTE**, par la fonction de maintenance de F6 étendue (`anonymize_registry_operator`, `author_id -> NULL`, texte de `note` vidé si le compte l'a écrit ; migration 0012). **Suppression de ferme** : aucun DELETE explicite sur les tables protégées ; elles disparaissent par `ON DELETE CASCADE` depuis `farms` (mécanisme de F6, `operations.farm_id REFERENCES farms ON DELETE CASCADE`), `irrigation_events`/`water_analyses` déclarent la même clé étrangère ; seules les tables non protégées par garde (journal de notifications) sont vidées par `purge_member_irrigation`/`purge_farm_irrigation`. Aucun DELETE physique sur `operations`, `registry_entries`, `irrigation_events` (annulation = `status='cancelled'` + opération de correction F6).
- **Synchro** : le lot `/v1/sync/upload` est refusé entier (403) si une écriture viole le rôle ; non-membre -> 404 ; champs serveur (`farm_id` d'un enregistrement existant, `author_id`, `operation_id`, `net_mm_applied`, `volume_m3` dérivés, `parcel_archived_at`, `server_version`) ignorés/rejetés.

### G1b — Alimenter l'état de parcelle de F3 (FR-018)
F3 attend la source `irrigation_need` (`status_sources._TABLE_OF`, priorité déjà fixée dans `parcel_status.py`). F4 livre le **lecteur** dans `recompute_status` (extension minimale du worker F3, tracée dans `decisions.md`), qui lit `irrigation_plans` du jour local pour les parcelles visibles (`NOT archived`) :

| `irrigation_plans` | Signal F3 (`severity`, `reason_key`, `reason_params`) |
| --- | --- |
| `kind=irrigate` | `act`, `status.irrigation_needed`, `{minutes}` |
| `kind=postpone_rain` | `ok` (non listé), `status.irrigation_postponed` |
| `kind=no_need` | `ok`, `status.irrigation_ok` |
| `kind=rainfed_stress`, `stress_level=high` | `act`, `status.water_stress` |
| `kind=rainfed_stress`, `stress_level=watch` | `watch`, `status.water_stress` |
| `kind=unavailable` | aucun signal ; la parcelle reste « doute » (jamais verte par défaut, règle F3) |

`observed_at = computed_at`, `ttl_s` = 24 h. `compute_irrigation_plans` met en file `recompute_status` pour les parcelles dont le conseil change (dédoublonné par parcelle). Les parcelles archivées sont exclues du lecteur. Test RED : conseil `irrigate` -> la parcelle passe orange/rouge avec la raison ; vecteur `f3_parcel_status.json` inchangé ; parcelle archivée -> aucun signal.

### G2 — Agrégats et bilans sans fuite, cache scopé
- Tout total (m³, m³/ha, nombre de parcelles à irriguer, compteur « à irriguer » pour F3) est **calculé sur la portée de l'appelant** : `FROM irrigation_applied WHERE <visible_parcels>`. Aucune somme n'est lue d'une colonne de ferme (`farms.area_ha`, total ferme) ni d'un cache partagé. La réponse d'un ouvrier ne contient aucun champ « total ferme ».
- **Clé de cache** : `irr:{farm_id}:{role}:{sha256(sorted visible_parcel_ids)}:{date_locale}:{data_version}` (module `app/irrigation/cache.py`, miroir de `monitoring/cache.py`) ; ETag dérivé du contenu borné à la portée. Test : ferme à 10 parcelles dont 3 attribuées à l'ouvrier -> totaux ouvrier = calcul manuel sur 3 ; un changement d'attribution ou d'archivage change la clé.
- Le conseil **par parcelle** est identique pour tout rôle autorisé (il ne dépend pas de l'appelant), mais sa lecture passe par `visible_parcels`.

### G3 — PowerSync : ni jointure ni sous-requête
Le service refuse jointures et sous-requêtes (`infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`, `make sync-rules`). Chaque table synchronisée porte **dénormalisés** : `farm_id`, `parcel_id`, `parcel_archived_at` (posé par triggers serveur à l'archivage/restauration/fusion, comme `operation_parcels`), `crop_slug`, `season_id`, et les clés i18n utiles (`reason_key`, `reason_params`).
- **Données d'auteur (patron F6)** : la table `irrigation_events` (avec `author_id`, `note`) n'est livrée à l'ouvrier que par le seau paramétré `SELECT parcel_id, request.user_id() AS user_id FROM worker_parcels WHERE user_id = request.user_id() AND farm_id = ...` avec filtre `author_id = bucket.user_id` ; **chaque requête de données couvre TOUS les paramètres du seau** (leçon F3 : « Query must cover all bucket parameters » ; les seaux sans auteur n'ont que `parcel_id`). Le **bilan de l'ouvrier** a besoin de tous les apports de ses parcelles : ils viennent de la table dénormalisée **sans auteur ni note** `irrigation_applied` (id, farm_id, parcel_id, performed_on, sector_no, net_mm, volume_m3, parcel_archived_at), servie par le seau `farm_worker_parcels`-like sur `parcel_id`. Le propriétaire/gestionnaire reçoit `irrigation_events` complète.
- Les analyses d'eau (`water_analyses`) ne sont **pas** servies à l'ouvrier (aucun seau). Le référentiel (`crop_irrigation_params`, `soil_textures`, `irrigation_params`) est global, sans paramètre, avec sa date de source. `irrigation_plans` (conseils) : par parcelle, servi aux 3 rôles via la visibilité.
- Seaux par utilisateur : appartenance active uniquement (`farm_members ... removed_at IS NULL` dans la requête de paramètres).
- Tests : `validate-sync-rules` (aucun JOIN/IN-sous-requête), requêtes de seaux exécutées telles quelles sur PostgreSQL (le test RED échoue tant que le contrat de seaux contient une jointure), un test de contrat exigeant que chaque requête de `farm_worker_irrigation_own` référence `bucket.parcel_id` ET `bucket.user_id`.

### G4 — Plafonds avant tout calcul coûteux, verrous par ferme
Contrôles **avant** parsing lourd, calcul de bilan ou I/O (taille de corps lue d'abord : 413/422 immédiat, `body_limit.py`). Constantes dans `app/domain/irrigation_limits.py` + `irrigation-limits.ts` (vecteur `f4_limits.json`). Ces plafonds sont des bornes de **robustesse**, pas des valeurs agronomiques ; valeurs proposées, à confirmer (decisions).

| Ressource | Plafond |
| --- | --- |
| Installations par parcelle | 1 active (versions conservées <= 50) |
| Secteurs par installation | <= 50 |
| Irrigations par parcelle et par jour | <= 24 (par secteur) ; durée <= 24 h par secteur ; volume <= plafond par parcelle (surface × 1000 m³/ha) |
| Antidatage d'une irrigation | <= 400 jours ; recalcul du bilan borné à 400 jours |
| Analyses d'eau par parcelle | <= 50 ; EC <= 100 dS/m |
| Lot `/v1/sync/upload` | <= 100 opérations (413 `batch_too_large` avant toute écriture) |
| Historique / consommation | fenêtre <= 24 mois ; <= 400 points par réponse ; `limit` <= 100 (défaut 50), curseur |
| Recalculs | 1 job actif par parcelle (les antidatages sont **coalescés** sur la date la plus ancienne) ; <= 5 jobs par ferme simultanés ; lecture REST = lecture seule du cache, **jamais** de calcul déclenché par une requête |
| Passerelle météo | inchangée (F3) : aucun appel déclenché par F4 ; F4 lit `farm_weather` |
| Débit | limiteur Redis par IP/utilisateur/ferme (G6) ; 429 `Retry-After` |

**Verrous** : création d'installation, d'irrigation, d'analyse et planification de recalcul -> `SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` (même clé que `fields/service.py`, F3 et F6), comptage des quotas et écriture dans la **même transaction, y compris sur le chemin synchro**. Le worker prend le verrou consultatif `irrigation:{farm}` pour qu'un recalcul n'entre pas en course avec une écriture. Idempotence par `applied_ops` (acquis F0) et par `id` client des événements. Test de course à 2 requêtes concurrentes par quota, REST et synchro.

### G5 — Sources externes, valeurs agronomiques, hébergement Maroc
- **Météo/ET0 via les passerelles Maroc existantes** (`AYLAL_WEATHER_URL`, liste blanche `AYLAL_EXTERNAL_ALLOWED_HOSTS`, F3). F4 **n'ajoute aucun appel sortant déclenché par utilisateur**. Une seule extension : une lecture facultative des pluies **observées** des jours passés par la même passerelle (variable `AYLAL_WEATHER_OBSERVED_URL`, **vide par défaut**, mêmes règles d'hôte, requête à clés exactes `lat, lon, from, to`) ; vide -> pluie du jour passé = dernière prévision connue, marquée `rain_source=forecast` et confiance abaissée (jamais une valeur inventée) ; voir `contracts/external-gateways.md`. URL vide / hôte hors liste / passerelle muette -> `availability: unavailable` + `reason`, dernier conseil conservé et daté.
- **Minimisation sortante** : latitude/longitude arrondies à 0,1° et dates uniquement ; **aucune géométrie exacte, aucun identifiant de ferme/utilisateur/parcelle, aucune donnée personnelle**. Test : adaptateurs espions vérifiant les clés exactes ; test d'inventaire des imports (aucun SDK étranger).
- **Valeurs agronomiques** : aucun Kc, aucune réserve utile, aucune profondeur racinaire, aucun seuil de salinité, aucune méthode de pluie efficace n'est codé en dur ni semé par migration. Tout provient de `crop_irrigation_params` / `soil_textures` / `irrigation_params` (vides, `validated_by` + `source` obligatoires, `validated=false` -> confiance abaissée « non validé »). Les **formules** publiées (FAO-56 éq. 21, 52 ; USDA-SCS ou autre pour la pluie efficace ; FAO-29 pour le lessivage) sont dans le domaine, leurs **paramètres** dans le référentiel. Culture/stade sans Kc -> `unavailable (reason=no_crop_coefficient)`. Texture inconnue -> réserve utile **la plus faible du référentiel** (spec) signalée dans les hypothèses ; référentiel sols vide -> `unavailable (reason=no_soil_reference)`. Test : base vierge -> aucun conseil chiffré.
- **Constantes du CPS seules codées** : efficiences 90 / 75 / 60 %, seuil de report 10 mm / 24 h.
- **Cas où le CPS est muet** (pivot traité comme aspersion 75 %, pluie ignorée sous serre, « avant 7 h » en heure locale de la ferme, état initial du sol, méthode ET0, formule de lessivage, répartition par secteur, confiance) : consignés dans `decisions.md`, section **« À confirmer »**.

### G6 — Identifiants d'objets, URL signées, X-Forwarded-For
- F4 ne stocke **aucun objet** (pas de photo, pas de fichier) : aucune URL signée. Le client n'envoie jamais de clé de stockage ni d'URL ; toute clé reçue (`file_key`, `object_key`, `url`…) rejette l'opération (`invalid_object_ref`, patron F6). Les identifiants (`event_id`, `plan_id`, `system_id`) sont générés par le client pour l'idempotence **mais validés et rattachés à la ferme côté serveur** (UUID v4 inconnu ailleurs ; collision avec un id d'une autre ferme -> 404 identique) ; `operation_id` est **émis par le serveur** : `uuid5(NS_F4, farm_id:event_id)` (idempotent, jamais lu du client, aucune collision avec une opération F6 existante).
- **X-Forwarded-For** : `client_ip()` (`app/auth/client_ip.py`) uniquement ; en-tête lu seulement si le pair appartient à `AYLAL_TRUSTED_PROXIES`, saut le plus à droite non fiable. Limiteur Redis sur les routes F4 (enregistrement, historique, consommation, analyses). Tests : en-tête falsifié depuis un pair non fiable ignoré ; depuis un proxy fiable pris en compte ; 429 + `Retry-After`.

### G7 — Horloge injectée, tests déterministes, hygiène e2e
- Toute logique dépendant de l'heure (jour local de la ferme, « avant 7 h », fenêtre « prévue dans les 24 h », ancienneté d'une analyse/d'un conseil, antidatage, expiration du cache, planification des workers) reçoit une **`Clock`** (`packages/domain/src/clock.ts`, `app/domain/clock.py` : vérifié, **aucune horloge ni aide de fuseau n'existe** dans `services/` ou `packages/domain`, donc création ; F3 reçoit déjà `now` en paramètre, la `Clock` est compatible) ; aucun appel direct à `now()`/`Date.now()`/`current_date` dans le métier (test d'inventaire par grep). Fuseau de la ferme : `Africa/Casablanca` (`zoneinfo`), jamais l'heure système. Les images `python:3.13-slim` (API et worker) n'embarquent pas la base de fuseaux : **ajouter le paquet `tzdata` aux `pyproject` des deux images** (tâche G7, test qui échoue sans lui : `ZoneInfo('Africa/Casablanca')` dans le conteneur). Les tests figent l'horloge (jours de changement d'heure et de Ramadan inclus).
- **Jamais de `FLUSHDB`** (Redis par worker de test, clés préfixées) ; **numéros de téléphone e2e uniques** par test (générateur) ; **aucun DELETE** sur les tables protégées (`operations`, `registry_entries`, `irrigation_events`, `water_analyses`) y compris dans les nettoyages de tests (isolation par ferme unique).

### G8 — Écrans et porte design
Les écrans suivent `docs/design/aylal-design-system.md` (jetons, 4 états, RTL, >= 48 dp, plein soleil ; une couleur n'est jamais seule : icône + phrase). **Porte design T004-like** : tâche `T-DESIGN-GATE` = maquettes haute fidélité arabe + français validées par un humain dans `docs/design/007-irrigation-water-balance/` pour F4-E1 installation, F4-E2 conseil du jour + hypothèses, F4-E3 enregistrement d'une irrigation (P1) ; F4-E4 consommation, F4-E5 analyse d'eau (P2). **Dépendance** : fusion de `004-design-system` avant tout écran ; **je ne modifie ni `packages/ui` ni `docs/design/*`** ; composants manquants demandés à 004 (decisions) : `AdviceCard`, `DurationStepper`, `HypothesisSheet`, `WaterStressGauge`, `SectorList`, `OfflineBadge` (réutilise celui de F3 s'il existe). Les tâches d'écran sont **bloquées** par la porte et la fusion.

### G9 — Mesure APK
Mesure `make apk-size` (limite 40 Mo, `scripts/in-container/apk-size.sh`) en fin d'implémentation et avant fusion. F4 n'ajoute **aucune dépendance native** (voix : `expo-speech` déjà présent). **Rappel** : un dépassement n'est accepté que via un `specs/007-irrigation-water-balance/apk-budget.env` (`APK_LIMIT_MB`, `APK_BUDGET_REASON`, `DECISION_REF`) ET une section **« Dérogation »** dans `specs/007-irrigation-water-balance/decisions.md` **propre à cette branche** (le script refuse un `DECISION_REF` sans cette section ; la dérogation de F2/F3 n'est pas héritée). Par défaut : aucun `apk-budget.env` créé.

## Structure du projet

### Documentation

```text
specs/007-irrigation-water-balance/
├── plan.md  research.md  data-model.md  quickstart.md  decisions.md
├── contracts/ (openapi.yaml, powersync-sync-rules.yaml, external-gateways.md)
└── tasks.md   # produit par /speckit-tasks
docs/design/007-irrigation-water-balance/   # maquettes HD ar + fr (porte design, avant tout écran)
```

### Code source (réutilise F0-F6, ajoute seulement ce qui est requis)

```text
packages/domain/src/{clock,irrigation-efficiency,application-rate,et0,effective-rain,water-balance,irrigation-advice,leaching,advice-confidence,rainfed-stress,irrigation-units,irrigation-limits}.ts
packages/domain/src/roles.ts (étendu)
packages/domain/vectors/f4_{roles,limits,efficiency,application_rate,et0,effective_rain,water_balance,advice,leaching,confidence,stress,units,reference_gaps}.json   # partagés TS/Python
packages/i18n/locales/{ary,ar,fr}/{irrigation,advice,waterbalance,wateranalysis}.json
services/api/app/domain/{clock.py,irrigation_efficiency.py,application_rate.py,et0.py,effective_rain.py,water_balance.py,irrigation_advice.py,leaching.py,advice_confidence.py,rainfed_stress.py,irrigation_units.py,irrigation_limits.py}   # miroirs Python
services/api/app/irrigation/{access.py,service.py,plans.py,reference.py,consumption.py,weather_input.py,cache.py,lifecycle.py,corrections.py}
services/api/app/routers/{irrigation_systems.py,irrigation_advice.py,irrigation_events.py,consumption.py,water_analyses.py}
services/api/app/sync/irrigation.py                  # authorize + apply (systèmes, événements, analyses), même access.py ; crée l'opération F6 liée
services/api/app/db/models.py (+ modèles)
services/api/alembic/versions/0012_irrigation_water_balance.py   # tables, triggers de recopie parcel_archived_at, fixtures de TEST seulement
services/api/app/accounts/{export.py,purge.py} (étendus)
services/workers/tasks/{compute_irrigation_plans.py,send_irrigation_reminders.py,import_irrigation_params.py}
infra/powersync/sync-rules.yaml (étendu) ; scripts/validate-sync-rules.* (cas F4)
apps/mobile/src/screens/{IrrigationSystem,DailyAdvice,RecordIrrigation,WaterConsumption,WaterAnalysis}/
apps/mobile/src/irrigation/{viewModels,localBalance.ts,adviceVoice.ts,pendingBadge.ts}
apps/mobile/maestro/{irrigation_system,daily_advice,rain_postpone,record_irrigation_offline,consumption,water_analysis,worker_scope}.yaml
```

**Décision de structure** : pas de nouveau service Docker permanent ; le worker existant exécute les tâches ; `make` inchangé (nouveaux tests découverts par les cibles actuelles).

## Ordre de livraison (pour `tasks`)

1. Fondations non-écran : G1-G7 (RED puis GREEN), migration, domaine + vecteurs + horloge, référentiels vides + import.
2. Récits P1 non-écran : R1 (installation, efficience, débit par m²), R2 (bilan, conseil, report pluie, confiance, hypothèses, hors ligne/dernier conseil, pluvial), R3 (enregistrement, lien F6, idempotence, recalcul antidaté).
3. `T-DESIGN-GATE` (humain) + fusion 004 puis écrans P1 ; puis P2 : R4 (consommation), R5 (analyse d'eau, lessivage), R6 (point d'accueil F9, sans écran).
4. G9 mesure APK, puis documentation `docs/modules/007-irrigation-water-balance/`.

## Vérification de la constitution (après conception)

Aucune violation. Risques résiduels consignés : valeurs agronomiques tant que l'import validé n'est pas fourni (conseil `unavailable` plutôt qu'inventé) ; hébergeur Maroc des passerelles non désigné (F3, point ouvert) ; porte design et fusion 004 bloquant les écrans.
