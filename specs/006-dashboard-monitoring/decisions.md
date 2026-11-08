# Décisions et points ouverts : F3

1. **Valeurs de seuils agronomiques** : non fixées par le plan ; référentiel validé par l'agronomie (`crop_weather_thresholds`). Fixtures de test seulement. Point ouvert : fournisseur de la liste initiale (équipe AYLAL + agronome).
2. **Hébergeur Maroc des passerelles** (météo, imagerie, push) : non choisi ; configuration par variables d'environnement vides et liste blanche d'hôtes. Point ouvert : désigner l'hôte (constitution XIII).
3. **Garantie « avant 18 h » hors couverture réseau** : tenue par notification locale à partir d'alertes déjà synchronisées ; une prévision de gel apparaissant alors que l'appareil n'a pas synchronisé ne peut être notifiée que par push (passerelle facultative). Mesure SC-003 côté serveur (`notify_at`, `notified_at`) et note de limite en recette.
4. **Voix darija** : synthèse native de l'appareil ; si aucune voix, repli arabe puis texte affiché (spec).
5. **Composants UI manquants** à demander à `004-design-system` (sans modifier `packages/ui` ni `docs/design/*`) : `StatusBadge`, `WeatherDayCard`, `AlertRow`, `VigorChart`, `VigorMapOverlay`, `ZoneGuidanceCard`, `StaleDataBanner`.
6. **Porte design T-DESIGN-GATE** : validation humaine à consigner ici avant tout écran.
7. **Numéro de migration** : `0010` provisoire, à recaler lors de la fusion.
