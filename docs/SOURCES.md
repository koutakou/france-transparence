# SOURCES.md — Référentiel unique des sources de données

**Projet France Transparence · Document de référence de la suite du projet · Établi le 19 août 2026.**
**Révisé le 19/08/2026 après critique de complétude (docs/recherche/10-critique-completude.md)** — corrections C1-C2, I1-I10 et mineures (M1, M3, M4, M6-M9) intégrées ; périmètre v1 inchangé (13 pipelines).

> **Mise à jour du 20/08/2026 (soir).** Le périmètre a depuis dépassé la v1 : deux sources
> classées v2 dans ce document ont été ingérées — **S15** (contenu des déclarations d'intérêts
> HATVP, via `pipelines/ingest_hatvp_declarations.py`) et **S26** (participation électorale,
> via `pipelines/ingest_elections.py`, agrégats commune/département, **sans aucune nuance
> politique ni nom de candidat**). Les mentions de « 13 pipelines » ci-dessous décrivent le
> périmètre v1 tel qu'arrêté le 19/08/2026 et sont conservées à ce titre : la liste qui fait
> autorité est la variable `PIPELINES` du `Makefile`.

Ce document synthétise les 9 rapports de la Phase 0 (`docs/recherche/01` à `09`), tous fondés sur des **appels réels effectués le 19/08/2026** (curl/API, codes HTTP constatés). Chaque affirmation de fraîcheur ou de volumétrie cite son rapport source entre parenthèses. Règle du projet : **données réelles uniquement, fraîcheur affichée et mesurée** — pas de promesse que les sources ne peuvent pas tenir.

Contexte 2026 à garder en tête : LFI 2026 promulguée tardivement le 19/02/2026 et jamais publiée en données structurées (01-budget-etat.md) ; municipales des 15 et 22 mars 2026 intégrées au RNE et à la HATVP (04-elus-integrite.md) ; renouvellement sénatorial le 27/09/2026 et 17e législature paramétrable, jamais codée en dur (03-parlement.md).

---

## 0. Conventions transverses d'ingestion (pièges valables partout)

1. **Plateformes Opendatasoft** (data.economie, BOAMP, OFGL, annuaire, journal-officiel/bodacc-datadila) : `/records` plafonné à **offset+limit ≤ 10 000** (HTTP 400 au-delà, constaté) ; quota **50 000 appels/jour/IP** (en-tête `x-ratelimit-limit`) ; le bulk passe par `/exports/{csv,parquet,json}` qui streame avec `where`/`select` sans plafond (02-commande-publique.md, 06-finances-locales.md).
2. **Date de modification d'un dataset ≠ fraîcheur des données** : toujours vérifier par tri sur le champ date (démonstration : marchés PLACE « modifiés 2026 » mais figés fin 2017, 01-budget-etat.md §10 ; sites civic-tech morts qui répondent HTTP 200, 08-ecosysteme.md leçon n° 3).
3. **URLs `static.data.gouv.fr` horodatées** (RNE, CNCCFP, Sirene…) : le chemin change à chaque millésime → re-résoudre via l'API data.gouv à chaque ingestion (04-elus-integrite.md, 09-referentiels.md).
4. **Anti-bots à ne pas confondre avec des pannes** : Légifrance (403 Datadome), budget.gouv.fr et economie.gouv.fr (Incapsula/Cloudflare), Tricoteuses (Anubis) — ne jamais scraper ces sites, passer par les données ; les sondes de fraîcheur doivent gérer ces cas (07-documents-juridique.md, 08-ecosysteme.md).
5. **Encodages** : AN = UTF-8 ; **Sénat = ISO-8859-1 avec lignes de commentaire `%` à sauter** ; CNCCFP campagnes = cp1252 + 6 lignes de garde ; montants DGFiP/HATVP avec espaces insécables U+00A0/U+202F ; valeur de remplissage **`"CDL"` = null** sur data.economie (03, 04, 01, 02).
6. **Jointures d'identité** : pas d'identifiant national d'élu partagé (HATVP ↔ RNE = nom+prénom+département, homonymes à arbitrer, 04) ; l'open data AN fournit `uri_hatvp` par député (03) ; collectivités : joindre par **SIREN**, jamais par code INSEE dans les balances DGFiP (tronqué, 06).
7. **Licences** : quasi tout est en Licence Ouverte/Etalab 2.0 (mention de la source obligatoire) ; exceptions : **HowTheyVote = ODbL** (attribution + share-alike base), NosDéputés historique = ODbL, code Tricoteuses = AGPL-3.0 (viralité si code réutilisé) (09, 08).

---

## 1. Catalogue final des sources retenues (exploitabilité décroissante)

### Groupe A — Exploitables directement, rafraîchies quotidiennement

#### S1. DECP consolidées au format tabulaire (data.gouv.fr / consolidation Colin Maudry) ★ source n° 1 des attributions et de la carte
- **URLs testées** : Parquet `https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432` (302 → static.data.gouv.fr, HTTP 200, **build du jour même 19/08 05:15**) ; API tabulaire sans clé `https://tabular-api.data.gouv.fr/api/resources/22847056-61df-452d-837d-8b8ceadbfc52/data/` (filtres `__exact/__greater/__less/__contains`, `page_size` ≤ 200). Page : `https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire` (02-commande-publique.md).
- **Accès/format** : Parquet **243 Mo** (ou CSV 2,54 Go) + API REST. **Granularité** : 1 ligne = marché × titulaire × modification, avec noms, SIRET, **lat/lng, commune/département/région, catégorie PME/ETI/GE pour l'acheteur ET le titulaire**, `montant_rationalise`, `montant_anomalie`, `donneesActuelles`, CPV, procédure, `offresRecues`, durée (02).
- **Période/fraîcheur** : consolidation de ~53 sources officielles ; **mise à jour quotidienne**, marché le plus récent notifié la veille (2026-08-18 vu le 19/08) (02).
- **Licence** : Licence Ouverte v2.0. **Volumétrie** : **3 238 492 lignes** au build du 19/08 (02).
- **Pièges** : 1 marché = n lignes → **dédoublonner par `uid` + `donneesActuelles=true`** ; montants d'accords-cadres = maximum, pas dépensé → utiliser `montant_rationalise`/`montant_anomalie` ou écrêter p99 ; consolidation communautaire (code public `decp-processing`) à créditer ; latence légale de publication jusqu'à 2 mois (02) ; ⚠ **l'API tabulaire data.gouv est en bêta** (08 §2.1) : contrat susceptible de changer sans préavis — simple raccourci, substituable par des requêtes DuckDB sur le parquet local (mode nominal de P3).
- **Plan B (point de défaillance unique)** : consolidation maintenue par une personne — profil exact des morts recensées par 08 (`decp_augmente` [Obsolète], `decp.info` 301 vers offre commerciale). (a) **Mode dégradé documenté** = S8 + fichiers consolidés DAJ bruts, résolution des noms via S18 Sirene, géolocalisation par `lieuexecution` + annuaire S11 — carte en **agrégats départementaux** au lieu de points ; (b) le build quotidien S1 **et** l'activité du dépôt `decp-processing` sont inscrits au moniteur A11 ; (c) **archivage local du dernier parquet sain avant chaque remplacement** (le fichier EST l'état : un build cassé écraserait tout) (10-critique C1).
- **Modules** : Commande publique (carte, attributions, fiches acheteurs/titulaires), Accueil (flux + carte), Alertes.

#### S2. BOAMP — annonces de marchés (API DILA/Opendatasoft) ★ le module « appels d'offres en cours » est réellement alimentable
- **URL testée** : `https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records` (HTTP 200, sans clé) (02).
- **Fraîcheur** : quotidienne, **annonces du jour même présentes le matin** (`dateparution=2026-08-19` vues le 19/08) (02).
- **Volumétrie** : 1 698 829 annonces ; natures : APPEL_OFFRE 1 154 552, ATTRIBUTION 463 698… ; **8 988 AO à clôture future** constatés (02).
- **Licence** : etalab-2.0. **Pièges** : montant non à plat (JSON eForms dans `donnees`, parsing hétérogène) ; `datelimitereponse` nulle sur attributions ; joindre `annonce_lie` pour rectificatifs/annulations ; `code_departement` = liste ; pagination profonde via `/exports/*` (02).
- **Modules** : Commande publique (AO en cours triés par urgence, attributions du jour), Accueil.

#### S3. DILA — dumps JORFSIMPLE (Journal officiel) ★ « voie royale », JO du jour à 00h30
- **URL testée** : `https://echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/` (HTTP 200, sans auth, sans quota) ; le tarball nocturne `JORFSIMPLE_20260819-003035.tar.gz` (392 Ko) contient le **JORF n° 0192 du 19/08/2026 complet** (sommaire structuré + 83 textes en XML autocontenus) (07-documents-juridique.md).
- **Format/granularité** : 1 texte = 1 XML avec `NATURE` (LOI/DECRET/ARRETE), `NOR`, `TITREFULL`, `MINISTERE`, dates, articles complets, `ID_ELI` → lien Légifrance sortant ; le sommaire (`JORFCONT`) donne les rubriques dont **« Mesures nominatives »** (07).
- **Fraîcheur** : livraison nocturne ~00h20-00h45 = JO du jour (76-440 Ko) ; livraison du soir (2,8-13 Mo) = corrections rétroactives à ignorer pour le flux ; jours sans JO existants (07).
- **Licence** : Licence Ouverte (fr-lo). **Pièges** : URLs non prédictibles → parser l'index HTML (ISO-8859-1) ; historique complet = Freemium 1,0 Go optionnel (07).
- **Modules** : Documents/JO (flux quotidien, nominations, lois, décrets), Accueil.

#### S4. HATVP — répertoire des représentants d'intérêts AGORA (lobbying), mis à jour chaque nuit
- **URLs testées** : JSON intégral `https://www.hatvp.fr/agora/opendata/agora_repertoire_opendata.json` (200, **137,7 Mo**, Last-Modified **19/08/2026 00:04** → quotidien) ; **vues CSV recommandées** `https://www.hatvp.fr/agora/opendata/csv/Vues_Separees_CSV.zip` (200, 14,2 Mo, 15 tables) (04-elus-integrite.md).
- **Granularité/volumétrie** : 6 829 entités, **118 516 fiches d'activités**, 24 568 exercices ; par exercice : fourchettes de dépenses de lobbying, CA, flags **`defautDeclaration`**/`declaration_incomplete` ; par action : décisions visées et **institutions ciblées** (table `13_ministeres_aai_api.csv`, 37,8 Mo) (04).
- **Licence** : LO Etalab. **Pièges** : JSON de 137 Mo sur une ligne → ijson ou préférer les CSV ; budgets en fourchettes ; jamais le nom de l'élu rencontré, seulement l'institution/fonction (04).
- **Modules** : Lobbying, Alertes.

