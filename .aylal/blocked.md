## F0 001-foundations — bloquée à l'étape E (2026-11-07)
- `E2E_SKIP=1 make check` rouge uniquement à cause de `apk-size` : APK release non constructible (apps/mobile sans expo/react-native ni projet natif ; image android-build sans SDK ; hôte aarch64). Détail : specs/001-foundations/decisions.md.
- Non réalisé : T110 (Android 2 Go), T111, T115, T116 (docs). Branche laissée telle quelle, non fusionnée.
- Aussi : e2e Maestro non exécutés (pas de KVM sur macOS) ; reviewer refusé par le classificateur auto (revue de groupe faite à la main).

## F1 002-account-onboarding-farm — bloquée (2026-11-07)
- Backend, domaine, worker, sync et mobile non-écran : faits et verts (API 420, JS 135+131+31+23, e2e-api 8, couverture pytest 94 %).
- Porte design T004 (principe 10) : maquettes HD arabe/français des écrans P1/P2 à valider par un humain avant tout code d'écran. Écrans bloqués : T027, T028, T032, T034, T036, T037(écran), T041, T044, T049, T052, T055, T058, T060, T061, T062, T067, T070. Référence design : docs/design/aylal-design-system.md (Olivier, Unistyles) ; les maquettes se font dans Storybook (docs/design/002-account-onboarding-farm/).
- apk-size NON MESURE (build APK arm64 bloqué dans android-build) ; test-visual et e2e Maestro non exécutés.
- Ouverts hors écran : T017/T018 (tests de règles PowerSync par rôle), T071 (refactor), T074 (docs).
- Non fusionnée : F2 à F9 dépendent de F1 (comptes/fermes) et ne sont pas démarrées (F2 : specify+clarify faits dans .worktrees/003-fields-crops).

## F2 003-fields-crops — bloquée à l'étape E (2026-11-07)
- Non-écran fait et vert (domaine 277, unit 274, intégration 471+, API 741, e2e-api 16, mobile 168). Sécurité traitée en test first : parcelle archivée côté ouvrier (sync, REST, export), plafond de sommets, plafond de 500 parcelles avec verrou par ferme.
- `E2E_SKIP=1 make check` rouge uniquement sur `apk-size` : APK 49,9 Mo pour un seuil de 40 Mo (38,3 Mo en F1). Cause : libmaplibre.so (10,8 Mo, indissociable de la carte) ; libcrypto (5 Mo) requis par le chiffrement. R8 appliqué (-0,9 Mo) ; la compression des .so contournerait la porte en aggravant la taille installée.
- DÉCISION HUMAINE requise (mesures dans specs/003-fields-crops/decisions.md) : relever le budget à ~52 Mo avec amendement du CPS (recommandé), ou retirer/alléger la carte.
- Aussi ouverts : porte design T004 et tâches d'écran ; photos de cultures (assets/crops/*.webp) ; morocco.pmtiles (source et hébergement marocains) ; T071 (retrait de parcels.vigor) ; T072 (mesures de recette) ; passage Maestro sur le build R8 ; docs (T074) non faites.
- Non fusionnée : la branche 003-fields-crops reste telle quelle (aucune balise).
