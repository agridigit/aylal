# Changelog

Tenu automatiquement par Claude (sous-agent `git-keeper`). Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions [SemVer](https://semver.org/lang/fr/).

## [0.6.0] - 2026-11-08 — F4 Irrigation et bilan hydrique
### Ajouts
- green - setup
- green - foundations
- green - US1 installation (T051)
- green - US2 daily advice (T057)
- green - US3 record an irrigation (T062)
- green - US4 water consumption (T072)
- green - US5 water analysis and leaching (T077)
### Documentation
- engineer and farmer documentation
### Technique
- red - foundations
- extend the F3 task inventory with the three F4 tasks
- red - US1 installation (T047-T050)
- red - US2 daily advice (T052-T056)
- red - US3 record an irrigation (T058-T061)
- red - US4 water consumption (T069-T071)
- red - US5 water analysis and leaching (T074-T076)
- fix contradictory fixtures (irrigation_jobs, global bucket, fx_* crops)
- lint and typecheck fixes, honest task ticks
- APK budget derogation (T080)
- mark 007-irrigation-water-balance as merged

Documentation du module : [docs/modules/007-irrigation-water-balance/](docs/modules/007-irrigation-water-balance/)

## [0.5.0] - 2026-11-08 — F3 Tableau de bord et monitoring
### Ajouts
- Tableau de bord et monitoring : météo, alertes par culture et stade, vigueur, zones à vérifier, état résumé, comparaison N-1, résumé vocal
- Passerelles externes à URLs vides par défaut (fonctionnalité signalée non disponible)
- Dérogation de budget APK à 52 Mo documentée via apk-budget.env
### Corrections
- Corrections de sécurité : appartenance active vérifiée, agrégats limités à la portée de l'appelant
- Corrections de fiabilité : seaux PowerSync valides, drain des jobs backfill, limite de retraitement
### Documentation
- Documentation ingénieur et agriculteur (fr, ar) du module 006-dashboard-monitoring
- Limites connues : écrans reportés (porte design T004 + 004-design-system) ; aucun seuil agronomique semé donc ni alerte ni zone ; rasters non câblés ; recalcul < 5 min non implémenté (cron seulement)
### Technique
- Redis isolé par worker de test
- Test météo déterministe
- Tests rouges puis verts par histoire utilisateur

Documentation du module : [docs/modules/006-dashboard-monitoring/](docs/modules/006-dashboard-monitoring/)

## [0.4.0] - 2026-11-07 — F6 Journal des opérations
### Ajouts
- Journal des opérations de l'exploitation
- Traitements phytosanitaires avec contrôles (produit, dose, délai avant récolte)
- Calcul de la date de récolte au plus tôt
- Planification des opérations et rappels
- Registre phytosanitaire append-only avec export PDF et Excel
- Catalogue d'homologations (la recherche ne renvoie que la dernière version)
- Corrections de sécurité : parité des gardes, clés d'objets émises par le serveur, anonymisation par colonne, conservation basée sur l'horodatage serveur, season_id fixé par le serveur, quotas sous verrou
- Dérogation de budget APK à 52 Mo documentée via apk-budget.env
### Corrections
- Règles de synchronisation PowerSync valides
- Durcissement du registre (aucune suppression de ligne, y compris dans l'aide e2e)
- Tests rouges contradictoires corrigés
### Documentation
- Documentation ingénieur et agriculteur (fr, ar) du module 005-operations-journal
- Taille de l'APK mesurée et dérogation documentée
- Limites connues : écrans reportés (porte design T004 et 004-design-system), dictée et reconnaissance d'étiquette non câblées, durée de conservation de 5 ans à confirmer
### Technique
- Migration 0006, configuration, client_ip et limiteur de débit
- Simplification de l'écriture des lignes d'opération
- Lint vert sur les tests (idiome d'import des fixtures, ordre des imports)
Documentation du module : [docs/modules/005-operations-journal/](docs/modules/005-operations-journal/)

## [0.3.0] - 2026-11-07 — F2 Parcelles et cultures
### Ajouts
- Parcelles, cultures et campagnes : modèle, API, synchronisation et règles de domaine
- Découper et fusionner des parcelles, avec quota
- Carte et tuiles hors ligne (style de carte, garde des tuiles)
- Archivage, purge et export des parcelles
- Irrigation liée aux parcelles et aux cultures
- Corrections de sécurité : parcelle archivée masquée à l'ouvrier en REST, synchronisation et export ; plafonds de sommets et de 500 parcelles avec verrou ; règles PowerSync valides avec garde-fou
- Dérogation de budget APK à 52 Mo, documentée via le mécanisme apk-budget.env
### Corrections
- Les règles de synchronisation PowerSync sont acceptées par le service
- Vérification de types des règles de domaine sous noUncheckedIndexedAccess
- L'export applique la barrière des parcelles archivées pour les ouvriers
### Documentation
- Documentation ingénieur et agriculteur du module 003-fields-crops
- Audit du contenu de l'APK : aucun levier ne comble l'écart de 40 Mo ; dérogation à 52 Mo documentée
- Limites connues : écrans reportés (porte design T004), photos de cultures et morocco.pmtiles non fournis
### Technique
- Tests rouges puis verts pour fondations, règles de domaine, géométrie, découpe/fusion, archivage, export, garde des tuiles et dérogation APK
- R8 et réduction des ressources, mesures du budget APK
- Corrections de lint et annotations de types
- Fusion de main dans la branche

Documentation du module : [docs/modules/003-fields-crops/](docs/modules/003-fields-crops/)

## [0.2.0] - 2026-11-07 — F1 Compte, onboarding et ferme
### Ajouts
- Fondations du module compte, onboarding et ferme (modèle, API, domaine)
- Inscription par OTP
- Langue, consentement et ferme
- Suppression de compte, multi-fermes et invitations
- Durcissement de sécurité : OTP (limitation de débit, auth renforcée), proxys de confiance fail-closed (Caddy /32 sur réseau edge dédié, port API sur loopback, repli sur le pair), ferme supprimée refusée, autorisation par rôle sur les écritures admin (REST et upload de synchronisation)
### Corrections
- Caddy joint l'API via le réseau edge pour que l'adresse du proxy de confiance corresponde
- Les tests d'intégration obtiennent toujours leur base jetable sous xdist
- diagrams: un fichier markdown sans image n'échoue plus au contrôle des images
### Documentation
- Documentation ingénieur et agriculteur du module 002-account-onboarding-farm
- Référence du design system mobile AYLAL
- Les flux Maestro vivent dans apps/mobile/maestro (émulateur aylal-2go)
- Tableau de mesures 001-foundations (non mesuré)
- Limites connues : écrans mobiles reportés (porte design T004 bloquée) ; e2e Maestro non exécutés
### Technique
- Portes qualité accélérées (conteneurs de test préchauffés, base modèle, pytest parallèle, revue à deux niveaux)
- Configuration lint des tests, couverture compatible greenlet, sous-processus bloquant autorisé au démarrage des tests
- Tâches F1 cochées, état de fusion marqué
Documentation du module : [docs/modules/002-account-onboarding-farm/](docs/modules/002-account-onboarding-farm/)

## [0.1.1] - 2026-11-07 — hotfix App mobile réelle et e2e Android sur émulateur macOS
### Corrections
- e2e: no host python/openssl, measures extraction never fails the run; untrack .coverage
- platform: make up applies database migrations before the API starts
- platform: API e2e tests run only through make e2e-api, after make up
- platform: one compose project per branch, shared build caches
- api: isolate integration tests in a throw-away database per session
- mobile: green - map and showcase routes, home.root, provisional emulator measures export
- mobile: valid PowerSync sync rules and e2e stack bootstrap (secret, seed) before Maestro
- mobile: green - PowerSync/SQLCipher local db, connector, trial record route, e2e stack wiring
- mobile: green - real Expo SDK 58 app, APK builds and home flow passes on emulator
### Technique
- mobile: classify schema contract test as integration; pyramid gate recognises app test layout
- build: skip APK rebuild when its inputs are unchanged
- mobile: provisional emulator measures (startup, map, fps)
- mobile: red - measure session and E2E local parcels
- mobile: red - real PowerSync adapter, connector, runtime config and app config
- mobile: add PowerSync, op-sqlite and build-properties dependencies
- hotfix: red - real mobile deps guard and Android e2e on macOS emulator

Documentation du module : [specs/001-foundations/decisions.md](specs/001-foundations/decisions.md) (section « Hotfix android-e2e »)

## [0.1.0] - 2026-11-07 — F0 Fondations : monorepo, Docker, CI, design system, i18n, synchronisation hors ligne
### Ajouts
- foundations: green - repo skeleton, shared validation, platform docker
- foundations: green - offline sync, auth hardening, design system
- foundations: green - mobile home, mobile shell, diagrams, device measures
### Corrections
- foundations: correctif sécurité (IDOR, JWT) et dev-token activé uniquement pour les cibles de test
- foundations: lint, typecheck et pyramid gate
- foundations: apk-size rapporte honnêtement « non mesuré » (limite connue : taille APK non mesurée, blocage documenté)
### Documentation
- foundations: spec, plan, tâches, décisions, quickstart, matrice de traçabilité
- 001-foundations: documentation ingénieur et agriculteur
- foundations: raison du blocage F0 (apk-size non mesuré) consignée
### Technique
- tests red de chaque lot, tests unitaires/intégration/e2e obligatoires par module
- chore(loop), chore(git): pipeline et versionnement local
- build: montage du domaine dans api-test, ignore du store pnpm

Documentation du module : [docs/modules/001-foundations/](docs/modules/001-foundations/)

