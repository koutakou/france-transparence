# DÉCISION D'HÉBERGEMENT — France Transparence (19/08/2026)

## Décision

**Le site est déployé en statique pré-rendu sur GitHub Pages, reconstruit chaque matin par GitHub Actions.**

- **URL publique** : https://koutakou.github.io/france-transparence/ (project page, `basePath` Next `/france-transparence`).
- **Repo** : `koutakou/france-transparence`, public (aucun secret dans le code — audité ; cohérent avec un projet civique de transparence ; Pages et minutes Actions gratuits exigent un repo public).
- **Ingestion quotidienne** : workflow `ingest.yml`, cron 04:45 UTC (06:45 Paris — après le lot JO ~00h30 et les builds DECP nocturnes) : `make ingest` (db neuve dans le runner éphémère) → `make test` → `next build` (export statique) → déploiement Pages **atomique**. En cas d'échec de n'importe quelle étape : **pas de déploiement** — le site de la veille reste servi tel quel, une issue GitHub s'ouvre automatiquement. La fraîcheur affichée (meta_sources) reste la vraie par construction.
- **Coût : 0 €/mois.** Aucune action humaine requise.

## Pourquoi ce choix

1. **C'est la seule option exécutable sans humain** (constat machine-locale.md) : seul GitHub est authentifié (`koutakou`, scopes repo/admin:public_key). Toutes les plateformes à disque persistant exigent compte + CB en 2026 (plateformes.md : tier gratuit Fly mort, Railway CB « post-paid », Render crons sans disque, Koyeb volumes « testing only », Clever FS incompatible better-sqlite3). Le VPS OVH de ~/.ssh/config est injoignable (ping OK, ports 24533/22/80/443 fermés) et koutakou.fr a expiré (AFNIC : NOT FOUND).
2. **Le produit est nativement statique-quotidien** : les données ne changent qu'à l'ingestion (audit-app.md : force-dynamic partout était déjà un contresens à corriger). Le HTML pré-rendu est le cache parfait, servi par le CDN Fastly de Pages, HTTPS inclus, HSTS préchargé sur *.github.io.
3. **L'atomicité demandée par la mission est structurelle** : un déploiement Pages remplace tout le site d'un coup ; pas de bascule de db à orchestrer, pas de restart, pas d'état intermédiaire possible.
4. **Journalisation et healthcheck** : logs Actions publics, badge de statut, issue automatique en échec, `meta.json` daté comme témoin de fraîcheur.

## Conséquences techniques assumées (chantiers R2)

- `output: 'export'`, `basePath` et `images.unoptimized` ; suppression de tous les `force-dynamic`.
- **Fiches élus statiques limitées aux mandats nationaux et exécutifs** : députés (593), sénateurs (352), présidents de conseil départemental (94) et régional (14) ≈ 1 053 fiches — les seules riches (votes nominaux, groupes, HATVP). Maires et présidents d'EPCI (36 008) restent dans les listes et agrégats, sans page dédiée (leurs fiches n'affichaient que l'état civil RNE) ; expliqué sur la page /elus. Si l'allègement des fiches descend sous ~60 Ko brut/fiche, les 1 182 présidents d'EPCI seront ajoutés.
- **Recherche convertie côté client** (l'API paramétrique `/api/recherche?q=` ne peut pas être statique) : index JSON pré-généré, chargé à la première frappe.
- **Exports JSON quotidiens** en remplacement des 5 autres routes API, avec extension `.json` explicite (Content-Type correct sur Pages) ; documentés sur /donnees comme snapshots quotidiens, plus « API ».
- Pages à `searchParams` (elus, marches, collectivites, alertes, documents) : filtres et pagination côté client, budget < 500 Ko de HTML au premier chargement.
- Headers de sécurité : Pages ne permet pas de headers custom → CSP portée par `<meta http-equiv>` (limite connue : `frame-ancestors` ignoré en meta — risque clickjacking résiduel faible, documenté), HSTS déjà préchargé par github.io, nosniff posé par Pages (à vérifier en R3).

## Alternatives écartées (résumé — détail dans plateformes.md)

- **Hetzner CX33 (8,49 € HT/mois)** : meilleure option VPS, architecture systemd idéale — mais compte + CB + vérification d'identité possible = bloquant sans humain. Documentée comme montée en gamme dans ACTIONS-HUMAINES.md.
- **OVHcloud VPS-2** : souveraineté FR maximale mais commande panier + pas de cloud-init sur la gamme VPS.
- **Serverless (Vercel/Netlify/Cloudflare)** : incompatibilités structurelles prouvées (bundle 250 Mo Vercel vs db 447 Mo, crons ≤ 30 min vs ingestion 25-60 min, D1 = réécriture).

## Limites acceptées et suivies

- Bande passante Pages ~100 Go/mois (soft) et site ≤ ~1 Go : suivi dans RUNBOOK ; si dépassement → migration VPS (chemin décrit dans ACTIONS-HUMAINES.md).
- URL en github.io tant que le domaine n'est pas racheté (action humaine, DNS prêts dans ACTIONS-HUMAINES.md).
- Pas de rate-limiting à poser : contenus statiques servis par CDN, surface d'attaque nulle côté app (aucun process serveur à nous).