#### S5. Open data Assemblée nationale (data.assemblee-nationale.fr) — dumps quotidiens, législature 17
- **URLs testées** (toutes HTTP 200, last-modified du jour même le 19/08) (03-parlement.md) :
  - **AMO10** députés/mandats/organes : `…/repository/17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip` (4,9 Mo ; 577 acteurs, 7 125 organes, déports, **champ `uri_hatvp`**) ; AMO30 historique 13,6 Mo ; AMO40 CSV 6,8 Mo ; ⚠ AMO50 figé au 11/07/2024.
  - **Scrutins** : `…/repository/17/loi/scrutins/Scrutins.json.zip` (26,3 Mo zip, **8 434 scrutins**, votes nominaux par député ; dernier : n° 8434 du 21/07/2026 — vacances d'été).
  - **Questions** écrites (45,8 Mo) / au gouvernement (5,4 Mo) : `…/repository/17/questions/…` (ministère interrogé + réponse → délais par ministère).
  - Amendements (`…/loi/amendements_div_legis/Amendements.json.zip`, **296,7 Mo**) et Agenda/réunions (7,8 Mo) : quotidiens mais **avec effort** (volumétrie ; reconstruction de la présence en commission).
- **Licence** : Licence Ouverte. **Pièges** : champs objet→liste selon cardinalité ; jointures par `acteurRef`/`organeRef` ; paramètre `legislature=17` jamais en dur (03).
- **Modules** : Élus & Institutions (fiches, votes, cumuls, déports), Alertes (lien HATVP).

#### S6. Open data Sénat (data.senat.fr) — CSV quotidiens + dumps PostgreSQL
- **URLs testées** (HTTP 200, last-modified du jour) (03) : `https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv` (427 Ko, 1 965 sénateurs actifs+anciens, groupe, commission) + ~19 CSV `ODSEN_*` ; questions `…/data/questions/questions-depuis-un-an.csv` ; **Dosleg** `…/data/dosleg/dosleg.zip` (16 Mo → dump SQL 126,3 Mo, tables `scr`/`votsen` = **scrutins nominaux depuis 2006**, 337 scrutins session 2025-2026, dernier 22/06/2026) et **Ameli** (154 Mo) : **avec effort** (PostgreSQL).
- **Licence** : Licence Ouverte. **Pièges** : **ISO-8859-1**, séparateur `;`, lignes `%` d'en-tête ; renouvellement du **27/09/2026** à prévoir (03).
- **Modules** : Élus & Institutions.

#### S7. Datan — statistiques de votes des députés (CSV data.gouv.fr)
- **URL testée** : dataset « Députés actifs de l'Assemblée nationale — Informations et statistiques » (data.gouv.fr, org. Datan), ressource `deputes-active.csv` — **mise à jour du jour même** (`dateMaj=2026-08-19`) ; colonnes `scoreParticipation, scoreLoyaute, scoreMajorite`, id `PA…` joignable avec l'open data AN (03, 08-ecosysteme.md).
- **Licence** : fr-lo. **Pièges** : AN seulement ; scores calculés par Datan → **créditer et lier la méthodologie** (03) ; projet communautaire fragile (leçon n° 1 de 08) → **CSV inscrit au moniteur A11**.
- **Fallback écrit (si Datan s'arrête)** : recalculer le taux de participation/loyauté depuis **S5 Scrutins.json** (votes nominaux, déjà ingérés en P9 ; dénominateur = scrutins de la période de mandat de chaque député) (10-critique I6).
- **Modules** : Élus & Institutions (participation/loyauté sans recalcul).

#### S8. DECP officielles data.economie.gouv.fr (DAJ) — chiffres « officiels » + agrégats serveur
- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp-2022-marches-valides/records` (200 ; `group_by` serveur testé) (02).
- **Fraîcheur/volumétrie** : J-2 (17/08 vu le 19/08) ; **689 062 marchés** (1 ligne/marché) ; frère `decp-2022-concessions-valides` : 589 lignes seulement (couverture concessions trop faible) (02).
- **Licence** : LO v2.0. **Pièges** : `"CDL"` = null ; montants bruts non rationalisés (l'Oise à 4,33 Md€/30 j en sommant brut — démonstration réelle) ; `lieuexecution_code` à granularité mixte (« 60 », « FR », « 14000 ») ; pas de noms ni géocodage (SIRET seuls) (02).
- **Modules** : Commande publique (compteurs officiels, contrôle de cohérence de S1).

#### S9. APProch — projets d'achats publics (marchés À VENIR)
- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/records` (200) ; **11 388 projets, dont 4 060 à publication future**, maj 15/08/2026 (02, 01).
- **Licence** : LO v2.0. **Pièges** : SIREN en entier (re-padder à 9 chiffres) ; montants en tranches texte (pas de somme) ; couverture surtout État/hôpitaux (02).
- **Modules** : Commande publique (« ce que l'État s'apprête à acheter »).

#### S10. API Recherche d'entreprises (recherche-entreprises.api.gouv.fr) — résolution d'entités
- **URL testée** : `https://recherche-entreprises.api.gouv.fr/search?q=<texte|SIREN|SIRET>` (200, **sans auth**) ; recherche par SIRET 14 chiffres OK ; filtres `est_administration`, `departement`… ; bonus : fiches collectivités avec **liste des élus** (RNE) et coordonnées GPS (09-referentiels.md).
- **Fraîcheur** : quotidienne (`date_mise_a_jour` du jour même constatée). **Licence** : LO 2.0. **Pièges** : **7 req/s/IP max** (429 au-delà) ; API de recherche, pas d'extraction massive (09).
- **Modules** : transverse (fiches acheteurs/titulaires/institutions), Élus & Institutions.

#### S11. Annuaire de l'administration (api-lannuaire.service-public.fr)
- **URL testée** : `…/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/records?where=pivot LIKE "prefecture"` (200 ; 107 préfectures avec **lat/lon du bâtiment** ; 94 117 fiches au total) (09).
- **Licence** : données DILA en open data (mention DILA). **Piège** : pas de pivot `ministere` (09). **Modules** : Élus & Institutions (fiches), carte.

#### S12. ODS DILA — BODACC et JO associations (périphériques, v2)
- **URLs testées** : `https://bodacc-datadila.opendatasoft.com` (`annonces-commerciales` : 50 393 102 enreg., parution 19/08) ; `https://journal-officiel-datadila.opendatasoft.com` (`jo_associations` : 5 645 043 enreg., parution 19/08) — **aucun dataset JORF lois-décrets sur ces portails** (07).
- **Licence** : Licence Ouverte. **Modules** : recoupements associations/entreprises (v2).

### Groupe B — Exploitables directement, hebdomadaires à trimestrielles

#### S13. Situations mensuelles budgétaires de l'État, séries longues (DGFiP) ★ la meilleure fraîcheur qui existe pour les dépenses de l'État
- **URLs testées** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/situations-mensuelles-budgetaires-series-longues/records?limit=3` (200) et `…/exports/csv` (200) (01-budget-etat.md).
- **Format/granularité** : **26 lignes** (solde, dépenses par grands titres — personnel, fonctionnement, intervention, dette… — recettes, comptes spéciaux) × une colonne par mois ; **pas de détail mission/programme** (01).
- **Période/fraîcheur** : 2013 → **30/06/2026** constaté le 19/08 (dataset modifié le 07/08/2026) → **mensuel, ~5-7 semaines de décalage** ; mois infra-annuels provisoires (01).
- **Licence** : LO v2.0. **Pièges** : noms de colonnes commençant par un chiffre → backticks en ODSQL ; anomalie `24_04_2024` (ne pas parser les dates de colonnes naïvement) ; ~10 décimales flottantes ; ne pas utiliser le jumeau vide `series-longues-smb_dgfip-vdef` (01).
- **Modules** : Dépenses de l'État (compteur mensuel, N vs N-1), Accueil.

#### S14. HATVP — liste des déclarations publiées (`liste.csv`) ★ pièce maîtresse des alertes
- **URL testée** : `https://www.hatvp.fr/livraison/opendata/liste.csv` (200, 3,3 Mo, **12 930 dossiers déclaratifs**, Last-Modified 14/08/2026 → **hebdomadaire**) (04).
- **Contenu décisif** : `statut_publication` compté le 19/08 : Livrée 8 884 ; **« En cours » (attendue, non déposée) 1 241** ; **« Déclaration non déposée » (constat officiel) 4** ; vague post-municipales 2026 incluse (3 234 dépôts 2026) (04).
- **Licence** : LO Etalab. **Pièges** : pas d'identifiant personne stable (`id_origine` rempli seulement pour les parlementaires) ; **toujours tirer hatvp.fr** (miroir data.gouv moins frais) (04).
- **Modules** : Alertes transparence, Élus & Institutions.

#### S15. HATVP — contenu intégral des déclarations (`declarations.xml`)
- **URL testée** : `https://www.hatvp.fr/livraison/merge/declarations.xml` (200, **88,8 Mo**, hebdo ; ⚠ l'ancienne URL `livraison/opendata/declarations.xml` = 404) ; **6 611 déclarations** en texte intégral structuré (rémunérations annuelles, participations, activités du conjoint…) (04).
- **Licence** : LO Etalab. **Pièges** : parser en streaming (SAX/iterparse) ; montants « 70 676 » avec espaces ; delta avec liste.csv (versions dépubliées absentes) ; doc structure `opendata-structure.xlsx` (04).
- **Modules** : Élus & Institutions (fiches patrimoine/intérêts) — v2.

#### S16. OFGL — data.ofgl.fr ★ source pivot des finances locales
- **URLs testées** : `https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-communes/records` (200, API ODS sans clé) ; export filtré testé : **toutes les communes × 1 agrégat × 2025 = 34 778 lignes, 1,9 Mo, 2,8 s** ; `group_by=dep_code` serveur → 101 départements en 1 requête (06-finances-locales.md).
- **Granularité/période** : 1 ligne = collectivité × exercice × budget × agrégat (55 agrégats, `euros_par_habitant` déjà calculé) ; communes 2018-**2025** (21,97 M lignes, maj 29/07/2026), départements/régions 2012-2025, **dotations 2018-2026** (27,1 M lignes, maj 04/08/2026 ; DGF 2026 de Lyon = 56 959 311 € testé) (06).
- **Fraîcheur** : millésime N chargé en juillet N+1 (provisoire), consolidé en décembre N+1 ; **~97 communes sans comptes 2025 avant décembre 2026** (06).
- **Licence** : LO 2.0. **Pièges** : `exer` est une date → `year(exer)=2025` sinon HTTP 400 ; filtrer `type_de_budget="Budget principal"` ou prendre les bases `-consolidee` ; dotations en format long `variable`/`valeur` (7 variantes « DGF ») ; millésimes anciens déplacés en pièces jointes (06).
- **Modules** : Finances locales (carte, fiches, dotations), Accueil.

#### S17. Répertoire national des élus (RNE, ministère de l'Intérieur) — à jour post-municipales 2026
- **URL testée** : `https://www.data.gouv.fr/datasets/repertoire-national-des-elus-1/` (200) ; **12 CSV maj 11/08/2026** (maires 4,26 Mo, conseillers municipaux 65,3 Mo, EPCI 10 Mo, députés, sénateurs…), mandats de mars 2026 intégrés (04).
- **Fraîcheur** : trimestrielle. **Licence** : lov2. **Pièges** : URLs static horodatées → re-résoudre ; pas d'identifiant commun HATVP → jointure nom+prénom+département ; ~500 000 lignes municipales (04).
- **Modules** : Élus & Institutions (référentiel « qui est élu où », démographie), **dénominateur des alertes HATVP** (date de début de fonction).

#### S18. Stock Sirene (INSEE via data.gouv.fr) — résolution massive
- **URL testée** : ressources du dataset « Base Sirene… » — StockUniteLegale CSV zip 970,6 Mo / **Parquet 705 Mo** (StockEtablissement Parquet 2,20 Go), last-modified **01/08/2026**, mensuel (09).
- **Licence** : lov2. **Pièges** : l'ancien chemin `files.data.gouv.fr/insee-sirene/` = 404 (09). **Modules** : transverse (table SIREN→nom/catégorie via DuckDB) — v2, S1 fournissant déjà noms et géoloc.

#### S19. HowTheyVote.eu — votes des eurodéputés français
- **URLs testées** : `https://howtheyvote.eu/api/votes` (200 ; 2 421 votes, positions des **81 eurodéputés FR**) + dumps hebdo GitHub `HowTheyVote/data` (release 15/08/2026, export 68,6 Mo) (09).
- **Licence** : **ODbL + DbCL — attribution obligatoire**. **Modules** : Élus & Institutions (volet européen) — v2.

### Groupe C — Exploitables directement, annuelles / par scrutin / statiques

#### S20. PLF 2026 — Budget vert (seule donnée structurée 2026 par action)
- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plf-2026-budget-vert/records?limit=2` (200) ; **1 816 lignes, 46 missions** × programme × action, avec `execution_2024_cp` (l'exécution réelle par action la plus fine disponible), LFI 2025, PLF 2026, cotations environnementales ; modifié 13/11/2025, annuel (01).
- **Licence** : LO v2.0. **Piège majeur** : montants 2026 = **PLF déposé, PAS la LFI promulguée le 19/02/2026** → mention « PLF » obligatoire à l'affichage (01).
- **Modules** : Dépenses de l'État (treemap mission→action, budget vert), Accueil (top missions).

#### S21. PLF 2025 — dépenses par destination et nature
- **URL testée** : `…/plf25-depenses-2025-selon-destination/records?limit=2` (200) ; 2 404 lignes ministère→mission→programme→action→sous-action × titre, AE et CP ; famille complète maj 11/10/2024 ; **aucun équivalent PLF/LFI 2026** (vérifié au catalogue) ; les crédits votés s'arrêtent à LFI 2023 (01).
- **Licence** : LO v2.0. **Modules** : Dépenses de l'État (navigation fine du budget).

#### S22. Balances des comptes de l'État (CGE) 2016-2025
- **URL testée** : `…/balances_des_comptes_etat/records?limit=2` (200) ; **517 489 lignes** compte × programme × année, 2016→**2025** (le CGE 2025 est publié) (01).
- **Licence** : LO v2.0. **Piège** : comptabilité générale ≠ budgétaire — ne pas additionner avec S13 (01). **Modules** : Dépenses de l'État (vue patrimoniale) — v2.

#### S23. Subventions de l'État aux associations (jaune PLF 2025, versements 2023)
- **URL testée** : `…/plf25-donnees-de-l-annexe-jaune-effort-financier-de-l-etat-en-faveur-des-associations/records?limit=2` (200) ; **112 722 lignes** — une par subvention (SIREN, montant, programme, commune) ; millésime = versements **2023**, publié décembre 2024 → décalage ~2 ans ; **le jaune PLF 2026 n'est pas publié en données** (01).
- **Licence** : LO v2.0. **Pièges** : qualité brute Chorus (SIREN « NR », retours ligne, U+00A0) ; « associations » au sens large (01).
- **Modules** : Dépenses de l'État (« qui l'État subventionne »).

#### S24. Performance de la dépense — RAP 2025
- **URL testée** : `…/performance-de-la-depense-rap-2025/records?limit=1` (200 ; 2 140 lignes, maj **04/06/2026**, exécutions 2023-2025 vs cibles) (01).
- **Licence** : LO v2.0. **Piège** : valeurs en texte avec espaces insécables (01). **Modules** : Dépenses de l'État (atteinte des cibles) — v2.

#### S25. CNCCFP — comptes des partis politiques (exercice 2024 publié le 10/02/2026)
- **URL testée** : `https://static.data.gouv.fr/resources/comptes-des-partis-et-groupements-politiques/20260210-110641/comptes-partis-exercice-2024.csv` (200, 298 Ko, **575 partis × 166 colonnes**) ; CSV homogènes 2021-2024 ; l'exercice N est publié début N+2 (04).
- **Licence** : LO. **Contenu décisif** : dons, cotisations, **aide publique (colonnes 103-105)**, flux inter-partis, par parti et par an (04).
- **Pièges** : formats hétérogènes avant 2021 ; l'avis CNCCFP listant les partis privés d'aide = PDF JO seulement (04).
- **Modules** : Financement de la vie politique, Alertes.

#### S26. Résultats électoraux agrégés (MI/data.gouv.fr)
- **URL testée** : dataset `https://www.data.gouv.fr/datasets/6481e741d4cf002ec0efec9d/` (maj 07/07/2026) ; Parquet « généraux » 70,9 Mo / « par candidat » 161,3 Mo ; via API tabulaire : législatives 2024 = 70 102 BV ; **municipales 2026 T1/T2 publiées** (70 003 / 17 398 BV) (09).
- **Licence** : lov2. **Pièges** : `code_circonscription` vide sur les législatives 2024 ; `nuance` vide pour les petites communes ; préférer le Parquet (09).
- **Modules** : Élus & Institutions (résultats, contexte électoral) — v2.

#### S27. Référentiel géographique et population
- **geo.api.gouv.fr** (testé 200, sans auth) : ~35 000 communes avec centroïde + population en **un appel de 4,7 Mo** ; contours unitaires GeoJSON ; pas de population départementale (09).
- **france-geojson** (gregoiredavid, raw.githubusercontent.com) : `departements-version-simplifiee.geojson` **569 Ko** → fond de carte SVG retenu ; millésime 2018 (sans conséquence départements/régions) ; contours Etalab millésimés 2025 en complément (`etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/departements-100m.geojson`, 302 → S3, 2,75 Mo) (09).
- **Populations de référence 2023** (INSEE, en vigueur au 01/01/2026, décret n° 2025-1362) : `https://www.insee.fr/fr/statistiques/fichier/8680726/ensemble.zip` (200, 1 Mo, 34 900 communes + départements + régions ; utiliser **PMUN** pour les €/habitant) (09).
- **Licences** : LO/INSEE. **Modules** : cartes et ratios, transverse.

#### S28. Balances comptables des collectivités (DGFiP, data.economie)
- **URL testée** : `…/balances-comptables-des-communes-en-2025/records` (200) ; 2025 = **6 963 040 lignes** (balances **provisoires** de juillet, maj 13/07/2026, définitives en décembre) ; un dataset par année 2010→2025 ; grain budget × compte (06).
- **Licence** : LO v2.0. **Pièges majeurs** : `insee` tronqué aux 3 derniers caractères → **joindre par `siren` uniquement** ; budgets annexes mêlés ; export intégral ≈ **950 Mo/an** (mesuré : ~143 o/ligne) → requêtes ciblées par siren seulement (06).
- **Modules** : Finances locales (drill-down comptable à la demande) — v2.

### Groupe D — Exploitables avec effort (retenues)

#### S29. CNCCFP — comptes de campagne (dernier scrutin publié : législatives 2024)
- **URL testée** : `https://static.data.gouv.fr/resources/elections-legislatives-generales-des-30-juin-et-7-juillet-2024/20250729-150633/comptes-campagne-legislatives-2024.csv` (200, 1,14 Mo, **4 010 candidats**, maj 29/07/2025) ; dépenses détaillées, remboursement État, **décision CNCCFP (A/AR/R)** (04).
- **Pièges MAJEURS constatés** : **cp1252 + CRLF + 6 lignes quasi vides avant l'en-tête** → `skiprows=6, sep=';', encoding='cp1252'` ; pas de dons nominatifs (interdit) ; **municipales 2026 : aucun dataset au 19/08/2026**, publication attendue fin 2026/2027 (04).
- **Modules** : Financement de la vie politique, Alertes.

#### S30. DGFiP — Situation mensuelle de l'État (SME, PDF)
- **URL testée** : dataset `situation-mensuelle-de-l-etat` (211 documents, maj 14/08/2026) mais **PDF bloqué : HTTP 403 Cloudflare** même avec User-Agent navigateur (01).
- **Intérêt unique** : seule publication **mensuelle au niveau mission/programme** (juin 2026 disponible). **Effort** : récupération manuelle/headless + parsing PDF (01). **Modules** : Dépenses de l'État (détail missions mensuel) — v2.

#### S31. Corpus PDF « train de vie » (chiffres officiels → constantes sourcées)
Tous téléchargés/dépouillés le 19/08/2026 (05-frais-indemnites.md) :
- **Cour des comptes, Élysée exercice 2024** (publié 18/07/2025, 74 p., curl 200) : charges 123,3 M€, **94 déplacements présidentiels = 20,1 M€**, dotation 122 563 852 € ; **l'exercice 2025 n'est pas paru au 19/08/2026** ; le seul audit annuel détaillé d'un train de vie au sommet de l'État.
- **Rapport du déontologue AN** (13/05/2026, 80 p., curl 200) : 100 % des députés contrôlés (exercice 2024), **84 demandes de reversement pour 276 335 €**, anonymat absolu.
- **Comité de déontologie du Sénat 2024-2025** (45 p., curl 200) : 362 sénateurs contrôlés, 149 685 justificatifs JULIA, **frais déclarés 2024 : 29,9 M€** ; aucun montant de reversement publié.
- **Jaune PLF 2026 « cabinets ministériels »** (curl 200, 11 p.) : 521 membres + 2 220 support = 2 741 personnes, ISP totale 27 361 062 € ; **les rémunérations par cabinet ont disparu depuis le jaune PLF 2024** (dernières données : 2022, moyenne 8 495 €/mois) — recul documenté.
- **Barème DGCL indemnités élus locaux au 01/01/2026** (PDF collectivites-locales.gouv.fr, curl 200) : maire < 500 hab 1 155,06 €, ≥ 100 000 hab 5 960,26 €, IB 1027 = 4 110,52 €.
- **Barèmes parlementaires et gouvernement** (fiches AN/Sénat WebFetch OK ; décret 2012-983 en 403 anti-bot, montants recalculés par la presse — à marquer « calculé ») : indemnité parlementaire brute 7 637,39 € ; **DFP députés 7 238,04 €/mois (créée au 01/01/2026)** ; AFM sénateurs 6 600 € ; mission « Pouvoirs publics » LFI 2026 = 1 140 179 221 € (AN 607,6 M€, Sénat 353,5 M€, Élysée 122,6 M€).
- **Rapport annuel HATVP 2025 (pantouflage)** : **641 avis de mobilité public-privé** rendus (contrôle des reconversions, art. 23 loi 2013-907) — chiffres agrégés à intégrer aux constantes sourcées ; **aucun export en masse des avis** (publication individuelle sur hatvp.fr, à confirmer en Phase 1) → volet documentaire du module Élus & Institutions + veille « export open data » au même rythme que la veille RIE (08 §3.2 ; 10-critique I7).
- **SIREN « sommet de l'État » à documenter en constantes** (Présidence de la République, Assemblée nationale, Sénat) : leurs marchés sont couverts de fait par S1/S2 via filtre SIREN acheteur — requête différenciante à coût nul pour Frais & train de vie (10-critique M9).
- **Format** : PDF/HTML → intégrer comme **bloc de constantes sourcées** (bloc YAML au §9 de 05-frais-indemnites.md — ⚠ **à corriger avant usage** : la ligne `mission_pouvoirs_publics_lfi_2026: total: … ; an: …` n'est pas du YAML valide, les `;` en font une chaîne unique → passer en clés/valeurs, 10-critique M2). **Modules** : Frais & train de vie (+ volet pantouflage d'Élus & Institutions).

#### S32. Subventions versées par les collectivités (schéma SCDL — panel seulement)
- **URL testée** : `https://www.data.gouv.fr/api/1/datasets/?schema=scdl%2Fsubventions&page_size=200` (200, **53 datasets**, ~45 organisations ; ⚠ slug `scdl/subventions`, pas `scdl-subventions`) ; **aucune consolidation nationale officielle** (`consolidation_dataset_id: None`) (06).
- **Exemples frais** : Côtes-d'Armor conforme SCDL (maj 16/08/2026) ; **Paris hors schéma** : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/subventions-associations-votees-/records` (107 693 lignes, maj 28/07/2026, exercices jusqu'à 2026) (06).
- **Pièges** : obligation légale massivement inappliquée ; SIRET bénéficiaire parfois vide ; **jamais présenter comme national** (06). **Modules** : Finances locales (panel assumé) — v2.

#### S33. Comptes individuels des collectivités (DGFiP)
- **URL testée** : `…/comptes-individuels-des-communes-fichier-global-2023-2024/records` (200 ; 69 877 lignes × 252 champs, maj 01/12/2025) ; apport unique : **moyennes de strate** ; s'arrête à **2024** (06).
- **Pièges** : **montants en milliers d'euros** ; slugs incohérents (06). **Modules** : Finances locales (position dans la strate) — v2.

#### S34. TED — Tenders Electronic Daily (UE)
- **URL testée** : `POST https://api.ted.europa.eu/v3/notices/search` (200, sans clé) ; 58 379 avis FR publiés en 2026 ; largement **redondant avec BOAMP** (famille JOUE déjà incluse) ; vaut pour les eForms normalisés et la comparaison UE (02). **Modules** : Commande publique — v2.

#### S35. Autres fonds DILA (echanges.dila.gouv.fr/OPENDATA/)
- **Testés le 19/08** : LEGI (consolidé, 18/08), DOLE (dossiers législatifs, 18/08), Debats (AN 31/07 — vacances), COMPTES_DES_ASSOCIATIONS (19/08 14:29), **RefOrgaAdminEtat** (référentiel de l'organisation de l'État, flux quotidien 19/08 08:30 — utile pour la table des intitulés ministériels par période) (07).
- **Licence** : fr-lo. **Modules** : Documents/JO (extensions) — v2.

#### S36. API Légifrance via PISTE — optionnelle
- **Testé** : `POST https://oauth.piste.gouv.fr/api/oauth/token` → 400 `invalid_client` (endpoint vivant, OAuth2 client_credentials) ; **création de compte + CGU = one-shot humain ~10-15 min**, ensuite tout est automatisable ; **non nécessaire** au module Documents (les dumps DILA couvrent le besoin) (07).

#### S37. Décret annuel d'aide publique aux partis
- Décret n° 2026-149 du 03/03/2026 : **64 262 871,05 €** répartis en 2 fractions ; **Légifrance en 403 curl** (anti-bot), tableau dans le corps du décret, pas de CSV ; l'essentiel du besoin est couvert par les colonnes 103-104 de S25 (04). **Modules** : Financement de la vie politique — v2.

*Ajouts du 19/08/2026 issus du contre-audit `10-critique-completude.md` (placés en fin de groupe pour ne pas renuméroter le catalogue) :*

#### S38. Avis et conseils de la CADA (ajout post-critique I1)
- **URL testée** (10-critique, appels n° 1 et 6, HTTP 200) : `https://www.data.gouv.fr/api/1/datasets/avis-et-conseils-de-la-cada/` — dataset « Avis et conseils de la CADA » (org. CADA) ; ressource « Ensemble consolidé des avis et conseils de la CADA » = **CSV 198,4 Mo (198 398 592 o), dernière modification 14/08/2026**, plus lots mensuels/trimestriels 2022-2024.
- **Licence** : fr-lo. **Intérêt** : sens des avis **par administration mise en cause** (qui refuse quoi) — alimente directement la « carte des verrous juridiques » du module Frais & train de vie et le lien avec Ma Dada (08 §1.2).
- **Pièges** : volumétrie à **échantillonner avant toute promesse** (CSV de 198 Mo). **Modules** : Frais & train de vie (boîte noire, carte des verrous) — **v2** (aucun module v1 n'en dépend).
- **Évaluation du 20/08/2026 (CSV consolidé téléchargé et mesuré en entier)** : 60 941 lignes (57 385 avis, 3 553 conseils, 3 sanctions), 1984→2024 ; **89 % du fichier est du texte intégral** (176,6 Mio) qui ne sera jamais ingéré (poids et prudence RGPD — les demandeurs sont anonymisés à la source, mais des noms de responsables publics subsistent dans les motifs). Piège décisif : le jeu est « modifié le 14/08/2026 » mais la **dernière séance date du 18/04/2024** — 28 mois de retard de versement, millésimes 2023-2024 vraisemblablement incomplets, à afficher tel quel. **Verdict : à ingérer en v2, en agrégats seulement** (sens × administration × année, +3 à 6 Mo en base).

#### S39. Jaune « opérateurs de l'État » PLF 2026 (ajout post-critique I4)
- **Vérifié le 19/08/2026** (10-critique, appels n° 2 et 3) : dataset « PLF 2026, jaune opérateurs de l'État, liste des opérateurs et catégories » (data.gouv.fr, id `69665c766034b48d897c47be`), maj **13/01/2026** — **seule photographie 2026 du paysage des agences/opérateurs** (liste et catégories ; **pas les crédits par opérateur**). Retenu plutôt qu'écarté : le débat public 2026 sur les agences de l'État en fait un référentiel naturel.
- **Licence** : **confirmée le 20/08/2026** — la réponse API du dataset porte `"license": "lov2"` (Licence Ouverte 2.0).
- **Modules** : Dépenses de l'État (référentiel des opérateurs, complète l'encart de périmètre) — **v2**.
- **Évaluation du 20/08/2026** : le **volet budgétaire n'existe pas en données structurées** — recherche data.gouv (9 résultats) et énumération des 606 jeux de data.economie : le dernier jeu financier des opérateurs est **PLF 2014** (166 lignes, grain programme et non opérateur × SCSP, figé en 2018) ; le jeu PLF 2019 répond 200 mais contient **0 enregistrement** (`total_count: 0` constaté) ; les jaunes PDF sont derrière l'anti-bot de budget.gouv.fr (groupe E). **Verdict : ne pas ingérer le volet budgétaire (il n'existe pas)** ; seule la liste 2026 (431 lignes, cp1252, aucun montant, 70 826 octets) peut servir de référentiel à coût quasi nul, adossée à un pipeline existant plutôt qu'un pipeline dédié ; re-vérifier chaque janvier si un jaune structuré paraît.

#### S40. Registre de transparence de l'Union européenne (évalué le 20/08/2026)
- **URL testée** (HTTP 200) : `https://data.europa.eu/api/hub/search/datasets/transparency-register` ; export XML intégral téléchargé et mesuré : **115 010 602 octets**, `<exportDate>` du 19/08/2026 (quotidien réel — la métadonnée DCAT, périmée de 2 ans, ne fait pas foi).
- **Licence** : la réponse API référence la **décision 2011/833/UE** (`COM_REUSE`, réutilisation y compris commerciale avec mention de source, sans clause de partage à l'identique) — compatible avec la promesse Licence Ouverte 2.0 des agrégats. Une note antérieure annonçait « CC BY 4.0 » : non confirmé par l'API.
- **Contenu mesuré** : 17 711 organisations inscrites dont **1 654 à siège en France** ; coûts de lobbying en fourchettes ; **aucune balise SIREN ni TVA** (77 balises inventoriées) → aucun rapprochement automatique possible avec le répertoire HATVP (S14), constat définitif.
- **Pièges éditoriaux (bloquants)** : lobbying UE et lobbying France sont **deux registres, deux cadres juridiques** — blocs jamais fusionnés, montants jamais comparés ; à titre d'illustration du contraste, 141 entités HATVP (sur 4 068) déclarent un niveau d'action « Européen » quand 1 654 organisations françaises sont inscrites à Bruxelles — **deux compteurs séparés, jamais un ratio**. Ne jamais ingérer le fichier des 8 927 accrédités (personnes physiques) ; exclure les 235 « Self-employed individuals » de toute restitution nominative. Parseur tolérant XML 1.1 ; fraîcheur lue dans `<exportDate>`.
- **Verdict : à ingérer en v2, périmètre minimal cloisonné** (organisations seulement, +2 à 5 Mo en base). **Modules** : Lobbying.

### Groupe E — Sources écartées (raison prouvée le 19/08/2026)

| Source écartée | Raison constatée | Rapport |
|---|---|---|
| Détail des paiements Chorus / Data-État | Aucun dataset « chorus » en open data (search = 0) ; Data-État « réservé aux agents autorisés » | 01 |
| LFI 2026 en données structurées | N'existe pas (catalogues vérifiés : seul le budget vert PLF 2026) ; crédits votés arrêtés à LFI 2023 | 01 |
| data.budget.gouv.fr / datafin / transparence.gouv.fr / dataviz.budget.gouv.fr | **NXDOMAIN** — n'existent pas | 01, 08 |
| budget.gouv.fr, economie.gouv.fr (PDF), Légifrance (HTML) en collecte | Anti-bots Incapsula/Cloudflare/Datadome (403 constatés) ; liens sortants seulement | 01, 07, 08 |
| Marchés PLACE 2013-2017 (data.economie) | Série close : dernière notification 30/12/2017 malgré `modified: 2026` | 01 |
| PLACE (consultations État) | Pas d'API publique ; données via BOAMP/DECP/APProch | 02 |
| `decp_augmente` | Marqué **[Obsolète]** par le producteur | 02, 08 |
| API Data.Subvention | `access_type: restricted` (agents publics) | 01 |
| NosDéputés.fr / NosSénateurs.fr | Figé au 09/06/2024 (`enmandat` = 0) / arrêté (archive 2023) — historique seulement | 03, 08 |
| HATVP répertoire de l'influence étrangère (RIE) | Ouvert le 01/10/2025 mais **aucun export open data découvrable** (404 sur toutes les URLs candidates) — à re-tester trimestriellement | 04 |
| Notes de frais parlementaires | **Non publiées ET non communicables** (ord. 58-1100, CE mars 2025, refus des deux chambres du 11/06/2026) | 05 |
| Frais de représentation et voyages des ministres | Jamais publiés ; gouvernement se déclarant incapable de les détailler (QE, demandes CADA sans effet) | 01, 05 |
| Indemnités locales réellement versées | État récapitulatif annuel (art. L. 2123-24-1-1 CGCT) jamais centralisé ni mis en ligne | 05 |
| Rémunérations des cabinets ministériels post-2022 | Disparues des jaunes depuis PLF 2024 | 05 |
| DGF sur data.gouv (DGCL) | Gelé depuis le 10/01/2020 → remplacé par OFGL | 06 |
| API Sirene INSEE | 401 sans clé ; inutile (S10 + S18 couvrent tout) | 09 |
| AMO50 (AN) | Figé au 11/07/2024 | 03 |
| api.gouv.fr | Décommissionné 2025 (redirigé vers data.gouv.fr/dataservices) | 08 |

### Requêtes prêtes à l'emploi (toutes testées HTTP 200 le 19/08/2026)

```bash
# Dépenses de l'État — export mensuel complet (26 lignes) [S13] (01)
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/situations-mensuelles-budgetaires-series-longues/exports/csv"

# Marchés notifiés ces 30 jours, géolocalisés pour la carte — 24 554 lignes [S1] (02)
# ⚠ API tabulaire en bêta (08 §2.1) : raccourci seulement — le mode nominal est le parquet local + DuckDB (P3)
curl "https://tabular-api.data.gouv.fr/api/resources/22847056-61df-452d-837d-8b8ceadbfc52/data/?dateNotification__greater=2026-07-20&donneesActuelles__exact=true&page_size=200"

# Bulk quotidien recommandé — decp.parquet 243 Mo, build du jour [S1] (02)
curl -L -o decp.parquet "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"

# Appels d'offres EN COURS (clôture future) — 8 988 résultats [S2] (02)
curl --compressed "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records?where=datelimitereponse%3Edate'2026-08-19'%20AND%20nature%3D'APPEL_OFFRE'&order_by=datelimitereponse%20asc&limit=20"

# Marchés officiels DAJ 30 jours (6 657) + agrégat carte group_by [S8] (02)
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp-2022-marches-valides/records?where=datenotification%3E%3Ddate'2026-07-20'&order_by=datenotification%20desc&limit=100"
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp-2022-marches-valides/records?where=datenotification%3E%3Ddate'2026-07-20'&group_by=lieuexecution_code&select=lieuexecution_code,count(*)%20as%20nb,sum(montant)%20as%20total&order_by=total%20desc"

# Projets d'achats à venir — 4 060 résultats [S9] (02)
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/records?where=date_previsionnelle_de_publication%3E%3Ddate'2026-08-19'&order_by=date_previsionnelle_de_publication%20asc&limit=20"

# JO du jour (index à parser, puis tarball nocturne ~00h30) [S3] (07)
curl "https://echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/"

# HATVP : dossiers déclaratifs (hebdo) + lobbying CSV (quotidien) [S14, S4] (04)
curl -O "https://www.hatvp.fr/livraison/opendata/liste.csv"
curl -O "https://www.hatvp.fr/agora/opendata/csv/Vues_Separees_CSV.zip"

# AN : députés/mandats/organes + scrutins nominaux (quotidien) [S5] (03)
curl -O "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip"
curl -O "https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip"

# Sénat : sénateurs (quotidien, ISO-8859-1) [S6] (03)
curl -O "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv"

# OFGL : dépenses de fonctionnement, toutes communes 2025 (34 778 lignes, 1,9 Mo) [S16] (06)
curl "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-communes/exports/csv?where=year(exer)%3D2025%20and%20agregat%3D%22D%C3%A9penses%20de%20fonctionnement%22%20and%20type_de_budget%3D%22Budget%20principal%22&select=com_code,com_name,dep_code,montant,euros_par_habitant,ptot"

# CNCCFP : comptes des partis, exercice 2024 [S25] (04)
# ⚠ URL de millésime static.data.gouv.fr : re-résoudre via l'API data.gouv avant chaque ingestion (convention §0.3)
curl -O "https://static.data.gouv.fr/resources/comptes-des-partis-et-groupements-politiques/20260210-110641/comptes-partis-exercice-2024.csv"

# Référentiels : communes + population + centroïdes (4,7 Mo) ; résolution SIRET [S27, S10] (09)
curl "https://geo.api.gouv.fr/communes?fields=nom,code,centre,population,codeDepartement"
curl "https://recherche-entreprises.api.gouv.fr/search?q=21750001600019"
```

---

## 2. Mapping module → sources

> **Encart de périmètre « argent public » (obligatoire, affiché sur l'Accueil et dans API & Données)** : le dashboard couvre le **budget général de l'État**, le **Parlement et la vie politique** (élus, lobbying, financement), la **commande publique** et les **finances locales**. Hors champ, et dit tel quel dans l'UI : les **administrations de sécurité sociale (~600 Md€, premier poste de la dépense publique)**, la dépense propre des **opérateurs de l'État** (seuls leurs crédits budgétaires apparaissent via S20/S21 ; référentiel S39 en v2) et les **entreprises publiques**. Tout compteur global porte la mention « budget général de l'État » — jamais « la dépense publique » (10-critique I8).

### Accueil synthétique
- **Sources** : S13 (compteur dépenses État), S1 (flux marchés + carte 30 j), S2 (nb d'AO en cours), S3 (derniers textes JO), S14 (compteur d'alertes HATVP), S17/S4 (bandeau de stats), S20 (top missions).
- **Fraîcheur affichable** : « Dépenses de l'État : données au 30/06/2026 (publication mensuelle DGFiP) » (01) · « Marchés publics : mise à jour quotidienne, notifications jusqu'à la veille — **en cours de consolidation** (latence légale de publication jusqu'à 2 mois) » (02) · « Journal officiel du 19/08/2026 » (07) · « Déclarations HATVP : mise à jour hebdomadaire » (04). La mention « en cours de consolidation » accompagne le flux marchés **partout où il apparaît** (10-critique M3).
- **Contenu concret** : compteur « dépenses de l'État depuis le 1er janvier » (cumul mensuel, ex. réel : 195,0 Md€ de dépenses nettes du BG au 31/05/2026, 01) avec variation vs même période 2025 ; donut par grands postes (titres, S13) ; top missions (S20, annuel, mention PLF) ; carte de France des marchés notifiés sur 30 jours (S1, lat/lng natives) ; flux « derniers marchés notifiés » (J-1) et « derniers textes au JO » (jour même) ; « X appels d'offres en cours » ; bandeau : marchés notifiés/12 mois, ~500 000 mandats d'élus (S17), 6 829 lobbyistes enregistrés (S4), 12 930 dossiers déclaratifs HATVP (S14).

### Dépenses de l'État
- **Sources** : S13 (mensuel), S20 + S21 (structure mission→action), S23 (subventions aux associations), S24 (performance, v2), S22 (patrimonial, v2), S30 (missions mensuelles PDF, v2), S39 (référentiel des opérateurs, v2).
- **Fraîcheur affichable** : « Exécution mensuelle : données au 30/06/2026, ~6 semaines de décalage » (01) · « Structure du budget : PLF 2026 (déposé oct. 2025) et exécution 2024 » (01) · « Subventions aux associations : versements 2023 (dernier millésime publié) » (01).
- **Contenu concret** : courbes 2013-2026 dépenses/recettes/solde, N vs N-1 par titre ; treemap mission → programme → action (comparateur exéc. 2024 / LFI 2025 / PLF 2026 + cotation budget vert) ; recherche parmi 112 722 subventions (SIREN, programme, commune). **Avertissements obligatoires** : PLF ≠ LFI 2026 (jamais publiée en données) ; aucune donnée de paiement en temps réel n'existe (01).

### Commande publique & appels d'offres
- **Sources** : S1 (attributions + carte + fiches), S2 (AO en cours), S8 (chiffres officiels DAJ, contrôle), S9 (marchés à venir), S34 (UE, v2).
- **Fraîcheur affichable** : « Attributions : consolidation quotidienne (dernière notification : la veille) ; publication légale sous 2 mois — données en cours de consolidation » (02) · « Appels d'offres : annonces du jour même » (02) · « Projets d'achats : mise à jour continue » (02).
- **Contenu concret** : 8 988 AO ouverts triés par date limite ; flux et carte des attributions (montants rationalisés, écrêtage p99) ; fiches acheteur/titulaire (PME/ETI/GE, NAF, flux géographiques) ; pipeline amont APProch (4 060 projets à venir) ; contexte des seuils 2026 (dispense 40 k€ → **60 k€ au 01/04/2026**, décret 2025-1386 ; BOAMP/JAL ≥ 90 k€ : le bas du spectre est invisible, 02).

### Élus & Institutions
- **Sources** : S5 (députés, votes nominaux, questions), S6 (sénateurs), S7 (scores Datan, crédités), S17 (RNE : tous les élus locaux), S14/S15 (déclarations HATVP), S10/S11 (fiches institutions), S26/S19 (élections, Europe, v2).
- **Fraîcheur affichable** : « Données parlementaires : mises à jour quotidiennes (open data AN/Sénat) » (03) · « Répertoire des élus : 11/08/2026, post-municipales 2026 » (04) · « Dernier scrutin AN : n° 8434 du 21/07/2026 (vacances parlementaires) » (03).
- **Contenu concret** : fiches députés (mandats, groupe, commission, déports, lien direct `uri_hatvp`, scores de participation/loyauté Datan) ; votes nominaux des 8 434 scrutins ; sénateurs et scrutins Sénat (v2 via Dosleg) ; annuaire des ~500 000 mandats locaux avec démographie (âge, sexe, CSP) ; questions au gouvernement et questions écrites — **les délais de réponse par ministère ne se mesurent que sur les questions écrites** (les QAG ont réponse immédiate, 03 §2.4 ; 10-critique M4) ; **volet documentaire pantouflage** : chiffres agrégés du rapport annuel HATVP (641 avis de mobilité public-privé en 2025, constantes cf. S31), pas d'export open data des avis — veille active (10-critique I7). **Architecture** : paramètre `legislature`, renouvellement Sénat 27/09/2026, table des intitulés ministériels par période (03).

### Lobbying
- **Sources** : S4 (AGORA quotidien) ; à surveiller : RIE (aucun open data au 19/08/2026, 04).
- **Fraîcheur affichable** : « Répertoire des représentants d'intérêts : mise à jour quotidienne (19/08/2026) ; **dépenses et activités déclarées par exercice annuel** » (04) — la « pression par ministère » repose sur des données à maille annuelle, à dire dans l'UI (10-critique M3).
- **Contenu concret** : 6 829 entités, 118 516 activités ; pression par ministère/AAI ciblé (table 13 × exercices) ; top budgets de lobbying (fourchettes) ; activités par type de décision ; croisement différenciant à terme : calendrier d'un texte × entrées au répertoire (08, créneau n° 1).

### Financement de la vie politique
- **Sources** : S25 (comptes des partis 2021-2024), S29 (comptes de campagne par scrutin), S37 (décret d'aide publique, v2).
- **Fraîcheur affichable** : « Comptes des partis : exercice 2024 (publié le 10/02/2026 — dernier possible, dépôt légal N+1, publication N+2) » (04) · « Comptes de campagne : législatives 2024 (municipales 2026 attendues fin 2026/2027) » (04).
- **Contenu concret** : recettes des 575 partis (dons, cotisations, aide publique 64,26 M€, flux inter-partis) ; dépendance à l'aide publique ; coût par voix et remboursements des 4 010 candidats aux législatives 2024 ; comptes rejetés/réformés.

### Frais & train de vie
- **Sources** : S31 (constantes sourcées + rapports annuels) ; volet « boîte noire » documentaire (05) ; S38 (avis CADA — carte des verrous, v2).
- **Fraîcheur affichable** : « Barèmes en vigueur au 01/01/2026 » · « Contrôles des frais de mandat : exercice 2024 (rapports mai 2026) » · « Élysée : exercice 2024 audité (Cour des comptes, juillet 2025) — exercice 2025 non paru » (05).
- **Contenu concret** : « combien gagnent-ils » (indemnité parlementaire 7 637,39 € brut, DFP 7 238,04 €, AFM Sénat 6 600 €, PM ≈ 16 038 € « calculé ») ; résultats agrégés des contrôles (84 députés / 276 335 € reversés ; 29,9 M€ de frais déclarés au Sénat) ; sous-module Élysée (coût par déplacement : 94 déplacements = 20,1 M€) ; **marchés du sommet de l'État** (Élysée/AN/Sénat via filtre SIREN acheteur sur S1/S2 — requête à coût nul, SIREN documentés en constantes S31, 10-critique M9) ; coût des institutions (mission Pouvoirs publics 1,14 Md€) ; chronologie IRFM → DFP ; **carte des verrous juridiques** (Parlement non communicable vs élus locaux communicables — CE 08/02/2023 ; enrichie en v2 par les avis CADA S38) et compteur des demandes citoyennes refusées (05).
- **Boîte noire — arbitrages post-critique (documentaire assumé, aucun pipeline)** : **aides publiques aux entreprises** : ~211 Md€/an « ni lisibles, ni conditionnées, ni évaluées » (rapport Sénat 08/07/2025) et **aucune donnée consolidée** (vérifié le 19/08 : 0 dataset) → alerte documentaire + veille active ; micro-module v2 possible sur les briques partielles (CIR via jaune, exonérations) (I2). **Hautes rémunérations de la fonction publique** : obligation « 10 plus hautes rémunérations » (art. 37, loi TFP du 06/08/2019) éclatée en **25 datasets épars sans consolidation nationale** (vérifié) → patron S32 : panel assumé en v2, **jamais « national »**, + ligne documentaire « obligation légale massivement inappliquée/éclatée » (I3). **Collaborateurs parlementaires et emplois familiaux** (loi 2017) : **0 dataset** (vérifié) ; listes HTML par élu sur les sites AN/Sénat → extraction coûteuse, v2 ou documentaire (I10). **Comptes des groupes politiques des assemblées** : **0 dataset** (vérifié) ; PDF probables sur les sites AN/Sénat à vérifier en Phase 1 → intégrer aux constantes S31, sinon manque assumé ici (I10).

### Finances locales
- **Sources** : S16 (OFGL : comptes + dotations), S27 (fonds de carte + population), S28 (balances, drill-down v2), S33 (strates, v2), S32 (subventions locales, panel v2).
- **Fraîcheur affichable** : « Comptes 2025 provisoires (chargés juillet 2026 ; ~97 communes manquantes jusqu'en décembre 2026) » (06) · « Dotations de l'État : exercice 2026 » (06).
- **Contenu concret** : carte départementale en 1 requête `group_by` (101 départements) ; carte communale pré-calculée (34 778 communes, €/habitant natif) ; fiches collectivité (séries 2012/2018→2025, DGF 2018-2026, comparaison de strate) ; drill-down comptable par SIREN à la demande. **Jamais** de vue « subventions France entière » (aucune consolidation nationale SCDL, 06).

### Documents/JO
- **Sources** : S3 (JORFSIMPLE quotidien), S35 (LEGI/DOLE/Debats/RefOrga, v2), S36 (recherche Légifrance, optionnel), S12 (BODACC/associations, v2).
- **Fraîcheur affichable** : « Journal officiel du jour (disponible chaque nuit vers 00h30) » (07).
- **Contenu concret** : flux quotidien des textes (83 textes le 19/08 dont 5 lois) ; filtre **nominations** (38 textes « nominat » le 19/08) ; filtres lois/décrets/budget par rubrique du sommaire, nature et ministère ; chaque item lié vers `https://www.legifrance.gouv.fr/jorf/id/{ID}` (les liens navigateurs fonctionnent, seule la collecte est bloquée, 07).

### Alertes transparence
- **Sources** : S14 + S17 (retards déclaratifs), S4 (défauts lobbying), S1/S8 (marchés), S25/S29 (financement politique), toutes (moniteur de fraîcheur). Détail au § 4.
- **Fraîcheur affichable** : « Alertes recalculées à chaque mise à jour des sources (HATVP : hebdomadaire ; lobbying et marchés : quotidien) ».

### API & Données
- **Sources** : les métadonnées de toutes les autres + ce document.
- **Contenu concret** : catalogue public des sources avec **fraîcheur mesurée** (dernière donnée réellement ingérée, testée automatiquement — le « moniteur de santé des sources » qui n'existe nulle part, 08 leçon n° 3 et créneau n° 2) ; licences et attributions (LO 2.0, ODbL HowTheyVote, crédit Datan/consolidation DECP) ; ré-export des agrégats calculés en Licence Ouverte ; documentation des règles d'alerte et de leurs bases légales ; reprise de l'**encart de périmètre « argent public »** (en tête du § 2, 10-critique I8).

---

## 3. Promesses de la maquette intenables — et leur reformulation honnête

La maquette de référence est une fiction marketing sur plusieurs points. Voici la liste explicite, chaque impossibilité étant **prouvée par un rapport**, et la reformulation retenue.

| # | Promesse de la maquette | Pourquoi c'est intenable (preuve) | Reformulation honnête retenue |
|---|---|---|---|
| 1 | **Gros compteur « dépenses aujourd'hui » + variation vs veille** | Il n'existe **aucune donnée ouverte de paiement en temps réel** (aucun dataset Chorus, search = 0 ; Data-État réservé aux agents). Meilleure fraîcheur réelle : **mensuelle, ~5-7 semaines de décalage** (exécution au 30/06/2026 vue le 19/08) (01-budget-etat.md §1, §11) | Compteur « L'État a dépensé X Md€ depuis le 1er janvier » sur données mensuelles DGFiP, badge « données au 30/06/2026 », **variation vs même période 2025** (pas vs veille) |
| 2 | **Flux « dernières dépenses en direct » horodaté à la minute** | Même absence de paiements temps réel (01 §11) ; les flux quotidiens réels sont contractuels (marchés notifiés J-1, latence légale de publication jusqu'à 2 mois, 02 §7) ou normatifs (JO à 00h30, 07 §1.3) | Deux flux réels et datés : « **Derniers marchés publics notifiés** » (quotidien, J-1, mention « en cours de consolidation ») et « **Derniers textes au Journal officiel** » (jour même) |
| 3 | **Module « Notes de frais » en flux** | **Aucune note de frais du pouvoir national n'est publiée ni même communicable** : Parlement hors CADA (ord. 58-1100, confirmé CE mars 2025), refus explicites des deux chambres le 11/06/2026 ; frais de représentation des ministres jamais publiés (05-frais-indemnites.md §2.4, §4.3) | Module « **Frais & train de vie** » : barèmes exacts 2026, enveloppes (DFP/AFM), résultats agrégés des contrôles, sous-module Élysée audité (le seul détaillé), et la **« boîte noire »** documentant ce qui est caché et pourquoi — l'opacité elle-même est une information |
| 4 | **Top 5 ministères « aujourd'hui » + tableau par ministère avec évolution en continu** | Le niveau **mission/programme mensuel n'existe qu'en PDF** anti-bot (SME, 403 Cloudflare) ; l'API mensuelle n'a que 26 lignes par grands titres (01 §1, §8, §11) | v1 : répartition **mensuelle par nature de dépense** (titres) + répartition **annuelle par mission** (PLF 2026/exéc. 2024, mention « PLF ») ; v2 : missions mensuelles via parsing des PDF SME |
| 5 | **Carte de France à points lumineux des « dépenses en direct »** | Les dépenses de l'État ne sont **pas géolocalisées** en open data (Data-État restreint, 01 §11) ; en revanche les **marchés publics le sont nativement** (lat/lng acheteur et titulaire, 02 §1) et les finances locales aussi (06) | Carte réelle des **marchés publics notifiés sur 30 jours** (24 554 lignes constatées) + carte des **finances locales en €/habitant** — libellées comme telles |
| 6 | KPI jour/semaine/mois/année | Pas de série quotidienne/hebdomadaire de dépenses (01) | KPI mois/trimestre/année (SMB) ; les KPI « du jour » sont réservés aux flux qui le sont vraiment : textes au JO, AO clôturant aujourd'hui, marchés notifiés la veille |
| 7 | Bandeau « transactions » | Les DECP sont des **engagements contractuels (montants max), pas des paiements** (01 §7, 02 §8) | Libellé exact : « marchés notifiés », montants rationalisés, jamais « transactions » ni « dépensé » |
| 8 | Horodatage « à la minute » du flux | Publication par lots (JO : 1 lot nocturne ; DECP : builds quotidiens ; HATVP : hebdo) (07, 02, 04) | Horodater **au jour de publication de la source** et afficher la latence connue de chaque flux |
| 9 | « Notes de frais » et « Dépenses en direct » dans la navigation | cf. #1 et #3 | Navigation renommée : « Dépenses de l'État » et « Frais & train de vie » |
| 10 | « Alertes transparence » implicitement temps réel | Les sources d'alertes sont hebdomadaires (HATVP liste.csv) à quotidiennes (AGORA, DECP) (04, 02) | « Alertes recalculées à chaque mise à jour source », chacune datée |

**Promesses de la maquette parfaitement tenables** (à valoriser) : « **Appels d'offres en cours** » (BOAMP quotidien jour même, 8 988 AO ouverts, requête testée, 02) ; recherche globale sur les entités ingérées (élus, marchés, acheteurs, textes JO, lobbyistes) ; compteur d'« élus suivis » (~500 000 mandats RNE, 04) ; « alertes transparence » en tant que telles (§ 4).

---

## 4. Alertes transparence calculables

Chaque alerte ci-dessous est calculable avec les données réellement testées. Les règles et bases légales sont reprises des rapports 04, 02 et 08.

| Alerte | Règle de calcul | Source(s) | Base légale | Rapport |
|---|---|---|---|---|
| **A1. Déclaration HATVP présumée manquante ou en retard** | Retard **présumé** (libellé UI obligatoire) : `date de début de la fonction` (RNE) + 60 jours dépassée ET `statut_publication` = « En cours ». **Garde-fous** : (1) **mandats EPCI exclus ou classés à part** — pour les VP d'EPCI élus en 2026, le délai court à la transmission de la délégation de fonction à la préfecture, date absente de tout open data (2 248 dossiers `epci`) → faux positifs mécaniques sinon ; (2) jointure nom+prénom+département **sans date de naissance côté HATVP** → règle de matching documentée (normalisation accents/casse), **homonyme non tranché = non-alerte** ; (3) RNE **trimestriel** (dernier : 11/08/2026) → dates de fonction périmées jusqu'à ~3 mois. **Affichage nominatif en « constat » réservé aux 4 « Déclaration non déposée »** (constat officiel HATVP, affiché tel quel) ; le reste en **agrégats**, fiches individuelles portant toutes les réserves. État au 19/08/2026 : **1 241 « En cours », 4 « non déposées »** | S14 (liste.csv) × S17 (RNE) | Loi n° 2013-907 du 11/10/2013 (art. 4 et 11) et art. LO 135-1 du code électoral : dépôt sous 2 mois ; sanctions art. 26 : 3 ans, 45 000 €, inéligibilité | 04, 10-critique C2 |
| **A2. Défaut de déclaration lobbying** | Flags natifs `defautDeclaration=true` ou `declaration_incomplete=true` par exercice (constaté sur données réelles) | S4 (AGORA, `15_exercices.csv`) | Loi n° 2016-1691 « Sapin II » (répertoire des représentants d'intérêts) | 04 |
| **A3. Pression de lobbying sur une décision/institution** | Nb d'actions × fourchettes de dépenses agrégés par ministère/AAI visé et par type de décision | S4 (tables `13_ministeres_aai_api` × `15_exercices` × `12_decisions_concernees`) | Sapin II (publicité des activités) | 04 |
| **A4. Parti privé d'aide publique / sur-dépendant** | Partis n'ayant pas respecté leurs obligations comptables (avis CNCCFP annuel) ; ratio aide publique (col. 103-105) / total recettes. L'avis CNCCFP n'existe qu'en **PDF au JO** → **P6/S3 le détecte par NOR/titre** et déclenche un traitement manuel annuel (mitigation gratuite) | S25 (CSV) + avis CNCCFP (PDF JO, détecté via S3) | Loi n° 88-227 du 11/03/1988 (financement des partis) | 04, 10-critique M7 |
| **A5. Compte de campagne rejeté ou réformé** | Colonne décision ∈ {R, AR} par candidat ; montants réformés = écart déclaré/retenu | S29 | Contrôle CNCCFP (code électoral) | 04 |
| **A6. Marché juste sous le seuil de publicité** | Concentration anormale de marchés **fournitures/services d'un acheteur dans la bande 40-60 k€, notifiés après le 01/04/2026** (publiés en DECP mais dispensés de publicité préalable). La bande « juste sous 40 k€ » est un **angle mort structurel de la donnée** (l'obligation DECP démarre à ≥ 40 k€ HT : ces marchés ne sont pas publiés, hors sous-ensemble volontaire biaisé) — à dire en méthodo | S1 (dédupliqué `uid`) | Décret n° 2025-1386 du 29/12/2025 (seuil 60 k€) ; arrêté DECP du 22/12/2022 (obligation ≥ 40 k€) | 02, 08, 10-critique I5 |
| **A7. Attributaire récurrent** | Part d'un même titulaire dans les marchés d'un acheteur sur 12-24 mois (indicateur de vigilance, pas d'infraction — à libeller ainsi) | S1 | — (signal d'attention recommandé par l'état de l'art) | 08 |
| **A8. Avenant/modification tardive ou gonflante** | `modification_id` : modifications augmentant le montant ou la durée peu après notification | S1 (lignes de modification) | Obligation de publier les modifications (arrêté du 22/12/2022) | 02, 08 |
| **A9. Montant aberrant** | Champ natif `montant_anomalie` (+ raisons) ; écrêtage p99 pour les agrégats | S1 | — (qualité de données, à afficher en méthodo) | 02 |
| **A10. Publication DECP hors délai légal** | `datePublicationDonnees − dateNotification > 2 mois` par acheteur | S1/S8 | Arrêté du 22/12/2022 : publication sous 2 mois après notification | 02 |
| **A11. Moniteur de fraîcheur des sources (méta-alerte)** | Dernière donnée réellement ingérée vs fréquence promise par source ; alerte si dérive (leçon : les sites morts répondent 200). **Surveillance nominative des maillons communautaires** : build quotidien S1 **et** activité du dépôt `decp-processing` (plan B C1) ; CSV Datan S7 (fallback I6) | toutes | — (engagement méthodologique du projet) | 08, 10-critique C1/I6 |

Alertes **documentaires** (sans calcul, mais sourcées) : refus de publication des justificatifs parlementaires (11/06/2026) ; disparition des rémunérations des cabinets des jaunes budgétaires depuis PLF 2024 ; absence de LFI 2026 en open data ; RIE sans open data (04, 05, 01, 08) ; **aides publiques aux entreprises : ~211 Md€/an sans donnée consolidée** (rapport Sénat 08/07/2025 ; vérifié le 19/08 : 0 dataset) ; **« 10 plus hautes rémunérations » : obligation légale (art. 37, loi TFP 2019) éclatée en 25 datasets sans consolidation nationale** ; **collaborateurs parlementaires et comptes des groupes politiques : 0 dataset** (listes/PDF sur les sites des assemblées) ; **pantouflage : 641 avis de mobilité HATVP 2025 sans export open data** ; **périmètre : sécurité sociale (~600 Md€) et dépense propre des opérateurs hors champ du dashboard** (10-critique I2, I3, I7, I8, I10).

---

## 5. Périmètre d'ingestion recommandé : v1 vs v2

### v1 — 13 pipelines, meilleur rapport signal/effort, **zéro clé d'API, zéro compte**

| # | Pipeline | Sources | Fréquence | Stratégie volumétrique (période, échantillonnage, taille) |
|---|---|---|---|---|
| P1 | Budget État mensuel | S13 | mensuelle (poll hebdo) | Export CSV complet à chaque publication ; série 2013→courant ; **26 lignes, < 100 Ko** (01) |
| P2 | Structure budgétaire annuelle | S20, S21, S23 | annuelle (one-shot + veille) | Exports complets : 1 816 + 2 404 + 112 722 lignes ; qq dizaines de Mo, une fois par an (01) |
| P3 | Marchés publics | S1 | quotidienne | `decp.parquet` **243 Mo/jour**, remplacement complet (le fichier EST l'état) — **archiver le dernier parquet sain avant chaque remplacement** ; **mode nominal = parquet local + DuckDB** (l'API tabulaire, en bêta, n'est qu'un raccourci substituable) ; base locale filtrée `donneesActuelles=true` + dédup `uid` ; affichage fenêtres 30 j / 12 mois ; agrégats pré-calculés au build ; mode dégradé documenté dans la fiche S1 (plan B) (02, 10-critique C1/I9) |
| P4 | Appels d'offres en cours | S2 | 2-4×/jour | **Aucun stock** : requêtes API filtrées (`datelimitereponse > now`, ~9 000 lignes) + exports filtrés pour les attributions du jour ; quota 50 000/j très au-dessus du besoin (02) |
| P5 | Marchés à venir | S9 | hebdomadaire | Dataset complet : 11 388 lignes (02) |
| P6 | Journal officiel | S3 | quotidienne (cron ~06h) | Delta nocturne **~100-500 Ko/jour** ; démarrage au premier delta (pas de Freemium 1 Go) ; lister l'index, ignorer la livraison du soir ; stock cumulé de l'ordre de 15 Mo/mois (07) |
| P7 | Intégrité des élus | S14 + S17 | hebdo / trimestrielle | `liste.csv` 3,3 Mo remplacement complet ; RNE : 12 CSV **~81 Mo** remplacement complet trimestriel (04) |
| P8 | Lobbying | S4 | quotidienne | `Vues_Separees_CSV.zip` **14,2 Mo/jour**, remplacement complet ; **ne pas prendre le JSON 137 Mo en v1** (04) |
| P9 | Parlement | S5 (AMO10 + Scrutins), S6 (ODSEN + questions), S7 (Datan) | quotidienne (nocturne) | 4,9 + 26,3 + ~0,5 Mo/jour + CSV Datan ; **Scrutins en incrémental** : le zip (172,7 Mo décompressés, 8 434 fichiers) est re-livré entier chaque nuit → ne re-parser que les nouveaux numéros de scrutin (diff) ; périmètre = législature 17 paramétrée ; prévoir renouvellement Sénat 27/09/2026 (03, 10-critique M6) |
| P10 | Financement politique | S25 + S29 | annuelle / par scrutin | One-shot : 4 CSV partis 2021-2024 (~300 Ko chacun) + législatives 2024 (1,14 Mo, `cp1252, skiprows=6`) ; veille municipales 2026 (attendues fin 2026/2027) (04) |
| P11 | Finances locales | S16 | au build + à la demande | **Jamais d'aspiration des bases 22 M lignes** : exports filtrés pré-calculés par indicateur × exercice (34 778 lignes / 1,9 Mo chacun ; ~6 indicateurs ≈ 12 Mo) + `group_by=dep_code` à la volée (cache) + dotations par requêtes ciblées (06) |
| P12 | Référentiels | S27, S10 | annuelle / à la volée | geo.api.gouv 4,7 Mo one-shot ; france-geojson 569 Ko statique ; populations INSEE 1 Mo/an ; recherche-entreprises au fil de l'eau (≤ 7 req/s) (09) |
| P13 | Train de vie (constantes) | S31 | à parution (annuelle) | **Zéro pipeline** : bloc de constantes sourcées (bloc YAML du §9 de 05-frais-indemnites.md, **à corriger avant usage** : ligne `mission_pouvoirs_publics_lfi_2026` invalide, `;` → clés/valeurs, 10-critique M2) ; revue à chaque rapport annuel (Élysée 2025 à surveiller) |

**Bilan v1** : ~290 Mo/jour téléchargés (dominés par le parquet DECP), stockage vif < 2 Go, aucune authentification, tous les modules de la navigation alimentés honnêtement, alertes A1-A11 calculables. **Périmètre v1 confirmé après la critique de complétude : 13 pipelines, inchangé** — les ajouts (S38 avis CADA, S39 jaune opérateurs, panels rémunérations/collaborateurs) sont classés v2 ou documentaires : aucun ne conditionne un module v1, et chacun exige échantillonnage ou extraction avant toute promesse.

### v2 — le reste, documenté et priorisé

1. **S15 declarations.xml** (88,8 Mo hebdo, parsing SAX) → fiches patrimoine/intérêts détaillées (04).
2. **S30 SME PDF** (headless + parsing) → le seul mission/programme mensuel (01).
3. **Sénat approfondi** : Dosleg (dump SQL 126,3 Mo → scrutins nominaux depuis 2006) + Ameli 154 Mo (03).
4. **AN approfondi** : amendements 296,7 Mo/j ; questions écrites 45,8 Mo ; Agenda 7,8 Mo (reconstruction de la présence en commission — plus rien d'autre ne la fournit depuis la mort de NosDéputés) (03).
5. **S28 balances collectivités** (requêtes ciblées par SIREN) + **S33 comptes individuels** (strates) + **S32 subventions SCDL** (panel Paris/Lyon/départements conformes, jamais « national ») (06).
6. **S26 élections Parquet** (71 + 161 Mo) + **S19 HowTheyVote** (68,6 Mo hebdo, ODbL) + Europarl (09).
7. **S18 stock Sirene Parquet** (705 Mo/mois, DuckDB) si les trous de résolution le justifient (09).
8. **S22 CGE** (517 k lignes) + **S24 RAP** ; **S34 TED** ; **S12 BODACC/associations** ; **S35 LEGI/DOLE/Debats/RefOrgaAdminEtat** ; **S36 PISTE** (one-shot humain) ; **S37 décret d'aide publique** (01, 02, 07, 04).
9. **Ajouts post-critique (19/08)** : **S38 avis CADA** (CSV consolidé 198,4 Mo, échantillonner avant promesse → carte des verrous) ; **S39 jaune opérateurs PLF 2026** (référentiel des opérateurs) ; **panel « 10 plus hautes rémunérations »** (25 datasets épars, patron S32 : jamais « national ») ; **collaborateurs parlementaires** (extraction HTML des fiches AN/Sénat, coûteuse) ; **comptes des groupes politiques** (PDF AN/Sénat à vérifier en Phase 1 → constantes S31 ou boîte noire) (10-critique I1, I3, I4, I10).
10. **Veilles actives** (re-tester périodiquement) : open data du RIE (trimestriel) ; **export open data des avis de mobilité HATVP (pantouflage), au même rythme que la veille RIE** ; comptes de campagne municipales 2026 ; rapport Cour des comptes Élysée exercice 2025 ; jaune cabinets PLF 2027 ; jaune associations PLF 2026 ; publication éventuelle de la LFI en données ; **datasets PLF 2027** (famille destination/nature + budget vert, attendus oct.-nov. 2026 — ils remplaceront S20/S21 quelques semaines après le lancement) ; **donnée consolidée « aides aux entreprises »** (0 dataset au 19/08) ; **réserve parlementaire historique** (7 datasets figés, vérifiés — chronologie IRFM → DFP / boîte noire ; successeur FDVA jamais traité) (04, 05, 01, 10-critique M8/I2/I7).

---

## 6. Tableau récapitulatif final

| Source | Fraîcheur réelle (constatée le 19/08/2026) | Licence | Module(s) | v1/v2 |
|---|---|---|---|---|
| S1 DECP consolidées tabulaires | Quotidienne (build du jour, notifications J-1) (02) | LO 2.0 | Commande publique, Accueil, Alertes | **v1** |
| S2 BOAMP | Quotidienne, annonces du jour même (02) | etalab-2.0 | Commande publique (AO en cours), Accueil | **v1** |
| S3 DILA JORFSIMPLE | JO du jour à ~00h30 (07) | LO (fr-lo) | Documents/JO, Accueil | **v1** |
| S4 HATVP AGORA (lobbying) | Quotidienne (00h04) (04) | LO Etalab | Lobbying, Alertes | **v1** |
| S5 Open data AN (AMO, scrutins, questions) | Quotidienne (jour même) (03) | LO | Élus & Institutions | **v1** (amendements/agenda v2) |
| S6 Open data Sénat (ODSEN, questions) | Quotidienne (jour même) (03) | LO | Élus & Institutions | **v1** (Dosleg/Ameli v2) |
| S7 Datan (scores députés) | Quotidienne (CSV du 19/08/2026) (03) | fr-lo | Élus & Institutions | **v1** |
| S8 DECP data.economie (DAJ) | J-2 (02) | LO 2.0 | Commande publique (contrôle) | **v1** |
| S9 APProch (projets d'achats) | Continue (maj 15/08) (02) | LO 2.0 | Commande publique | **v1** |
| S10 API Recherche d'entreprises | Quotidienne (09) | LO 2.0 | Transverse (résolution SIRET) | **v1** |
| S11 Annuaire de l'administration | Vivante (94 117 fiches) (09) | DILA open data | Élus & Institutions, carte | v2 |
| S12 BODACC / JO associations (ODS) | Parution du jour (07) | LO | Recoupements | v2 |
| S13 SMB séries longues (DGFiP) | Mensuelle, données au 30/06/2026 (~6 sem.) (01) | LO 2.0 | Dépenses de l'État, Accueil | **v1** |
| S14 HATVP liste.csv | Hebdomadaire (14/08) (04) | LO Etalab | Alertes, Élus & Institutions | **v1** |
| S15 HATVP declarations.xml | Hebdomadaire (14/08) (04) | LO Etalab | Élus & Institutions (fiches) | v2 |
| S16 OFGL (comptes + dotations) | Comptes 2025 (juil. 2026, provisoires) ; dotations 2026 (04/08) (06) | LO 2.0 | Finances locales, Accueil | **v1** |
| S17 RNE | Trimestrielle (11/08/2026, post-municipales) (04) | lov2 | Élus & Institutions, Alertes | **v1** |
| S18 Stock Sirene Parquet | Mensuelle (01/08/2026) (09) | lov2 | Transverse | v2 |
| S19 HowTheyVote.eu | Hebdomadaire (release 15/08) (09) | **ODbL** | Élus & Institutions (UE) | v2 |
| S20 PLF 2026 Budget vert | Annuelle (13/11/2025) (01) | LO 2.0 | Dépenses de l'État, Accueil | **v1** |
| S21 PLF 2025 destination/nature | Annuelle (10/2024) (01) | LO 2.0 | Dépenses de l'État | **v1** |
| S22 Balances CGE État | Annuelle (2025 publié) (01) | LO 2.0 | Dépenses de l'État (patrimoine) | v2 |
| S23 Jaune associations | Annuelle, versements 2023 (01) | LO 2.0 | Dépenses de l'État (subventions) | **v1** |
| S24 RAP 2025 (performance) | Annuelle (04/06/2026) (01) | LO 2.0 | Dépenses de l'État | v2 |
| S25 CNCCFP comptes des partis | Exercice 2024 publié le 10/02/2026 (04) | LO | Financement politique, Alertes | **v1** |
| S26 Élections agrégées (MI) | Par scrutin (municipales 2026 incluses, 07/07/2026) (09) | lov2 | Élus & Institutions | v2 |
| S27 Géo + populations INSEE | Statique/annuel (pop. réf. 2023 en vigueur 2026) (09) | LO/INSEE | Cartes, ratios | **v1** |
| S28 Balances collectivités DGFiP | 2025 provisoire (13/07/2026) (06) | LO 2.0 | Finances locales (drill-down) | v2 |
| S29 CNCCFP comptes de campagne | Législatives 2024 (29/07/2025) ; municipales 2026 à venir (04) | LO | Financement politique, Alertes | **v1** |
| S30 SME PDF (missions mensuelles) | Mensuelle (juin 2026) mais 403 anti-bot (01) | LO 2.0 | Dépenses de l'État | v2 |
| S31 Corpus PDF train de vie | Annuel (rapports 2026 sur exercices 2024-2025) (05) | publications officielles | Frais & train de vie | **v1** (constantes) |
| S32 Subventions SCDL (panel) | Hétérogène (Armor 16/08/2026 ; Paris 28/07/2026) (06) | LO 2.0 (à vérifier) | Finances locales | v2 |
| S33 Comptes individuels collectivités | 2024 max (01/12/2025) (06) | LO 2.0 | Finances locales (strates) | v2 |
| S34 TED (UE) | Quotidienne (02) | réutilisation UE | Commande publique (UE) | v2 |
| S35 Autres fonds DILA (LEGI/DOLE/Debats/RefOrga) | Quotidienne à J-1 (07) | fr-lo | Documents/JO | v2 |
| S36 API Légifrance (PISTE) | Temps réel (one-shot humain requis) (07) | CGU PISTE + fr-lo | Documents (recherche) | v2 (optionnel) |
| S37 Décret aide publique partis | Annuel (décret 03/03/2026, 403 curl) (04) | — | Financement politique | v2 |
| S38 Avis CADA (ensemble consolidé) | Consolidé maj 14/08/2026 + lots mensuels/trimestriels (10-critique) | fr-lo | Frais & train de vie (carte des verrous, boîte noire) | v2 |
| S39 Jaune opérateurs PLF 2026 | Annuelle (13/01/2026) (10-critique) | lov2 (confirmée 20/08/2026) | Dépenses de l'État (référentiel opérateurs) | v2 |
| S40 Registre de transparence UE | Export XML quotidien (exportDate) | décision 2011/833/UE (20/08/2026) | Lobbying (bloc cloisonné) | v2 |

---

*Document établi à partir des rapports 01 à 09 de `docs/recherche/`, révisé après le contre-audit `10-critique-completude.md` (tous appels réels du 19/08/2026). Toute évolution (RIE, municipales 2026 CNCCFP, rapport Élysée 2025, LFI en données, PLF 2027, export des avis de mobilité HATVP) passe par la mise à jour de ce fichier.*
