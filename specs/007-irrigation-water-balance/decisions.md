# Décisions et points ouverts : F4

## À confirmer

Valeurs ou règles sur lesquelles le CPS est muet ; le plan applique la règle ci-dessous, tracée dans les hypothèses du conseil, jusqu'à confirmation (agronomie ou produit). Aucune n'est un chiffre agronomique inventé : ce sont des règles de calcul ou de produit.

1. **Pivot = aspersion** : efficience 75 % par défaut, modifiable, hypothèse visible (spec, clarification ; CPS §9 ne donne que 90/75/60 pour les trois autres types).
2. **Pluie ignorée sous serre** : ni dans le bilan ni dans le report (CPS §9 muet ; choix prudent).
3. **« Avant 7 h »** = heure locale de la ferme (`Africa/Casablanca`, horloge injectée), conseil calculé la nuit (03:00) puis à chaque météo reçue.
4. **Fenêtre « 24 h » du report pour pluie** : jour local J entier (> 10 mm strict), voir research note 9 ; la pluie de J+1 n'entre pas dans le conseil de J.
5. **Valeurs agronomiques** (Kc par stade, profondeur racinaire, fraction d'épuisement, réserve utile par texture, seuils de salinité, méthode de pluie efficace, `leaching_max`, `stress_watch_ratio`) : **fournies uniquement par un import validé** (`import_irrigation_params`) ; point ouvert : désigner le fournisseur de la liste initiale (équipe AYLAL + agronome). Tant que le référentiel est vide, le conseil est `unavailable`.
6. **Méthode ET0** : passerelle si `et0_mm` fourni, sinon Hargreaves-Samani (FAO-56 éq. 52) ; à valider contre Penman-Monteith par l'agronomie. Abaisse la confiance d'un cran.
7. **Formule de lessivage** : FAO-29 `LR = ECw / (5·ECe_max − ECw)`, plafonnée par `leaching_max` ; à valider.
8. **Surfaces de secteur égales** (surface parcelle / nombre de secteurs) pour le débit par m² des installations à débit de pompe.
9. **Initialisation du bilan** : sol à la capacité au champ au début de campagne (hypothèse visible, confiance abaissée).
10. **Règle de confiance** (high / medium / low selon le nombre de facteurs dégradants) : règle de produit, à valider avec l'agronomie et la revue design.
11. **Plafonds de robustesse** (secteurs <= 50, 24 irrigations/jour/secteur, antidatage 400 j, 50 analyses/parcelle, 50 versions) : valeurs proposées, non agronomiques.
12. **Doublons** : un rejeu du même `id` est idempotent ; deux saisies distinctes proches sont signalées `possible_duplicate` mais conservées (aucune perte d'apport réel).
13. **Rôles** : ouvrier = lecture installation/conseil et enregistrement sur ses parcelles, aucune analyse d'eau, consommation limitée à sa portée ; CPS §9 muet, déduit de §6 et §16.
14. **Hébergeur Maroc** des passerelles : non choisi (hérité de F3, constitution XIII).
15. **Numéro de migration** : `0012` provisoire, à recaler à la fusion.
16. **Composants UI manquants** à demander à `004-design-system` (sans modifier `packages/ui` ni `docs/design/*`) : `AdviceCard`, `DurationStepper`, `HypothesisSheet`, `WaterStressGauge`, `SectorList`.
17. **Extensions de F3 tracées** (jamais d'édition silencieuse) : `gateways.py` (entrée `weather_observed`, `et0_mm` facultatif, copie unique embarquée dans l'image worker), `refresh_weather` (conserve `et0_mm`, écrit `weather_observed`), `recompute_status` (lecteur `irrigation_need`, plan G1b), fonction de maintenance d'anonymisation F6 (colonnes F4). Mapping `kind -> severity/reason_key` à confirmer avec la revue design du texte.
18. **Porte design `T-DESIGN-GATE`** : validation humaine à consigner ici avant tout écran ; dépend de la fusion de `004-design-system`.
19. **Vue ouvrier « worker-safe »** (sécurité, données dérivées) : `assumptions` et `leaching_fraction` d'`irrigation_plans` peuvent contenir ECw, source d'eau, âge d'analyse, sol. L'ouvrier reçoit UNIQUEMENT `worker_assumptions` (colonne séparée, écrite par le serveur dans la même transaction, liste blanche `et0, kc, effective_rain, efficiency, application_rate, rain_source`, deny-by-default), sans `leaching_fraction`, et `water_balance_days` sans `taw_mm`/`raw_mm`/`moisture_source`. Même vue pour seau PowerSync, `getAdvice`/`listAdvice`, export, rappels/notifications. Conséquence : le bilan local hors ligne de l'ouvrier ne recalcule pas la réserve utile ; il lit le dernier conseil synchronisé (durée incluse, car il doit l'exécuter). Alternative écartée : expurgation par blocklist (fragile aux clés futures).

## Poids de l'APK

Aucune dérogation à ce stade. Une section nommée « Dérogation » (titre de niveau 2) n'est à créer **uniquement** si la mesure `make apk-size` dépasse 40 Mo ; alors créer aussi `specs/007-irrigation-water-balance/apk-budget.env` avec `DECISION_REF=specs/007-irrigation-water-balance/decisions.md`. Le script refuse un `DECISION_REF` sans section « Dérogation » : la dérogation de F2/F3 n'est pas héritée.

## Journal d'exécution

- T004 (porte design humaine) : non faite ; bloque les tâches [écran] T063-T068, T073, T078.
- Écarts de test : aucun.
- Migration : 0012 provisoire, à recaler à la fusion.
- T001 : tzdata épinglé (pip, 2025.2) ; AYLAL_WEATHER_OBSERVED_URL ajoutée à api et worker (vide par défaut).
