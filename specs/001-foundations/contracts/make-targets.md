# Contrat des commandes `make`

Prérequis hôte : Docker (Compose v2) et make. Les cibles existantes ne sont ni renommées ni supprimées.

| Cible | Comportement | Code de sortie |
| --- | --- | --- |
| `make up` | `docker compose up -d --build --wait` ; tous les services sains | ≠ 0 en nommant le service non sain |
| `make down` | arrête (volumes conservés) | 0 |
| `make test` | `test-api` + `test-domain` + `test-mobile` | ≠ 0 si un test échoue, le test est nommé dans la sortie |
| `make test-api` / `test-domain` / `test-mobile` | pytest / Vitest sur packages / Jest-RNTL mobile | idem |
| `make test-visual` (nouveau) | captures Storybook 3 thèmes × 2 sens contre les références | ≠ 0 si écart ; `make update-visual` régénère (revue obligatoire) |
| `make e2e` | Maestro sur émulateur Android (KVM requis) | ≠ 0 avec message explicite si KVM absent, sauf `E2E_SKIP=1` (avertissement visible) |
| `make lint` / `typecheck` | Ruff, ESLint, mypy, tsc | ≠ 0 |
| `make coverage` | seuil 80 % pytest et Vitest | ≠ 0 sous le seuil |
| `make check` | lint, typecheck, test, coverage, test-visual, apk-size, diagrams, e2e | ≠ 0 si l'un échoue |
| `make diagrams` | rend `docs/**/diagrams/*.mmd` en SVG + PNG ; reproductible | ≠ 0 en nommant le `.mmd` invalide |
| `make report` | produit `docs/modules/001-foundations/mesures.md` depuis les JSON de mesure | ≠ 0 si un seuil est « non tenu » avec `STRICT=1` |
| `make apk-size` (nouveau) | construit l'APK release en conteneur et compare à 40 Mo | ≠ 0 au-dessus du seuil |

Services attendus et noms figés : `db`, `redis`, `minio`, `powersync`, `api`, `worker`, + `proxy`, `minio-init`, `storybook` ; profils `test` (`api-test`, `js-test`, `visual`) et `e2e` (`e2e`).
