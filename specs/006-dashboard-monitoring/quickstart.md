# Quickstart : valider F3 de bout en bout

Prérequis : Docker ; `make bootstrap` déjà exécuté. Aucune installation sur l'hôte. Passerelles externes **non configurées** par défaut : les tests utilisent des passerelles factices locales.

1. **Domaine** : `make test-domain` (Vitest : vecteurs `f3_*.json` : seuils par stade, règle des 80 %, fiabilité < 0,3 ha/serre, anomalie, état, tri, planning de notification, résumé).
2. **API et intégration** : `make test-api` — doit couvrir : matrice de parité G1 (REST, synchro, export, purge, résumé, agrégats), 404 inter-ferme/ferme supprimée identiques, 403 par rôle, parcelle archivée masquée à l'ouvrier partout, invariance des agrégats G2, clés de cache, plafonds et courses de quota G4 (aucun appel passerelle avant refus), minimisation et allowlist G5, objets opaques et URL signées G6, `X-Forwarded-For` falsifié.
3. **Workers** : `make test-worker` — météo (verrou par cellule), alertes (dédoublonnage, gel avant 18 h), imagerie (80 %), backfill < 10 min sur jeu de test, zones, états, résumé.
4. **Règles de synchro** : `make sync-rules` / `scripts/validate-sync-rules.sh` — aucune jointure ni sous-requête, aucune colonne `*_key`.
5. **Mobile** : `make test-mobile` (view models, staleness, notifications locales, guidage, résumé) ; écrans seulement après la porte design et la fusion de 004.
6. **E2E** : `make e2e` — Maestro `dashboard_30s`, `weather_offline`, `frost_alert`, `vigor_cloud`, `zone_guidance`, `status_detail`, `year_compare`, `voice_summary`, `worker_scope`.

Scénarios de recette (docker compose up, passerelles factices) :
- Ferme localisée : météo J0 + 7 ; coupure réseau : dernières données avec date (SC-005).
- Gel −3 °C à 48 h sur amandier en floraison : alerte + notification avant 18 h la veille ; même gel sur culture non sensible : rien (SC-003).
- Scène à 79 % sans nuage : non affichée, dernière valide gardée avec sa date ; 80 % : affichée (SC-004).
- Nouvelle parcelle : historique 12 mois < 10 min (SC-002) ; parcelle 0,2 ha : bandeau « peu fiable ».
- Gestionnaire vs ouvrier à 3 parcelles : compteurs, ordre, résumé et alertes de l'ouvrier ne bougent pas quand une parcelle invisible passe au rouge.
- Passerelles vides : « non disponible » partout, aucune valeur inventée, aucune erreur.

Références : [data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml), [contracts/powersync-sync-rules.yaml](contracts/powersync-sync-rules.yaml), [contracts/external-gateways.md](contracts/external-gateways.md).
