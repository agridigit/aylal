# Contrat i18n

- **Locales** : `ary` (darija, graphie arabe, RTL), `ary-Latn` (darija latine, LTR), `ar` (arabe standard, RTL), `fr` (LTR, repli par défaut).
- **Fichiers** : `packages/i18n/locales/<locale>.json`, structure imbriquée, clés en anglais (`home.title`, `states.error.retry`).
- **Règles testées (Vitest)** : mêmes clés dans les 4 fichiers ; aucune valeur vide ; mêmes variables d'interpolation (`{{count}}`) ; pluriels déclarés pour `ary`, `ar` (6 formes) et `fr`.
- **Repli** : langue d'appareil non prise en charge → `fr`. Choix utilisateur persisté (`app_settings.locale`).
- **RTL** : `ary` et `ar` ⇒ `isRTL = true` ; changement de sens ⇒ rechargement de l'activité.
- **Interdit** : chaîne littérale visible dans le JSX (règle ESLint `no-literal-jsx-text` dans `apps/mobile` et `packages/ui`).
- **Statut des textes** : provisoires, relecture darija planifiée.
