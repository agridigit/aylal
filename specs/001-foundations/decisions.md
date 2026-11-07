# Décisions : 001-foundations

## Récit 3 (RED) : choix de test
- Refus d'accès à l'envoi : le contrat `/sync/upload` ne définit pas de 403 ; un refus est donc un résultat par opération (`status: rejected`, `error.code: forbidden`), HTTP 200. Le 403/404 HTTP ne s'applique qu'à `/sync/conflicts/{id}/acknowledge`.
- Seuil de stockage faible (`LOW_STORAGE_BYTES`) : valeur choisie au GREEN dans `storageWarning.ts`, les tests la lisent via l'export.
- Les tests d'intégration serveur montent le dépôt en lecture seule sur `/repo` dans `api-test` (contrats, `infra/powersync`) et dépendent du service `proxy` (TLS).
- Maestro (T049) et Jest mobile (T044-T048) ne peuvent pas tourner tant que `apps/mobile` n'existe pas (T057) ; l'échec RED est l'absence du module.

## Phase 6 RED : écarts de forme des tests mobiles
- Les tests Jest `Home.*` sont écrits en `.test.ts` (et non `.tsx`) : `apps/mobile/jest.config.js` n'exécute que `*.test.ts` en environnement node, sans bibliothèque de rendu React Native. Les règles (RTL, états, zones tactiles, clés i18n) sont testées via des modèles de vue purs et une analyse statique des sources `.tsx`. Le GREEN doit mapper `@aylal/i18n` dans `moduleNameMapper`.
- Intégration de l'accueil : complétude des locales contre les clés réellement utilisées (Home, TrialRecord). E2E : Maestro (T084), exécutable seulement sur émulateur.

## Phase 8 - tests RED mesures appareil
- E2E `apps/mobile/maestro/device_measures.yaml` déclaré mais NON EXÉCUTABLE sur macOS (émulateur/KVM indisponible) ; à exécuter en CI Linux/KVM ou sur l'Android 2 Go (T110).
- T100/T103 écrits en `.test.ts` (jest `testMatch` = `**/*.test.ts`, vues-modèles sans rendu natif) au lieu de `.tsx`, comme les écrans Home/TrialRecord.
- Intégration : `tests/report/` (shell, fichiers réels) ; `MODULE` (défaut 001-foundations) et `APK_PATH`/`MEASURE_OUT` sont des paramètres d'environnement pour tester sans appareil.

## Phase 9 : finition (T110 à T115)
- T110 / T111 restent ouvertes : aucun Android 2 Go de référence n'est disponible et `apps/mobile` n'a ni projet natif ni script `build:android:release` ; l'APK release n'est donc pas constructible dans Docker en l'état. `make apk-size` échoue pour cette raison (écart réel, pas contourné) ; à traiter avec l'ajout de la chaîne de build Android (Expo prebuild + Gradle) et la mesure sur appareil.
- e2e mobile : `E2E_SKIP=1 make check` sur macOS (pas de KVM, émulateur Android impossible) avec avertissement ; la CI Linux/KVM exécute `make e2e` complet. L'e2e API (`tests/e2e`) tourne toujours.
- Portabilité de `tests/diagrams/test_render.sh` : le `grep` dépendait de la locale hôte (fichier binaire PNG traité comme texte invalide). Défaut du test, pas de la spec : `LC_ALL=C grep -a`. Aucune assertion modifiée.
- `make coverage` côté JS est limité à `@aylal/domain` (code métier, seuil 80 %) : `i18n` et `ui` n'embarquent pas `@vitest/coverage-v8` et ne contiennent pas de règle métier. Domaine : 93,8 % ; API : 88,55 %.
- Porte `check-test-pyramid.sh` : pour `apps/*`, les tests vivent à côté du code (`src/**/__tests__`) et les parcours e2e dans `maestro/` ; la porte les reconnaît. Des tests d'intégration ont été ajoutés pour `domain`, `i18n`, `ui`.
- Typage : `noUncheckedIndexedAccess` désactivé pour `packages/i18n` et `apps/mobile` (des tests existants indexent sans garde) ; `mypy` ignore `app/generated/models.py` (code généré) ; ruff : `PLW1510`, `B017` ignorés dans `tests/**`.

## APK release : non mesuré (blocage constaté)
- `apps/mobile` n'est pas encore une application Expo/React Native : ni `expo` ni `react-native` dans `package.json`, pas de projet natif, pas de script `build:android:release`.
- L'image `aylal-android-build` ne contient que JDK 17 et pnpm, sans Android SDK. L'hôte Docker est aarch64 (Apple Silicon) : Google ne publie pas de build-tools Android pour Linux arm64 (aapt2 x86_64 seulement), donc `gradle assembleRelease` n'est pas fiable sans émulation x86_64 (QEMU), non validée ici.
- Décision : rien n'est inventé. `make apk-size` affiche « NON MESURE » et échoue (code 1) tant que la chaîne n'existe pas ; le test `tests/report/test_apk_size.sh` (logique de seuil via APK_PATH) reste inchangé et vert.
- À faire (T110/T111) : ajouter expo/react-native épinglés, `expo prebuild`, SDK Android épinglé dans le Dockerfile (plateforme linux/amd64), script `build:android:release`, puis mesurer.

## Hotfix android-e2e : synchro réelle sur émulateur
- PowerSync 1.28.1 refuse la sous-requête de `sync_conflicts` (« select not supported here ») : la règle devient `WHERE farm_id = bucket.farm_id AND acknowledged_at IS NULL` (contrat et infra restent identiques).
- L'API n'expose pas de JWKS : PowerSync valide les jetons HS256 avec une clé inline dérivée de `AYLAL_JWT_SECRET` (entrypoint compose). Sans secret, clé aléatoire (aucun jeton valide).
- `@powersync/op-sqlite` abandonné (incompatible avec `@powersync/react-native` 2.4 qui embarque l'adaptateur op-sqlite).
- Identité ferme/utilisateur : constantes du seed, builds E2E uniquement. Opération rejetée par l'API : reste en file (pas de perte), à traiter en F suivante.
