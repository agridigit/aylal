# Contrat des passerelles externes (F4)

F4 **réutilise** la passerelle météo de F3 (`AYLAL_WEATHER_URL`, `AYLAL_EXTERNAL_ALLOWED_HOSTS`, `app/monitoring/gateways.py`, worker `refresh_weather`) et **n'ajoute aucun appel sortant déclenché par une requête utilisateur**. Constitution XIII : aucune donnée personnelle, aucune géométrie exacte hors du Maroc.

| Donnée | Source | Requête sortante (liste blanche exacte) | Si vide / en échec |
| --- | --- | --- | --- |
| Prévision J0..J+7 (Tmin, Tmax, pluie, vent, humidité, **`et0_mm` facultatif**) | `farm_weather` (F3) | inchangée : `lat`, `lon` arrondis à 0,1°, `days` | `unavailable` (`gateway_not_configured` / `gateway_unreachable` / `stale`) ; **aucun** ET0 ni pluie inventés |
| Pluies **observées** des jours passés (facultatif) | `AYLAL_WEATHER_OBSERVED_URL` (+ clé facultative), **vide par défaut**, hôte dans `AYLAL_EXTERNAL_ALLOWED_HOSTS` | `GET ?lat=<0,1°>&lon=<0,1°>&from=<date>&to=<date>` (clés exactes `lat, lon, from, to`) ; fenêtre <= 7 jours | pluie du jour passé = dernière prévision connue, `rain_source=forecast`, confiance abaissée |

**Extension de la liste blanche** (`OUTBOUND_ALLOWLIST["weather_observed"] = {lat, lon, from, to}`) : un seul nouveau type de requête, appelé uniquement par le worker, par **cellule 0,1° et par 6 h** (verrou Redis, budget journalier global configurable, comme F3).

**Fichiers touchés (extension de F3, à tracer dans `decisions.md`)** : `services/api/app/monitoring/gateways.py` (entrée `weather_observed` de `OUTBOUND_ALLOWLIST`, constructeur de requête, `et0_mm` facultatif accepté sans être exigé dans `_DAY_KEYS`) **et sa copie embarquée dans l'image worker** (`services/workers/Dockerfile` copie le même fichier : une seule source) ; `refresh_weather` conserve `et0_mm` tel que reçu dans `days` ; une table globale `weather_observed(cell_id, day, rain_mm, fetched_at)` reçoit les pluies observées. Les tests F3 existants (`test_f3_outbound_allowlist.py`) assertent des clés précises et restent verts : l'ajout d'une entrée n'en modifie aucun (sinon : noter dans `decisions.md`, jamais d'édition silencieuse).

**ET0** : `et0_mm` de la passerelle s'il est présent (`et0_method=gateway`) ; sinon calcul local Hargreaves-Samani (`hargreaves`) à partir de `tmin`, `tmax` et de la latitude de la ferme (arrondie 0,1°, jamais exacte hors du serveur). Aucune requête sortante supplémentaire.

Interdit dans toute requête sortante : identifiant de ferme/utilisateur/parcelle, nom, téléphone, polygone, coordonnées plus fines que 0,1°. Tests : adaptateurs espions vérifiant les clés exactes (y compris `weather_observed`) ; test d'inventaire des imports (aucun SDK étranger) ; test de configuration (URL vide par défaut, aucun secret par défaut, `${VAR:-}` dans `docker-compose.yml`) ; horloge injectée pour les fenêtres de dates.
