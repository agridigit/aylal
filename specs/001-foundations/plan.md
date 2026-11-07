# Plan d'implémentation : F0 — Fondations techniques d'AYLAL

**Branche** : `001-foundations` | **Date** : 2026-11-07 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F0 + CPS sections 15, 16, 19 + constitution v1.0.0

## Résumé

F0 pose le socle exécutable : monorepo pnpm, plateforme Docker Compose en bonne santé (`make up`), porte de qualité `make check`, application Expo (écran d'accueil trilingue RTL à 4 états), synchronisation hors ligne PowerSync sans perte, design system + catalogue Storybook avec captures de référence, rendu Mermaid, et prototype mesuré sur Android 2 Go. Approche : tout vit dans des conteneurs ; règles métier et validation définies une fois en Zod (`packages/domain`), exportées en JSON Schema puis Pydantic (génération + vecteurs de test partagés) ; conflits résolus côté serveur par ordre d'arrivée, champ par champ, avec journal des valeurs écartées. Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x (strict), Python 3.13.
**Dépendances principales** : pnpm workspaces, Expo (SDK courant figé au lockfile) + React Native, Unistyles, Reanimated, Skia/SVG, MapLibre RN, Expo Haptics, Expo Speech, i18next ; `@powersync/react-native` + SQLCipher ; FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Arq ; Storybook (react-native-web) + Playwright.
**Stockage** : PostgreSQL 16 + PostGIS (service `db`, `wal_level=logical`), SQLite chiffré (SQLCipher) sur le téléphone, Redis, MinIO (S3).
**Tests** : pytest (+pytest-cov), Vitest (domain, i18n, ui-logique), Jest `jest-expo` + React Native Testing Library (apps/mobile, voir research R4), Playwright (captures), Maestro (E2E).
**Plateforme cible** : Android 9+ (2 Go RAM) ; serveur Linux conteneurisé ; web/desktop = squelettes.
**Type de projet** : monorepo mobile + API + workers.
**Objectifs de performance** : démarrage < 3 s ; carte de 50 parcelles < 2 s depuis le cache ; 60 i/s ; APK < 40 Mo ; < 5 Mo/jour de données ; `make diagrams` < 2 min.
**Contraintes** : hors ligne 30 jours, 0 perte/0 doublon sur ≥ 1 000 enregistrements, chiffrement transit + repos, aucune dépendance obligatoire hors Maroc, rien installé sur l'hôte, couverture métier ≥ 80 %.
**Échelle/portée** : 1 écran d'accueil, 1 écran de saisie d'essai, 1 écran carte, 1 écran animé, catalogue de ~12 composants de base.

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| II Hors ligne | OK | SQLite + PowerSync, file d'envoi persistante, test 30 jours simulés |
| III Gratuit/sobre | OK | Composants open source auto-hébergés, aucun service payant |
| IV Données à l'utilisateur | OK | Contrôle d'accès ferme/rôle côté serveur ; télémétrie anonyme désactivable |
| VI Logique unique | OK | Zod → JSON Schema → Pydantic + vecteurs partagés |
| VII Petits téléphones | OK | Hermes, ABI arm64, polices sous-ensemble, budget 40 Mo vérifié par script |
| VIII/XI Test first | OK | Tâches ordonnées RED → GREEN → REFACTOR, commits dédiés |
| IX Anglais/i18n | OK | Clés `ary`, `ary-Latn`, `ar`, `fr`, test de complétude |
| X Design | OK | Jetons 3 thèmes, catalogue, captures de référence, RTL |
| XII Docker | OK | Tout via `docker compose` ; Dockerfiles ajoutés |
| XIII Maroc | OK | Aucun SaaS hors Maroc (pas de Firebase/EAS/CDN de polices en F0) ; hébergeur final hors périmètre |
| XIV Documentation | OK | `docs/modules/001-foundations/` en fin de fonctionnalité |
| XV Seuils | OK | Rapport de mesure prototype contre section 15 |

Aucune violation : tableau de complexité non requis. Deux écarts de moyens sont justifiés en research (R4 runner Jest pour mobile, R9 E2E nécessitant KVM).

## Structure du projet

### Documentation (cette fonctionnalité)

```text
specs/001-foundations/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/
│   ├── openapi.yaml            # API : santé, jeton d'essai, envoi de synchronisation
│   ├── powersync-sync-rules.yaml
│   ├── make-targets.md         # contrat des commandes make
│   ├── i18n-contract.md        # clés, langues, repli, RTL
│   ├── design-tokens.schema.json
│   └── shared-validation.md    # chaîne Zod -> JSON Schema -> Pydantic + vecteurs
└── tasks.md                    # produit par /speckit-tasks
```

### Code source (racine du dépôt) — existant : `Makefile`, `docker-compose.yml`, `scripts/`, `docs/`. Tout le reste est à créer.

```text
package.json  pnpm-workspace.yaml  tsconfig.base.json  .env.example  .env.test  .dockerignore
apps/
├── mobile/            # Expo (Android) : app/, src/screens/Home, src/sync/, src/voice/, src/perf/, maestro/
├── web/               # squelette (README + package.json)
└── desktop/           # squelette (README + package.json)
packages/
├── domain/            # Zod schémas, règles, résolution de conflits (pure), vecteurs de test, export JSON Schema
├── ui/                # jetons, thèmes, composants, stories, tests visuels
└── i18n/              # locales ary, ary-Latn, ar, fr ; test de complétude
services/
├── api/               # app/{main,config,db,auth,domain,generated,routers,sync}, alembic/, tests/
└── workers/           # Arq : worker.py, tâche de santé, tests/
infra/
├── docker/            # js.Dockerfile, e2e.Dockerfile, android-build.Dockerfile, visual.Dockerfile
├── powersync/         # config.yaml, sync-rules.yaml
├── caddy/             # Caddyfile (TLS interne)
└── minio/             # init des buckets
docs/modules/001-foundations/   # ingenieur.md, agriculteur.{fr,ar}.md, diagrams/, img/, mesures.md
```

**Décision de structure** : celle du CPS section 16, sans paquet superflu ; web et desktop restent des squelettes. Les services du `docker-compose.yml` existant gardent leurs noms ; on ajoute `proxy` (Caddy, TLS), `minio-init`, `storybook`, `visual` (profil test) sans renommer l'existant.

## Phases de livraison (ordre pour /speckit-tasks)

1. **Socle** : monorepo, Dockerfiles, compose complété avec healthchecks, `make up/check`, `.env*`. (Récit 1)
2. **Domaine et validation partagée** : Zod, JSON Schema, Pydantic généré, vecteurs. (Récit 3.5)
3. **API + sync** : modèles, migrations, auth d'essai, ACL, envoi idempotent, journal de conflits, config PowerSync. (Récit 3)
4. **i18n + design system + catalogue + captures**. (Récits 2 et 4)
5. **App mobile** : accueil 4 états, voix, saisie hors ligne, indicateur « non envoyé ». (Récits 2 et 3)
6. **Diagrammes** : validation Mermaid (échec nommant le fichier), reproductibilité. (Récit 5)
7. **Prototype et mesures** : carte 50 parcelles, instrumentation, rapport. (Récit 6)
8. **Documentation de module**.

## Vérification de la constitution (après conception)

Inchangée : conforme. Points de vigilance suivis en tâches : budget 40 Mo (script de taille dans `make check`), absence de dépendance hors Maroc (test qui échoue si un domaine externe est configuré par défaut), couverture 80 % (seuils bloquants Vitest et pytest).
