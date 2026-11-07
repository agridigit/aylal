# Quickstart F2 (tout dans Docker)

```bash
cp .env.example .env     # AYLAL_JWT_SECRET, AYLAL_OTP_PEPPER (>= 32 car.), identifiants MinIO : aucune valeur par défaut en dur
make up
make tiles               # génère les PMTiles Maroc (fond + satellite) dans MinIO ; AYLAL_TILES_BASE_URL pointe sur l'hébergement marocain
make test-api            # unit + integration + contrat : géométrie, 404 inter-ferme, 403 par rôle, archivage, synchro
make test-domain test-mobile
make e2e                 # Maestro : dessin par touches, dessin GPS simulé, culture + campagne, carte, découpage/fusion, import
```
Parcours manuel (dev/test, `AYLAL_ENABLE_TEST_OTP=1`) :
1. Se connecter (F1), créer une ferme, puis `POST /v1/farms/{id}/fields` avec un Polygon (3 sommets minimum) : réponse avec `area_calc_ha` serveur ; vérifier l'affichage à 2 décimales.
2. Envoyer un polygone en papillon : **422** `geometry_self_intersecting` avec `crossings[]`.
3. `POST .../seasons` avec une culture du référentiel, puis une seconde campagne de la même culture : **409** ; d'une autre culture : 201 (deux actives).
4. Avec un second compte (autre ferme) : `GET /v1/farms/{id}/fields` -> **404** ; avec un ouvrier non attribué : fiche -> **404**, ouvrier attribué + `PATCH` -> **403**.
5. `DELETE` d'une parcelle : fiche -> 404, présente dans `/fields/archived`, `POST .../restore` -> 200 ; supprimer la ferme : toutes les routes -> 404.
6. Hors ligne : couper le réseau, dessiner par GPS simulé, redémarrer l'app, rétablir le réseau : la parcelle est sur le serveur (SC-002).
7. Mesures de recette : première parcelle < 3 min (SC-001), carte de 50 parcelles < 2 s (SC-004, fixture `make seed-fields N=50`), écarts d'aire < 1 % (SC-003).
8. Vérifier qu'aucune requête mobile ne sort vers un domaine autre que `AYLAL_TILES_BASE_URL` et l'API (journal Caddy / test d'allowlist).
