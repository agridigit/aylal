# Démarrage rapide : F8

1. `make up` puis migration `0013_farm_economics` (automatique au démarrage de l'API).
2. Tests ciblés (conteneurs chauds) : `make test-domain ARGS=packages/domain/tests/unit/money.test.ts` ; `make test-api ARGS=services/api/tests/unit/economics`.
3. Parcours serveur : créer une ferme, une parcelle, une campagne ; `POST /v1/farms/{id}/expenses` (prorata), `POST /harvests`, `POST /sales`, `GET /economics/parcels/{pid}` ; vérifier marge = somme des lignes.
4. Stock : `POST /stock/purchases` (produit du catalogue), valider une opération F6 de 2 L, vérifier `GET /stock/items` (-2 L) ; seuil franchi -> `GET /stock/alerts`.
5. Ticket : `POST /receipts` avec `AYLAL_OCR_URL` vide -> statut `unavailable`, saisie manuelle OK.
6. Prix : `AYLAL_MARKET_PRICES_URL` vide -> `available=false`.
7. Rôle ouvrier : toute route financière -> 403 ; `GET /harvests` sans champ monétaire.
8. Avant fusion : `make check-fast-cached`, puis `make check-cached` ; `make sync-rules`.
Les écrans ne sont codés qu'après `docs/design/010-farm-economics/VALIDATION.md` (écrit par l'humain).
