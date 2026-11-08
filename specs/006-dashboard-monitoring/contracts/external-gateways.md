# Contrat des passerelles externes (F3)

Principe (constitution XIII) : **aucune donnée personnelle ni géométrie exacte de ferme** ne sort du Maroc. Les trois passerelles sont des **URL de configuration, vides par défaut** ; seul le worker les appelle ; toute URL doit avoir un hôte présent dans `AYLAL_EXTERNAL_ALLOWED_HOSTS` (vide = refus total). Hors dev/test, démarrage refusé si une URL est donnée sans hôte autorisé ou en HTTP clair. Aucun secret par défaut (`${VAR:-}` vides dans `docker-compose.yml`).

| Passerelle | Variable | Requête (liste blanche exacte) | Réponse | Si vide / en échec |
| --- | --- | --- | --- | --- |
| Météo | `AYLAL_WEATHER_URL` (+ `AYLAL_WEATHER_KEY` facultative) | `GET ?lat=<0,1°>&lon=<0,1°>&days=8` | `days[8]` : `date,tmin,tmax,rain_mm,wind_kmh,humidity_pct,code` | `availability=unavailable` (`gateway_not_configured` / `gateway_unreachable`) ; dernière prévision datée conservée ; **aucune valeur par défaut** |
| Imagerie | `AYLAL_IMAGERY_URL` (+ `AYLAL_IMAGERY_KEY`) | `GET /tiles/{mgrs}/scenes?from=&to=` puis `GET /scenes/{id}/bands/{B04,B08,B11,SCL}` | scènes publiques + rasters de tuile | pas de scène, pas de point ; écran « traitement en cours / indisponible » ; état fondé sur les autres sources |
| Push (facultatif) | `AYLAL_PUSH_URL` (+ `AYLAL_PUSH_KEY`) | `POST {device_token, alert_id, locale}` | 2xx | repli : notification locale sur l'appareil |

Interdit dans toute requête sortante : identifiant de ferme/utilisateur/parcelle, nom, téléphone, polygone, coordonnées plus fines que 0,1°. Tests : adaptateurs espions vérifiant les clés exactes ; test d'inventaire des imports (aucun SDK étranger) ; test de configuration (aucune valeur secrète par défaut).
