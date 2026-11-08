# F4 — Irrigation et bilan hydrique : document ingénieur

Branche `007-irrigation-water-balance`. Sources : `specs/007-irrigation-water-balance/{spec,plan,data-model,decisions}.md` et `contracts/`, migration `0012`, code `services/api/app/irrigation`, `services/workers/tasks`, `packages/domain`, `apps/mobile/src/irrigation`.

## 1. Résumé

**Objectif** : décrire l'installation d'irrigation, tenir un bilan hydrique journalier (FAO-56), produire le conseil du jour (durée par secteur, report si pluie > 10 mm, confiance et hypothèses), enregistrer une irrigation en un geste (opération F6), suivre la consommation (m³, m³/ha), enregistrer une analyse d'eau (fraction de lessivage) et accueillir une mesure d'humidité externe (F9).

**Livré** : migration `0012_irrigation_water_balance`, 4 routeurs REST (+ consommation), écritures par `/v1/sync/upload` (`app/sync/irrigation.py`), seaux PowerSync, 3 tâches worker (`compute_irrigation_plans`, `send_irrigation_reminders`, `import_irrigation_params`), règles pures TS/Python à vecteurs partagés (`packages/domain/vectors/f4_*.json`), lecteur `irrigation_need` pour l'état de parcelle F3, clés i18n `ary/ar/fr` (`irrigation`, `waterbalance`, `wateranalysis`), logique mobile non-écran (`localBalance.ts`, `adviceVoice.ts`, `pendingBadge.ts`, view models `system`, `record`).

**Non livré ou à ne pas présumer**

| Sujet | État |
| --- | --- |
| Écrans F4-E1 à E5 | **Bloqués** : porte design T004 (validation humaine des maquettes) non donnée et fusion de `004-design-system` attendue (T063-T068, T073, T078 non démarrés). Maestro et captures non écrits. `packages/ui` et `docs/design/` non modifiés. |
| View models `advice`, `consumption`, `waterAnalysis` | Non créés (viennent avec les écrans) ; T057, T062, T072, T077 laissées décochées (PARTIEL) dans `tasks.md`. |
| Référentiels agronomiques | **Vides à la livraison** : `crop_irrigation_params`, `soil_textures`, `irrigation_params`. Aucun Kc, réserve utile, profondeur racinaire, seuil de salinité ou méthode de pluie efficace n'est codé ni semé. Tant qu'un import validé (`import_irrigation_params`) n'a pas eu lieu, le conseil est `unavailable` (raisons `no_crop_coefficient`, `no_root_depth`, `no_depletion_fraction`, `no_soil_reference`, `no_soil_reserve`). Le fournisseur de la liste initiale reste à désigner. |
| Passerelles météo | `AYLAL_WEATHER_URL` et `AYLAL_WEATHER_OBSERVED_URL` vides par défaut : pas d'appel réseau, « non disponible ». Hébergeur marocain non choisi (hérité de F3). |
| Choix « À confirmer » | Voir §11 : pivot traité comme aspersion à 75 %, pluie ignorée sous serre, « prêt avant 7 h » = heure locale de la ferme. |
| Numéro de migration | `0012` provisoire, à recaler à la fusion. |
| Budget APK | **Dérogation** : 50 480 024 o mesurés (défaut 40 Mo), plafond 52 Mo (`specs/007-irrigation-water-balance/apk-budget.env`). Cause : MapLibre hérité de F2/F3 ; F4 n'ajoute aucune dépendance native. |
| Maestro, e2e mobile | Aucun fichier Maestro F4 (écrans bloqués). Seuls les e2e API existent. |

## 2. Architecture

![Architecture des composants F4](img/architecture.svg)

