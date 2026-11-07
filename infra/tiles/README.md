# Tuiles de carte (PMTiles)

Les tuiles sont construites localement avec tippecanoe (`make tiles`) à partir d'une source marocaine fournie par l'opérateur
(`AYLAL_TILES_SOURCE`), puis hébergées au Maroc et servies sous `AYLAL_TILES_BASE_URL` (https obligatoire).
Aucune URL externe par défaut : sans `AYLAL_TILES_BASE_URL`, rien n'est construit ni référencé.
Format : pmtiles, fichier `morocco.pmtiles`.
