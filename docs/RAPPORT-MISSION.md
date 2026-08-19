# Rapport de mission — France Transparence

**Mission menée le 19/08/2026. Tous les chiffres de ce rapport sont vérifiés dans `data/france.db` (lecture seule), `meta_sources`, la table `alertes`, le Makefile et le journal du projet (JOURNAL.md).**

---

## 1. Résumé exécutif

Construit en une journée : un dashboard de transparence de la vie politique française alimenté à 100 % par des données publiques réelles — 13 pipelines Python ingèrent 25 sources officielles dans une base SQLite unique de 447 Mo (51 tables), servie par une app Next.js 16 de 12 pages et 6 routes API. L'honnêteté est le principe produit : la fraîcheur de chaque donnée est stockée en base (`meta_sources`) et affichée sur chaque page, le « en direct » de la maquette d'origine a été remplacé par les fréquences réelles des sources (quotidienne à annuelle), et ce que l'open data ne contient pas est documenté comme un fait (8 opacités sourcées). Chaque source a été testée par appels HTTP réels avant d'être documentée ; chaque volumétrie affichée vient d'un comptage en base, pas d'une promesse. État final vérifié : `make ingest` réel vert, 150/150 tests pytest, build de production vert (19 routes), 15 routes servies en HTTP 200, 12 captures d'écran validées.

---

## 2. Alimentation réelle, module par module

Les 12 pages, leurs sources, la fraîcheur affichée et les volumes constatés en base le 19/08/2026 :

