# Guide de validation : F0

Prérequis : Docker et make uniquement. Détails : [contracts/make-targets.md](contracts/make-targets.md), [data-model.md](data-model.md).

## 1. Démarrer la plateforme (Récit 1)
```bash
cp .env.example .env && cp .env.example .env.test
make up        # attendu : db, redis, minio, powersync, api, worker, proxy sains
curl -k https://localhost:8443/v1/health   # {"status":"ok",...}
```

## 2. Porte de qualité (Récit 1)
```bash
make check     # attendu : succès global ; sinon le test fautif est nommé
```
Contrôle négatif : ajouter un test qui échoue, `make test` doit retourner un code ≠ 0 et nommer le test.

## 3. Synchronisation hors ligne (Récit 3)
```bash
make test-api  # inclut : 1 000 enregistrements, 30 jours simulés, 0 perte, 0 doublon, conflits, ACL, idempotence
make test-domain   # vecteurs partagés TS (mêmes vecteurs que pytest)
```

## 4. Langues, RTL, 4 états (Récit 2)
```bash
make test-mobile   # RNTL : 3+1 langues, états, zones tactiles >= 48 dp, aucune clé manquante
E2E_SKIP=1 make e2e  # sans KVM (macOS) : e2e mobile ignoré avec avertissement ; en CI Linux/KVM : make e2e
make e2e           # Maestro : ouverture < 3 s, bascule de langue, mode avion -> saisie -> retour réseau
```

## 5. Catalogue et captures (Récit 4)
```bash
docker compose up -d storybook   # http://localhost:6006 (thème et sens dans la barre d'outils)
make test-visual                 # 3 thèmes x 2 sens ; écart = échec
```

## 6. Diagrammes (Récit 5)
```bash
make diagrams   # SVG + PNG ; relancer : « 0 fichier rendu » ; .mmd invalide : échec nommant le fichier
```

## 7. Prototype sur Android 2 Go (Récit 6)
```bash
make apk-size                       # APK < 40 Mo
# installer l'APK release sur l'appareil, lancer le protocole de mesure (écran « Mesures » en build dev), puis
make report                         # docs/modules/001-foundations/mesures.md : valeur, seuil, verdict
```
Un seuil « non tenu » (démarrage 3 s, carte 2 s, 60 i/s, 40 Mo, 5 Mo/jour) ouvre un réexamen du choix technique correspondant.
