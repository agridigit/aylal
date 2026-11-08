# Passerelles externes F8

Toutes : URL vide = « non disponible » (aucune valeur inventée) ; hôte dans `AYLAL_EXTERNAL_ALLOWED_HOSTS` ; hébergement Maroc ; réponse validée par bornes avant usage.

| Passerelle | Variable | Entrée sortante | Réponse attendue | Échec |
| --- | --- | --- | --- | --- |
| OCR de tickets | `AYLAL_OCR_URL` | image du reçu (déjà plafonnée/typée), langue ; aucun identifiant de ferme, utilisateur ou parcelle | `{amount_cents?, date?, category?, confidence}` | reçu `failed`/`unavailable`, saisie manuelle |
| Prix de gros | `AYLAL_MARKET_PRICES_URL` | liste de cultures du référentiel, fenêtre de dates ; aucune donnée de ferme | lignes `{crop_slug, market, unit, price_cents, observed_on, source}` | dernier relevé daté ou « non disponible » |

Validation avant envoi : reçu de la ferme de l'appelant, statut `uploaded`, appartenance active revérifiée par le worker, plafonds quotidiens respectés.