| Page | Sources | Fraîcheur affichée | Volumes clés |
|---|---|---|---|
| `/` Accueil | S13, S1, S2, S3, S14, S20 + référentiels | par bloc : budget au 30/06/2026, marchés J-1, JO du jour, HATVP hebdo | dépenses nettes cumulées 240,54 Md€ au 30/06/2026 (+5,44 % vs 2025) ; bandeau 36 018 élus, 4 067 lobbyistes, 12 930 dossiers HATVP |
| `/depenses` Dépenses de l'État | S13 (SMB DGFiP), S20 (budget vert), S21, S23 | « exécution mensuelle, données au 30/06/2026 » ; « PLF 2026 » (jamais « LFI ») ; « versements 2023 » | 4 212 lignes mensuelles (2013→06/2026) ; 1 816 lignes budget vert (46 missions, 479,5 Md€ CP) ; 2 404 lignes destination 2025 ; 112 722 subventions aux associations |
| `/marches` Commande publique | S1 (DECP consolidées), S2 (BOAMP), S9 (APProch) | « consolidation quotidienne, notifications J-1 (18/08), publication légale ≤ 2 mois » ; annonces du jour même (19/08) | **586 229 marchés** dédupliqués (`donneesActuelles`, `uid`) ; 18 437 annonces BOAMP dont **9 011 AO en cours** ; 4 060 achats à venir ; agrégats écrêtés à 100 M€/marché |
| `/elus` Élus & institutions | S5 (AN), S6 (Sénat), S7 (Datan), S17 (RNE), S14 (HATVP) | AN/Sénat/Datan au 19/08 (quotidien) ; RNE au 11/08/2026 (trimestriel) | **36 018 élus** fusionnés sans doublon (dont 577 députés, 348 sénateurs ; conseillers municipaux en agrégats) ; RNE brut 37 041 lignes |
| `/elus/[id]` Fiche élu | S5, S7, S14 | dernier scrutin AN : n° 8434 du 21/07/2026 (vacances parlementaires) | votes nominaux sur 8 434 scrutins ; scores Datan crédités avec méthode ; lien direct vers la déclaration HATVP |
| `/lobbying` Lobbying | S4 (HATVP AGORA) | « répertoire quotidien, données au 18/08/2026 ; dépenses par exercice annuel » | **4 067 entités** (3 692 actives) ; 41 601 activités détaillées sur 24 mois (112 450 historiques en agrégats) ; budgets en fourchettes, pression par ministère/institution ciblés |
| `/financement` Financement politique | S25, S29 (CNCCFP), S37 | « exercice 2024, publié le 10/02/2026 — le dernier possible » ; « législatives 2024 ; municipales 2026 attendues fin 2026/2027 » | 2 179 lignes de comptes 2021-2024 (718 partis au référentiel) ; top produits 2024 : PCF 31,6 M€, Renaissance 19,49 M€, Ensemble! 19,47 M€ ; 4 010 comptes de campagne ; aide publique 2026 : 64 262 871,05 € (décret 2026-149) |
| `/frais` Frais & train de vie | S31 (corpus officiel) | « à parution » — barèmes au 01/01/2026, contrôles exercice 2024, Élysée exercice 2024 audité (le 2025 non paru) | **56 faits** chiffrés, chacun avec source/URL/date (indemnité parlementaire 7 637,39 € brut, DFP 7 238,04 €, AFM 6 600 €, Élysée : 94 déplacements = 20,1 M€, mission Pouvoirs publics 1,14 Md€) + **8 opacités** documentées |
| `/collectivites` Finances locales | S16 (OFGL), S27 (géo/INSEE) | « comptes 2025 provisoires (chargés juillet 2026, ~97 communes manquantes jusqu'en décembre) ; dotations 2026 » | 16 079 lignes agrégées (101 départements, régions, CD) ; 618 lignes de DGF 2018-2026 ; €/habitant de 1 055 (Orne) à 4 493 (Paris) |
| `/documents` Journal officiel | S3 (DILA JORFSIMPLE) | « JO du jour, disponible vers 00h30 » (le JO ne paraît pas tous les jours — assumé) | **2 778 textes** sur les 30 derniers JO ; JO du 19/08/2026 : 83 textes dont 5 lois et 41 nominations |
| `/alertes` Alertes transparence | S14×S17, S4, S25, S29 | « recalculées à chaque mise à jour des sources », chaque alerte datée | **1 590 alertes**, 8 types, toutes avec règle + base légale (détail § 4) |
| `/donnees` API & Données | meta_sources (toutes) | fraîcheur mesurée de chaque source (date de la donnée réellement ingérée) | 25 sources tracées, licences et crédits ; 6 routes API JSON (`/api/meta`, `/api/alertes`, `/api/budget/mensuel`, `/api/elus`, `/api/marches/agregats`, `/api/recherche`) |

---

## 3. Les promesses de la maquette non tenables — et ce qui les remplace

La maquette d'origine promettait un temps réel qui n'existe dans aucune donnée publique. Chaque impossibilité a été prouvée par des appels réels le 19/08/2026 (docs/SOURCES.md §3), puis reformulée :

1. **« Dépenses de l'État aujourd'hui » avec variation vs veille** — aucun dataset Chorus n'existe (recherche = 0 résultat ; Data-État « réservé aux agents autorisés »). Meilleure fraîcheur réelle : exécution mensuelle DGFiP, ~6 semaines de décalage (données au 30/06/2026 vues le 19/08). → Compteur « depuis le 1er janvier », badge daté, variation vs même période 2025.
2. **Flux « dernières dépenses en direct » à la minute** — même absence de paiements temps réel. → Deux flux réels et datés : marchés notifiés (J-1, « en cours de consolidation ») et textes au JO (jour même, lot nocturne ~00h30).
3. **Module « Notes de frais » en flux** — les justificatifs parlementaires ne sont ni publiés ni communicables : ordonnance 58-1100 (Parlement hors CADA), confirmée par le Conseil d'État en mars 2025, refus écrits des deux chambres le 11/06/2026 ; frais de représentation des ministres jamais publiés. → Module « Frais & train de vie » : barèmes exacts 2026, enveloppes (DFP/AFM), contrôles agrégés (déontologue AN : 84 reversements pour 276 335 €), sous-module Élysée (seul train de vie audité en détail, Cour des comptes), et la « boîte noire » : l'opacité elle-même est traitée comme une information.
4. **Top ministères « aujourd'hui »** — le niveau mission/programme mensuel n'existe qu'en PDF derrière un anti-bot (SME : HTTP 403 Cloudflare constaté) ; l'API mensuelle n'a que 26 lignes par grands titres. → Répartition mensuelle par nature + répartition annuelle par mission (PLF 2026, mention obligatoire « PLF » : la LFI 2026, promulguée le 19/02/2026, n'a jamais été publiée en données).
5. **Carte des « dépenses en direct »** — les dépenses de l'État ne sont pas géolocalisées en open data ; les marchés publics le sont nativement. → Carte réelle des marchés notifiés et carte des finances locales en €/habitant, libellées comme telles.
6. **Bandeau « transactions »** — les DECP sont des engagements contractuels (montants maximums), pas des paiements. → Libellé « marchés notifiés », montants rationalisés et écrêtés, jamais « dépensé ».
7. **Horodatage à la minute** — toutes les sources publient par lots (JO : 1 lot nocturne ; DECP : build quotidien ; HATVP déclarations : hebdomadaire). → Horodatage au jour de publication, latence connue affichée.

