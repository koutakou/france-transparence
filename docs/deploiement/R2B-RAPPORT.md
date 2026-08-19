# R2B — Pages listes en filtres client + recherche statique

Chantier « pages à searchParams → statique + client » (DECISION.md), mesures réelles `curl` sur build classique servi en local (port 3622, brut non compressé), 19/08/2026.

## Par page — avant / après (octets bruts, budget < 500 000)

| Page | Avant (audit) | Après | Passé côté client |
|---|---:|---:|---|
| /elus | 2 276 593 | **176 251** | Tables députés (577) et sénateurs (348) : 25 premières lignes dans le HTML, filtres groupe/département + « Tout afficher » sur fragments |
| /marches | 1 290 695 | **371 229** | Carte (GeoJSON chargé au montage), table départements (20/107 + « Tout afficher », données en props), série mensuelle (2 graphiques + vue tableau recalculés client), filtre BOAMP par famille sur fragment |
| /collectivites | 1 848 314 | **222 749** | 2 cartes, séries pluriannuelles région/département (fragment au 1ᵉʳ clic), tables conseils dép. (20/97), grandes communes (20/50), DGF dép. (20/105) — reste en props, « Tout afficher » sans fetch |
| /alertes | 270 958 | **176 030** | Filtres gravité/type + pagination sur fragment (1 590 alertes) ; page 1 (50) dans le HTML |
| /documents | 279 878 | **155 461** | Filtres nature/nominations + pagination du flux (2 778 textes) sur fragment ; page 1 (50) dans le HTML |

Plus aucun `searchParams` ni `force-dynamic` dans ces 5 pages ; zéro `headers()`/`cookies()` ; les 5 routes sortent « ○ Static » au build. Chaque troncature est annoncée à l'écran (« Affichage des N premiers … sur X »), tout reste accessible en ≤ 2 interactions, et les URL historiques (`?famille=…`, `?gravite=…`, `?region=…`, `?gd=…`…) sont restaurées côté client et réécrites à chaque filtre (replaceState).

## Fragments statiques créés (routes `force-static`, URL /data/…)

| Fragment | Octets | Contenu |
|---|---:|---|
| /data/geo-departements.json | 692 397 | fond de carte S27 (chargé 1 fois pour toutes les cartes) |
| /data/elus/deputes.json | 134 610 | 577 députés (colonnes du tableau) |
| /data/elus/senateurs.json | 73 702 | 348 sénateurs |
| /data/marches/ao.json | 34 855 | AO BOAMP pré-agrégés par famille (total, % sans montant, 20 échéances) |
| /data/collectivites/series.json | 97 498 | séries pluriannuelles des 17 régions + 97 conseils dép. |
| /data/alertes.json | 421 208 | 1 590 alertes, règle/base légale dédupliquées par type, URLs indexées |
| /data/documents/textes.json | 527 978 | 2 778 textes groupés par jour, natures/ministères indexés, lien Légifrance reconstruit (`préfixe + texte_id`, vérifié 2 778/2 778) |
| /data/recherche-index.json | 1 038 402 | index de recherche (≤ 1,5 Mo visé) |

Autres leviers de poids : cellules `DataTable` allégées (filet et gabarit posés une fois sur le conteneur, plus par cellule) ; les gros sous-arbres serveur (tables, graphiques série mensuelle) convertis en composants client — l'arbre d'éléments ne se duplique plus dans le payload RSC, seules les données compactes voyagent.

## Recherche (remplace /api/recherche)

- `SearchBox` : au premier focus/frappe, fetch unique de `/data/recherche-index.json` (mémoïsé au niveau module), puis recherche 100 % locale, insensible accents/casse (NFD), debounce 150 ms, clavier inchangé.
- Index : les 36 018 élus `[nom, prénom, typeMandatIdx, départementIdx, id?]` + 1 059 entités routables (ministères → /depenses, collectivités → /collectivites, partis → /financement, institutions → /frais, AN/Sénat → /elus). Mêmes plafonds que l'API (8 élus + 4 entités), parlementaires puis préfixe de nom puis alphabétique.
- Contrat fiches : `id` transporté SEULEMENT pour les 1 053 élus à mandat `depute`/`senateur`/`president_conseil_departemental`/`president_conseil_regional` (vérifié en base : exactement 1 053) → lien `/elus/<id>` ; les autres → lien liste `/elus` avec mention « dans les listes /elus » — jamais de fiche 404. Mention visible sur /elus : « Fiches détaillées : parlementaires et présidences d'exécutifs départementaux/régionaux. Les autres élus figurent dans les listes et agrégats. »
- basePath : tout fetch client passe par `urlSite()` (`NEXT_PUBLIC_BASE_PATH ?? ""`, inliné au build) — aucun `fetch("/data/…")` nu (grep vérifié).

## Honnêteté / design

Fraîcheur par bloc inchangée (badges meta_sources) ; libellé BOAMP corrigé (« re-filtré à chaque construction du site », plus « à l'affichage ») ; DATAVIZ respecté (vues tableau jumelles conservées, re-fetch en opacité 0,5 sans skeleton, pilules à coche) ; metadata posées telles que spécifiées sur les 5 pages. `npm run lint` : 0 erreur ; `next.config.ts` non modifié.
