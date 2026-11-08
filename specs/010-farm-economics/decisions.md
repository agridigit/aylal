# Décisions et points ouverts : F8

## À confirmer

Règles sur lesquelles le CPS est muet ; le plan applique la règle ci-dessous jusqu'à confirmation.

1. **Moteur OCR** : passerelle auto-hébergée au Maroc, moteur à choisir (open source) ; URL vide = saisie manuelle.
2. **Source des prix de gros** : non désignée par le CPS ; passerelle configurable, donnée de référence à faire valider avant la v1 ; URL vide = « non disponible ».
3. **Prorata** : parcelles à campagne active à la date, ajustables, répartition figée ; plus fort reste.
4. **Rôles** : ouvrier = aucune dépense, vente, marge, stock, prix ; il enregistre/lit ses récoltes (quantité seule) sur ses parcelles attribuées non archivées (CPS §13 : « jamais les ouvriers » pour les montants ; récolte par l'ouvrier déduite de §6).
5. **Stock** : unité unique par produit, prix moyen pondéré, stock insuffisant = écart signalé (le journal prime), coût inconnu si jamais acheté.
6. **Plafonds de robustesse** (6 Mo, 3 pièces, 100 lectures/jour, 20 000 lignes, 800 jours, 100 000 000 MAD) : valeurs proposées, non métier.
7. **Prix du marché** : tendance = médiane hebdomadaire sur 13 semaines ; ancien au-delà de 14 jours.
8. **Hook F6** : extension minimale de `operations/service.py` (appel unique), tracée ici ; pas d'édition silencieuse.
9. **Numéro de migration** : `0013` provisoire, à recaler à la fusion (F7 / 009 en parallèle).
10. **Composants UI manquants** à demander à la couche design (sans modifier `packages/ui` ni `docs/design/*`) : `AmountInput`, `ReceiptCapture`, `MarginCard`, `StockLevelBar`, `PriceSparkline`.
11. **Porte design** : `docs/design/010-farm-economics/VALIDATION.md` n'est jamais écrit par un agent ; sans lui les tâches d'écran restent bloquées.
12. **Vente hors ligne dépassant la récolte au rejeu** : conservée et signalée (`sync_conflict`), jamais perdue.
13. **Harvests sans montant** : choix de structure pour que l'ouvrier ne reçoive jamais de champ monétaire.

## Poids de l'APK

Aucune dérogation à ce stade. Une section « Dérogation » (titre de niveau 2) n'est à créer que si `make apk-size` dépasse la limite ; alors créer `specs/010-farm-economics/apk-budget.env` (`APK_LIMIT_MB` <= 52, `APK_BUDGET_REASON`, `DECISION_REF=specs/010-farm-economics/decisions.md`).
