# France Transparence

Dashboard web sur la transparence de la vie politique française : dépenses et recettes de l'État, commande publique, élus, lobbying, financement politique, frais et train de vie, finances locales, Journal officiel — **100 % données publiques réelles**, aucun chiffre fabriqué. L'honnêteté est le principe produit : chaque module affiche la date réelle de ses données (badge de fraîcheur alimenté par la table `meta_sources`), le mot « en direct » est banni parce qu'aucune source publique ne le permet, et ce que l'open data ne contient pas est documenté comme tel (la « boîte noire » du module Frais & train de vie, l'encart « hors champ » de l'accueil). L'ensemble tient dans une base SQLite unique, reconstruite localement depuis **41 sources officielles tracées** — le catalogue daté, avec la date réellement ingérée de chacune, est la page [`/donnees`](https://francetransparence.fr/donnees/), régénérée à chaque publication. Une page pédagogique [`/comprendre`](https://francetransparence.fr/comprendre/) — **hors navigation principale** — explique comment lire ces publications : glossaire, provenance, limites, journal des lectures.

![Page d'accueil, 24/08/2026 : onze onglets dont Recettes, champ de recherche dans le chrome, encart « hors champ » au-dessus du 240 Md€ d'exécution](docs/screenshots/accueil.png)

## Site public

**https://francetransparence.fr**

Export statique du dashboard, servi **directement par nginx** depuis un serveur dédié (Scaleway Dedibox, Ubuntu 22.04). **Aucun process Node en production** : le HTML est pré-rendu au build, nginx ne fait que servir des fichiers déjà écrits sur disque (et déjà compressés). Thème sombre unique, **aucun cookie, aucun traceur** — le HTML servi n'en porte pas. Ce n'est pas un flux temps réel : la fraîcheur affichée est celle de la dernière ingestion qui a réussi à publier.

Le site est reconstruit chaque matin vers 05:17 (heure de Paris) par le script serveur `ft-deploy`, déclenché par la minuterie systemd `ft-deploy.timer`. La publication est **tout ou rien** : mise à jour du dépôt → contrôle de l'identité de déploiement → ingestion de tous les pipelines → tests → build statique → contrôles de santé du site généré → **bascule atomique** du lien symbolique `current` vers la nouvelle release. Si une étape échoue, le lien ne bascule pas : l'ancienne version continue d'être servie sans interruption, et une alerte part. La fraîcheur affichée reste donc toujours celle de la base réellement construite.

Les cinq dernières releases sont conservées sur le serveur : `ft-rollback` revient à l'une d'elles en quelques secondes, sans rebuild.

```bash
make build-static   # export statique local (FT_EXPORT=1 → app/out/)
make serve-static   # sert app/out/ sur http://localhost:3620
```

L'ancienne adresse GitHub Pages ne sert plus le site : elle ne porte plus qu'une **page de redirection canonique** vers le domaine (`pages-redirection/`). Publier une copie intégrale du site sur les deux hôtes aurait fait vivre deux sites identiques en ligne et partagé l'autorité de référencement de chacune de ses quelque mille pages entre deux domaines ; GitHub Pages ne sachant pas émettre de 301, la canonique et le rafraîchissement méta sont les seuls instruments disponibles.

**La CI GitHub Actions ne publie plus le site**, et ce n'est pas une perte : elle valide chaque jour (cron 04:45 UTC) la chaîne complète — ingestion de tous les pipelines dans une base neuve, tests, build, contrôles de santé — dans un environnement neuf, **indépendant du serveur**. Si une source amont casse, on l'apprend là avant que le serveur ne rebuilde. Elle vérifie aussi chaque proposition de fusion **avant** qu'elle n'atteigne `main`, puisque c'est `main` qui alimente le serveur.

L'identité de déploiement est **paramétrable au build** : un fork change d'adresse sans toucher une ligne de source. `NEXT_PUBLIC_SITE_URL` (défaut `https://francetransparence.fr`) porte l'URL du site — canoniques, sitemap et `robots.txt` en sont dérivés (`app/src/app/robots.ts` génère le `robots.txt`, il n'y a plus de fichier statique), et les variables `NEXT_PUBLIC_HEBERGEUR_*` portent l'identité de l'hébergeur publiée dans les mentions légales (`app/src/lib/hebergeur.ts`).

Hébergement : serveur dédié — donc payant, contrairement à la première mise en ligne sur GitHub Pages.

Décision d'hébergement et limites : [docs/deploiement/DECISION.md](docs/deploiement/DECISION.md) · exploitation quotidienne : [docs/deploiement/RUNBOOK.md](docs/deploiement/RUNBOOK.md) · ce qui exige encore un humain : [docs/ACTIONS-HUMAINES.md](docs/ACTIONS-HUMAINES.md).

## Démarrage rapide

