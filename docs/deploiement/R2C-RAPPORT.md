# R2C — Façade publique (mentions légales, RGPD, robots/sitemap/favicons/OG, footer)

Chantier exécuté le 19/08/2026. Périmètre : les 9 points « façade publique » — aucun fichier des autres chantiers touché (`next.config.ts` intact, `app/api/*`, pages listes, fiche élu, header/nav/recherche non modifiés).

*État constaté le 19/08/2026. Les volumétries de ce document (nombre de sources, de pages et de fiches) décrivent ce jour-là et ont dérivé depuis ; l'état courant se lit sur la page /donnees du site. L'hébergeur y est GitHub Pages : le site a depuis migré vers un serveur dédié, et les mentions légales en ligne font foi (voir [DECISION.md](DECISION.md) et [exigences-publiques.md](exigences-publiques.md)).*

## Livré

1. **/mentions-legales** — régime éditeur non professionnel anonyme (art. 1-1, II LCEN, rédaction SREN 2024) ; hébergeur **GitHub, Inc., 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis — service GitHub Pages** (adresse vérifiée le 19/08/2026 sur le GitHub General Privacy Statement § Contact Us + registre LEI, sourcée en commentaire du code) ; directeur de la publication non publié (art. 93-2 loi 1982) ; droit de réponse via l'hébergeur ; contact = issues GitHub du repo + « une adresse e-mail dédiée sera ajoutée prochainement » ; licences : code sous licence du repo, données sous LO 2.0 avec attribution sur /donnees.
2. **/donnees-personnelles** — information art. 14 RGPD (dérogation 14(5)(b)) : responsable (l'éditeur via le canal de contact), finalité, base légale (intérêt légitime + art. 86 RGPD + L. 322-2 CRPA), catégories (données de responsables publics issues exclusivement de publications officielles ouvertes → /donnees), **zéro collecte visiteurs** (aucun cookie/traceur/compte/formulaire ; logs GitHub Pages seuls, doc GitHub liée), droits (accès/rectification/opposition sous un mois, **48 h en période électorale**), réclamation CNIL, ni transfert ni enrichissement.
3. **not-found.tsx** racine — 404 française dans le style du site, liens Accueil et /donnees (remplace le défaut Next anglais).
4. **Footer** (inline dans `layout.tsx`, pas de composant séparé) — « ODbL » retiré (25 sources toutes en LO — exigences §1.3), lien Licence Ouverte 2.0 → etalab.gouv.fr, + Mentions légales · Données personnelles · Code source (repo GitHub).
5. **public/** — `robots.txt` (Allow / + Sitemap absolu) ; `app/src/app/icon.svg` (monogramme FT, fond #0a1628, liseré tricolore) ; `apple-icon.png` 180×180 et `og.png` 1200×630 **réellement rasterisés** (Playwright chromium headless, HTML locaux) ; les 5 SVG create-next-app supprimés (grep préalable : zéro référence).
6. **app/src/app/sitemap.ts** + **app/src/lib/site.ts** (`SITE_URL`, `REPO_URL`, `CONTACT_ISSUES_URL`) — 13 pages statiques + 1 053 fiches élus (`SELECT DISTINCT` sur json_each(mandats), 4 types nationaux/exécutifs), trailing slash partout, garde « base absente ».
7. **Layout racine** — `metadataBase`, template `%s — France Transparence`, title défaut long, description factuelle, OpenGraph (og.png en URL absolue : un chemin relatif perdrait le basePath) + `twitter:card summary_large_image` ; **CSP en `<meta httpEquiv>`** hoistée dans `<head>` par React 19, émise en production seulement (`next dev` = HMR/eval incompatibles), limites documentées en commentaire (`unsafe-inline` exigé par l'hydratation Next en export ; `frame-ancestors` ignoré en meta, non inclus — cf. DECISION.md).
8. **Metadata** — ajoutées : accueil (description), /lobbying, /financement, 2 pages légales, 404 ; réécrite : /donnees ; /depenses et /frais déjà conformes (aucun chiffre périssable) — non touchées.
9. **/donnees** — carte « API locale » remplacée par **« Exports JSON (reconstruits chaque matin) »** listant exactement les 6 fichiers (méta/alertes/élus/budget-mensuel/marchés-agrégats/recherche-index), phrase « instantané quotidien daté (champ `genere_le` de `meta.json`), et non plus une API interrogeable ; la recherche du site interroge l'index côté navigateur » ; h1 et title « Données & exports » ; aucune mention ODbL ; crédits par source conservés tels quels.

## Preuves (build classique + `next start` :3623)

- `npm run build` **VERT** (TS ok, 0 lint error sur les 10 fichiers touchés) ; routes ○ statiques : /_not-found, /mentions-legales, /donnees-personnelles, /sitemap.xml, /icon.svg, /apple-icon.png.
- `/mentions-legales` **200**, `/donnees-personnelles` **200** (contenus légaux vérifiés point par point), `/url-bidon` → **404 française** (noindex), `/robots.txt` **200**, `/sitemap.xml` **200 avec 1 066 URLs, 1 066/1 066 en trailing slash**.
- `og.png` : PNG 1200×630, 101 491 octets, servi 200, référencé dans le `<head>` de l'accueil (og:image + twitter:image absolus) ; `apple-icon.png` : PNG 180×180.
- CSP présente dans le `<head>` de chaque page (vérifié au curl) ; **test Playwright sur / et /donnees-personnelles : 0 violation `securitypolicyviolation`, 0 console.error, 0 pageerror**, hydratation vivante (54 et 23 liens interactifs). Note : les prefetchs RSC en `net::ERR_ABORTED` observés sont des annulations du routeur Next sur pages force-dynamic, pas des blocages CSP (aucun évènement CSP associé).
- Footer sans ODbL avec les 3 nouveaux liens (vérifié dans le HTML + screenshot) ; `app/public/` ne contient plus que robots.txt et og.png.
- Serveur :3623 arrêté après tests ; aucun `.next/`, `out/`, `node_modules/` commité ; `next.config.ts` non modifié.

## Restes connus (hors périmètre R2C)

- `/elus` : title doublonné pré-existant (« … — France Transparence » codé en dur dans la page liste) — à corriger par le chantier pages listes avec le nouveau template.
- Les chemins `/api/*.json` et `/data/recherche-index.json` documentés sur /donnees ne serviront qu'après le chantier exports statiques (404 en attendant sur le serveur classique — assumé).
