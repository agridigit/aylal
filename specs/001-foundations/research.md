# Recherche : F0 — Fondations

Toutes les inconnues sont tranchées (aucun « NEEDS CLARIFICATION » restant). Format : Décision / Justification / Alternatives.

## R1 — Organisation du monorepo
- **Décision** : pnpm workspaces (`apps/*`, `packages/*`), TypeScript strict, `tsconfig.base.json` partagé ; Python géré par `uv`/pip dans l'image `services/api`.
- **Justification** : CPS section 16 ; un seul lockfile JS ; images Docker reproductibles.
- **Alternatives** : Nx/Turborepo (surcoût inutile en F0).

## R2 — Plateforme Docker
- **Décision** : compléter `docker-compose.yml` sans renommer ; healthchecks sur tous les services (`db` pg_isready, `redis` ping, `minio` /minio/health/live, `powersync` /probes/liveness, `api` GET /v1/health, `worker` commande Arq `--check`, `proxy`) ; `make up` = `docker compose up -d --build --wait` (échoue en nommant le service non sain). Migrations Alembic lancées au démarrage de `api` après `db` sain. `depends_on: condition: service_healthy` partout.
- **Justification** : FR-002, cas limite d'ordre de démarrage.
- **Alternatives** : script d'attente maison (moins fiable).

## R3 — Images PowerSync et stockage de sync
- **Décision** : `journeyapps/powersync-service` (édition ouverte, auto-hébergée) avec Postgres comme source de réplication (publication logique `powersync`) et un second schéma/base `powersync_storage` pour le stockage de buckets ; version de l'image **figée** (plus de `latest`) lors de F0 puisque le compose note « à confirmer en F0 ».
- **Justification** : un seul moteur de base, aucun MongoDB à ajouter (sobriété) ; hébergement Maroc possible.
- **Alternatives** : MongoDB en stockage (service de plus) ; repli WatermelonDB (déclenché seulement si le prototype échoue).

## R4 — Stratégie de tests JS
- **Décision** : Vitest pour `packages/*` ; **Jest `jest-expo` + React Native Testing Library** pour `apps/mobile` (et les composants natifs de `packages/ui`) ; Playwright pour captures sur Storybook web.
- **Justification** : RNTL + preset Expo sont supportés et stables sous Jest ; Vitest avec le transformeur React Native est fragile. Écart mineur à la liste d'entrée (Vitest cité), documenté ici ; `make test-mobile` reste l'interface.
- **Alternatives** : Vitest partout (risque de plugins instables).

## R5 — Validation partagée mobile/serveur (FR-016, scénario 3.5)
- **Décision** : source unique = schémas Zod dans `packages/domain` (+ règles pures). Un script exporte du JSON Schema (`zod-to-json-schema`) vers `packages/domain/schema/*.json`; `datamodel-code-generator` génère `services/api/app/generated/*.py` (Pydantic v2), committé. Un **test de dérive** échoue si la génération diffère. Des **vecteurs de test** (`packages/domain/vectors/*.json` : entrée, résultat attendu) sont exécutés par Vitest et pytest.
- **Justification** : garantit des résultats identiques sans maintenir deux définitions à la main.
- **Alternatives** : OpenAPI comme source (inverse, moins adapté au hors ligne) ; réécriture manuelle (dérive).

## R6 — Règle de résolution des conflits (FR-015, cas « horloge décalée »)
- **Décision** : fusion **champ par champ côté serveur**, ordre = **ordre d'arrivée au serveur** (`server_version` croissant), jamais l'horloge de l'appareil. Chaque opération envoyée porte `op_id` (UUID), `base_version` et les seuls champs modifiés. Si un champ modifié a changé sur le serveur depuis `base_version`, la dernière arrivée l'emporte, **la valeur écartée est écrite dans `sync_conflicts`** et l'enregistrement passe à l'état « en conflit » visible jusqu'à acquittement. Suppression = suppression logique ; modification concurrente d'une suppression : la suppression l'emporte mais la modification est journalisée. Idempotence : table `applied_ops(op_id)` → 0 doublon à la reprise après coupure.
- **Justification** : déterministe, indépendant des horloges, aucune perte silencieuse, simple à documenter.
- **Alternatives** : LWW sur horloge appareil (perte avec horloge fausse) ; CRDT (complexité disproportionnée en F0).