Prérequis : `python3.14`, Node.js ≥ 24, `make`.

```bash
make venv         # crée .venv (requests, duckdb, pytest)
make ingest       # reconstruit data/france.db — ~5-10 min et plus de 1 Go de
                  # téléchargements, gardés en cache dans data/raw
make app-install  # npm install dans app/
make dev          # http://localhost:3620
```

Le mode local SSR (`make build` puis `cd app && npm run start`, port 3620) n'est **pas** la production : en ligne, c'est `make build-static` (`FT_EXPORT=1`) servi par nginx, sans process Node.

La base `data/france.db` (493 Mo, 81 tables et 6 vues au 24/08/2026 — ça bouge ; le schéma : [docs/SCHEMA-DB.md](docs/SCHEMA-DB.md)) est gitignorée : elle se reconstruit entièrement par `make ingest`.

## Ré-ingérer

`make ingest` est rejouable à volonté : les téléchargements sont mis en cache dans `data/raw` et chaque pipeline remplace proprement ses tables. Pour rejouer un seul pipeline :

```bash
make ingest-<source>
```

avec `<source>` parmi les pipelines déclarés dans la variable `PIPELINES` du `Makefile`, qui fait autorité (24 cibles, dans cet ordre) : `referentiels`, `budget_mensuel`, `budget_structure`, `decp`, `boamp`, `approch`, `jorf`, `parlement`, `integrite`, `hatvp_declarations`, `lobbying`, `financement`, `collectivites`, `elections`, `trainvie`, `cada`, `registre_ue`, `dette_maastricht`, `deficit_maastricht`, `dole`, `agregats_apu`, `cge`, `protection_sociale`, `sirene`.

## Tests

```bash
make test         # suite pytest complète
```

