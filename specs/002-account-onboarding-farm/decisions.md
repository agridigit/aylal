# Décisions F1 (tests RED fondations)

- T005 : `AYLAL_OTP_PEPPER` (>= 32 car.) devient obligatoire hors dev/test, comme `AYLAL_JWT_SECRET`. Le test F0 `test_given_prod_env_when_secret_is_strong_then_settings_load` (test_auth_hardening_config.py) n'a plus de pepper : il devra fournir `AYLAL_OTP_PEPPER` au GREEN T016 (écart contraint par contracts/auth-otp.md, non une triche).
- T007 : `tests/conftest.py` (`make_farm`, TABLES) et les anciens tests F0 utilisant `editor`/`viewer` devront être migrés vers `manager`/`worker` au GREEN T014 (la migration 0002 change la contrainte de rôle) ; `farms` gagnera des colonnes NOT NULL (owner_id...), `make_farm` sera adapté alors.
- T008a : une écriture de synchro d'un ouvrier sur une table d'administration renvoie HTTP 403 pour tout le lot (rien d'écrit) ; non-membre : 404. Le test F0 « farm_members -> 422 » sera remplacé quand `Op.table` accepte ces tables (T012b).
- Corps REST supposés : `PUT .../parcels` `{"parcel_ids": [...]}`, `POST .../invitations` `{"phone","role"}`, `PATCH .../members/{id}` `{"role"}`.
- Niveau E2E : reporté au récit 1 (T025) ; aucune pile de bout en bout propre aux fondations.
