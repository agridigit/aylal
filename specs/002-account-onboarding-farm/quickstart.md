# Quickstart F1 (tout dans Docker)

```bash
cp .env.example .env     # renseigner AYLAL_JWT_SECRET et AYLAL_OTP_PEPPER (>= 32 car.) ; aucune valeur par défaut en dur
make up
make test-api            # unit + integration + contrat (OTP, verrou, 404 inter-ferme, rôles)
make test-domain test-mobile
make e2e                 # Maestro : langue -> numéro -> code -> consentement -> surnom -> ferme
```
En dev/test uniquement : `AYLAL_ENABLE_TEST_OTP=1` active l'adaptateur `console` (le code est écrit dans les logs du worker). Parcours manuel :
1. `POST /v1/auth/otp/request {phone, channel}` puis `POST /v1/auth/otp/verify`.
2. `POST /v1/me/consents`, `PATCH /v1/me`, `POST /v1/farms`.
3. Vérifier qu'un second compte reçoit **404** sur `GET /v1/farms/{id}` de la première ferme.
4. Mesurer la durée du parcours E2E (< 2 min).
