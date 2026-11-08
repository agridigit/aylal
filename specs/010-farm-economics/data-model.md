# Modèle de données : F8

Conventions : `id uuid` (généré par le client, validé par le serveur), `farm_id` partout avec FK composites `UNIQUE (farm_id, id)`, montants `*_cents bigint`, quantités `*_milli bigint`, dates `date` en jour local de la ferme, horodatages `timestamptz`. **Registres append-only** : triggers refusant UPDATE/DELETE (hors recopie `parcel_archived_at`).

| Table | Colonnes principales | Règles |
| --- | --- | --- |
| `expenses` | id, farm_id, kind (`entry`/`reversal`), category (`inputs`,`labor`,`fuel`,`electricity`,`water`,`equipment_rental`,`other`), amount_cents (signé), spent_on, note, parcel_id?, season_id?, allocation_mode (`parcel`,`prorata`,`general`), receipt_id?, reverses_id? (UNIQUE), replaces_id?, author_id, created_at, server_version | `entry` > 0, `reversal` < 0 = - original ; `general` => pas de parcelle ; plafonds G4 |
| `expense_allocations` | id, farm_id, expense_id, parcel_id, share_cents (signé), parcel_archived_at, season_id? | somme des parts = montant (contrainte vérifiée par trigger différé) ; figée à la saisie ; la reversal porte les parts opposées |
| `receipts` | id, farm_id, expense_id?, object_key (serveur), content_type, size_bytes, status (`uploaded`,`reading`,`ready`,`failed`,`unavailable`), proposal jsonb?, uploaded_by, created_at | clé nommée serveur ; proposal borné et validé ; jamais écrit au registre |
| `harvests` | id, farm_id, kind, parcel_id, season_id, quantity_milli (signé), unit (`kg`), harvested_on, author_id, reverses_id?, parcel_archived_at | **aucune colonne monétaire** ; l'ouvrier écrit/lit les siennes (parcelles attribuées non archivées) |
| `sales` | id, farm_id, kind, harvest_scope (parcel_id, season_id), quantity_milli (signé), unit_price_cents, total_cents (signé, = qté × prix arrondi), buyer, sold_on, author_id, reverses_id?, replaces_id? | owner/manager seulement ; quantité vendue courante <= récoltée courante (sous verrou) |
| `stock_items` | id, farm_id, product_id? (catalogue), name, unit (`L`,`kg`,`unit`), threshold_milli?, qty_milli (cache), avg_unit_cost_cents (cache), shortfall_milli (cache), retired boolean | UNIQUE (farm_id, product_id) ; produit au catalogue expiré : non proposé pour de nouveaux achats, historique conservé |
| `stock_movements` | id, farm_id, stock_item_id, kind (`purchase`,`consumption`,`reversal`,`adjustment`), qty_milli (signé), unit_cost_cents?, total_cost_cents?, parcel_id?, season_id?, operation_id?, line_no?, correction_no?, reverses_id?, reason?, moved_on, author_id, parcel_archived_at | UNIQUE (operation_id, line_no, kind, correction_no) ; `consumption`/`reversal` issus du hook F6 ; `adjustment` avec motif |
| `stock_alerts` | id, farm_id, stock_item_id, status (`active`,`resolved`), episode, qty_milli, threshold_milli, product_name, created_at, notified_at? | dédoublonnage (item, épisode) |
| `market_sources` | id, label, public_url, active | référentiel global |
| `market_prices` | id, crop_slug, market, unit, price_cents, observed_on, source_id | global ; source et date obligatoires ; <= 500 lignes retenues |
| `economics_notification_log` | farm_id, user_id, kind, ref_id, sent_at | appartenance active exigée ; purgé à la sortie d'un membre |

Vues : `expenses_current`, `sales_current`, `harvests_current`, `stock_movements_current` (lignes non inversées, hors `reversal`). Agrégation du bilan : `economics_season_totals` calculée par le domaine (pas stockée), cache applicatif scopé (G2).

Relations : `expenses` 1-n `expense_allocations` ; `expenses` n-1 `receipts` ; `harvests`/`sales` n-1 parcelle/campagne (F2) ; `stock_items` 1-n `stock_movements` ; `stock_movements.operation_id` n-1 `operations` (F6) ; `stock_items.product_id` n-1 `phyto_products` (F6, exclusion si `expired_at IS NOT NULL`).

Cycle de vie d'une dépense : `entry` -> (`reversal` [+ nouvelle `entry` liée]) ; d'un reçu : `uploaded` -> `reading` -> `ready` | `failed` | `unavailable` (-> saisie manuelle).