Les tests de transformation tournent hors ligne sur des extraits réels figés dans `pipelines/tests/fixtures/` (pièges d'encodage inclus). Les tests d'intégration qui touchent le réseau portent le marqueur `reseau` — les exclure avec `pytest -m 'not reseau'`.

## Architecture

1. `pipelines/` (Python 3.14 + requests + DuckDB) télécharge les sources officielles dans `data/raw/` et les transforme ;
2. tout aboutit dans **une seule base SQLite**, `data/france.db` — le fichier est le contrat entre Python et Next ;
3. chaque ingestion réussie écrit sa ligne dans **`meta_sources`** (date des données, date d'ingestion, fréquence, licence, compte de lignes) : la fraîcheur est une donnée de premier rang, jamais un texte décoratif ;
4. l'app Next.js 16 (App Router, Tailwind 4, better-sqlite3) lit la base **en lecture seule**, sans aucun fetch externe au runtime ;
5. chaque page affiche son badge « Données au JJ/MM/AAAA · source · fréquence » depuis `meta_sources` ;
6. base absente = message « base non construite, lancer make ingest » — jamais de placeholder chiffré.

Le site public est l'export statique de cette même app (`make build-static`, `FT_EXPORT=1`) : toutes les pages sont pré-rendues au build, les filtres et la recherche tournent côté navigateur (index JSON pré-généré, fragments `/data/*.json`), et les anciennes routes API paramétriques sont remplacées par des exports `.json` quotidiens datés.

Détails : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Modules du dashboard

Onze onglets, dans l'ordre de la navigation (`MainNav`) — libellés complets, pas de 12ᵉ onglet. `/comprendre` et `/alertes` existent ; ce ne sont pas des onglets.

| Route | Module | Contenu et fraîcheur réelle |
|---|---|---|
| `/` | Accueil | Compteurs, carte des marchés, flux JO et alertes — chaque bloc daté par sa source (budget au dernier mois publié, marchés J-1, JO du jour). Encart « hors champ » au-dessus de l'exécution : ce que le site ne couvre pas. |
| `/depenses` | Dépenses | Exécution mensuelle DGFiP (~6 semaines de décalage), structure PLF 2026 (mention « PLF » : la LFI 2026 n'existe pas en données), subventions aux associations (versements 2023). Blocs cloisonnés : APU Maastricht, ESA TE, CFAP par fonction (S49), comptes INSEE par sous-secteur (S50), CGE, prestations DREES. |
| `/recettes` | Recettes | Même source S13 que les dépenses : recettes nettes du budget général (fiscales, non fiscales, fonds de concours à part), cumuls depuis le 1er janvier, séries depuis 2013. Sections cloisonnées : détail non fiscal du PLF (S46, projet, pas l'exécution) ; IRCOM (S47, impôt net sur rôle par territoire, année des revenus, pas l'IR de caisse) ; agrégats ESA des APU (S44) ; prélèvements obligatoires INSEE (S50, pas taxag) — ce n'est pas le budget de l'État. |
| `/marches` | Marchés publics | Marchés consolidés sur 24 mois glissants comptés à la date de notification initiale (quotidien, notifications J-1, consolidation légale ≤ 2 mois), appels d'offres en cours (BOAMP, jour même), achats à venir (APProch). Les comptes bougent chaque jour : voir `/donnees`. |
| `/elus` | Élus & Institutions | Environ 36 000 élus (RNE, trimestriel) dont 577 députés et 348 sénateurs (open data AN/Sénat/Datan, quotidien). Les conseillers municipaux n'entrent dans aucun chiffre de cette page. |
| `/elus/[id]` | Fiche élu | Pas un onglet. Plus de 1 000 fiches statiques (parlementaires et présidences d'exécutifs départementaux/régionaux — les autres élus restent dans les listes et agrégats) : mandats, 30 derniers votes sur les quelque 8 400 scrutins AN (le scrutin le plus récent est daté : hors session, il peut avoir plusieurs semaines), scores Datan crédités, lien HATVP. |
| `/lobbying` | Lobbying | Répertoire HATVP des représentants d'intérêts (quotidien) : entités inscrites, activités déclarées, dépenses par exercice annuel en fourchettes, croisement avec les marchés publics. Puis, dans un bloc **cloisonné** en fin de page, le registre de transparence de l'Union européenne (quotidien) : organisations inscrites, dont celles à siège en France. Deux registres, deux cadres juridiques — jamais fusionnés, jamais comparés. |
| `/financement` | Financement | Comptes des partis, exercice 2024 (publié le 10/02/2026 — le dernier possible) ; comptes de campagne des législatives 2024, 4 010 candidats (municipales 2026 : aucun compte publié à ce jour, instruction CNCCFP en cours). |
| `/frais` | Frais | 56 faits chiffrés sourcés (barèmes au 01/01/2026, contrôles exercice 2024, Élysée audité 2024) + 8 opacités documentées — pas de notes de frais : elles ne sont ni publiées ni communicables. **Carte des verrous** : avis et conseils de la CADA de 1984 à 2024, dépouillés en agrégats (qui refuse, sur quel fondement, et dans quel sens la commission tranche), avec le retard de versement de la source affiché en clair. |
| `/collectivites` | Finances locales | Comptes OFGL 2025 (provisoire), DGF, carte €/habitant ; fiscalité directe locale REI (imposition 2025, distincte des comptes). |
| `/documents` | Documents | Environ 2 600 textes des 30 derniers JO (quotidien, JO du jour disponible vers 00h30), filtres lois/décrets/nominations ; dossiers législatifs DILA (fonds DOLE) en page dédiée. |
| `/donnees` | Données | Catalogue des **41 sources** avec fraîcheur mesurée (le moniteur de santé des sources), licences, règles des alertes, **7** exports JSON statiques (`/api/meta.json`, `alertes`, `elus`, `budget-mensuel`, `marches-agregats`, `lobbying-marches`, `/data/recherche-index.json`) reconstruits à chaque publication. |
| `/alertes` | Alertes transparence | **Page, pas un onglet.** Environ 1 600 alertes sur 8 types, chacune avec sa règle de calcul et sa base légale, recalculées à chaque ingestion. |
| `/comprendre` | Comprendre les données | **Hors nav.** Appareil pédagogique déjà en ligne : fonctionnement de chaque publication, glossaire, provenance, limites, journal daté des lectures. Lien pied de page, encart accueil, `/donnees`. Aucun chiffre qui dérive. |

Les volumes de ce tableau sont donnés en **ordre de grandeur** : la plupart des sources publient quotidiennement, ces nombres bougent à chaque ingestion. La seule valeur qui fait foi est celle affichée par le site lui-même, avec la date de ses données — c'est le rôle du badge de fraîcheur et de la page `/donnees`, régénérée à chaque publication.

Captures de la release servie le 24/08/2026 — elles datent ce jour-là, elles ne gèlent pas un compteur :

![Dépenses de l'État : tuiles d'exécution, recettes et solde au pli, onze onglets dont Recettes](docs/screenshots/depenses.png)

![Marchés publics : tuiles DECP, BOAMP et APProch, carte des montants par département](docs/screenshots/marches.png)

![Comprendre les données : sommaire pédagogique, page hors navigation principale](docs/screenshots/comprendre.png)

![Données & exports : catalogue des sources, moniteur de fraîcheur](docs/screenshots/donnees.png)

## Sources & licences

Sources majeures (le catalogue **complet et daté** des 41 sources est la page `/donnees`, régénérée à chaque publication ; le référentiel : [docs/SOURCES.md](docs/SOURCES.md)) :

| Source | Fraîcheur | Licence |
|---|---|---|
| DECP consolidées — data.gouv.fr, consolidation `decp-processing` (Colin Maudry) | quotidienne | Licence Ouverte 2.0 |
| BOAMP — annonces de marchés (DILA) | quotidienne | etalab-2.0 |
| Journal officiel JORFSIMPLE (DILA) | quotidienne | Licence Ouverte (fr-lo) |
| HATVP — répertoire des représentants d'intérêts AGORA | quotidienne | Licence Ouverte Etalab |
| HATVP — liste des déclarations publiées | hebdomadaire | Licence Ouverte Etalab |
| Open data Assemblée nationale (députés, scrutins) | quotidienne | Licence Ouverte |
| Open data Sénat (sénateurs) | quotidienne | Licence Ouverte |
| Datan — scores de participation/loyauté des députés | quotidienne | Licence Ouverte (fr-lo) |
| DGFiP — situations mensuelles budgétaires (data.economie) | mensuelle | Licence Ouverte 2.0 |
| PLF 2026 budget vert, PLF 2025, jaune associations (data.economie) | annuelle | Licence Ouverte 2.0 |
| Répertoire national des élus (ministère de l'Intérieur) | trimestrielle | Licence Ouverte 2.0 |
| OFGL — comptes des collectivités et dotations | annuelle | Licence Ouverte 2.0 |
| CNCCFP — comptes des partis et comptes de campagne | annuelle / par scrutin | Licence Ouverte |
| geo.api.gouv.fr, france-geojson, populations INSEE | statique / annuelle | Licence Ouverte |
| CADA — avis et conseils (ensemble consolidé, agrégats seulement) | irrégulière (lots, 2 à 4 fois par an) | Licence Ouverte (fr-lo) |
| CGE — bilan patrimonial de l'État, pièce de synthèse (DGFiP) | annuelle | Licence Ouverte 2.0 (Etalab) |
| Eurostat — dette et déficit des APU au sens de Maastricht, agrégats ESA | trimestrielle / annuelle | Décision 2011/833/UE |
| DREES — prestations de protection sociale | annuelle | Licence Ouverte 2.0 (Etalab) |

Crédits : consolidation DECP par le projet communautaire `decp-processing` de Colin Maudry ; scores calculés par Datan (datan.fr, méthodologie liée dans l'UI) ; DILA (BOAMP, JORF, annuaire, référentiel de l'organisation de l'État) ; HATVP ; CADA ; OFGL ; INSEE ; CNCCFP ; DGFiP / data.economie.gouv.fr ; Eurostat ; DREES ; fonds de carte france-geojson (Grégoire David) et contours Etalab. Chaque réutilisation mentionne sa source et porte la licence de **cette** source — il n'y a pas une licence unique pour tout le site.

## Limites connues

Assumées et affichées dans l'interface — l'honnêteté est le principe produit :

- **Budget de l'État** : publication mensuelle avec ~6 semaines de décalage ; la date réelle du dernier mois publié est portée par le badge de fraîcheur et par `/donnees`. Aucun flux Chorus temps réel n'existe en open data.
- **Notes de frais parlementaires** : ni publiées ni communicables (ord. 58-1100, CE mars 2025, refus écrits AN/Sénat du 11/06/2026) → le module Frais & train de vie est pédagogique : barèmes exacts, contrôles agrégés, opacités documentées.
- **Montants d'accords-cadres** : ce sont des maximums contractuels, pas des paiements — libellés « marchés notifiés », jamais « dépensé ».
- **DECP** : latence légale de publication jusqu'à 2 mois — mention « en cours de consolidation » partout où le flux apparaît. Un marché est daté de sa **notification initiale** et non de son dernier avenant : c'est cette date qui décide de la fenêtre et du mois où il est compté, tandis que le montant, l'objet et les titulaires affichés sont ceux de sa version courante.
- **Lobbying** : la donnée HATVP ne sépare pas AN et Sénat (« Parlement » agrégé) et les dépenses sont déclarées par exercice annuel. Le registre européen, lui, ne publie aucun identifiant national d'entreprise (ni SIREN, ni TVA) : aucun rapprochement automatique n'est possible entre les deux registres, et aucun n'est tenté.
- **Comptes locaux 2025** : provisoires (chargés en juillet 2026, ~97 communes manquantes).
- **Outre-mer** : hors rendu de la carte (présent dans les tableaux et agrégats).
- **Scrutins du Sénat** : non ingérés à ce jour (le dump Dosleg n'est pas exploité).

## Contribuer

Signaler une donnée fausse (avec source officielle), proposer une source, corriger du code : [CONTRIBUTING.md](CONTRIBUTING.md). Une faille de sécurité se signale en privé, jamais par issue publique : [SECURITY.md](SECURITY.md).

## Rapport de mission

Journal de construction du 19-20/08/2026 (volumétrie **datée**, non réécrite) : [docs/RAPPORT-MISSION.md](docs/RAPPORT-MISSION.md). L'état courant se lit ici et sur `/donnees`.
