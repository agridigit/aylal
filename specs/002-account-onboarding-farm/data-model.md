# Modèle de données F1

Migration Alembic `0002_account_farm` (réversible). Identifiants UUID générés côté client pour les entités créées hors ligne. Toutes les tables d'entités synchronisées portent `farm_id` (sauf `users`).

| Table | Colonnes principales | Règles |
| --- | --- | --- |
| `users` | id, phone_e164 (unique, vérifié), display_name, language (`ary`,`ar`,`fr`), status (`pending`,`active`,`deletion_requested`), onboarding_step, deletion_requested_at, created_at | un numéro = un compte ; `pending` purgé après 24 h sans consentement |
| `consents` | id, user_id, purpose, text_version, granted_at, withdrawn_at | horodaté, versionné, révocable (FR-010, FR-012) |
| `otp_challenges` | id, phone_e164, code_hash, channel (`sms`,`whatsapp`), expires_at, failed_attempts, locked_until, last_sent_at, consumed_at | verrou serveur 5 min après 3 échecs ; code haché |
| `refresh_tokens` | id, user_id, token_hash, device_id, family_id, rotated_at, revoked_at, created_at | rotation, détection de réutilisation |
| `farms` (étend F0) | id, name, owner_id (FK users), location (geometry Point 4326), commune_id (FK), area_ha (nullable), created_at, deleted_at | un propriétaire unique ; nom et emplacement requis |
| `farm_members` (étend F0) | farm_id, user_id, role (`owner`,`manager`,`worker`), added_at, removed_at | PK (farm_id, user_id) ; un seul `owner` par ferme (index unique partiel) ; le propriétaire n'est jamais retirable |
| `worker_parcels` | farm_id, user_id, parcel_id, assigned_at | FK composite vers `farm_members` et `parcels` de la même ferme ; contenu effectif avec F2 |
| `invitations` | id, farm_id, phone_e164, role (`manager`,`worker`), status (`pending`,`accepted`,`cancelled`,`expired`), invited_by, expires_at, created_at | unique (farm_id, phone) en attente ; expire à 30 j |
| `geo_regions`, `geo_provinces`, `geo_communes` | id, name_ar, name_fr, parent_id, geom (communes : MultiPolygon) | référentiel en lecture seule, index GiST |

États : `users.status` pending -> active -> deletion_requested -> (purgé). `invitations.status` pending -> accepted | cancelled | expired.
Migration des rôles F0 : `editor` -> `manager`, `viewer` -> `worker`. Index : `farm_members(user_id)`, `invitations(phone_e164)`.
Aucun champ financier dans F1 ; la sync-rule ouvrier exclut toute table future de F8 par liste blanche.
