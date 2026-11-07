# Plan d'implémentation : F1 — Compte, onboarding et ferme

**Branche** : `002-account-onboarding-farm` | **Date** : 2026-11-07 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F1 (clarifications corrigées contre CPS section 6) + CPS sections 4, 6, 15, 16, 19 + constitution + leçons F0

## Résumé

F1 ajoute l'authentification par téléphone + code à usage unique (OTP), l'onboarding (langue, consentement, profil, ferme), les rôles par ferme (propriétaire, gestionnaire, ouvrier), l'invitation, le changement d'appareil, l'export et la suppression de compte. Approche : règles (format de numéro marocain, tentatives, rôles, validations) en Zod dans `packages/domain` puis JSON Schema vers Pydantic (chaîne F0) ; API FastAPI sous `/v1/auth`, `/v1/me`, `/v1/farms/...` ; OTP et verrouillage gérés dans Redis + PostgreSQL côté serveur ; envoi via un port `OtpSender` (SMS ou WhatsApp, au choix de l'utilisateur, repli sur l'autre) exécuté par le worker Arq ; session = jeton d'accès court + jeton de rafraîchissement rotatif stocké dans le coffre sécurisé du téléphone ; code local à 4 chiffres vérifié uniquement sur l'appareil. Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x strict, Python 3.13.
**Dépendances** : celles de F0 (FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Arq, Expo, i18next, PowerSync, MapLibre, Expo Speech). Ajouts minimaux : `expo-secure-store` (jeton et code local haché), `expo-location`, `argon2-cffi` (hachage OTP et jetons côté serveur). Aucun SaaS étranger.
**Stockage** : PostgreSQL 16 + PostGIS (référentiel géographique `geo_communes` avec géométrie, recherche point-dans-polygone), Redis (compteurs d'envoi), SQLite chiffré local.
**Tests** : pytest (unit, integration, contract, e2e), Vitest (domain, i18n), Jest + RNTL (écrans, view models), Maestro (parcours E2E < 2 min).
**Plateforme** : Android 9+ ; API Linux conteneurisée.
**Type** : monorepo mobile + API + workers.
**Performance** : parcours complet < 2 min (90 %) ; vérification d'un code < 300 ms p95 ; coût de données du parcours < 200 Ko ; référentiel géo embarqué compressé < 3 Mo (ou récupéré en un appel, mis en cache).
**Contraintes** : hors ligne sauf vérification initiale ; verrouillage 5 min appliqué serveur ; chiffrement transit/repos ; hébergement Maroc ; gratuit.
**Échelle** : 13 écrans (E1-E13), ~16 routes, 7 tables nouvelles.

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| I Agriculteur d'abord | OK | Parcours icônes + voix, un objectif par écran, Expo Speech |
| II Hors ligne | OK | Ferme/profil/consentement créés localement puis synchronisés ; seule la vérification initiale exige le réseau |
| III Gratuit/sobre | OK | OTP via passerelle locale/auto-hébergée ; quotas d'envoi pour borner le coût |
| IV Données à l'utilisateur | OK | Export, suppression sous 30 j, consentements versionnés et révocables |
| VI Logique unique | OK | Zod -> JSON Schema -> Pydantic ; vecteurs partagés |
| VIII/XI Test first | OK | RED -> GREEN -> REFACTOR ; chaque critère P1 a un test |
| IX i18n | OK | Clés `ary`, `ar`, `fr`, aucune chaîne en dur |
| X Design | OK | Maquettes HD validées avant tout écran (porte dans tasks) |
| XII Docker | OK | Services existants étendus, aucun outil sur l'hôte |
| XIII Maroc | OK sous condition | Passerelle SMS/WhatsApp d'un opérateur marocain ou auto-hébergée ; aucun envoi de numéro à un tiers hors Maroc (voir R3) |
| XV Seuils | OK | Mesure du parcours en recette |

### Garde-fous issus de la leçon F0 (obligatoires)

1. **Aucun secret par défaut en dur.** `AYLAL_JWT_SECRET`, `AYLAL_OTP_PEPPER`, clés de la passerelle d'envoi : lus de l'environnement, longueur minimale vérifiée, refus de démarrer hors dev/test s'ils manquent ou valent une valeur faible connue. En dev/test : secret éphémère par processus, jamais une constante. Aucune valeur dans `docker-compose.yml` autre que `${VAR:-}` vide. Le mode « code OTP fixe de test » est interdit hors `AYLAL_ENV in (dev, test)` et ne s'active que par drapeau explicite (`AYLAL_ENABLE_TEST_OTP=1`), sur le modèle de `AYLAL_ENABLE_DEV_TOKEN` ; test d'intégration qui vérifie son refus en prod.
2. **Accès toujours scopé à la ferme, 404 inter-ferme.** Toute route `/v1/farms/{farm_id}/...` passe par une dépendance unique `farm_context(farm_id, user)` qui lit le rôle en base ; si l'utilisateur n'est pas membre, réponse **404** identique à « ferme inexistante » (pas 403, pas de fuite d'existence) ; si membre mais rôle insuffisant, 403. Les objets enfants (invitation, membre, attribution) sont toujours chargés avec `farm_id` dans la clause WHERE. Tests inter-ferme obligatoires sur chaque route. Les règles PowerSync filtrent par appartenance ; l'ouvrier ne reçoit que ses parcelles et aucune table financière.
3. Rôle lu en base à chaque requête (jamais fié au jeton) ; retrait d'un membre effectif immédiatement côté API, côté synchro à la prochaine émission de jeton PowerSync.

## Structure du projet

### Documentation

```text
specs/002-account-onboarding-farm/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/ (openapi.yaml, auth-otp.md, powersync-sync-rules.yaml)
└── tasks.md   # produit par /speckit-tasks
```

### Code source (réutilise F0, ajoute seulement ce qui est requis)

```text
packages/domain/src/{phone,otp-policy,roles,farm,consent,onboarding}.ts   # règles + Zod
packages/i18n/locales/{ary,ar,fr}/{auth,onboarding,farm,team,account}.json
services/api/app/auth/{otp.py,sessions.py,access.py(étendu),farm_context.py}
services/api/app/domain/{roles.py,otp_policy.py}
services/api/app/routers/{auth.py,me.py,farms.py,members.py,invitations.py,geo.py,account.py}
services/api/app/db/models.py (+ tables) ; services/api/alembic/versions/0002_account_farm.py
services/api/app/geo/ (référentiel, point-dans-commune)
services/workers/tasks/{send_otp.py,purge_deleted_accounts.py,expire_invitations.py}
infra/powersync/sync-rules.yaml (étendu : rôles, parcelles attribuées)
apps/mobile/src/screens/{Language,Phone,Code,Consent,Profile,FarmCreate,FarmSwitcher,Team,Invite,WorkerAccess,Settings,DeleteAccount,Restore}/
apps/mobile/src/auth/{session.ts,secureStore.ts,localPin.ts}
apps/mobile/maestro/onboarding.yaml
```

**Décision de structure** : pas de nouveau service Docker ; le worker existant exécute les tâches ; `geo` est un module de l'API. Les `Makefile` cibles existantes restent inchangées (nouveaux tests découverts par les cibles actuelles).

## Vérification de la constitution (après conception)

Inchangé : OK. Écart signalé à `tasks` : migration des rôles F0 (`owner/editor/viewer`) vers `owner/manager/worker` (data-model, M1) avec test de non-régression des tests ACL F0. Point ouvert non bloquant : choix de l'opérateur marocain de passerelle (R3), interface `OtpSender` isolant ce choix.

## Suivi de complexité

Aucune violation.
