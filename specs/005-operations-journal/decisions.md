# Décisions : F6 — Journal des opérations et registre phyto

## À confirmer

- **Durée de conservation du registre phyto** : le CPS ne fixe aucune durée. Valeur par défaut retenue : **5 ans** à compter de la date de l'opération (`AYLAL_REGISTRY_RETENTION_YEARS=5`, supérieure aux 2-3 ans des référentiels d'export de type GlobalG.A.P.). À confirmer par un juriste (loi 09-08 / CNDP / ONSSA). Pendant la durée, la suppression de compte anonymise les données personnelles et conserve les lignes du registre ; purge par `purge_expired_registry` après échéance.
- **Articulation suppression de compte (30 j) et conservation légale** : anonymisation + export préalable au demandeur, à valider avec la même revue juridique.
- **Source du catalogue PhytoIndex et reconnaissance d'étiquette / dictée** (F5/F7 absents) : ports `LabelRecognizer` et `VoiceParser` avec repli ; fournisseurs à décider.

## Dépendance design

- La porte design (T004) est une validation humaine, non encore donnée. Les écrans dépendent aussi de la fusion de `004-design-system` dans main. F6 ne modifie ni `packages/ui` ni `docs/design/aylal-design-system.md`.
- **Composants demandés à `004-design-system`** : `OperationTypeTile`, `WarningBanner`, `DoseField`, `HarvestDateCard`, `PendingBadge`, `ProductRow`.

## Tests RED des fondations (T005-T022a)

- **Niveau bout en bout** : aucun E2E pour les fondations (garde-fous, règles pures, migration) ; les E2E API de F6 sont portés par T035, T046, T056, T062 (récits). Les fondations sont couvertes en unitaire, intégration et contrat.
- **Contrat `openapi.yaml` invalide en YAML** : la ligne `earliest-harvest` contient `: ` dans un mappage de flux (échec de `yaml.safe_load`) ; T030 doit le corriger pour faire passer T022.
- **T021** : la migration crée 10 tables (7 « de ferme » + `phyto_products`, `phyto_product_uses`, `catalog_versions`), comme dans T024 ; le test vérifie les 10.
- **Lignes produit (`product_lines`, <= 5)** : absentes de `OperationInput` du contrat ; le test T016 les exige dans le corps ; T030 doit les ajouter au contrat.
- **MinIO** : les défauts de développement existants de `docker-compose.yml` (MINIO_ROOT_*) ne sont pas touchés ; T008 exige seulement le refus de démarrage hors dev/test (`require_minio_credentials`) et des variables F6 vides.
- **Contrat PowerSync F6** : fragment non autonome (non validé seul par le service) ; T015 valide les règles réelles `infra/powersync/sync-rules.yaml`.