Promesses tenues telles quelles : appels d'offres en cours (BOAMP jour même), recherche globale, compteur d'élus, alertes transparence.

---

## 4. Alertes transparence implémentées

1 590 alertes en base, 8 types, chacune portant sa règle de calcul et sa base légale (affichées dépliables dans l'UI). Comptes réels de la table `alertes` :

| Type | Nb | Gravité | Règle (condensée) | Base légale |
|---|---|---|---|---|
| `A1_hatvp_non_deposee` | 4 | haute | Constat officiel HATVP repris tel quel (statut natif « Déclaration non déposée ») — seuls cas nominatifs de A1 | Loi 2013-907 (art. 4 et 11), art. LO 135-1 du code électoral ; sanctions art. 26 : 3 ans, 45 000 €, inéligibilité |
| `A1_hatvp_retard_presume` | 3 | moyenne | Retard **présumé** : statut « En cours » ET début de fonction (RNE) + 60 jours dépassé ; garde-fous : EPCI exclus, homonyme non tranché = non-alerte, agrégat non nominatif, réserve RNE trimestriel | idem A1 |
| `lobbying_defaut_declaration` | 316 | haute | Flag natif AGORA : informations exigibles non communiquées à la HATVP pour au moins un exercice — aucun calcul de délai, constat officiel | Loi 2016-1691 « Sapin II » — art. 18-3 loi 2013-907 ; sanctions art. 18-9/18-10 ; décret 2017-867 |
| `lobbying_declaration_incomplete` | 1 | moyenne | Flag natif AGORA `declaration_incomplete` par exercice | idem Sapin II |
| `financement_campagne_rejetee` | 85 | haute | Décision CNCCFP = « R » (rejet), législatives 2024 | Code électoral, art. L.52-15 (contrôle CNCCFP) |
| `financement_campagne_reformee` | 1 175 | moyenne | Décision « AR » (approbation après réformation) ; montant réformé = déclaré − retenu | Code électoral, art. L.52-15 |
| `financement_parti_dependance_aide` | 5 | info | Aide publique ≥ 75 % des produits ET produits ≥ 1 M€, dernier exercice publié — indicateur de structure, pas une infraction | Loi 88-227 du 11/03/1988 |
| `financement_parti_prive_aide` | 1 | info | Avis annuel CNCCFP (publié au JO en PDF seulement, détecté via le pipeline JORF) | Loi 88-227 du 11/03/1988 |

Non matérialisés en lignes d'alertes en v1 : les signaux marchés du plan initial (A6-A10 de SOURCES.md §4) — la qualité DECP est traitée dans les données elles-mêmes (champ natif `montant_anomalie`, écrêtage des agrégats à 100 M€/marché, montant NULL jamais affiché 0) ; le moniteur de fraîcheur (A11) est porté par la page `/donnees`, qui confronte la date réelle des données ingérées à la fréquence promise de chaque source. S'y ajoutent les alertes documentaires du module Frais (8 opacités sourcées : refus AN/Sénat du 11/06/2026, rémunérations des cabinets disparues des jaunes depuis PLF 2024, etc.).

---

## 5. Méthode

- **Orchestrateur pur + ~30 sous-agents** : 9 agents de recherche (un par axe, rapports `docs/recherche/01-09`), 1 agent de synthèse (SOURCES.md), 1 critique de complétude (2 findings critiques et 10 importants, tous appliqués), 11 agents pipelines (pour 13 pipelines), 1 agent design system (19 composants UI conformes au guide DATAVIZ), 8 agents pages (12 pages + API), plus des agents de correctifs.
- **Les fichiers sont la mémoire partagée** : JOURNAL.md (décisions numérotées), STATUS.md, docs/SOURCES.md, docs/NOTES-FRONT.md et docs/SCHEMA-DB.md servent de contrats entre agents ; aucun agent ne dépend de la mémoire d'un autre.
- **Épreuves sur bases jetables** : chaque pipeline a été développé et éprouvé sur une base temporaire (`FT_DB_PATH`) ; la base servie n'a été remplie que par l'orchestrateur, via un `make ingest` réel séquentiel.
- **Vérification par appels réels systématiques** : aucune source documentée sans code HTTP constaté le jour même (curl/WebFetch) ; SQL des pages testé sur la base réelle en lecture seule ; build de production et smoke tests HTTP joués par l'orchestrateur en fin de chaque vague.

---

## 6. Corrections d'honnêteté faites en route

Exemples concrets où le chiffre facile a été remplacé par le chiffre vrai :

- **Lobbying : 4 067 entités, pas 6 829.** Le 6 829 des documents de recherche était un artefact de comptage de lignes CSV (`wc -l`) ; le dédoublonnage réel donne 4 067 entités, dont 3 692 actives. Corrigé en base et dans tous les bandeaux.
- **Carte des marchés : fenêtre ramenée à 12 mois** au lieu des 24 annoncés initialement, pour coller à la fenêtre réellement calculée dans les agrégats.
- **Montant NULL n'est jamais 0** : ~70 % des appels d'offres BOAMP n'ont pas de montant publié → affiché « non publié » ; dans les agrégats départementaux, NULL = « aucun montant connu ». Aucune somme ne mélange l'inconnu et le zéro.
- **Alerte A1 réécrite avec garde-fous après la critique de complétude** : mandats EPCI exclus (le délai légal court à une date absente de l'open data — faux positifs mécaniques sinon), homonyme non tranché = non-alerte, retards « présumés » jamais nominatifs (agrégats seulement) ; le nominatif est réservé aux 4 constats officiels « Déclaration non déposée » de la HATVP.
- **JO du 19/08 recompté à l'ingestion** : 83 textes dont 41 nominations (le stade recherche en dénombrait 38 par un filtre lexical plus étroit).
- **Pas de bouton « Se connecter »** : la maquette en avait un, l'app n'a pas de comptes — l'honnêteté a primé sur la fidélité à la maquette.

---

## 7. Pistes v2

Documentées dans docs/SOURCES.md §5, aucune ne conditionne un module v1 :

- **Avis CADA** (CSV consolidé 198 Mo) → « carte des verrous juridiques » du module Frais : qui refuse quoi, administration par administration.
- **Jaune « opérateurs de l'État » PLF 2026** → référentiel des agences (liste et catégories ; les crédits par opérateur n'existent pas en données).
- **Hautes rémunérations de la fonction publique** : obligation légale (art. 37, loi TFP 2019) éclatée en 25 datasets épars → panel assumé, jamais présenté comme national.
- **Aides publiques aux entreprises** (~211 Md€/an, rapport Sénat 07/2025) : 0 dataset consolidé au 19/08/2026 → veille active + alerte documentaire.
- **Scrutins du Sénat** : dump Dosleg (scrutins nominaux depuis 2006).
- **Encarts outre-mer** sur les cartes (les DROM sont déjà dans les tableaux et agrégats).
- **Comptes de campagne des municipales 2026** : à ingérer dès publication CNCCFP (attendue fin 2026/2027).
- **Rapport Cour des comptes Élysée exercice 2025** : à parution (opacité dédiée en attendant).
- **Page recherche dédiée** (l'API `/api/recherche` existe déjà).
- Également : declarations.xml HATVP (patrimoine/intérêts détaillés), SME PDF (seul mission/programme mensuel), amendements et présence en commission AN, balances DGFiP en drill-down, veille RIE et export des avis de pantouflage HATVP, datasets PLF 2027 à leur sortie.

---

## 8. Chiffres de la mission

| Indicateur | Valeur |
|---|---|
| Sous-agents mobilisés | ~30 (9 recherche + 1 synthèse + 1 critique + 11 pipelines + 1 design system + 8 pages + correctifs) |
| Pipelines d'ingestion | 13 (`make ingest-<source>`) |
| Tests pytest | 150/150 verts (marqueur `reseau` pour l'intégration) |
| Base | `data/france.db` : 447 Mo, 51 tables, 25 sources tracées dans `meta_sources` |
| Volumes phares | 586 229 marchés · 36 018 élus · 12 930 dossiers HATVP · 4 067 entités lobbying · 2 778 textes JO (30 derniers JO) · 1 590 alertes · 56 faits + 8 opacités train de vie |
| App | 12 pages + 6 routes API ; build de production vert, 19 routes ; 15 routes vérifiées HTTP 200 ; 12 captures validées (docs/screenshots/) |
| Commits | 8 sur `main` (le huitième — clôture — embarque captures d'écran, correctifs UI, README et ce rapport) |
| Sources documentées | 39 cataloguées (S1-S39) + 18 écartées sur preuve dans SOURCES.md ; 25 tracées en base (v1) |

---

## 9. Déploiement public (reprise du 19/08/2026, décisions 20-22)

**URL : https://koutakou.github.io/france-transparence/** — statique pré-rendu sur GitHub Pages, reconstruit chaque matin par GitHub Actions. Premier run de publication lancé le 19/08/2026, en cours au moment de la rédaction de cette section (voir dernière ligne).

### Pourquoi GitHub Pages (docs/deploiement/DECISION.md)

- **Fait décisif : la seule voie exécutable sans action humaine** (docs/deploiement/machine-locale.md et plateformes.md). Seul GitHub est authentifié sur la machine (`koutakou`) ; toutes les plateformes à disque persistant exigent compte + CB en 2026 (tier gratuit Fly mort, Railway « post-paid », Render crons sans disque, Koyeb volumes « testing only », Clever FS incompatible better-sqlite3) ; le VPS OVH 51.83.96.83 est injoignable (ping OK, ports 24533/22/80/443 fermés) et koutakou.fr a expiré (AFNIC : NOT FOUND).
- **Cohérence produit statique-quotidien** : les données ne changent qu'à l'ingestion — le HTML pré-rendu est le cache parfait, servi par le CDN Fastly de Pages (HTTPS, HSTS préchargé sur \*.github.io) ; les `force-dynamic` posés partout en v1 étaient déjà un contresens relevé par l'audit (audit-app.md).
- **Atomicité structurelle** : un déploiement Pages remplace tout le site d'un coup — pas de bascule de base à orchestrer, pas d'état intermédiaire possible.
- Alternatives écartées sur preuve (plateformes.md) : Hetzner CX33 (8,49 € HT/mois, meilleur VPS mais compte + CB = humain requis — documenté comme montée en gamme), OVHcloud VPS-2 (commande panier manuelle), serverless (bundle Vercel 250 Mo vs base 447 Mo, crons ≤ 30 min vs ingestion 25-60 min).

### Durcissement statique (chantiers R2A/R2B/R2C, mesures réelles)

Budget tenu : < 500 Ko de HTML brut par page au premier chargement. Mesures `curl` non compressées (avant = audit R1, après = mesure finale R2, correctif accueil/lobbying inclus) :

| Page | Avant | Après |
|---|---:|---:|
| `/elus` | 2 276 Ko | **176 Ko** |
| `/collectivites` | 1 848 Ko | **223 Ko** |
| `/marches` | 1 290 Ko | **371 Ko** |
| `/lobbying` | 950 Ko | **276 Ko** (après correctif) |
| `/` (accueil) | 744 Ko | **174 Ko** |

Méthode : tables et dataviz converties en composants client alimentés par des fragments statiques `/data/*.json` (le payload RSC ne duplique plus l'arbre serveur), premières lignes dans le HTML, chaque troncature annoncée à l'écran (« Affichage des N premiers … sur X »), filtres et pagination côté client avec URLs historiques restaurées (`replaceState`).

- **Fiches élus : 1 053 fiches statiques** (`generateStaticParams` — députés 593, sénateurs 352, présidents de conseil départemental 94 et régional 14, les seules fiches riches) ; fiche témoin PA719930 : 323 → **128 Ko** (votes plafonnés aux 30 derniers avec mention « sur 8 434 en base » ; pire fiche du parc 141 Ko). Les ~35 000 autres élus restent dans les listes et agrégats — expliqué sur /elus.
- **Recherche côté client** : l'API `/api/recherche` (non statifiable) est remplacée par un index JSON pré-généré de ~1 Mo (1 038 402 o : 36 018 élus + 1 059 entités routables), chargé à la première frappe, recherche locale insensible aux accents et à la casse. Les 5 autres routes API deviennent des exports statiques `.json` datés (`meta.json` porte `genere_le`) qui jettent au build si la base manque — jamais de snapshot vide déployé.
- **Façade publique** : mentions légales (LCEN/SREN, éditeur non professionnel anonyme, hébergeur GitHub vérifié), page données personnelles (art. 14 RGPD, zéro collecte visiteurs), robots.txt, sitemap **1 066 URLs** (100 % en trailing slash), favicons + image OG réellement rasterisés, 404 française.
- **CSP portée par `<meta http-equiv>`** (Pages n'autorise aucun header custom), limites documentées : `unsafe-inline` exigé par l'hydratation Next en export, `frame-ancestors` ignoré en meta — risque clickjacking résiduel faible, assumé dans DECISION.md.
- **Footer corrigé : Licence Ouverte 2.0 seule** — la mention ODbL du footer v1 était inexacte et a été retirée : les 25 sources tracées sont toutes sous Licence Ouverte.

Build export intégral vert (décision 22) : zéro route dynamique, 1 053 fiches SSG, site 232 Mo, 12 pages < 500 Ko, 150/150 pytest.

### Exploitation quotidienne

Workflow `publication.yml` : cron **04:45 UTC** (~06h45 Paris, après le lot JO ~00h30 et les builds DECP nocturnes) — `make ingest` (base neuve dans le runner éphémère) → `make test` → build export → déploiement Pages atomique. **Toute étape en échec = aucun déploiement** : le site de la veille reste servi tel quel et une issue « publication-echec » s'ouvre automatiquement ; la fraîcheur affichée (meta_sources) reste vraie par construction. Déclenchement manuel : `gh workflow run publication.yml`. Détail d'exploitation : docs/deploiement/RUNBOOK.md. **Coût : 0 €/mois** (repo public — audité sans secret —, Pages et minutes Actions gratuites).

### Actions humaines restantes (optionnelles — docs/ACTIONS-HUMAINES.md)

Rien n'est bloqué sans elles : rachat d'un domaine (koutakou.fr expiré, redevenu libre ; DNS et procédure prêts), adresse e-mail de contact dédiée (les issues GitHub servent de canal RGPD en attendant), vérification au manager OVH du VPS 51.83.96.83 (peut-être facturé sans servir), montée en gamme VPS si la bande passante Pages (~100 Go/mois, souple) devenait limitante.

_Vérifications externes du site public : [[EN COURS — à confirmer par l'orchestrateur]]_

---

*Rapport établi le 19/08/2026. Toute reprise du projet commence par JOURNAL.md + STATUS.md, puis docs/SOURCES.md, docs/ARCHITECTURE.md, docs/deploiement/DECISION.md et docs/deploiement/RUNBOOK.md.*
