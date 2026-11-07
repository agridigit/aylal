
## T003 : refus de démarrer sans AYLAL_TILES_BASE_URL

Les tests F1 existants (`test_auth_hardening_config.py`, `test_f1_secrets_config.py`) exigent que `get_settings()` réussisse en prod avec seulement les secrets forts ; un refus dans `get_settings()` les casserait (et ils ne sont pas modifiables). Décision : `get_settings()` lit la variable (vide par défaut), et `require_tiles_base_url(settings)` refuse hors dev/test si elle est absente ; elle est appelée par le démarrage des routes carte (récit 4). À confirmer à la revue.