```mermaid
flowchart LR
  subgraph Mobile["apps/mobile (SQLite + PowerSync)"]
    LB[localBalance.ts]
    VOICE[adviceVoice.ts]
    VM[viewModels system, record]
  end
  subgraph Domain["packages/domain + app/domain (vecteurs f4_*.json)"]
    ADV[irrigation-advice]
    WB[water-balance]
    LEACH[water-analysis / leaching]
    EV[irrigation-event / units]
  end
  subgraph API["services/api (FastAPI)"]
    R[routers irrigation_*, water_analyses, consumption]
    ACC[irrigation/access.py visible_parcels]
    SVC[irrigation/service.py]
    SYNC[sync/irrigation.py]
    WV[worker_view.py]
  end
  subgraph Workers["services/workers (Arq)"]
    CP[compute_irrigation_plans]
    REM[send_irrigation_reminders]
    IMP[import_irrigation_params]
    RS[recompute_status F3]
  end
  PG[(PostgreSQL)]
  PS[PowerSync]
  RD[(Redis)]
  GW[Passerelle meteo Maroc]
  F9[F9 ingest_moisture]
  Mobile <--> PS
  PS <--> PG
  Mobile -->|/v1/sync/upload| SYNC
  R --> ACC
  SYNC --> ACC
  R --> SVC
  SYNC --> SVC
  SVC --> PG
  SVC --> Domain
  CP --> Domain
  CP --> PG
  CP --> WV
  REM --> PG
  IMP --> PG
  CP --> RS
  RS --> PG
  GW --> PG
  F9 --> PG
  R --> RD
  Workers --> RD
  LB --> Domain
```

Points structurants :
- Toute règle vit dans `packages/domain` (TS) avec miroir `services/api/app/domain/` ; les deux lisent les mêmes vecteurs JSON.
- Un seul module d'accès, `app/irrigation/access.py`, délègue à `visible_parcels` de F3 (ferme + `archived_at IS NULL` + attribution pour l'ouvrier). REST, synchro, export, purge, agrégats, calcul et rappels l'utilisent.
- Le serveur fait foi ; le mobile recalcule le bilan depuis SQLite (`localBalance.ts`). Aucune requête REST ne déclenche un calcul : le conseil est une lecture de `irrigation_plans`.

## 3. Flux principaux

**Enregistrer une irrigation (hors ligne puis synchro)**

