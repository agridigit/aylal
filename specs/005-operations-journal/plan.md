# Plan d'implémentation : F6 — Journal des opérations et registre phyto

**Branche** : `005-operations-journal` | **Date** : 2026-11-07 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F6 + CPS sections 4, 11, 15, 16, 17, 19 + constitution + livrables F0/F1/F2 fusionnés (`farm_context`, `app/domain/roles.py`, `worker_parcels`, `/v1/sync/upload`, `sync/fields.py`, `accounts/export.py`, `accounts/purge.py`, `client_ip`/`AYLAL_TRUSTED_PROXIES`, verrou `pg_advisory_xact_lock`, `infra/powersync/sync-rules.yaml`).

## Résumé

F6 ajoute le **journal des opérations** (9 types, multi-parcelles, statuts planifiée/faite/à valider/validée), le **catalogue phyto** (référentiel ONSSA/PhytoIndex, lu hors ligne), les **contrôles phyto** (homologation × culture, dose max, nombre max d'applications, DAR — avertissements seulement), la **date de récolte au plus tôt**, les **rappels**, la **dictée** (pré-remplissage, confirmation obligatoire), la **reconnaissance d'étiquette** (port, repli par nom) et l'**export PDF/Excel** du registre. Approche :
- toute règle (répartition au prorata, contrôles, DAR, statuts, conversion d'unités) dans `packages/domain` (Zod -> JSON Schema -> Pydantic, vecteurs JSON partagés TS/Python) ; le serveur **recalcule** les avertissements et fait foi ;
- **registre phyto = grand livre append-only** (`registry_entries`, triggers PostgreSQL interdisant UPDATE/DELETE) ; toute correction ou annulation est une **écriture compensatoire** ; l'historique (`operation_corrections`) est lui aussi immuable ;
- journal hors ligne via PowerSync ; **écritures par `/v1/sync/upload`** (même `authorize` que REST) ; lecture par un modèle dénormalisé `operation_parcels` (aucune jointure dans les règles de sync) ;
- rappels : **notifications locales** programmées sur l'appareil (fonctionnent hors ligne, aucun push tiers) ; le worker Arq ne fait que marquer « en retard » côté serveur ;
- export généré par le worker (PDF, XLSX) dans MinIO (Maroc), URL signée courte. Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x strict, Python 3.13.
**Dépendances** : celles de F0-F2. Ajouts API/worker : `reportlab` (PDF, polices IBM Plex Sans Arabic embarquées, texte arabe via `arabic-reshaper` + `python-bidi`), `openpyxl` (XLSX). Ajouts mobiles : `expo-notifications` (locales uniquement), `expo-camera` (déjà prévu F5, sinon `expo-image-picker`), `expo-sharing` (WhatsApp). Aucun SaaS étranger, aucune clé FCM.
**Stockage** : PostgreSQL 16 (7 tables nouvelles, 1 migration `0006_operations_journal`), SQLite local PowerSync, MinIO (photos d'étiquette, exports), Redis/Arq (export, bascule « en retard »).
**Tests** : pytest (unit, integration, contrat, e2e), Vitest (domain + vecteurs), Jest + RNTL (écrans, view models), Maestro (parcours).
**Plateforme** : Android 9+, 2 Go RAM ; API Linux conteneurisée.
**Performance** : saisie < 15 s (SC-001) ; journal de 5 000 lignes affiché < 2 s depuis SQLite ; contrôles phyto < 50 ms locaux ; catalogue embarqué ≤ 3 Mo compressé (budget app < 40 Mo, sync initiale < 5 Mo) ; export de 10 000 lignes < 60 s.
**Contraintes** : hors ligne complet 30 jours ; hébergement Maroc ; gratuit ; 4 états + RTL par écran.
**Échelle** : 11 écrans (F6-E1 à F6-E11), ~20 routes, 7 tables, 1 migration.

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| I Agriculteur d'abord | OK | Grille d'icônes, 3 champs obligatoires, voix, photo d'étiquette |
| II Hors ligne | OK | Saisie, contrôles, DAR, rappels et catalogue 100 % locaux ; conflits sans perte |
| III Gratuit/sobre | OK | Pas de push tiers, pas d'API payante ; PDF/XLSX auto-générés |
| IV Données à l'utilisateur | OK | Journal et registre ajoutés à l'export de compte ; partage coopérative = F9 (hors périmètre) ; conservation légale vs suppression : voir garde-fou 4 |
| V Conseil prudent | OK | Aucun produit proposé par F6 ; produit libre « non contrôlé » ; date du catalogue affichée |
| VI Logique unique | OK | `packages/domain` + vecteurs partagés |
| VII Petits téléphones | OK | Catalogue compressé, pagination, pas de jointure locale lourde |
| VIII/XI Test first | OK | RED -> GREEN -> REFACTOR, un test par critère P1 |
| IX i18n | OK | Clés `ary/ar/fr` : `operations`, `phyto`, `registry`, `reminders` |
| X Design | OK sous condition | Porte design T004-like (ci-dessous) |
| XII Docker | OK | Aucun service nouveau ; `make test*` découvrent les nouveaux tests |
| XIII Maroc | OK | Photos, audio, texte dicté, inférence, exports : MinIO/serveurs Maroc ; notifications locales |
| XIV Documentation | OK | `docs/modules/005-operations-journal/` en fin de fonctionnalité |
| XV Seuils | OK | SC-001 à SC-007 mesurés en recette |

## Garde-fous obligatoires (leçons F0–F2)

Chaque point = **une tâche RED puis une tâche GREEN** dans `tasks.md` (identifiants `G<n>-RED` / `G<n>-GREEN`, avant les tâches de récit qui en dépendent).

### G1 — Accès scopé à la ferme, rôles, parité de tous les chemins
- **404 inter-ferme = 404 ferme inconnue** : toutes les routes `/v1/farms/{farm_id}/…` passent par `farm_context`/`require(action)` ; non-membre, membre retiré, ferme inexistante ou **supprimée** (`farms.deleted_at`) -> **404** de corps identique. Chargement de toute opération/ligne/produit libre **avec `farm_id` dans le WHERE** ; clés étrangères composites `(farm_id, parcel_id)`, `(farm_id, operation_id)` en base.
- **Matrice des droits** (`roles.py` + `roles.ts`, vecteur `f6_roles.json`) — la spec (FR-013, FR-014) et CPS §6/§11 donnent : l'ouvrier **saisit**, le gestionnaire **valide/corrige**, le propriétaire peut tout.

| Action | owner | manager | worker |
| --- | --- | --- | --- |
| `operation.create` (statut `validated`/`done` d'emblée) | oui | oui | oui, **parcelles attribuées seulement** ; statut forcé `pending_validation` (ou `planned`) |
| `operation.read` | toutes | toutes | **les siennes**, sur parcelles attribuées et non archivées |
| `operation.mark_done` / `cancel` (planifiée) | oui | oui | ses propres planifiées |
| `operation.validate`, `operation.correct` | oui | oui | **403** |
| suppression physique d'une opération | **jamais** (annulation = écriture compensatoire) | jamais | jamais |
| `registry.read`, `registry.export` | oui | oui | **403** (et aucune ligne de registre n'est synchronisée vers l'ouvrier) |
| `phyto_product.create_free` (produit libre) | oui | oui | oui (texte seulement, marqué non contrôlé) |
| `operation.read_cost` | — | — | aucun champ financier n'existe dans F6 ; réservé F8 (`finance.read` owner/manager) |

  Ouvrier sur parcelle **non attribuée** ou **archivée** : **404** (invisible) ; sur parcelle attribuée mais action de gestion : **403**.
- **Parcelle archivée masquée à l'ouvrier PARTOUT** : REST (liste, détail, journal, DAR), `/v1/sync/upload` (relecture et écriture), règles PowerSync (`parcel_archived_at IS NULL`), export de compte de l'ouvrier, journal local, calcul DAR. Pour propriétaire/gestionnaire, une parcelle archivée/fusionnée reste **lisible** dans journal et registre (cas limite de la spec).
- **Parité des chemins frères** : un seul module `app/operations/access.py` (prédicats SQL `visible_lines(role, user_id)` et `authorize(ops)`) est appelé par REST, `sync/operations.py`, `accounts/export.py`, `accounts/purge.py`, l'export de registre et le calcul DAR. Un **test de parité paramétré** exécute la même matrice (rôle × ferme × parcelle attribuée/archivée/supprimée × action) contre chaque chemin et exige des statuts identiques ; un test d'inventaire échoue si une route/table F6 n'apparaît pas dans la matrice.
- **Synchro** : à l'envoi, tout le lot est refusé (403) si une opération viole le rôle, rien n'est écrit ; non-membre -> 404. Champs serveur (`farm_id` d'un enregistrement existant, `status` hors transition autorisée, `author_id`, `warnings`, `validated_by`, `registry_*`, `parcel_archived_at`) ignorés/rejetés. Prise en compte des fermes/parcelles créées plus tôt dans le même lot (acquis F2).

### G2 — PowerSync : ni jointure ni sous-requête
Le service refuse les jointures et sous-requêtes (`infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`). F6 **dénormalise** sur chaque ligne synchronisée : `farm_id`, `parcel_id`, `author_id`, `parcel_archived_at` (posé par le serveur à l'archivage/restauration d'une parcelle, comme `seasons.parcel_archived_at` en F2), plus l'en-tête de l'opération (type, date, statut, produit, dose répartie, avertissements) dans `operation_parcels`. Le seau ouvrier utilise une requête de paramètres à deux colonnes (`parcel_id`, `user_id`) — pas de sous-requête. Le catalogue est un seau global sans paramètre. Voir [contracts/powersync-sync-rules.yaml](contracts/powersync-sync-rules.yaml). Tâches : RED = étendre `validate-sync-rules.sh` + `tests/platform/test_powersync_rules_valid.sh` avec les règles F6 (échec attendu) ; GREEN = règles + colonnes + triggers serveur de recopie. Test d'intégration : archiver une parcelle retire les lignes du seau ouvrier à la synchro suivante.

### G3 — Plafonds avant tout travail coûteux, quotas sous verrou
Contrôles **avant** parsing lourd, I/O ou rendu (taille de corps lue d'abord, 413/422 immédiat). Constantes dans `app/domain/operation_limits.py` + `operation-limits.ts` (vecteur) :

| Ressource | Plafond |
| --- | --- |
| Parcelles par opération | ≤ 50 |
| Lignes de produit par opération | ≤ 5 |
| Opérations par lot `/v1/sync/upload` | ≤ 100 (refus du lot entier, 413 `batch_too_large`, avant toute écriture) |
| Texte libre (note, produit libre, nom d'opérateur libre) | note ≤ 500 car. ; produit libre/opérateur ≤ 80 car. |
| Texte dicté envoyé à l'analyse | ≤ 500 car. ; audio brut jamais envoyé par F6 |
| Photo d'étiquette | 1 par traitement, ≤ 3 Mo après compression client, JPEG/WebP, vérification du type par signature |
| Opérations par ferme | ≤ 20 000 par ferme et par an ; planifiées en attente ≤ 500 |
| Dose / quantité | 0 < x ≤ 100 000 ; décimales ≤ 3 |
| Pagination | `limit` ≤ 200 (défaut 50), curseur ; jamais de liste non bornée |
| Export | ≤ 10 000 lignes ; période ≤ 5 ans ; 1 export actif par ferme ; ≤ 10 par heure et par ferme |
| Reconnaissance d'étiquette / analyse dictée | ≤ 20 / h et ≤ 60 / h par utilisateur |
| Date | `performed_on` entre 2000-01-01 et +2 ans |

**Quotas sous verrou** : création d'opération, planification, mise en file d'export — `SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` (même clé que `fields/service.py`) puis comptage puis écriture dans la même transaction, y compris dans `sync/operations.py` (le chemin synchro ne contourne pas le quota : test de course à 2 requêtes concurrentes pour chaque quota, REST et synchro). Idempotence des opérations par `applied_ops` (acquis F0).

### G4 — Registre phyto réglementaire
- **Append-only** : `registry_entries` (une ligne par traitement × parcelle × version) : triggers `BEFORE UPDATE OR DELETE` -> exception ; le rôle applicatif n'a pas `UPDATE`/`DELETE` (GRANT). `operation_corrections` idem. Test : tentative SQL directe d'UPDATE/DELETE = échec ; tentative via REST/synchro = aucune voie n'existe.
- **Correction = écriture compensatoire** : une correction insère une écriture `reversal` (mêmes valeurs, signe annulé, `supersedes_id`) puis une écriture `application` corrigée ; l'annulation insère seulement `reversal`. La « vue courante » du registre, le DAR et le décompte d'applications ne lisent que les écritures non annulées. Ligne de correction : auteur, date, avant/après.
- **Snapshot** : l'écriture fige nom de parcelle, culture, surface, produit, matière active, DAR, dose max, unité, opérateur (nom), avertissements et **version du catalogue** : un registre exporté plus tard reste identique, même si la parcelle est purgée ou le catalogue mis à jour. Pas de clé étrangère bloquante vers `parcels` (la purge à 90 jours F2 ne détruit pas le registre).
- **Conservation légale** : le CPS est silencieux sur la durée. **Décision par défaut prudente : 5 ans à compter de la date de l'opération** (`AYLAL_REGISTRY_RETENTION_YEARS=5`, ≥ aux 2-3 ans exigés par les référentiels d'export type GlobalG.A.P.), **point ouvert à confirmer** (juriste / CNDP / ONSSA) dans `decisions.md`. Pendant cette durée, la suppression de compte (loi 09-08, 30 j) **anonymise les données personnelles** (opérateur nommé -> « opérateur supprimé », téléphone absent du registre) mais conserve les lignes du registre rattachées à la ferme ; si l'unique propriétaire demande la suppression, le registre est **exporté au demandeur d'abord** puis conservé pseudonymisé jusqu'à l'échéance, puis purgé par tâche worker (`purge_expired_registry`). `accounts/purge.py` est étendu et testé (RED : purge avant échéance ne supprime pas le registre ; après échéance le supprime).
- **Export** : PDF et XLSX avec les mêmes lignes/colonnes (date, parcelle, culture, produit, matière active, dose, surface, opérateur, avertissements, statut produit libre « non contrôlé », écritures corrigées indiquées) ; empreinte SHA-256 du contenu imprimée en pied de page. Inclus dans l'export de compte JSON.
- **Maroc, pas de secret par défaut** : MinIO/DB au Maroc ; identifiants via `${VAR:-}` vides dans `docker-compose.yml`, démarrage refusé hors dev/test si absents ; aucune URL de fournisseur de reconnaissance/STT en dur (`AYLAL_VISION_URL`, `AYLAL_NLU_URL` vides = fonctions indisponibles, repli par nom/icônes) ; test d'allowlist : le code F6 n'appelle aucun domaine étranger ; test de configuration sans valeur secrète par défaut.

### G5 — Limites de débit et IP
Limites par IP/utilisateur/ferme (G3) via un **limiteur Redis** unique ; l'IP vient de `client_ip()` existant (`routers/auth.py`) : `X-Forwarded-For` n'est lu que si le pair de la socket appartient à `AYLAL_TRUSTED_PROXIES`, saut le plus à droite non fiable, sinon pair direct. Le limiteur est partagé (extrait dans `app/auth/client_ip.py`, comportement inchangé, tests F1 conservés). Tests : en-tête falsifié depuis un pair non fiable ignoré ; depuis un proxy fiable pris en compte ; réponse 429 `Retry-After`. Limite appliquée aux routes d'analyse dictée, étiquette, export et upload de photo.

### G6 — Écrans et porte design
Les écrans suivent `docs/design/aylal-design-system.md` (jetons, 4 états, RTL, ≥ 48 dp, plein soleil). **Porte design T004-like** : tâche `T-DESIGN-GATE` = maquettes haute fidélité arabe + français, validées par un humain, dans `docs/design/005-operations-journal/` pour F6-E1 journal, F6-E2 choix d'icône, F6-E3 formulaire d'opération, F6-E4 traitement phyto (produit, dose, avertissements), F6-E5 date de récolte (fiche parcelle), F6-E6 planifiées/rappels (P1) ; F6-E7 dictée (P1), F6-E8 étiquette, F6-E9 validation gestionnaire, F6-E10 historique des corrections, F6-E11 export (P2). **Aucun code d'écran avant cette validation** ; toutes les tâches `[écran]` en dépendent ; la logique hors écran n'est pas bloquée.
**Dépendance signalée — branche `004-design-system`** (autre session) : elle reconstruit `packages/ui`. **F6 ne modifie pas `packages/ui` ni `docs/design/aylal-design-system.md`.** Les composants manquants (`OperationTypeTile`, `WarningBanner`, `DoseField`, `HarvestDateCard`, `PendingBadge`, `ProductRow`) sont demandés par une note dans `specs/005-operations-journal/decisions.md` ; les tâches d'écran ne démarrent qu'une fois 004 fusionnée dans main et la porte design validée.

## Structure du projet

### Documentation

```text
specs/005-operations-journal/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/ (openapi.yaml, powersync-sync-rules.yaml, registry-rules.md)
└── tasks.md   # produit par /speckit-tasks
docs/design/005-operations-journal/   # maquettes HD ar + fr (porte design, avant tout écran)
```

### Code source (réutilise F0-F2, ajoute seulement ce qui est requis)

```text
packages/domain/src/{operation,operation-limits,phyto-controls,harvest-date,allocation,units,dictation-parse,registry}.ts   # règles + Zod
packages/domain/src/roles.ts (étendu)
packages/domain/vectors/f6_{allocation,phyto_controls,harvest_date,units,status_machine,roles,limits,dictation}.json        # partagés TS/Python
packages/i18n/locales/{ary,ar,fr}/{operations,phyto,registry,reminders}.json
services/api/app/domain/{operation_rules.py,phyto_controls.py,harvest_date.py,allocation.py,units.py,operation_limits.py}   # miroirs Python
services/api/app/operations/{access.py,service.py,registry.py,export_job.py,parse.py,label.py}
services/api/app/routers/{operations.py,phyto_products.py,registry.py}
services/api/app/sync/operations.py                      # authorize + apply (même access.py)
services/api/app/auth/client_ip.py                       # extrait de routers/auth.py (inchangé fonctionnellement)
services/api/app/db/models.py (+ 7 modèles)
services/api/alembic/versions/0006_operations_journal.py # tables, triggers append-only, GRANT, seed de fixtures de test seulement
services/api/app/accounts/{export.py,purge.py} (étendus)
services/workers/tasks/{build_registry_export.py,mark_overdue_operations.py,purge_expired_registry.py,import_phyto_catalog.py}
infra/powersync/sync-rules.yaml (étendu) ; scripts/validate-sync-rules.* (cas F6)
apps/mobile/src/screens/{OperationJournal,OperationTypePicker,OperationForm,PhytoTreatment,HarvestDate,PlannedOperations,Dictation,LabelScan,ManagerValidation,CorrectionHistory,RegistryExport}/
apps/mobile/src/operations/{viewModels,localControls.ts,reminders.ts,catalogCache.ts,share.ts}
apps/mobile/maestro/{operation_quick,phyto_warning,harvest_date,planned_reminder,dictation,registry_export,worker_validation}.yaml
```

**Décision de structure** : pas de nouveau service Docker ; le worker existant exécute les tâches ; `make` inchangé (nouveaux tests découverts par les cibles actuelles).

## Ordre de livraison (pour `tasks`)

1. Fondations non-écran : G1-G5 (RED puis GREEN), migration 0006, domaine + vecteurs.
2. Récits P1 non-écran : R1 (saisie, répartition, hors ligne), R2 (contrôles), R3 (DAR), R4 (planification), R5 (analyse de dictée côté domaine/API).
3. `T-DESIGN-GATE` (humain) puis écrans P1 ; puis P2 : R6 (export), R7 (validation, corrections).
4. Documentation `docs/modules/005-operations-journal/`.

## Vérification de la constitution (après conception)

Inchangé : OK. Écarts signalés à `tasks` :
- durée de conservation du registre (5 ans par défaut) et articulation avec la suppression 30 j de la loi 09-08 : décision à confirmer ;
- source technique du catalogue PhytoIndex et de la reconnaissance d'étiquette/dictée (F5/F7 absents) : ports `LabelRecognizer`, `VoiceParser` avec repli ; non bloquant ;
- ajout de dépendances `reportlab`, `openpyxl`, `arabic-reshaper`, `python-bidi` aux Dockerfiles API/worker (jamais sur l'hôte) ;
- dépendance externe : branche `004-design-system` (packages/ui).

## Suivi de complexité

Aucune violation. Le grand livre append-only ajoute une table mais évite toute réécriture réglementaire.
