# Design system AYLAL — application mobile

**Statut** : validé par le porteur du projet le 2026-11-07 (sections 1 à 4) ; section 5 proposée.
**Portée** : fondations, icônes et composants de `packages/ui`. Les maquettes des écrans (T004 de `002-account-onboarding-farm`) sont un chantier séparé, construit avec ces composants.
**Autorité** : ce document est le design de référence de l'application mobile. Il complète le CPS §15 et la constitution (article X) ; en cas de conflit, constitution > CPS > ce document.
**Maquettes de travail** : `.superpowers/brainstorm/53465-1794064175/content/` (non versionnées : palette, formes, icônes, couleurs, typographie).

## 0. Choix validés

| Sujet | Choix |
|---|---|
| Direction de couleur | **Olivier** : vert olive profond, fond lin chaud, accents terre cuite et eau |
| Surfaces | **Cartes blanches élevées** : rayon 16, ombres douces teintées olive, état porté par une pastille |
| Icônes | **Trait arrondi** : trait unique 1,8 px, une couleur, dessin sur mesure |
| Source des maquettes | **Storybook** (code) : vrais écrans en composants `packages/ui`, captures PNG générées dans Docker vers `docs/design/<feature>/` |
| Architecture des jetons | **Évolution en place, deux niveaux** : primitives → rôles sémantiques, source TypeScript, Unistyles (décision R10 de F0) |

## 1. Couleurs

Règle d'or : un état n'est **jamais** porté par la couleur seule (icône + mot toujours présents).

### Primitives (niveau 1 — jamais utilisées directement par un composant)

| Gamme | 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 |
|---|---|---|---|---|---|---|---|---|---|---|
| olive (marque) | #F2F4EA | #E3E8D2 | #C8D3AA | #A6B87C | #829A55 | #5F7B3C | #4A6530 | **#3F5A2E** | #2E4322 | #1E2D17 |
| lin (neutres) | #FBF9F3 | **#F6F2E8** | #ECE6D6 | #DCD4C0 | #B9B19C | #8E8775 | #6A6455 | #4D493E | #302E27 | #1C1B17 |

| Gamme | 50 | 200 | 500 | 700 | 900 |
|---|---|---|---|---|---|
| feuille (« rien à faire ») | #E6F2DF | #C6E2B6 | #5E9E45 | #2F6B22 | #1D4515 |
| safran (« à surveiller ») | #FDF5E3 | #F8E6C0 | #C98B14 | #8E6000 | #5A3D00 |
| terre (« action conseillée », danger) | #FBEFE9 | #F5DCD3 | #C4583A | #A63A22 | #6B2213 |
| eau (info, focus, irrigation) | #E8F3F4 | #CFE6E8 | #2F8A96 | #1F5F69 | #123A40 |

### Rôles sémantiques (niveau 2)

| Rôle | Clair | Sombre | Plein soleil |
|---|---|---|---|
| bg.canvas | lin.100 | #151A12 | #FFFFFF |
| bg.raised (cartes) | #FFFFFF + élévation 1 | #20281C | #FFFFFF + bordure 2 px lin.900 |
| text.primary | #1F2A1D | #EEEADF | #000000 |
| text.secondary | lin.700 | lin.400 | lin.900 (graisse 500) |
| border.default | lin.300 | #343D2E | lin.900 |
| action.primary / on | olive.700 / lin.50 | olive.300 / olive.900 | olive.900 / #FFFFFF |
| status.ok (fg / bg) | feuille.700 / feuille.50 | #9FD38A / #26401D | #FFFFFF / feuille.900 |
| status.watch (fg / bg) | safran.700 / safran.50 | #F0C25A / #40310F | #FFFFFF / safran.900 |
| status.act (fg / bg) | terre.700 / terre.50 | #F29A80 / #4A2218 | #FFFFFF / terre.900 |
| info | eau.700 | eau.200 | eau.900 |
| focus (anneau 3 px) | eau.500 | eau.200 | #000000 |

Contrastes vérifiés par test (`contrast.test.ts`) : texte courant ≥ 4,5:1 (clair, sombre), ≥ 7:1 (plein soleil).

## 2. Typographie, espacement, rayons, élévations

Polices : IBM Plex Sans et IBM Plex Sans Arabic, graisses **400 / 500 / 600** (remplace 400/500/700 de R11). Chiffres tabulaires pour les quantités. Taille minimale 14. Échelle de police système respectée jusqu'à 200 % (retour à la ligne, jamais de troncature d'une information clé).

| Niveau | Taille | Interligne latin | Interligne arabe | Graisse |
|---|---|---|---|---|
| display | 32 | 40 | 48 | 600 |
| title | 26 | 34 | 40 | 600 |
| heading | 22 | 30 | 36 | 600 |
| subheading | 18 | 26 | 32 | 600 |
| body | 18 | 28 | 32 | 400 |
| label | 16 | 22 | 28 | 500 |
| caption | 14 | 20 | 24 | 400 |