![Enregistrement d'une irrigation](img/sequence-record.svg)

```mermaid
sequenceDiagram
  actor U as Agriculteur
  participant M as Mobile SQLite
  participant S as /v1/sync/upload
  participant A as irrigation/service.py
  participant DB as PostgreSQL
  participant W as Worker compute_irrigation_plans
  U->>M: Saisit duree ou volume (id client)
  M->>M: Ligne locale "a envoyer", bilan local recalcule
  M->>S: Lot PUT irrigation_events
  S->>S: authorize (role, parcelle visible) sur tout le lot
  S->>A: record_event
  A->>DB: verrou de ferme, quotas
  A->>DB: derives net_mm, volume, operation_id (uuid5)
  A->>DB: irrigation_events + operation F6 + trigger irrigation_applied
  A->>DB: irrigation_jobs (coalesce a la date la plus ancienne)
  S-->>M: ack (rejeu du meme id = idempotent)
  W->>DB: verrou irrigation:{farm}, rejoue le bilan, ecrit irrigation_plans
```

**Calcul nocturne du conseil**

![Calcul nocturne du conseil](img/sequence-advice.svg)

```mermaid
sequenceDiagram
  participant C as Cron Arq (nuit, minute 05)
  participant W as compute_irrigation_plans
  participant DB as PostgreSQL
  participant D as Domaine (bilan + conseil)
  participant F as recompute_status F3
  C->>W: nightly_irrigation_plans
  W->>DB: verrou irrigation:{farm}, jobs queued -> running
  W->>DB: parcelles visibles (non archivees)
  loop chaque parcelle
    W->>DB: installation, referentiels, farm_weather, evenements, analyses
    W->>D: replayBalance puis computeAdvice
    D-->>W: kind, minutes par secteur, confiance, hypotheses
    W->>DB: water_balance_days + irrigation_plans (+ worker_assumptions)
  end
  W->>DB: jobs done, bump de version du cache
  W->>F: recompute_status si le conseil change
```

Le cron `nightly_irrigation_plans` tourne à `hour={2,3}, minute=5` (UTC, pour couvrir 03:00 locale selon la zone) ; `morning_irrigation_reminders` à `{5,6}:30`. Le conseil est aussi recalculé à chaque météo reçue.

## 4. Modèle de données

![Modèle de données F4](img/data-model.svg)

```mermaid
erDiagram
  PARCELS ||--o| IRRIGATION_SYSTEMS : "1 active"
  IRRIGATION_SYSTEMS ||--o{ IRRIGATION_SYSTEM_VERSIONS : historique
  PARCELS ||--o{ IRRIGATION_EVENTS : recoit
  IRRIGATION_EVENTS ||--o| IRRIGATION_APPLIED : "trigger (done)"
  IRRIGATION_EVENTS ||--|| OPERATIONS : "operation_id derive"
  PARCELS ||--o{ WATER_ANALYSES : analyse
  SEASONS ||--o{ WATER_BALANCE_DAYS : journal
  PARCELS ||--o{ IRRIGATION_PLANS : conseil
  PARCELS ||--o{ IRRIGATION_JOBS : recalcul
  PARCELS ||--o{ MOISTURE_CORRECTIONS : "F9"
  IRRIGATION_SYSTEMS {
    uuid id PK
    text kind
    numeric efficiency
    int sectors_count
  }
  IRRIGATION_EVENTS {
    uuid id PK
    date performed_on
    text input_mode
    numeric net_mm
    text status
    uuid author_id
  }
  IRRIGATION_APPLIED {
    uuid id PK
    numeric volume_m3
    numeric net_mm
  }
  WATER_ANALYSES {
    uuid id PK
    numeric ec_ds_m
    date analysed_on
  }
  WATER_BALANCE_DAYS {
    uuid id PK
    date day
    numeric depletion_mm
    text rain_source
  }
  IRRIGATION_PLANS {
    uuid id PK
    date for_date
    text kind
    text confidence
    jsonb worker_assumptions
  }
  IRRIGATION_JOBS {
    uuid id PK
    text state
  }
```

Colonnes complètes : `specs/007-irrigation-water-balance/data-model.md`. Compléments : `irrigation_notification_log` (par utilisateur), `weather_observed` (globale, PK `(cell_id, day)`), référentiels `crop_irrigation_params`, `soil_textures`, `irrigation_params`. Toutes les tables de ferme portent `farm_id` avec clés étrangères composites `(farm_id, parcel_id)` et `parcel_archived_at` posé par trigger.

## 5. États

![États : événement, conseil, job](img/states-plan-event.svg)

```mermaid
stateDiagram-v2
  state "Evenement d'irrigation" as EVT {
    [*] --> done: enregistrement
    done --> cancelled: annulation (jamais l'inverse)
  }
  state "Conseil du jour" as PLN {
    [*] --> unavailable: referentiel vide ou pas d'installation
    unavailable --> irrigate
    unavailable --> no_need
    irrigate --> no_need
    no_need --> irrigate
    irrigate --> postpone_rain: pluie > 10 mm
    postpone_rain --> irrigate
  }
  state "Job de recalcul" as JOB {
    [*] --> queued
    queued --> running
    running --> done
    running --> failed
  }
```

- `irrigation_events.status` : `done` vers `cancelled` uniquement ; pas de DELETE ; l'annulation déclenche le recalcul à la date de l'événement.
- `irrigation_plans.kind` : `rainfed_stress` n'apparaît que pour une parcelle pluviale. `unavailable` n'est écrit que s'il n'existe aucun conseil antérieur valide ; sinon l'ancien est servi avec sa date et `confidence=low` (FR-017). Le diagramme montre les transitions principales, pas toutes les combinaisons.

## 6. API

Préfixe `/v1/farms/{farm_id}`. Contrat : `specs/007-irrigation-water-balance/contracts/openapi.yaml` (test `tests/contract/test_f4_openapi_contract.py`).

| Méthode et chemin | Droit | Remarque |
| --- | --- | --- |
| `GET /irrigation/advice` | `advice.read` | liste des conseils (vue ouvrier pour `worker`) |
| `GET /parcels/{id}/irrigation/advice` | `advice.read` | conseil du jour |
| `GET /parcels/{id}/irrigation/balance` | `advice.read` | journal du bilan |
| `GET`/`PUT /parcels/{id}/irrigation-system` | lecture / `irrigation_system.write` | écriture refusée à l'ouvrier (403), 422 si parcelle pluviale |
| `GET /parcels/{id}/irrigation-system/versions` | lecture | historique |
| `POST`/`GET /parcels/{id}/irrigation/events` | `irrigation.record` / `advice.read` | 201 créé, 200 rejeu du même `id` |
| `POST /parcels/{id}/irrigation/events/{event_id}/cancel` | `irrigation.correct` | l'ouvrier : les siennes |
| `GET /irrigation/consumption` | `consumption.read` | m³ et m³/ha sur la portée de l'appelant, ETag, fenêtre <= 24 mois |
| `GET`/`POST /parcels/{id}/water-analyses` | owner, manager | ouvrier : 403 |

Erreurs : `404 {"detail":"not_found"}` identique pour non-membre, ferme supprimée, parcelle non attribuée, archivée ou inconnue ; `403 forbidden` (rôle) ; `422 {"detail":"validation","field","code"}` ; `422 limit_out_of_range`, `422 window_too_long` ; `409 {"detail":"quota_exceeded","code"}` ; `413 batch_too_large` (lot de synchro > 100) ; `429` avec `Retry-After` (limiteur Redis, par heure : `record` 60, `history` 120, `consumption` 120, `analysis` 60). Pagination `limit` <= 100 (défaut 50) et curseur.

Aucune route pour `moisture_corrections` (service interne `ingest_moisture`, F9) ni pour plans et bilans (non inscriptibles par la synchro).

## 7. Règles métier et où elles sont codées

| Règle | Domaine TS (`packages/domain/src`) | Miroir Python (`app/domain`) |
| --- | --- | --- |
| Efficience 90 % goutte, 75 % aspersion, 60 % gravitaire ; pivot = aspersion 75 % | `irrigation-efficiency.ts` | `irrigation_efficiency.py` |
| Conseil : `no_need` si épuisement < réserve facilement utilisable ; report si pluie du jour > 10 mm (strict, `POSTPONE_RAIN_MM`) ; pluie ignorée sous serre ; durée = besoin brut / (débit × efficience) par secteur | `irrigation-advice.ts` | `irrigation_advice.py` |
| Bilan journalier rejouable (ET0, Kc, pluie efficace, apports, épuisement) | `water-balance.ts` | `water_balance.py` |
| Lessivage FAO-29 plafonné par `leaching_max` ; âge de l'analyse | `water-analysis.ts` | `water_analysis.py` |
| Dernier conseil connu servi s'il n'y a pas de nouveau (FR-017) | `irrigation-last-known.ts` | `irrigation_last_known.py` |
| Conversions durée/volume/mm, débit par m² | `irrigation-units.ts`, `irrigation-event.ts` | `irrigation_units.py`, `irrigation_event.py` |
| Validation d'installation | `irrigation-system-validation.ts` | `irrigation_system_validation.py` |
| Plafonds (secteurs <= 50, 24 irrigations/jour/secteur, 1440 min, antidatage 400 j, 50 analyses, EC <= 100) | `irrigation-limits.ts` | `irrigation_limits.py` |
| Matrice des droits | `roles.ts` (vecteur `f4_roles.json`) | `app/domain/roles.py` |
| Vue ouvrier : liste blanche `et0, kc, effective_rain, efficiency, application_rate, rain_source`, sans `leaching_fraction`, `taw_mm`, `raw_mm`, `moisture_source` | `advice-worker-view.ts` | `app/irrigation/worker_view.py` |

Côté serveur seulement : `operation_id` dérivé (`ids.py`, uuid5), dérivés d'événement recalculés par `service.py`, quotas sous verrou de ferme, jobs coalescés, cache scopé `irr:{farm}:{role}:{sha256 des parcelles visibles}:{date}:{version}` (`cache.py`), horloge injectée (`Africa/Casablanca`). Les référentiels sont lus dans `engine.py` (pas de `reference.py`).

## 8. Hors ligne et synchronisation

- Seaux PowerSync (`infra/powersync/sync-rules.yaml`, sans jointure ni sous-requête, colonnes dénormalisées) : `farm_irrigation` (staff), `farm_worker_irrigation` (ouvrier, conseils via `worker_assumptions` uniquement), `farm_worker_irrigation_own` (événements avec auteur et note, filtrés sur `author_id = bucket.user_id`), `irrigation_reference` (global).
- Les analyses d'eau ne sont servies à aucun ouvrier. Le journal de bilan de l'ouvrier est sans `taw_mm`/`raw_mm` : il ne recalcule pas la réserve utile et lit le dernier conseil synchronisé.
- Écriture : `/v1/sync/upload` (<= 100 opérations) ; autorisation du lot entier avant toute écriture (403 rôle, 404 non-membre ou parcelle invisible) ; champs serveur rejetés ; idempotence par `id` client et `applied_ops`. Doublon proche : signalé `possible_duplicate`, conservé.
- Mobile : irrigation locale marquée « à envoyer » (`pendingBadge.ts`), bilan recalculé sur SQLite (`localBalance.ts`), lecture vocale (`adviceVoice.ts`, `expo-speech`).

## 9. Tests

Stratégie : TDD, trois niveaux (CLAUDE.md).
- **Unitaires** : `packages/domain/tests/*irrigation*|water*` (Vitest + vecteurs `f4_*.json`), `services/api/tests/unit/test_f4_*.py`, `apps/mobile/src/irrigation/__tests__/`.
- **Intégration** : `services/api/tests/integration/test_f4_*.py` (isolation de ferme, parité des chemins, rôles, archivage, sortie de membre, export/purge, quotas concurrents, limiteur, rédaction ouvrier, passerelles dégradées), `services/workers/tests/test_f4_*.py` (calcul, rappels, lecteur d'état, portée), contrat `tests/contract/test_f4_openapi_contract.py`.
- **Bout en bout** : `services/api/tests/e2e/test_f4_*_e2e.py` et `test_irrigation_greenhouse_e2e.py` (parcours HTTP sur la pile). Aucun Maestro (écrans bloqués).
- Couverture : seuil de 80 % du code métier ; le chiffre mesuré n'est pas reporté ici (voir `make coverage`).

Lancer (Docker uniquement) : `make test-domain`, `make test-api ARGS=<fichiers>`, `make test-mobile`, `make test-unit`, `make test-integration`, `make e2e`, `make check-fast-cached`, `make check-cached` avant release. `make test-pyramid` est inclus dans `make check`.

## 10. Exploitation Docker

- Services : `api`, `worker` (Arq), `db` (PostgreSQL + PostGIS), `redis`, `powersync`. Aucun service permanent ajouté par F4 ; API et worker sont des images (`docker compose up -d --build --no-deps api worker` avant l'e2e).
- Variables : `AYLAL_WEATHER_URL`, `AYLAL_WEATHER_KEY`, `AYLAL_WEATHER_OBSERVED_URL` (vide par défaut ; requête `lat, lon, from, to`, coordonnées arrondies à 0,1°, aucun identifiant), `AYLAL_EXTERNAL_ALLOWED_HOSTS` (liste blanche), `AYLAL_DATABASE_URL`, `AYLAL_REDIS_URL`.
- Migration : `0012_irrigation_water_balance` (Alembic, sans valeur agronomique). Référentiels : tâche worker `import_irrigation_params` (fichier validé, `validated_by` et `source` obligatoires).
- Commandes : `make up`, `make down`, `make sync-rules`, `make apk-size`, `make diagrams`.

## 11. Décisions et dettes techniques

**À confirmer** (`decisions.md`, section « À confirmer »)
- Pivot = aspersion à 75 %, modifiable, hypothèse visible (CPS §9 ne donne que 90/75/60 pour trois types).
- Pluie ignorée sous serre : ni bilan ni report (`rain_source = ignored_greenhouse`).
- « Prêt avant 7 h » = heure locale de la ferme, calcul à 03:00 puis à chaque météo.
- Fenêtre du report = jour local J entier (> 10 mm strict).
- ET0 : passerelle si `et0_mm`, sinon Hargreaves-Samani (confiance abaissée) ; lessivage FAO-29 ; surfaces de secteur égales ; sol à la capacité au champ au départ ; règle de confiance ; plafonds de robustesse : à valider par l'agronomie ou le produit.
- Rôles de l'ouvrier déduits de CPS §6/§16 (CPS §9 muet).

**Dettes**
- Écrans F4-E1 à E5 et composants UI manquants (`AdviceCard`, `DurationStepper`, `HypothesisSheet`, `WaterStressGauge`, `SectorList`) à demander à `004-design-system` ; porte T004 humaine.
- Référentiels vides : conseil `unavailable` en production tant que l'import n'est pas fait.
- Dérogation APK 52 Mo : réduction future par fractionnement par ABI ou chargement différé de la carte (hors F4).
- Extensions de F3 tracées : `gateways.py` (`weather_observed`, `et0_mm`), `refresh_weather`, `recompute_status` (lecteur `irrigation_need`), anonymisation F6. Mapping `kind` vers `severity/reason_key` à confirmer avec la revue design.
- Hébergeur Maroc des passerelles non choisi ; numéro de migration provisoire.
- Alternative écartée : expurgation de la vue ouvrier par liste de blocage (fragile aux clés futures), remplacée par une liste blanche.
