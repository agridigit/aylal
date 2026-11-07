# Décisions : 001-foundations

## Récit 3 (RED) : choix de test
- Refus d'accès à l'envoi : le contrat `/sync/upload` ne définit pas de 403 ; un refus est donc un résultat par opération (`status: rejected`, `error.code: forbidden`), HTTP 200. Le 403/404 HTTP ne s'applique qu'à `/sync/conflicts/{id}/acknowledge`.
- Seuil de stockage faible (`LOW_STORAGE_BYTES`) : valeur choisie au GREEN dans `storageWarning.ts`, les tests la lisent via l'export.
- Les tests d'intégration serveur montent le dépôt en lecture seule sur `/repo` dans `api-test` (contrats, `infra/powersync`) et dépendent du service `proxy` (TLS).
- Maestro (T049) et Jest mobile (T044-T048) ne peuvent pas tourner tant que `apps/mobile` n'existe pas (T057) ; l'échec RED est l'absence du module.
