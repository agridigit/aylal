## F0 001-foundations — bloquée à l'étape E (2026-11-07)
- `E2E_SKIP=1 make check` rouge uniquement à cause de `apk-size` : APK release non constructible (apps/mobile sans expo/react-native ni projet natif ; image android-build sans SDK ; hôte aarch64). Détail : specs/001-foundations/decisions.md.
- Non réalisé : T110 (Android 2 Go), T111, T115, T116 (docs). Branche laissée telle quelle, non fusionnée.
- Aussi : e2e Maestro non exécutés (pas de KVM sur macOS) ; reviewer refusé par le classificateur auto (revue de groupe faite à la main).
