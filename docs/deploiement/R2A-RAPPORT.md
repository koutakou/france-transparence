# R2A — Export statique cœur (config, fiches élus, exports JSON)

19/08/2026. Périmètre : next.config, 7 pages hors listes, fiches élus, exports JSON, Makefile/.gitignore.

*État constaté le 19/08/2026. Les volumétries de ce document (nombres de fiches et de pages, tailles en octets) décrivent ce jour-là et ont dérivé depuis ; l'état courant se lit sur la page /donnees du site.*

## Fichiers modifiés

- **app/next.config.ts** : `output: 'export'` si `FT_EXPORT` posé (build classique préservé sinon) ; `basePath`/`assetPrefix` = `NEXT_PUBLIC_BASE_PATH` (vide en local) ; `trailingSlash: true` ; `images.unoptimized` ; `poweredByHeader: false` ; `serverExternalPackages` et `turbopack.root` conservés.
- **7 pages statiques** (`force-dynamic` retiré) : `app/src/app/{page,depenses,lobbying,financement,frais,donnees}/…` et `elus/[id]/page.tsx`. Toutes sortent en `Cache-Control: s-maxage=31536000` (fini le `no-store`).
- **app/src/app/elus/[id]/page.tsx** : `generateStaticParams` (SQL `json_each(mandats)` sur depute/senateur/president_conseil_departemental/president_conseil_regional → **1 053 fiches**), `dynamicParams = false` (404 assumé pour les 35 000 autres), `generateMetadata` (« Prénom Nom — Élus » + description factuelle, requête légère). Allègement : votes plafonnés aux **30 derniers** avec mention « Affichage des 30 derniers scrutins sur 100 présents en base », décomptes réétiquetés « sur ces scrutins », attribut `title` redondant des titres de scrutins supprimé (le texte intégral reste dans le nœud, ellipse CSS ; −13 Ko/fiche).
- **app/src/lib/queries/elus.ts** : `VOTES_FICHE_MAX = 30`, `getFicheElu` limite les votes et retourne `nb_scrutins_base`.
- **Exports JSON statiques** (`export const dynamic = "force-static"`, GET sans searchParams, base absente au build → throw : jamais de snapshot vide déployé) : `app/src/app/api/{meta,alertes,elus,budget-mensuel,marches-agregats}.json/route.ts`. `meta.json` porte `meta.genere_le` (ISO, date du build) — témoin de fraîcheur. `alertes.json` = dump complet (1 590), `budget-mensuel.json` = série 2013→courant (4 212 lignes), `elus.json` = 36 018 élus en champs compacts (id, nom, prénom, uid_an, matricule_senat, hatvp_url, types_mandats ; clés vides omises) car le dump intégral pèse 14 Mo ; `marches-agregats.json` inchangé sur le fond.
- **Supprimés** : `app/src/app/api/{meta,alertes,elus,recherche}/route.ts`, `api/budget/mensuel/route.ts`, `api/marches/agregats/route.ts` (la recherche passe côté client — chantier séparé ; la SearchBox actuelle recevra 404 en attendant).
- **app/src/lib/queries/donnees.ts** : + `getElusExport()`, `getBudgetMensuelComplet()` ; **alertes.ts** : + `getAlertesToutes()` (additifs).
- **app/src/app/donnees/page.tsx** : la carte « API locale » devient « Exports JSON quotidiens » avec les 5 nouvelles URLs (contrat fixe), liens préfixés `NEXT_PUBLIC_BASE_PATH` (seuls `<a href="/…">` en dur du périmètre ; le reste passe par `<Link>`).
- **.gitignore** : + `app/out/`. **Makefile** : + `build-static` (FT_EXPORT=1) et `serve-static` (`python3 -m http.server 3620 --directory out` — servi SANS basePath en local), cibles normales (pas de pattern rule .PHONY, make 3.81 vérifié `make -n`).

## Preuves (mesures réelles, `next start -p 3621`, serveur tué ensuite)

- `npm run build` (classique) : **VERT** — 1 067 pages statiques (dont 1 053 fiches SSG), 5 routes ƒ restantes = les 5 pages listes.
- `FT_EXPORT=1 npm run build` : échec **attendu** sur les pages listes. Erreur exacte : `Error occurred prerendering page "/alertes" … Page with 'dynamic = "force-dynamic"' couldn't be exported … Export encountered an error on /alertes/page: /alertes, exiting the build.` **Next 16/Turbopack s'arrête à la PREMIÈRE page fautive** (pas de liste cumulée) ; les 5 à convertir sont exactement les ƒ du tableau de routes : `/alertes`, `/collectivites`, `/documents`, `/elus`, `/marches`.
- 7 pages en 200 + `Cache-Control: s-maxage=31536000` ; accueil brut 744 350 o (744 116 à l'audit : inchangé, allègement hors chantier).
- 5 `.json` en 200, `application/json`, JSON valide : meta 16 084 o · alertes 1 373 221 o · elus 3 579 541 o (< 5 Mo) · budget-mensuel 1 604 552 o · marches-agregats 17 950 o. `genere_le = 2026-08-19T19:05:13.041Z`.
- Fiches : `/elus/PA719930/` **128 131 o** (323 276 avant), 30 lignes de votes rendues + mention honnête ; pire fiche du parc **140 813 o** (PA794938, 11 déclarations HATVP), moyenne ~90 Ko — objectif ≤ 150 Ko **tenu sur les 1 053**.
- **EPCI NON ajoutés** : seuil « ≤ 60 Ko/fiche » non atteint (~90 Ko de moyenne) — conforme à la règle de DECISION.md.
- `/elus/rne-…` (maire) → 404 ; anciennes URLs `/api/*` → 404 (après redirect 308 trailingSlash).
- Base : lecture seule (mtime france.db inchangé, wal 0 o) ; aucun secret ; ni `out/` ni `.next/` ni `node_modules/` commités.

## Choix assumés

1. Snapshot jamais vide : les routes JSON **jettent** si la base manque au build (la CI ne déploie pas, le site de la veille reste servi) — les pages gardent leur état dégradé « lancer make ingest ».
2. `elus.json` compact (14 Mo → 3,58 Mo) : identité + identifiants publics + lien HATVP + types de mandat ; détail des mandats sur les fiches et dans le RNE (documenté dans `meta`).
3. Votes plafonnés à 30 (et non ~40) : à 40, la pire fiche restait à 164 Ko ; 30 tient TOUT le parc sous 150 Ko avec marge, la mention « N derniers sur X » garde l'honnêteté.
