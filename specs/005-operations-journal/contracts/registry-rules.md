# Règles du registre et des contrôles phyto (F6)

## Contrôles (fonction pure `phytoControls(line, product, uses, history)`)
Entrées : parcelle (culture, campagne), produit, dose + unité, date, historique des écritures actives du produit sur la campagne. Sortie : liste d'avertissements `{code, severity: "warning", data}`. Jamais d'erreur bloquante.
| Code | Condition |
| --- | --- |
| `not_authorized_for_crop` | aucune ligne `phyto_product_uses` pour (produit, culture) ou homologation expirée |
| `dose_above_max` | dose normalisée > `max_dose` de l'usage (unité convertie) |
| `max_applications_reached` | applications actives du produit sur la campagne + 1 > `max_applications` |
| `dar_unknown` | `dar_days` NULL |
| `free_product_unchecked` | produit libre (aucun contrôle d'homologation) |
Produit et dose absents : demandés (`missing_product`, `missing_dose` côté UI), aucun avertissement stocké.

## DAR
`earliest_harvest(parcel) = max(performed_on + dar_days)` sur `registry_current` (traitements faits, non annulés) ; `null` => « récoltable dès maintenant » ; un produit à `dar_days` NULL rend la date « inconnue » pour la parcelle.

## Immuabilité
`registry_entries` et `operation_corrections` : INSERT seulement. Correction = `reversal` (supersedes) + nouvelle `application`. Exceptions uniques et testées : anonymisation à la suppression de compte, purge après `retain_until`.

## Colonnes d'export (PDF = XLSX)
date, parcelle, culture, produit, matière active, dose (+unité), surface (ha), opérateur, avertissements, produit libre (oui/non), écriture corrigée (oui/non). Pied de page : ferme, période, date de génération, version du catalogue, SHA-256.

## Conservation
`retain_until = performed_on + AYLAL_REGISTRY_RETENTION_YEARS` (défaut 5, à confirmer). Purge par `purge_expired_registry` (worker) uniquement.
