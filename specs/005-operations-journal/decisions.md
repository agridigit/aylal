# Décisions : F6 — Journal des opérations et registre phyto

## À confirmer

- **Durée de conservation du registre phyto** : le CPS ne fixe aucune durée. Valeur par défaut retenue : **5 ans** à compter de la date de l'opération (`AYLAL_REGISTRY_RETENTION_YEARS=5`, supérieure aux 2-3 ans des référentiels d'export de type GlobalG.A.P.). À confirmer par un juriste (loi 09-08 / CNDP / ONSSA). Pendant la durée, la suppression de compte anonymise les données personnelles et conserve les lignes du registre ; purge par `purge_expired_registry` après échéance.
- **Articulation suppression de compte (30 j) et conservation légale** : anonymisation + export préalable au demandeur, à valider avec la même revue juridique.
- **Source du catalogue PhytoIndex et reconnaissance d'étiquette / dictée** (F5/F7 absents) : ports `LabelRecognizer` et `VoiceParser` avec repli ; fournisseurs à décider.

## Dépendance design

- La porte design (T004) est une validation humaine, non encore donnée. Les écrans dépendent aussi de la fusion de `004-design-system` dans main. F6 ne modifie ni `packages/ui` ni `docs/design/aylal-design-system.md`.
- **Composants demandés à `004-design-system`** : `OperationTypeTile`, `WarningBanner`, `DoseField`, `HarvestDateCard`, `PendingBadge`, `ProductRow`.
