# Traçabilité : critères d'acceptation P1 -> tests automatisés (SC-009)

Numérotation : Récit N, scénario M = ACN.M (ordre de `spec.md`). Chaque ligne a au moins un test automatisé.

| AC | Critère | Tests |
|----|---------|-------|
| AC1.1 | `make up` : services sains | `tests/platform/test_services_healthy.sh`, `services/api/tests/contract/test_health_contract.py` |
| AC1.2 | `make check` exécute tout dans des conteneurs | `tests/platform/test_make_targets.sh`, `tests/platform/test_coverage_gate.sh`, `scripts/check-test-pyramid.sh` |
| AC1.3 | Test en échec : `make check` échoue et nomme le test | `tests/platform/test_failing_test_named.sh` |
| AC1.4 | Aucune dépendance hôte hormis Docker | `tests/platform/test_no_host_deps.sh`, `tests/platform/test_no_foreign_defaults.sh` |
| AC2.1 | Accueil < 3 s | `apps/mobile/src/perf/__tests__/startupMark.test.ts`, `apps/mobile/maestro/home_languages.yaml` (e2e, KVM) |
| AC2.2 | 3+1 langues, aucune clé manquante | `packages/i18n/tests/completeness.test.ts`, `packages/i18n/tests/fallback.test.ts`, `packages/i18n/tests/integration/locales-files.test.ts`, `apps/mobile/src/screens/Home/__tests__/Home.i18n.test.ts` |
| AC2.3 | Miroir RTL complet | `apps/mobile/src/screens/Home/__tests__/Home.rtl.test.ts` |
| AC2.4 | 4 états (chargement, vide, erreur, hors ligne) | `apps/mobile/src/screens/Home/__tests__/Home.states.test.ts`, `apps/mobile/maestro/home_languages.yaml` |
| AC2.5 | Zones tactiles >= 48 dp | `apps/mobile/src/screens/Home/__tests__/Home.touch.test.ts`, `packages/ui/tests/touch-target.test.ts` |
| AC3.1 | Création hors ligne, « non envoyée » | `apps/mobile/src/screens/TrialRecord/__tests__/TrialRecord.test.ts`, `apps/mobile/src/sync/__tests__/localStore.test.ts`, `apps/mobile/maestro/offline_sync.yaml` |
| AC3.2 | Envoi automatique au retour du réseau, idempotent | `services/api/tests/integration/test_idempotency.py`, `services/api/tests/contract/test_openapi_sync.py`, `tests/contract/test_powersync_rules.py`, `apps/mobile/src/sync/__tests__/syncState.test.ts`, `services/api/tests/e2e/test_offline_sync_e2e.py` |
| AC3.3 | 30 jours hors ligne : 0 perte, 0 doublon | `services/api/tests/integration/test_offline_30_days.py` |
| AC3.4 | Conflit déterministe, valeur écartée journalisée | `packages/domain/tests/conflict.test.ts`, `services/api/tests/unit/test_conflict_resolution.py`, `services/api/tests/integration/test_conflicts.py`, `services/api/tests/integration/test_acl_conflict_ack.py` |
| AC3.5 | Même verdict TS / Python (vecteurs partagés) | `packages/domain/tests/validation.test.ts`, `packages/domain/tests/integration/rules-registry.test.ts`, `services/api/tests/unit/test_shared_validation.py`, `services/api/tests/integration/test_validation_server.py`, `services/api/tests/contract/test_generated_schema_fresh.py` |
| AC3.6 | Chiffrement au repos et en transit | `services/api/tests/integration/test_encryption.py`, `apps/mobile/src/sync/__tests__/encryptionKey.test.ts` |
| AC4.1 | 3 thèmes sans élément illisible | `packages/ui/tests/tokens.schema.test.ts`, `packages/ui/visual/catalog.spec.ts` |
| AC4.2 | Contraste plein soleil >= 7:1 | `packages/ui/tests/contrast.test.ts` |
| AC4.3 | Variantes et états documentés | `packages/ui/tests/stories-coverage.test.ts`, `packages/ui/tests/integration/exports.test.ts` |
| AC4.4 | RTL de chaque composant | `packages/ui/visual/catalog.spec.ts` (3 thèmes x 2 sens), `packages/ui/tests/long-text.test.ts` |
| AC4.5 | Régression visuelle détectée | `packages/ui/visual/regression-detect.spec.ts` |
| AC4.6 | Animations réduites (200 à 300 ms) | `packages/ui/tests/motion.test.ts` |

## Limites
- Les parcours Maestro (AC2.1, AC2.4, AC3.1, AC3.2) ne s'exécutent qu'avec KVM (CI Linux) ; sur macOS `E2E_SKIP=1` (voir `decisions.md`).
- AC2.1 : la mesure réelle < 3 s sur Android 2 Go relève de T110.
