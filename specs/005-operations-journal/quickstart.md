# Quickstart : valider F6 de bout en bout

Prérequis : Docker ; `make bootstrap` déjà exécuté. Aucune installation sur l'hôte.

1. **Tests unitaires et domaine** : `make test` (Vitest `packages/domain` : vecteurs `f6_*.json` ; pytest unit).
2. **API et intégration** : `make test-api` — doit couvrir : matrice de parité G1 (REST, `/v1/sync/upload`, export de compte, purge), 404 inter-ferme, 403 par rôle, parcelle archivée masquée à l'ouvrier, plafonds G3 et courses de quota, triggers append-only G4, limites de débit G5.
3. **Règles de synchro** : `scripts/validate-sync-rules.sh` (inclus dans `make check`) — aucune jointure ni sous-requête.
4. **Mobile** : `make test-mobile` (view models, contrôles locaux, rappels) ; écrans seulement après la porte design.
5. **E2E** : `make e2e` — parcours Maestro `operation_quick`, `phyto_warning`, `harvest_date`, `planned_reminder`, `dictation`, `registry_export`, `worker_validation`.

Scénarios de recette manuelle (docker compose up) :
- Créer une opération de chaque type, hors ligne puis synchroniser : aucune perte (SC-004).
- Traitement à DAR 21 j : la date de récolte passe à J+21 ; deux produits : le plus long l'emporte (SC-003).
- Dose > max, culture non autorisée, applications max atteintes : trois avertissements conservés au registre (SC-002).
- Corriger un traitement validé : écriture compensatoire + historique ; `UPDATE registry_entries …` en SQL direct échoue.
- Ouvrier : voit uniquement ses lignes, 403 sur validation et export ; parcelle archivée disparaît de son journal.
- Export PDF et XLSX d'une parcelle puis de la ferme : colonnes identiques, avertissements présents (SC-005).

Références : [data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml), [contracts/registry-rules.md](contracts/registry-rules.md), [contracts/powersync-sync-rules.yaml](contracts/powersync-sync-rules.yaml).
