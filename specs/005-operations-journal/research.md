# Recherche : F6 — Journal des opérations et registre phyto

Aucune clarification ouverte dans la spec ; ce document tranche les choix techniques et les points laissés au plan.

| # | Sujet | Décision | Justification | Alternatives écartées |
| --- | --- | --- | --- | --- |
| 1 | Modèle opération × parcelles | `operations` (en-tête) + `operation_parcels` (une ligne par parcelle, dose répartie, colonnes dénormalisées) | n-n exigé (FR-004) ; PowerSync refuse jointures : la ligne porte `farm_id`, `author_id`, `parcel_archived_at`, type, date, statut | Table de liaison nue (jointure impossible en sync) |
| 2 | Répartition au prorata | `allocation.ts`/`allocation.py`, surfaces en ha (déclarée si présente sinon calculée, règle F2), arrondi 3 décimales, le reste attribué à la plus grande parcelle pour que la somme soit exacte | Somme exacte = test de vecteur partagé | Arrondi libre (écart de somme) |
| 3 | Registre | Grand livre `registry_entries` append-only + triggers + GRANT restreint ; vue courante = écritures non annulées | Valeur réglementaire : preuve non réécrivable ; correction = compensation | Colonne `deleted_at`/UPDATE (réécriture possible) ; table d'audit seule (la donnée réelle reste modifiable) |
| 4 | Conservation | 5 ans après la date d'opération, paramétrable ; **à confirmer** | CPS muet ; défaut prudent supérieur aux 2-3 ans des référentiels d'export | Illimitée (conflit loi 09-08) ; 1 an (insuffisant audit) |
| 5 | Suppression de compte vs registre | Anonymisation des données personnelles, conservation des lignes jusqu'à l'échéance, export préalable | Concilie loi 09-08 et obligation de preuve | Suppression totale (perte de preuve) |
| 6 | Contrôles phyto | Fonction pure dans le domaine, 4 avertissements : `not_authorized_for_crop`, `dose_above_max`, `max_applications_reached`, `dar_unknown` (+ `free_product_unchecked`) ; jamais d'erreur bloquante ; serveur recalcule et stocke ; client conserve les siens pour l'affichage hors ligne | FR-006/007 ; SC-002 | Contrôle serveur seul (inutilisable hors ligne) |
| 7 | Décompte des applications | Par campagne (`season`) et par produit, sur écritures non annulées et statut `done`/`validated`/`pending_validation` | Hypothèse spec | Par année civile |
| 8 | Conversion d'unités | Table d'unités (`L/ha`, `mL/ha`, `kg/ha`, `g/ha`, `mL/hL`, `g/hL`, `L`, `kg`) ; conversion affichée avant validation ; dose normalisée dans l'unité du catalogue pour le contrôle | Cas limite de la spec | Saisie imposée dans l'unité du catalogue |
| 9 | DAR | `harvest_date.ts` : max(`performed_on` + `dar_days`) sur écritures actives des traitements faits ; sans traitement : « récoltable dès maintenant » ; recalcul réactif aux corrections | R3 | Colonne stockée sur la parcelle (obsolète vite, écrite hors F6) |
| 10 | Statuts | Machine à états dans le domaine : `planned -> done|cancelled` ; `done -> pending_validation` (ouvrier) ou `validated` (owner/manager) ; `pending_validation -> validated` ; « en retard » **dérivé** (date < aujourd'hui et `planned`), non stocké ; date future à la création = `planned` | Hypothèses de la spec ; évite un statut périmé hors ligne | Statut « overdue » stocké (désynchronisable) |
| 11 | Conflits hors ligne | Réutilise `conflict.py`/`sync_conflicts` + `field_versions` : champ par champ, les deux versions sont conservées dans `operation_corrections` | Cas limite spec ; acquis F0 | Dernier écrit gagne (perte) |
| 12 | Rappels | Notifications **locales** programmées à la création/modification (`expo-notifications`) à une heure fixée (07:00 locale, configurable) ; table `operation_reminders` pour l'état ; aucun push FCM | Hors ligne (R4-A2) ; FCM = Google = hors Maroc | Push serveur (dépend d'un tiers étranger) |
| 13 | Catalogue | Tables `phyto_products`, `phyto_product_uses`, `catalog_versions` ; seau PowerSync global ; import mensuel `import_phyto_catalog` depuis l'export PhytoIndex fourni par l'équipe AYLAL ; produits à homologation expirée marqués `expired_at` (cachés des propositions, conservés pour les anciens registres) ; budget ≤ 3 Mo compressé | CPS §17/§19 ; offline | Appel API à chaque recherche (hors ligne impossible) |
| 14 | Source du catalogue | Procédure d'import documentée (CPS risque §19) ; fixtures de test seulement dans la migration ; **aucune donnée de production codée en dur** | Maîtrise de la donnée réglementaire | Seed de la migration avec le vrai catalogue |
| 15 | Étiquette | Port `LabelRecognizer` (vision de F5 si présente, `AYLAL_VISION_URL` au Maroc) ; indisponible -> repli recherche par nom ; photo conservée localement et envoyée au retour du réseau (plafond 3 Mo) | FR-005 ; Maroc ; F5 absent | Service OCR cloud étranger |
| 16 | Dictée | Port `VoiceParser` : la transcription vient de l'assistant F7 ou du clavier vocal système ; l'analyse de texte (≤ 500 car.) est un parseur à lexique (darija/arabe/français : types, « cuivre », « oliviers du bas » -> parcelles par nom) dans le domaine ; champs incertains marqués `ambiguous` avec candidats ; **jamais d'enregistrement sans confirmation** | R5 ; transparence | LLM obligatoire (indisponible hors ligne) |
| 17 | Export | Worker Arq : PDF `reportlab` (polices embarquées, texte arabe remodelé) + XLSX `openpyxl`, mêmes lignes/colonnes ; fichier dans MinIO (Maroc), URL signée 15 min ; partage via `expo-sharing` (feuille de partage, WhatsApp inclus) ; hors ligne : génération locale si possible sinon mise en attente | R6 | Génération uniquement serveur (inutilisable hors ligne) -> repli local simplifié accepté |
| 18 | Limites de débit | Limiteur Redis par IP/utilisateur/ferme ; IP via `client_ip()` extraite sans changer son comportement | Leçon F1 | Limiteur en mémoire de processus (non partagé) |
| 19 | Parcelle archivée | Ouvrier : masquée partout ; propriétaire/gestionnaire : lisible ; snapshot dans le registre | Spec + leçon F2 | Cascade de suppression du registre |
| 20 | Fournisseur d'unités de catalogue/DAR inconnus | `dar_days` NULL -> avertissement `dar_unknown`, pas de date de récolte calculée pour ce produit (parcelle marquée « DAR inconnu ») | Prudence (principe V) | Supposer 0 jour (risque de résidus) |

## Points ouverts (non bloquants, isolés derrière un paramètre ou un port)

- Durée légale de conservation du registre (défaut 5 ans) : à confirmer ; `decisions.md`.
- Emplacement exact de l'export PhytoIndex et licence d'usage.
- Disponibilité de la vision (F5) et de l'assistant vocal (F7) : repli par icônes et par nom garanti.
- Heure par défaut des rappels (07:00) à valider avec les agriculteurs au prototype.
