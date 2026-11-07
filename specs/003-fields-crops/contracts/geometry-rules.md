# Contrat des règles géométriques (domaine, TS et Python)

Vecteurs partagés dans `packages/domain/vectors/f2_*.json`, consommés par Vitest et pytest ; toute divergence fait échouer les deux suites.

| Règle | Entrée -> sortie | Détails |
| --- | --- | --- |
| `validateRing(points)` | -> `ok` ou `{code, crossings[]}` | ≥ 3 sommets distincts ; ≤ 500 ; fermeture automatique ; croisement de segments non adjacents ; aire non nulle (> 1 m²) ; coordonnées lon/lat finies |
| `areaHa(ring)` | -> hectares | excès sphérique, rayon authalique ; arrondi d'affichage 2 décimales ; serveur : `ST_Area(geography)`, tolérance 0,5 % |
| `isInMorocco(point)` | -> bool | emprise nationale versionnée (`morocco-extent.json`) ; centroïde ; hors emprise -> `outside_morocco` |
| `overlapWarnings(ring, others)` | -> `field_ids[]` | intersection > 1 % de la plus petite aire ; même ferme seulement ; non bloquant |
| `blockInsideField(block, field)` | -> bool | débordement toléré ≤ 1 % de l'aire du bloc |
| `canStartSeason(active, crop)` | -> `ok` ou `season_already_active` | une active par (parcelle, culture) ; autres cultures autorisées (associées) |
| `seasonDate(crop, input)` | -> ok/erreur | pérenne : `planting_year` ; annuelle : `sowing_date` ; jamais les deux |
| `estimateStage(crop, planting, now, gdd?)` | -> stage | jours écoulés si `gdd` absent (étiqueté approximatif) ; `stage_corrected` prioritaire à l'affichage |
| `mergeFields(survivor, others, seasons)` | -> résultat | union contiguë sinon `merge_not_contiguous` ; aire cumulée ; fusion des campagnes de même culture active (la plus ancienne gardée) |
| `simplifyTrack(points, tol=1.5 m)` | -> points | Douglas-Peucker ; garantit ≤ 500 sommets |
| `imagerySuitable(area, greenhouse)` | -> bool | `area >= 0.3 && !greenhouse` (utilisé par F3) |
| `importFeatures(geojson)` | -> `{valid[], rejected[{reason}]}` | polygones seulement, MultiPolygon éclaté, mêmes validations, ≤ 200 entités |
