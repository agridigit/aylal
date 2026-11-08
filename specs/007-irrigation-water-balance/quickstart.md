# Quickstart de validation : F4 — Irrigation et bilan hydrique

Tout tourne dans Docker (`make`, `docker compose`) ; rien n'est installé sur l'hôte. Contrats : [openapi](contracts/openapi.yaml), [synchro](contracts/powersync-sync-rules.yaml), [passerelles](contracts/external-gateways.md). Modèle : [data-model.md](data-model.md).

## Prérequis

```bash
make up          # pile complète (API, worker, PostgreSQL, Redis, MinIO, PowerSync)
make sync-rules  # les règles F4 respectent le service (ni jointure ni sous-requête)
```

Référentiels : **vides par défaut**. Pour les scénarios chiffrés, charger le jeu de **test** (non agronomique, `validated=false`) : `docker compose run --rm worker python -m tasks.import_irrigation_params tests/fixtures/irrigation_params.test.json`. Passerelle météo : URL vide = « non disponible » ; les tests utilisent un faux serveur local (liste blanche de test).

## Scénarios

| # | Scénario | Commande | Résultat attendu |
| --- | --- | --- | --- |
| 1 | Domaine seul (formules, vecteurs partagés TS/Python) | `make test-domain` puis `make test-api` (cible `-k vectors`) | Mêmes résultats TS et Python sur `f4_*.json` ; écart < 5 % sur le jeu de référence (SC-004) |
| 2 | Installation (R1) | `make test-api -k irrigation_system` | Goutte-à-goutte et pompe acceptés ; débit <= 0 ou écartement 0 -> 422 avec champ ; efficience par défaut 90/75/60 (pivot 75) visible |
| 3 | Conseil du jour (R2) | `make test-api -k advice` | Durée = besoin net / (efficience × débit) ; pluie 10,1 mm -> report, 10,0 mm -> pas de report ; sol inconnu -> hypothèse `soil_default` ; météo absente -> dernier conseil daté, confiance `low` ; pluvial -> `rainfed_stress` sans durée |
| 4 | Avant 7 h (SC-001) | `make test-worker -k compute_irrigation_plans` | Horloge figée à 03:00 locale : conseil prêt, `ready_before_7=true` ; météo reçue à 06:59 -> prêt ; référentiel vide -> `unavailable` sans valeur |
| 5 | Enregistrer une irrigation (R3) | `make test-api -k irrigation_event` | Durée -> volume, volume -> durée ; opération F6 créée, **sans double saisie** ; rejeu du même `id` = une seule irrigation ; antidatage -> bilan rejoué dès la date |
| 6 | Hors ligne 30 jours (SC-005) | `make e2e` (scénario `record_irrigation_offline`) | Aucune perte ; badge « à envoyer » ; bilan local mis à jour ; après synchro, une seule irrigation |
| 7 | Consommation (R4) | `make test-api -k consumption` | m³ et m³/ha par parcelle ; ouvrier : totaux = calcul manuel sur ses parcelles visibles |
| 8 | Analyse d'eau (R5) | `make test-api -k leaching` | Salinité > seuil : fraction de lessivage + hypothèse ; <= seuil : aucune ; âge signalé ; ouvrier 403 |
| 9 | Accès (G1) | `make test-api -k irrigation_access` | Matrice de parité rôle × ferme × parcelle × chemin ; 404 identiques ; archivée masquée (REST, synchro, export, bilan, rappel) |
| 10 | Synchro (G3) | `make sync-rules && make test-integration -k irrigation_buckets` | Aucun JOIN ; seau ouvrier à auteur (`farm_worker_irrigation_own`) ; seaux exécutés tels quels |
| 11 | Plafonds et verrous (G4) | `make test-api -k irrigation_limits` | 413/422 avant calcul ; course à 2 requêtes concurrentes sur chaque quota |
| 12 | Passerelles (G5) | `make test-api -k irrigation_gateways` | Aucune clé hors liste blanche ; URL vide -> « non disponible » ; base vierge -> aucun chiffre |
| 13 | Bout en bout API | `make e2e` | Compte de test à numéro unique -> ferme -> parcelle -> installation -> météo de test -> conseil -> irrigation -> conseil du lendemain |
| 14 | Couverture | `make coverage` | >= 80 % du code métier |
| 15 | Poids de l'APK (G9) | `make apk-size` | <= 40 Mo ; sinon `apk-budget.env` + section « Dérogation » dans `decisions.md` de **cette** branche |

## Revue design (avant tout écran)

Maquettes HD ar + fr validées dans `docs/design/007-irrigation-water-balance/` (`T-DESIGN-GATE`), fusion de `004-design-system` faite ; `make test-visual` (3 thèmes × 2 sens) et revue RTL.
