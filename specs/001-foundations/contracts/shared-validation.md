# Contrat de validation partagée

```
packages/domain/src/schemas/*.ts (Zod)  ──export──►  packages/domain/schema/*.json (JSON Schema)
                                         ──generate──► services/api/app/generated/*.py (Pydantic v2)
packages/domain/vectors/*.json  ──► joués par Vitest ET pytest
```

- **Format d'un vecteur** : `{ "name": str, "rule": "trial_record.create", "input": {...}, "expect": { "valid": bool, "errors": [{"field": str, "code": str}] } }`.
- **Codes d'erreur stables** : `required`, `too_short`, `too_long`, `out_of_range`, `invalid_geometry`.
- **Commande** : `make test-domain` (TS) et `make test-api` (Python) ; le test de dérive échoue si `generated/` n'est pas à jour avec `schema/`.
- Aucune règle n'est écrite à la main côté Python : `services/api/app/domain` ne contient que l'orchestration (ACL, fusion de conflits) ; la fonction de fusion de référence est dans `packages/domain` (vecteurs `conflict.*.json`) et répliquée côté Python, vérifiée par les mêmes vecteurs.
