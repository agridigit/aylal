# Contrat OTP et session

- Numéro : normalisé E.164 marocain (`+2126…`/`+2127…`) ; `06…`/`07…` acceptés et convertis. Autre -> 422 `phone_invalid`.
- `POST /v1/auth/otp/request` : toujours 202 (même réponse numéro connu ou non) ; 429 `otp_rate_limited` + `retry_after`.
- `POST /v1/auth/otp/verify` : 200 jetons ; 400 `otp_invalid` (`attempts_left`) ; 423 `otp_locked` + `retry_after` (300 s) ; 410 `otp_expired`.
- Verrou : 3 échecs -> `locked_until = now + 5 min`, vérifié avant toute comparaison, y compris pour le bon code.
- Réponse de session : `access_token` (15 min), `refresh_token` (rotatif), `user`, `farms[]` (id, rôle).
- Secrets : `AYLAL_JWT_SECRET`, `AYLAL_OTP_PEPPER` obligatoires hors dev/test, jamais de défaut statique.
