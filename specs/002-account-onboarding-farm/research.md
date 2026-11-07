# Recherche F1

## Contrôle de la section Clarifications contre le CPS section 6
Contradiction trouvée et corrigée dans `spec.md` : la clarification « SMS par défaut, WhatsApp en alternative » contredisait le CPS (« SMS ou WhatsApp », au choix) et le corps de la spec ; remplacée par « au choix de l'utilisateur, repli sur l'autre canal ». Les trois autres réponses (réseau requis pour la vérification, session persistante + code local optionnel, langue explicite) sont conformes au CPS.

## R1 — OTP
Décision : code à 6 chiffres, valable 5 min, haché (Argon2id + poivre `AYLAL_OTP_PEPPER`) en base, un seul code actif par numéro. 3 échecs -> verrou 5 min stocké en base (`otp_challenges.locked_until`) donc persistant et indépendant de l'appli. Renvoi : 60 s minimum entre deux envois, 5 envois/heure/numéro et par IP (Redis). Alternative rejetée : TOTP/WebAuthn (inadapté au public).
Réponse uniforme pour numéro connu/inconnu (pas d'énumération de comptes).

## R2 — Session
Décision : jeton d'accès 15 min (HS256 existant, `tokens.py` étendu avec `jti`) + jeton de rafraîchissement opaque 256 bits, haché en base, rotatif avec détection de réutilisation, sans expiration absolue (CPS : jusqu'à déconnexion), stocké dans `expo-secure-store` (Keystore). Le jeton PowerSync est émis à partir du jeton d'accès. Alternative rejetée : session unique longue sans rotation (vol de jeton non détectable).

## R3 — Canal d'envoi et Maroc (constitution XIII)
Décision : port `OtpSender` avec deux adaptateurs (SMS, WhatsApp) et un adaptateur `console` dev/test. Fournisseur de production : passerelle d'un opérateur marocain (ou modem/SMPP auto-hébergé) ; WhatsApp Business exige Meta (hors Maroc) : écart signalé, activé seulement après décision explicite du porteur du projet ; sans cela, WhatsApp reste désactivé par drapeau `AYLAL_OTP_WHATSAPP_ENABLED=0` et le SMS fonctionne seul. Clés fournisseur : environnement uniquement.

## R4 — Code local à 4 chiffres
Décision : haché (Argon2id via module natif ou PBKDF2 expo-crypto) avec sel, dans SecureStore, jamais envoyé au serveur ; 5 essais puis délai croissant local ; oubli -> reconnexion OTP et réinitialisation.

## R5 — Géographie
Décision : référentiel officiel (régions, provinces, communes) importé en table PostGIS `geo_communes` (script de seed versionné, source HCP/ANCFCC à valider) ; point -> commune par `ST_Contains` ; liste hiérarchique servie par `/v1/geo/...` et mise en cache locale (SQLite) pour le repli hors ligne ; carte hors ligne : repli liste (spec).

## R6 — Hors ligne et synchronisation
Décision : User profile, consent, Farm, Membership créés localement via la file d'envoi existante (`/v1/sync/upload`), `farm.id` UUID généré sur l'appareil. Le serveur impose `owner_id = sub` (jamais la valeur du client). Invitations et changements de rôle : opérations en file, validées côté serveur (rôle du demandeur). Sync-rules : seuils par appartenance ; ouvrier = parcelles attribuées seulement.

## R7 — Rôles
Décision : `owner | manager | worker`. Migration des rôles F0 : `editor` -> `manager`, `viewer` -> `worker` (sans attribution = aucune parcelle visible, comportement le plus restrictif). Matrice des droits dans `packages/domain/roles` (TS) et `app/domain/roles.py` (Python) avec vecteurs partagés.

## R8 — Suppression et export
Décision : demande -> `deletion_requested_at`, déconnexion, jetons révoqués, données personnelles anonymisées/supprimées par tâche Arq quotidienne à J+30 au plus tard (planifiée à J+7 par défaut, marge de sécurité) ; export JSON asynchrone (tâche) déposé dans MinIO, lien signé court. Propriétaire avec membres : avertissement ; fermes sans autre propriétaire supprimées (pas de transfert en F1).

## R9 — Invitations
Décision : invitation liée au numéro normalisé E.164, expire à 30 j ; honorée à la première vérification réussie du numéro ; doublon membre refusé (409).

## R10 — Consentement
Décision : table `consents` (user, finalité, version du texte, accordé_le, retiré_le) ; politique embarquée dans l'app (versionnée dans `packages/i18n`) ; non-consentement : aucune donnée conservée au-delà du numéro vérifié (compte à l'état `pending`, purgé après 24 h).

## R11 — Reprise d'onboarding
Décision : état d'avancement local (étape courante) dans SQLite/SecureStore ; côté serveur, `users.onboarding_step` pour la reprise sur un nouvel appareil.