## R7 — Chiffrement
- **Transit** : TLS partout hors réseau Docker interne ; service `proxy` Caddy (CA interne en dev) devant `api` et `powersync` ; l'app refuse le HTTP en clair hors dev.
- **Repos téléphone** : SQLite via PowerSync avec **SQLCipher** ; clé aléatoire générée au premier lancement, stockée dans Android Keystore (`expo-secure-store`).
- **Repos serveur** : volumes chiffrés au niveau hébergeur (décision d'hébergement hors F0) ; F0 documente l'exigence et active `scram-sha-256` ; secrets via `.env` non versionné.
- **Alternatives** : chiffrement champ par champ (complexité, pas requis).

## R8 — Contrôle d'accès (FR-018) et compte d'essai
- **Décision** : JWT HS256 (secret d'environnement) émis par `POST /v1/auth/dev-token`, **actif uniquement si `AYLAL_ENV=dev|test`** ; claims `sub`, `farm_ids`, `roles`. PowerSync valide le JWT et filtre les buckets par ferme (voir `contracts/powersync-sync-rules.yaml`) ; l'API revérifie ferme + rôle sur chaque opération envoyée (propriétaire/éditeur/lecteur). F1 remplacera l'émetteur par téléphone + OTP.
- **Alternatives** : sécurité côté client seulement (rejeté).

## R9 — E2E mobile avec Maestro dans Docker
- **Décision** : image `infra/docker/e2e.Dockerfile` (Android SDK + émulateur x86_64 + Maestro) ; APK construit dans `android-build.Dockerfile`. L'émulateur exige `/dev/kvm` (Linux/CI). `make e2e` détecte l'absence de KVM et **échoue explicitement** avec un message ; `make check` appelle `e2e` sauf `E2E_SKIP=1` (écart signalé dans la sortie, jamais silencieux).
- **Risque** : Docker Desktop sur macOS n'expose pas KVM. Mitigation : e2e s'exécute en CI Linux ; les mesures sur appareil réel passent par le protocole R12.
- **Alternatives** : émulateur sur l'hôte (interdit par la règle Docker).

## R10 — Design system et catalogue (FR-021 à FR-024)
- **Décision** : jetons TypeScript dans `packages/ui/src/tokens` (3 thèmes `light`, `dark`, `sun` ; `sun` ≥ 7:1 pour le texte courant, vérifié par test calculant le ratio WCAG) ; Unistyles pour thèmes/RTL ; composants maison F0 : Button, IconButton, Text, Card, TextField, Switch, Chip/Badge, SyncBadge, Skeleton, EmptyState, ErrorState, OfflineBanner, ScreenScaffold, LanguageSwitcher. Catalogue = Storybook sur react-native-web (une story par variante/état, barre d'outils thème + sens) ; captures Playwright (`toHaveScreenshot`) 3 thèmes × 2 sens exécutées dans `visual.Dockerfile` (image Playwright épinglée pour des rendus stables). Zone tactile ≥ 48 dp imposée par le composant et testée. Durées d'animation via jeton `motion.base = 240 ms` ; `useReducedMotion` de Reanimated coupe/réduit.
- **Alternatives** : Tamagui (à ne considérer que si Unistyles échoue au prototype) ; Chromatic (service externe payant).

## R11 — i18n et RTL (FR-007, FR-008)
- **Décision** : i18next + `react-i18next`, locales `ary` (darija, graphie arabe), `ary-Latn` (darija latine), `ar`, `fr` ; repli `fr`. RTL forcé (`I18nManager.forceRTL`) pour `ary` et `ar` (redémarrage de l'activité géré au changement de langue) ; icônes directionnelles via jeton `mirror`. Polices IBM Plex Sans / Plex Sans Arabic embarquées en sous-ensemble (400/500/700). Test Vitest de complétude : mêmes clés dans les 4 fichiers, aucune valeur vide ; lint interdisant les chaînes littérales JSX.
- **Alternatives** : expo-localization seule (insuffisant pour darija).

## R12 — Prototype de validation et mesures (Récit 6)
- **Décision** : module `apps/mobile/src/perf` collecte : temps de démarrage à froid (`ReactMarkerPath`/horodatage natif → premier rendu), temps d'ouverture de la carte (50 parcelles GeoJSON synthétiques déterministes, couleur de vigueur par expression MapLibre, fond sans tuile distante), images/s (`useFrameCallback` Reanimated), octets réseau (compteur dans le connecteur de sync). Résultats JSON → `scripts/report.sh` produit `docs/modules/001-foundations/mesures.md` : valeur, seuil, appareil, verdict (tenu/non tenu) ; un « non tenu » écrit une entrée de réexamen. Taille APK vérifiée par script (`apk-size`), seuil 40 Mo. Micro et photo du CPS §16 : hors périmètre F0 (la spec FR-027 ne les cite pas).
- **Alternatives** : Flashlight/Perfetto (utiles mais non obligatoires).

## R13 — Lecture vocale (FR-011)
- **Décision** : `expo-speech` (synthèse de l'appareil), locale selon la langue (`ar-MA` si disponible, sinon `ar`, `fr-FR`) ; si aucune voix, bouton désactivé avec message (état erreur). Les voix darija hébergées relèvent de F7.

## R14 — Télémétrie (FR-020)
- **Décision** : module `telemetry` avec identifiant aléatoire non lié à la personne, réglage « activé » par défaut modifiable et persisté, transport **no-op** en F0 (comptage local) ; test : désactivé ⇒ aucun envoi.

## R15 — Diagrammes (FR-025)
- **Décision** : conserver `scripts/render-diagrams.sh` (Mermaid CLI en Docker) ; ajouter l'image épinglée par version, le fichier `docs/templates/mermaid-config.json` s'il manque, et un test qui lance un `.mmd` invalide et vérifie l'échec avec le nom du fichier. Reproductibilité : image épinglée, sortie SVG sans horodatage ; le script ne réécrit pas un rendu à jour. Problème noté : le script appelle `docker run` ; `make diagrams` tournant sur l'hôte avec Docker, c'est conforme (Docker seul prérequis).

## R16 — Couverture et qualité
- **Décision** : `pytest --cov=app --cov-fail-under=80` et Vitest `coverage.thresholds` 80 % sur `packages/domain` et `packages/i18n` ; Ruff, mypy strict, ESLint, `tsc --noEmit` ; `make check` = lint + typecheck + test + coverage + visual + diagrams + e2e.

## R17 — Hébergement Maroc (FR-019)
- **Décision** : F0 n'utilise aucun service tiers pour les données utilisateur (polices embarquées, pas de CDN, pas de Firebase, pas d'EAS) ; un test statique parcourt la configuration et échoue sur un hôte externe non autorisé (liste blanche : localhost, noms de services Compose).

## R18 — Budget de taille (40 Mo)
- **Décision** : build release Hermes, ABI `arm64-v8a` (+ `armeabi-v7a` à évaluer), `minify`/`shrinkResources`, polices en sous-ensemble ; script `scripts/apk-size.sh` mesure l'APK dans le conteneur de build et échoue au-dessus de 40 Mo.