- **Espacement** (grille 4 px) : 0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64. Marges d'écran 20 ; entre cartes 12 ; intérieur de carte 16 ; entre sections 32.
- **Zone tactile** : 48 minimum, 56 pour l'action principale.
- **Rayons** : sm 8 (pastilles, champs), md 12 (icônes d'état), lg 16 (cartes, boutons), xl 24 (feuilles du bas), pill 999 (puces, filtres).
- **Élévations** (ombres teintées olive, jamais noir pur) : 0 à plat (bordure lin.300) ; 1 cartes `0 1px 2px rgba(40,50,30,.08), 0 2px 8px rgba(40,50,30,.08)` ; 2 bouton flottant `0 4px 14px rgba(40,50,30,.14)` ; 3 feuilles et dialogues `0 12px 32px rgba(40,50,30,.20)`. Sombre : élévation = surface plus claire. Plein soleil : élévation = bordure 2 px.

## 3. Mouvement, haptique, iconographie, RTL

- **Durées** : fast 150 ms (retour de pression), base 240 ms (transitions, apparitions), slow 300 ms (feuilles, changement d'écran). Courbes `standard`, `enter` (décélération), `exit` (accélération), ressort doux pour les feuilles.
- Seules l'opacité et les transformations sont animées (Reanimated), 60 i/s sur Android 2 Go.
- « Réduire les animations » : fondus de 100 ms, aucun déplacement.
- Moments signature : coche animée « opération enregistrée » (`SuccessCheck`), changement d'état d'une pastille de parcelle.
- **Haptique** (Expo Haptics) : `selection`, `success`, `warning`, `error` ; jamais sans action de l'utilisateur, sauf alerte critique.
- **Icônes** : grille 24, trait 1,8 px, bouts et angles ronds, marge 2 px, une couleur (rôle sémantique). SVG sources dans `packages/ui/icons/` → composants RN ; drapeau `mirror` pour les icônes directionnelles ; libellé d'accessibilité par clé i18n. Lot de départ ≈ 40 : navigation et système (≈ 15), états et alertes (5), cultures (olivier, blé, orge, tomate, agrumes, maraîchage, vigne, palmier), opérations (irrigation, traitement, fertilisation, taille, récolte, semis, travail du sol, vente), météo (6).
- **RTL** : propriétés logiques uniquement (`start` / `end`), vérifiées par lint dans `packages/ui`. Icônes directionnelles et barres de progression miroitées ; chiffres, heures, téléphone et cases OTP restent LTR.

## 4. Architecture et composants

```
packages/ui/src/tokens/primitives.ts           niveau 1
packages/ui/src/tokens/themes/{light,dark,sun}.ts   niveau 2 (rôles)
packages/ui/src/tokens/index.ts                export typé + JSON Schema étendu (specs/001-foundations/contracts/design-tokens.schema.json)
packages/ui/src/unistyles.ts                   thèmes, points d'arrêt, RTL
packages/ui/src/icons/                         SVG + composants générés
packages/ui/src/components/<Name>/             <Name>.tsx, <Name>.stories.tsx, styles, tests
```

**Conventions d'API** : textes reçus déjà traduits (clés i18n), jamais en dur ; uniquement des rôles via Unistyles ; props `variant`, `size`, `disabled`, `loading` ; états pressé et focus réels (le faux prop `state` de F0 disparaît) ; rôle, libellé et état d'accessibilité ; zone tactile ≥ 48. Aucun composant ne contient de règle métier : `ParcelCard` reçoit un état déjà calculé par `packages/domain`.

| Famille | Composants |
|---|---|
| Base | Text, Icon, Divider, Spacer, Surface |
| Actions | Button (primary, secondary, tertiary, danger ; md, lg), IconButton, FAB, **VoiceButton** (lecture vocale, présent sur chaque écran) |
| Saisie | TextField, PhoneField (+212, LTR), OtpField (6 cases, LTR), Select, SegmentedControl, Switch, Checkbox, Radio, Stepper |
| Affichage | Card, ListItem, Chip, Badge, **StatusPill** (ok / watch / act, icône + mot), **ParcelCard**, WeatherCard, Avatar |
| Navigation et structure | **ScreenScaffold** (`status: loading \| empty \| error \| offline \| ready`), AppBar, TabBar, BottomSheet, Dialog, ProgressSteps |
| Retours | Skeleton, EmptyState, ErrorState, OfflineBanner, SyncBadge, Toast, SuccessCheck |

## 5. Tests, documentation, découpage (proposé, à confirmer)

- **Test first** (CLAUDE.md) : unitaires Vitest/RNTL par composant (rôles, accessibilité, zone tactile, RTL) ; tests de jetons (schéma, contrastes par thème) ; régression visuelle Playwright sur Storybook : 3 thèmes × 2 sens × 2 langues, dans Docker.
- **Documentation** : une story par variante et par état, page « Fondations » dans Storybook (couleurs, typo, espacement, icônes) ; doc de module `docs/modules/<NNN>-design-system/` en fin de chantier.
- **Découpage suggéré** : (1) jetons et Unistyles, migration des 12 composants F0 ; (2) icônes ; (3) composants de saisie et de structure nécessaires à la 002 (PhoneField, OtpField, ScreenScaffold, ProgressSteps, VoiceButton) ; (4) reste de l'inventaire.
