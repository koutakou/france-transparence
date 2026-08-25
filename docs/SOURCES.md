# SOURCES.md — Référentiel unique des sources de données

**Projet France Transparence · Document de référence de la suite du projet · Établi le 19 août 2026.**
**Révisé le 19/08/2026 après critique de complétude (docs/recherche/10-critique-completude.md)** — corrections C1-C2, I1-I10 et mineures (M1, M3, M4, M6-M9) intégrées ; périmètre d'ingestion inchangé (13 pipelines).

> **Mise à jour du 20/08/2026 (soir).** Le périmètre ingéré s'est étendu depuis le 19/08 : quatre
> sources s'y sont ajoutées — **S15** (contenu des déclarations d'intérêts HATVP, via
> `pipelines/ingest_hatvp_declarations.py`), **S26** (participation électorale, via
> `pipelines/ingest_elections.py`, agrégats commune/département, **sans aucune nuance
> politique ni nom de candidat**), **S38** (avis et conseils de la CADA, en agrégats seulement,
> via `pipelines/ingest_cada.py`) et **S40** (registre de transparence de l'Union européenne,
> via `pipelines/ingest_registre_ue.py`). L'ingestion compte donc **17 pipelines** et
> **29 sources tracées dans `meta_sources`**. Les mentions de « 13 pipelines » ci-dessous décrivent le
> périmètre d'ingestion tel qu'arrêté le 19/08/2026 et sont conservées à ce titre : la liste qui fait
> autorité est la variable `PIPELINES` du `Makefile`.
>
> **Mise à jour du 21/08/2026.** **S18** (stock Sirene, `pipelines/ingest_sirene.py`) s'ajoute au
> périmètre ingéré : un **référentiel d'attributs** — catégorie juridique, code NAF, état
> administratif, tranche d'effectifs, économie sociale et solidaire, date de création — restreint aux
> SIREN que les autres tables citent réellement, et **sans aucune identité de personne physique**.
> L'ingestion compte donc **18 pipelines** et **30 sources tracées dans `meta_sources`**. S18 étant
> dérivée des autres tables, son pipeline les lit et figure **en dernier** dans la variable
> `PIPELINES` du `Makefile` — cette place-là n'est pas arbitraire.
>
> **Mise à jour du 22/08/2026.** **S41** (encours de dette des APU au sens de Maastricht, Eurostat
> `gov_10q_ggdebt`, via `pipelines/ingest_dette_maastricht.py`) s'ajoute. L'ingestion compte donc
> **19 pipelines** et **31 sources tracées dans `meta_sources`**. Pipeline sans dépendance d'ordre,
> placé avant `sirene` (qui reste dernier). Le secteur ESA S13 (APU) n'est pas la source S13 (SMB
> DGFiP).
>
> **Mise à jour du 22/08/2026 (soir).** **S42** (déficit public des APU au sens de Maastricht,
> Eurostat `gov_10dd_edpt1`, na_item=B9, via `pipelines/ingest_deficit_maastricht.py`) s'ajoute.
> L'ingestion compte donc **20 pipelines** et **32 sources tracées dans `meta_sources`**.
> Distinct de S41 (stock GD trimestriel) et de S13 (solde du budget général). Pas de
> comparaison au seuil de 3 % du PIB. Pipeline sans dépendance d'ordre, placé avant
> `sirene`.
>
> **Mise à jour du 22/08/2026 (soir).** **S43** (dossiers législatifs DILA, fonds DOLE, via
> `pipelines/ingest_dole.py`) s'ajoute. L'ingestion compte donc **21 pipelines** et
> **33 sources tracées dans `meta_sources`**. Distinct de S3 (JORFSIMPLE, fenêtre 30 JO)
> et de S35 (LEGI, Debats, RefOrgaAdminEtat — toujours non ingéré). Pipeline sans
> dépendance d'ordre, placé avant `sirene`. La législature courante est le max des
> numéros, jamais 17 en dur.
>
> **Mise à jour du 23/08/2026.** **S44** (recettes et dépenses des APU, agrégats ESA, Eurostat
> `gov_10a_main`, na_item TE/TR, via `pipelines/ingest_agregats_apu.py`) s'ajoute.
> L'ingestion compte donc **22 pipelines** et **34 sources tracées dans `meta_sources`**.
> Distinct de S13 (État YTD, SMB DGFiP), de S41 (stock GD) et de S42 (B9). TE et TR
> ne sont pas des agrégats Maastricht — Maastricht est réservé à GD/B9. Pipeline
> sans dépendance d'ordre, placé avant `sirene`.
>
> **Mise à jour du 23/08/2026.** **S22** (bilan patrimonial de l'État, CGE, pièce
> de synthèse xlsx du jeu `balances_des_comptes_etat`, via
> `pipelines/ingest_cge.py`) s'ajoute. L'ingestion compte donc **23 pipelines**
> et **35 sources tracées dans `meta_sources`**. Distinct de S13 (budget,
> caisse, YTD), de S41/S42/S44 (Maastricht / ESA des APU). Les totaux I/II/III
> sont lus dans la pièce, jamais sommés depuis les 517 489 lignes
> compte×programme. Pipeline sans dépendance d'ordre, placé avant `sirene`.
>
> **Mise à jour du 23/08/2026.** **S45** (prestations de protection sociale,
> DREES « Les comptes de la protection sociale », via
> `pipelines/ingest_protection_sociale.py`) s'ajoute. L'ingestion compte donc
> **24 pipelines** et **36 sources tracées dans `meta_sources`**. Distinct
> de S13 (budget général, YTD), de S44 (TE des APU), de la LFSS (loi votée,
> non ingérée) et d'ESSPROS (Eurostat, non ingéré). Pipeline sans
> dépendance d'ordre, placé avant `sirene`.
>
> **Mise à jour du 24/08/2026.** **S46** (recettes du budget général au PLF,
> État A, data.economie `plf25-recettes-du-budget-general`, via
> `pipelines/ingest_recettes_plf.py`) s'ajoute. L'ingestion compte donc
> **25 pipelines** et **37 sources tracées dans `meta_sources`**. Distinct
> de S13 (exécution nette, cumul YTD). Recettes **brutes** du projet, pas
> la LFI votée, pas 2026. Pipeline sans dépendance d'ordre, placé avant
> `sirene`.
>
> **Mise à jour du 24/08/2026, soir.** **S47** (IRCOM, impôt sur le revenu
> par collectivité territoriale, DGFiP/DESF, via `pipelines/ingest_ircom.py`)
> s'ajoute. L'ingestion compte donc **26 pipelines** et **38 sources**.
> Distinct de S13 (IR de caisse, cumul YTD). Impôt net **sur rôle**, année
> des **revenus**. Tranches de RFR, salaires et pensions non ingérés.
>
> **Mise à jour du 24/08/2026, soir.** **S48** (REI, fiscalité directe
> locale, DGFiP/DESF, via `pipelines/ingest_rei.py`) s'ajoute.
> L'ingestion compte donc **27 pipelines** et **39 sources**. Distinct
> de S16 (comptes OFGL), S13 (caisse) et S47 (IRCOM). Impositions
> primitives du rôle général, année d'**imposition**. Taux, compensations
> TVA et pages communales non ingérés.
>
> **Mise à jour du 25/08/2026.** **S49** (dépenses des APU par fonction,
> Eurostat `gov_10a_exp`, CFAP / COFOG-99, na_item=TE, via
> `pipelines/ingest_cofog_apu.py`) s'ajoute. L'ingestion compte donc
> **28 pipelines** et **40 sources**. Distinct de S13 (budget de l'État),
> de S44 (TE `gov_10a_main`, table distincte) et de S45 (prestations
> DREES). TOTAL + GF01–GF10. TIME 2025 listé, 0 valeur FR au 25/08 :
> millésime 2024. Groupes et taxag non ingérés.
>
> **Mise à jour du 25/08/2026, après-midi.** **S50** (comptes des APU
> INSEE, Insee Résultats 8988845, via
> `pipelines/ingest_comptes_apu_insee.py`) s'ajoute. L'ingestion compte
> donc **29 pipelines** et **41 sources**. Tableaux 3.201/3.202/3.203/
> 3.205/3.212 (totaux par sous-secteur) et 3.216 (prélèvements
> obligatoires). Distinct de S13, S44, S42 (B9 non ingéré) et S49.
> PO officiel ≠ taxag. Sous-secteurs non additifs.
>
> **Document daté.** Les fraîcheurs et volumétries amont relevées ici l'ont été par appels réels le
> 19/08/2026 (et le 20/08 pour S38 et S40, le 22/08 soir ~22:30 CEST pour S43, le 23/08 pour S44, S22 et S45) : elles décrivent ces jours-là et **ont dérivé depuis**.
> Le catalogue vivant, avec la date réellement ingérée de chaque source, est la page `/donnees`
> du site, régénérée à chaque publication.

Ce document synthétise les 9 rapports de la Phase 0 (`docs/recherche/01` à `09`), tous fondés sur des **appels réels effectués le 19/08/2026** (curl/API, codes HTTP constatés). Chaque affirmation de fraîcheur ou de volumétrie cite son rapport source entre parenthèses. Règle du projet : **données réelles uniquement, fraîcheur affichée et mesurée** — le site n'affiche rien que les sources ne contiennent pas.

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
- **Pièges** : 1 marché = n lignes (titulaires, modifications) → **dédoublonner par `uid`**, en prenant les ATTRIBUTS (montant, titulaires, objet, procédure) sur `donneesActuelles=true` mais la **DATE du marché sur `min(dateNotification)` de TOUTES ses lignes, avenants compris** : la ligne d'un avenant porte comme `dateNotification` la date de l'avenant, et `donneesActuelles` ne vaut que sur la dernière modification — lire la date sur la seule ligne courante date le marché de son dernier avenant et le range dans le mauvais mois ; `min()` global plutôt que la ligne `modification_id = 0`, qui manque à des milliers de `uid` ; montants d'accords-cadres = maximum, pas dépensé → utiliser `montant_rationalise`/`montant_anomalie` ou écrêter p99 ; consolidation communautaire (code public `decp-processing`) à créditer ; latence légale de publication jusqu'à 2 mois (02) ; ⚠ **l'API tabulaire data.gouv est en bêta** (08 §2.1) : contrat susceptible de changer sans préavis — simple raccourci, substituable par des requêtes DuckDB sur le parquet local (mode nominal de P3).
- **Lecture bitemporelle — les deux axes du temps sont déjà dans la source** : `dateNotification` décrit une **VERSION du marché, pas le marché**. C'est explicite et assumé en amont : le code de la consolidation `decp-processing` définit `VERSION_KEY = ["uid", "dateNotification", "codeCPV"]` et commente lui-même cette clé comme « clé identifiant une VERSION de marché (pas un marché) », `modification_id` y étant le **rang** de `dateNotification` — ce que le parquet confirme : au 21/08/2026, aucun `uid` n'avait de ligne `modification_id = 0` portant autre chose que le `min(dateNotification)` du marché. Ce n'est donc pas un défaut de la consolidation amont, c'est son modèle de données ; le lire comme « la date du marché » est une erreur de lecture côté aval, et c'en fut une ici. Conséquence directe, déjà énoncée dans les pièges : la ligne d'un **avenant** porte comme `dateNotification` **la date de l'avenant**, d'où la datation par `min()` sur toutes les lignes du `uid`. Au 21/08/2026, 314 173 `uid` portaient plus d'une `dateNotification` distincte et 264 177 plus d'une `datePublicationDonnees` distincte — la multiplicité est le cas courant, pas la marge. **`datePublicationDonnees` porte, elle, la date d'OBSERVATION** : celle à laquelle la donnée a été mise à disposition. La source livre donc les deux axes du temps — la période décrite (notification) et la date à laquelle on l'a su (publication) — ce qui rend le **délai de publication mesurable sans rien historiser** de notre côté : par `uid`, `min(datePublicationDonnees) − min(dateNotification)`. C'est la mesure que servent les tables `decp_publication_qualite`, `decp_publication_annees` et `decp_publication_acheteurs` (`docs/SCHEMA-DB.md`). **Limites, non négociables et à porter avec tout chiffre issu de cette mesure** : le parquet ne contient que des marchés **publiés**, un marché jamais publié y étant absent du dénominateur comme du numérateur — tout taux est une **borne haute** ; les cohortes de notification récentes ont un dénominateur incomplet (marchés notifiés dont la publication n'est pas observée à la date d'ingestion, et ce sont les lents qui manquent) et sont **optimistes par construction**, d'où la règle de ne comparer que des cohortes closes ; les marchés dont la publication précède la notification sont **écartés et comptés à part**, jamais ramenés à un délai nul ; la ventilation par acheteur ne couvre pas les marchés dont `acheteur_categorie` n'est pas renseignée ; et le délai légal est de **2 MOIS** (arrêté du 22/12/2022), jamais de 60 jours — les deux ne coïncident pas et l'écart déplace exactement les marchés limites.
- **Plan B (point de défaillance unique)** : consolidation maintenue par une personne — profil exact des morts recensées par 08 (`decp_augmente` [Obsolète], `decp.info` 301 vers offre commerciale). (a) **Mode dégradé documenté** = S8 + fichiers consolidés DAJ bruts, résolution des noms via S18 Sirene, géolocalisation par `lieuexecution` + annuaire S11 — carte en **agrégats départementaux** au lieu de points ; (b) le build quotidien S1 **et** l'activité du dépôt `decp-processing` sont inscrits au moniteur A11 ; (c) **archivage local du dernier parquet sain avant chaque remplacement** (le fichier EST l'état : un build cassé écraserait tout) (10-critique C1).
- **Unité des identifiants — l'ajout du 21/08/2026, et c'est un piège de la source, pas du site** : la source n'identifie acheteurs et titulaires que par **SIRET**, c'est-à-dire par ÉTABLISSEMENT. Tout agrégat groupé sur ce SIRET compte donc des établissements et non des entreprises : une entreprise qui facture depuis un réseau d'agences locales est éclatée sur des dizaines ou des centaines de lignes dont aucune n'atteint le seuil d'entrée d'un top, et **disparaît d'un classement dont elle peut être la première** — mesuré sur la base servie le 21/08/2026, le premier attributaire par entreprise sur 12 mois (2 735 M€, 2 221 marchés, 204 établissements) était absent du top 50 par établissement, dont le seuil d'entrée était de 310 M€ ; 14 des 50 premiers SIREN manquaient à ce top 50. Ce relevé est daté et documente le défaut d'unité, pas l'état du jour : ces montants et ces rangs dérivent à chaque ingestion, et les valeurs vivantes sont celles qu'affiche `/marches`. La clé d'entreprise est le **SIREN**, les 9 premiers chiffres du SIRET, et c'est celle des tables `decp_top_acheteurs` et `decp_top_titulaires` (`docs/SCHEMA-DB.md`). Corollaire : le **libellé** publié par la source nomme lui aussi souvent l'établissement (« … (ETABLISSEMENT DE MERIGNAC) », « … (MAIRIE) ») — d'où le recours à S18 pour la dénomination de référence. Les identifiants inexploitables (numéros de TVA intracommunautaire, `00001`, chaînes tronquées) sont écartés de ces classements par un test de **format** (exactement 14 chiffres) et comptés à part dans `decp_titulaires_qualite` et `decp_acheteurs_qualite` : jamais remplacés par une valeur par défaut, jamais retirés en silence.
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

#### S12. ODS DILA — BODACC et JO associations (périphériques, non ingérés)
- **URLs testées** : `https://bodacc-datadila.opendatasoft.com` (`annonces-commerciales` : 50 393 102 enreg., parution 19/08) ; `https://journal-officiel-datadila.opendatasoft.com` (`jo_associations` : 5 645 043 enreg., parution 19/08) — **aucun dataset JORF lois-décrets sur ces portails** (07).
- **Licence** : Licence Ouverte. **Modules** : recoupements associations/entreprises (non ingérés).

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
- **Modules** : Élus & Institutions (fiches patrimoine/intérêts) — non ingéré au 19/08/2026 (ingéré depuis, voir l'encadré en tête).

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

#### S18. Stock Sirene (INSEE via data.gouv.fr) — référentiel d'attributs des unités légales citées en base
- **URLs testées le 21/08/2026** (codes HTTP constatés par `curl`) : page du jeu `https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret` → **200** ; API du jeu `https://www.data.gouv.fr/api/1/datasets/5b7ffc618b4c4169d30727e0/` → **200** (24 ressources, `"license": "lov2"`, `"frequency": "monthly"`) ; ressource retenue `https://static.data.gouv.fr/resources/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/20260801-073937/stock-stockunitelegale-parquet.parquet` → **200**, `content-length: 705090270`, `last-modified: 01/08/2026`.
- **Accès/format** : `StockUniteLegale` en **parquet** (≈ 705 Mo) plutôt qu'en CSV zippé (≈ 971 Mo, même millésime). Le parquet se lit par colonnes, et le référentiel n'a besoin que de 13 des 35 colonnes du fichier ; la semi-jointure sur les SIREN à retenir s'exécute en moins d'une seconde, là où un parcours du CSV en Python demande plus de deux minutes et demie. DuckDB est déjà une dépendance du projet (S1/DECP). **Granularité** : 1 ligne = 1 unité légale (SIREN) ; le stock amont en compte de l'ordre de **30 millions**.
- **Licence** : `lov2` — **Licence Ouverte 2.0**, lue dans la réponse de l'API. **Fréquence** : **mensuelle**, un millésime publié le 1er de chaque mois.
- **Pièges** :
  - **URL horodatée** (`…/20260801-073937/…`) : le chemin change à chaque millésime, la ressource est donc **re-résolue par l'API du jeu à chaque exécution** (convention §0.3, comme S17/RNE et S38/CADA). Le titre de la ressource sert de sélecteur (`StockUniteLegale` + `parquet`) avec **exclusion explicite de « Historique »** : le même jeu publie un `StockUniteLegaleHistorique` en parquet, qui répondrait sinon aux mêmes marqueurs.
  - **L'ancien chemin `files.data.gouv.fr/insee-sirene/` n'est plus une source de fichiers** : contrairement à ce qui était noté en 09, il répond **HTTP 200** (constaté le 21/08/2026) — mais l'index ne contient plus qu'un `migration-fichiers-sirene.txt` de 215 octets qui renvoie vers la page data.gouv.fr, et les fichiers eux-mêmes ont disparu (`…/insee-sirene/StockUniteLegale_utf8.zip` → **HTTP 404**). Illustration exacte de la convention §0.2 : un 200 ne prouve pas qu'une source vit.
  - `categorieJuridiqueUniteLegale` est livré **en entier** dans le parquet alors que c'est un **code à quatre chiffres** : il doit être reformaté sur 4 positions, faute de quoi tout code à zéro initial s'affiche amputé.
  - **Le fichier porte des données à caractère personnel** : `StockUniteLegale` décrit aussi les entrepreneurs individuels — nom de naissance, nom d'usage, quatre prénoms, prénom usuel, pseudonyme, sexe. La colonne `statutDiffusionUniteLegale` porte par ailleurs le **droit d'opposition** de l'article A123-96 du code de commerce : les unités non diffusibles ne se republient pas.
  - **Source dérivée, donc dépendante de l'ordre d'ingestion** : le périmètre retenu est celui des SIREN que les autres tables citent. Le pipeline lit ces tables et doit passer **après** elles ; sur une base neuve il refuse d'écrire plutôt que de produire un référentiel vide.
- **Modules** : transverse (qualification des acheteurs, titulaires de marchés, associations subventionnées et entités de lobbying).

**INGÉRÉE le 21/08/2026 — pipeline `pipelines/ingest_sirene.py`.** À ne pas confondre avec `pipelines/sirene.py`, qui est la résolution **unitaire** par API de S10 et n'a jamais été ingérée. Ce que cette source apporte, et ce qu'elle n'apporte pas :
- **Ce n'est pas un référentiel « SIREN → nom ».** Sur l'ordre de 164 000 SIREN cités par l'ensemble des tables, à peine **0,25 %** (quelques centaines) n'avaient aucun nom nulle part : les autres sources fournissent déjà le nom. Ce qui manquait, ce sont les **attributs** — environ **deux tiers** des SIREN cités n'avaient ni catégorie juridique, ni code d'activité, ni état administratif, ni appartenance à l'économie sociale et solidaire.
- **Périmètre restreint, et c'est une décision mesurée.** La base ne cite qu'environ **0,5 %** du stock amont. Le coût mesuré est de **≈ 155 octets par ligne** : de l'ordre de **24 Mio** pour le référentiel restreint, contre **≈ 5,8 Gio** pour le stock entier — 238 fois plus de données pour un usage identique, le surplus ne décrivant que des unités légales qu'aucune autre table ne mentionne.
- **Volumétrie** : de l'ordre de **163 000 unités légales** retenues, soit **plus de 99 %** des SIREN cités, après mise à l'écart d'environ **un millier d'unités non diffusibles**. Les comptes exacts du jour vivent sur la page `/donnees`, régénérée à chaque publication : eux seuls font foi.
- **Ce qui n'est délibérément PAS ingéré** : aucun nom, prénom, pseudonyme ni sexe de personne physique n'est lu du fichier — ces colonnes ne figurent pas dans la requête d'extraction. Les quelque **6 000 entrepreneurs individuels** du périmètre entrent au référentiel avec leur catégorie juridique, leur activité et leur état, **jamais avec leur identité** (`denomination` reste NULL, `est_personne_physique` vaut 1). Les unités non diffusibles sont écartées. Le référentiel sert à qualifier des personnes morales attributaires de marchés ou de subventions : cet usage n'a besoin d'aucune identité de personne physique.
- **Ce que la source répare, mesuré côté aval** : plusieurs milliers de SIREN titulaires de marchés portent **deux ou trois libellés distincts** dans les DECP (la même entreprise écrite de plusieurs façons), et le libellé déclaré nomme souvent l'**établissement** et non l'entreprise (« … (ETABLISSEMENT DE MERIGNAC) », « … (MAIRIE) ») ; sans dénomination de référence, un classement par entreprise porterait le nom d'un seul de ses établissements. C'est l'usage réel : `denomination` et `categorie_entreprise` sont jointes en `LEFT JOIN` sur `decp_top_acheteurs.siren` et `decp_top_titulaires.siren` **à la lecture** (`app/src/lib/queries/marches.ts`), avec repli sur les valeurs DECP. Les comptes exacts vivent en base et dérivent à chaque ingestion (`decp_titulaires_qualite`), jamais dans ce document.
- **Ce que la source ne fait PAS : servir de test de validité d'identifiant.** Rectification du 21/08/2026 : ce document présentait le rapprochement Sirene comme ce qui rend les identifiants malformés « distinguables d'un identifiant valide », et `docs/SCHEMA-DB.md` allait jusqu'à écrire « un SIREN absent de Sirene n'est pas un SIREN » — les deux formulations sont fausses et sont corrigées. L'absence d'un SIREN de `sirene_unites_legales` ne dit pas que ce SIREN est faux : la couverture des SIREN titulaires est haute sans être totale (quelques centaines manquent sur une fenêtre de 12 mois), et les unités non diffusibles sont écartées à l'extraction. Le tri des identifiants DECP inexploitables se fait par un test de **format** dans le pipeline DECP (exactement 14 chiffres), sans aucun recours à ce référentiel.
- **Table** : `sirene_unites_legales` (une seule table, trois index) — colonnes et conventions détaillées dans `docs/SCHEMA-DB.md`.
- **Fraîcheur** : `meta_sources.date_donnees` porte la **date du dernier traitement des unités retenues**, jamais la date de publication du jeu. Seuils `S18 |jc|40|55|10` — l'âge oscille de ~0 à ~32 jours en régime mensuel normal ; 55 jours = un millésime entièrement sauté.
- **Cache** : le millésime étant mensuel, le parquet est conservé 30 jours dans `data/raw/sirene/` — exception déclarée côté serveur dans `/etc/france-transparence/cache-long.conf`, sans quoi la purge quotidienne de `data/raw` le rendrait inopérant.

#### S19. HowTheyVote.eu — votes des eurodéputés français
- **URLs testées** : `https://howtheyvote.eu/api/votes` (200 ; 2 421 votes, positions des **81 eurodéputés FR**) + dumps hebdo GitHub `HowTheyVote/data` (release 15/08/2026, export 68,6 Mo) (09).
- **Licence** : **ODbL + DbCL — attribution obligatoire**. **Modules** : Élus & Institutions (volet européen) — non ingéré.

### Groupe C — Exploitables directement, annuelles / par scrutin / statiques

#### S20. PLF 2026 — Budget vert (seule donnée structurée 2026 par action)
- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plf-2026-budget-vert/records?limit=2` (200) ; **1 816 lignes, 46 missions** × programme × action, avec `execution_2024_cp` (l'exécution réelle par action la plus fine disponible), LFI 2025, PLF 2026, cotations environnementales ; modifié 13/11/2025, annuel (01).
- **Licence** : LO v2.0. **Piège majeur** : montants 2026 = **PLF déposé, PAS la LFI promulguée le 19/02/2026** → mention « PLF » obligatoire à l'affichage (01).
- **Modules** : Dépenses de l'État (treemap mission→action, budget vert), Accueil (top missions).

#### S21. PLF 2025 — dépenses par destination et nature
- **URL testée** : `…/plf25-depenses-2025-selon-destination/records?limit=2` (200) ; 2 404 lignes ministère→mission→programme→action→sous-action × titre, AE et CP ; famille complète maj 11/10/2024 ; **aucun équivalent PLF/LFI 2026** (vérifié au catalogue) ; les crédits votés s'arrêtent à LFI 2023 (01).
- **Licence** : LO v2.0. **Modules** : Dépenses de l'État (navigation fine du budget).

#### S22. Compte général de l'État — bilan patrimonial (CGE)
- **URL testée** (23/08/2026) : jeu `balances_des_comptes_etat` HTTP 200, **517 489** lignes compte × programme × année, 2016→2025 ; pièce jointe « 2006-2024 Bilan, CDR, solde.xlsx » HTTP 200, 92 411 o. Licence relue sur la fiche : **Licence Ouverte v2.0 (Etalab)**.
- **Ce qui est ingéré** : les totaux officiels I / II / III, les dettes financières et le solde de l'exercice, lus dans la pièce de synthèse — **pas** les 517 489 lignes. Millésime affiché = 31/12 du max de la pièce (**2024** au 23/08), jamais `modified` du catalogue (2026-04-22).
- **Pièges** : comptabilité générale ≠ budgétaire (ne pas additionner avec S13) ; l'en-tête de la pièce dit « millions d'euros » alors que 2024 et 2022-2018 sont en euros, 2023 et 2017-2006 en millions — détection par l'ordre de grandeur de I, colonne par colonne ; situation nette ≠ « dette de l'État » ≠ Maastricht (S41) ; un TOTAL ACTIF 2025 n'est pas fabriqué par somme de lignes tant que la pièce ne le porte pas.
- **Modules** : Dépenses de l'État (bloc cloisonné) — **ingérée** (23/08/2026, P21).

#### S23. Subventions de l'État aux associations (jaune PLF 2025, versements 2023)
- **URL testée** : `…/plf25-donnees-de-l-annexe-jaune-effort-financier-de-l-etat-en-faveur-des-associations/records?limit=2` (200) ; **112 722 lignes** — une par subvention (SIREN, montant, programme, commune) ; millésime = versements **2023**, publié décembre 2024 → décalage ~2 ans ; **le jaune PLF 2026 n'est pas publié en données** (01).
- **Licence** : LO v2.0. **Pièges** : qualité brute Chorus (SIREN « NR », retours ligne, U+00A0) ; « associations » au sens large (01).
- **Modules** : Dépenses de l'État (« qui l'État subventionne »).

#### S24. Performance de la dépense — RAP 2025
- **URL testée** : `…/performance-de-la-depense-rap-2025/records?limit=1` (200 ; 2 140 lignes, maj **04/06/2026**, exécutions 2023-2025 vs cibles) (01).
- **Licence** : LO v2.0. **Piège** : valeurs en texte avec espaces insécables (01). **Modules** : Dépenses de l'État (atteinte des cibles) — non ingéré.

#### S25. CNCCFP — comptes des partis politiques (exercice 2024 publié le 10/02/2026)
- **URL testée** : `https://static.data.gouv.fr/resources/comptes-des-partis-et-groupements-politiques/20260210-110641/comptes-partis-exercice-2024.csv` (200, 298 Ko, **575 partis × 166 colonnes**) ; CSV homogènes 2021-2024 ; l'exercice N est publié début N+2 (04).
- **Licence** : LO. **Contenu décisif** : dons, cotisations, **aide publique (colonnes 103-105)**, flux inter-partis, par parti et par an (04).
- **Pièges** : formats hétérogènes avant 2021 ; l'avis CNCCFP listant les partis privés d'aide = PDF JO seulement (04).
- **Modules** : Financement de la vie politique, Alertes.

#### S26. Résultats électoraux agrégés (MI/data.gouv.fr)
- **URL testée** : dataset `https://www.data.gouv.fr/datasets/6481e741d4cf002ec0efec9d/` (maj 07/07/2026) ; Parquet « généraux » 70,9 Mo / « par candidat » 161,3 Mo ; via API tabulaire : législatives 2024 = 70 102 BV ; **municipales 2026 T1/T2 publiées** (70 003 / 17 398 BV) (09).
- **Licence** : lov2. **Pièges** : `code_circonscription` vide sur les législatives 2024 ; `nuance` vide pour les petites communes ; préférer le Parquet (09).
- **Modules** : Élus & Institutions (résultats, contexte électoral) — non ingéré au 19/08/2026 (ingéré depuis, voir l'encadré en tête).

#### S27. Référentiel géographique et population
- **geo.api.gouv.fr** (testé 200, sans auth) : ~35 000 communes avec centroïde + population en **un appel de 4,7 Mo** ; contours unitaires GeoJSON ; pas de population départementale (09).
- **france-geojson** (gregoiredavid, raw.githubusercontent.com) : `departements-version-simplifiee.geojson` **569 Ko** → fond de carte SVG retenu ; millésime 2018 (sans conséquence départements/régions) ; contours Etalab millésimés 2025 en complément (`etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/departements-100m.geojson`, 302 → S3, 2,75 Mo) (09).
- **Populations de référence 2023** (INSEE, en vigueur au 01/01/2026, décret n° 2025-1362) : `https://www.insee.fr/fr/statistiques/fichier/8680726/ensemble.zip` (200, 1 Mo, 34 900 communes + départements + régions ; utiliser **PMUN** pour les €/habitant) (09).
- **Licences** : LO/INSEE. **Modules** : cartes et ratios, transverse.

#### S28. Balances comptables des collectivités (DGFiP, data.economie)
- **URL testée** : `…/balances-comptables-des-communes-en-2025/records` (200) ; 2025 = **6 963 040 lignes** (balances **provisoires** de juillet, maj 13/07/2026, définitives en décembre) ; un dataset par année 2010→2025 ; grain budget × compte (06).
- **Licence** : LO v2.0. **Pièges majeurs** : `insee` tronqué aux 3 derniers caractères → **joindre par `siren` uniquement** ; budgets annexes mêlés ; export intégral ≈ **950 Mo/an** (mesuré : ~143 o/ligne) → requêtes ciblées par siren seulement (06).
- **Modules** : Finances locales (drill-down comptable à la demande) — non ingéré.

### Groupe D — Exploitables avec effort (retenues)

#### S29. CNCCFP — comptes de campagne (dernier scrutin publié : législatives 2024)
- **URL testée** : `https://static.data.gouv.fr/resources/elections-legislatives-generales-des-30-juin-et-7-juillet-2024/20250729-150633/comptes-campagne-legislatives-2024.csv` (200, 1,14 Mo, **4 010 candidats**, maj 29/07/2025) ; dépenses détaillées, remboursement État, **décision CNCCFP (A/AR/R)** (04).
- **Pièges MAJEURS constatés** : **cp1252 + CRLF + 6 lignes quasi vides avant l'en-tête** → `skiprows=6, sep=';', encoding='cp1252'` ; pas de dons nominatifs (interdit) ; **municipales 2026 : aucun dataset au 19/08/2026**, l'instruction CNCCFP est en cours (04).
- **Modules** : Financement de la vie politique, Alertes.

#### S30. DGFiP — Situation mensuelle de l'État (SME, PDF)
- **URL testée** : dataset `situation-mensuelle-de-l-etat` (211 documents, maj 14/08/2026) mais **PDF bloqué : HTTP 403 Cloudflare** même avec User-Agent navigateur (01).
- **Intérêt unique** : seule publication **mensuelle au niveau mission/programme** (juin 2026 disponible). **Effort** : récupération manuelle/headless + parsing PDF (01). **Modules** : Dépenses de l'État (détail missions mensuel) — non ingéré.

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
- **Pièges** : obligation légale massivement inappliquée ; SIRET bénéficiaire parfois vide ; **jamais présenter comme national** (06). **Modules** : Finances locales (panel assumé) — non ingéré.

#### S33. Comptes individuels des collectivités (DGFiP)
- **URL testée** : `…/comptes-individuels-des-communes-fichier-global-2023-2024/records` (200 ; 69 877 lignes × 252 champs, maj 01/12/2025) ; apport unique : **moyennes de strate** ; s'arrête à **2024** (06).
- **Pièges** : **montants en milliers d'euros** ; slugs incohérents (06). **Modules** : Finances locales (position dans la strate) — non ingéré.

#### S34. TED — Tenders Electronic Daily (UE)
- **URL testée** : `POST https://api.ted.europa.eu/v3/notices/search` (200, sans clé) ; 58 379 avis FR publiés en 2026 ; largement **redondant avec BOAMP** (famille JOUE déjà incluse) ; vaut pour les eForms normalisés et la comparaison UE (02). **Modules** : Commande publique — non ingéré.

#### S35. Autres fonds DILA (echanges.dila.gouv.fr/OPENDATA/)
- **Testés le 19/08** : LEGI (consolidé, 18/08), Debats (AN 31/07 — vacances), COMPTES_DES_ASSOCIATIONS (19/08 14:29), **RefOrgaAdminEtat** (référentiel de l'organisation de l'État, flux quotidien 19/08 08:30 — utile pour la table des intitulés ministériels par période) (07). **DOLE** (dossiers législatifs) a été détaché sous **S43** le 22/08/2026 : S35 reste LEGI, Debats, RefOrgaAdminEtat, **toujours non ingéré**. Ne pas recycler `source_id='S35'` pour DOLE.
- **Licence** : fr-lo. **Modules** : Documents/JO (extensions) — non ingéré.

#### S36. API Légifrance via PISTE — optionnelle
- **Testé** : `POST https://oauth.piste.gouv.fr/api/oauth/token` → 400 `invalid_client` (endpoint vivant, OAuth2 client_credentials) ; **création de compte + CGU = one-shot humain ~10-15 min**, ensuite tout est automatisable ; **non nécessaire** au module Documents (les dumps DILA couvrent le besoin) (07).

#### S37. Décret annuel d'aide publique aux partis
- Décret n° 2026-149 du 03/03/2026 : **64 262 871,05 €** répartis en 2 fractions ; **Légifrance en 403 curl** (anti-bot), tableau dans le corps du décret, pas de CSV ; l'essentiel du besoin est couvert par les colonnes 103-104 de S25 (04). **Modules** : Financement de la vie politique — non ingéré.

*Ajouts du 19/08/2026 issus du contre-audit `10-critique-completude.md` (placés en fin de groupe pour ne pas renuméroter le catalogue) :*

#### S38. Avis et conseils de la CADA (ajout post-critique I1)
- **URL testée** (10-critique, appels n° 1 et 6, HTTP 200) : `https://www.data.gouv.fr/api/1/datasets/avis-et-conseils-de-la-cada/` — dataset « Avis et conseils de la CADA » (org. CADA) ; ressource « Ensemble consolidé des avis et conseils de la CADA » = **CSV 198,4 Mo (198 398 592 o), dernière modification 14/08/2026**, plus lots mensuels/trimestriels 2022-2024.
- **Licence** : fr-lo. **Intérêt** : sens des avis **par administration mise en cause** (qui refuse quoi) — alimente directement la « carte des verrous juridiques » du module Frais & train de vie et le lien avec Ma Dada (08 §1.2).
- **Pièges** : CSV de 198 Mo, dont la volumétrie exploitable **n'est pas mesurée à ce jour**. **Modules** : Frais & train de vie (boîte noire, carte des verrous) — **non ingérée au 19/08/2026** (aucun module ingéré n'en dépendait).
- **Évaluation du 20/08/2026 (CSV consolidé téléchargé et mesuré en entier)** : 60 941 lignes (57 385 avis, 3 553 conseils, 3 sanctions), 1984→2024 ; **93 % du fichier est du texte intégral** (176,6 Mio sur 189,2 Mio, mesuré colonne par colonne : 185 169 662 octets pour la seule colonne « Avis » sur 198 398 592) qui ne sera jamais ingéré (poids et prudence RGPD — les demandeurs sont anonymisés à la source, mais des noms de responsables publics subsistent dans les motifs). Piège décisif : le jeu est « modifié le 14/08/2026 » mais la **dernière séance date du 18/04/2024** — 28 mois de retard de versement, millésimes 2023-2024 vraisemblablement incomplets, à afficher tel quel. **INGÉRÉE le 20/08/2026** (pipeline `pipelines/ingest_cada.py`, P16), **en agrégats seulement** — sens × administration × année. Poids réel mesuré en base : **3,64 Mio** (`SELECT SUM(pgsize) FROM dbstat WHERE name LIKE '%cada%'` → 3 817 472 octets), conforme au budget annoncé. Volumes obtenus : **16 593 administrations distinctes** (après repli de la casse et des accents ; 16 984 graphies brutes), 32 614 lignes de saisines, 47 297 agrégats de sens, 2 034 lignes de motivations pour un vocabulaire de **89 motivations distinctes**. La colonne « Thème et sous thème » a été **écartée** : ses libellés contiennent le séparateur du champ (« Justice, Ordre Public Et Sécurité »), la découpe serait ambiguë et reconstituer la nomenclature reviendrait à l'inventer. Aucun référentiel d'administrations n'a été fabriqué (le champ est du texte libre sur 40 ans, plus de 10 000 libellés n'apparaissent qu'une fois) : seule une typologie par préfixe explicite est ajoutée, avec 23,2 % du corpus assumé « non classé » — détail et raisons dans `docs/SCHEMA-DB.md` § « Les tables `cada_*` ». `meta_sources.date_donnees` porte la dernière **séance** (18/04/2024), jamais la date de modification du dataset : S38 est donc en **ALERTE** dans `ft-fraicheur` (854 j pour des seuils de 730/820 j), ce qui rend le retard de versement visible au lieu de le masquer. Restitution : « carte des verrous » de la page `/frais`.

#### S39. Jaune « opérateurs de l'État » PLF 2026 (ajout post-critique I4)
- **Vérifié le 19/08/2026** (10-critique, appels n° 2 et 3) : dataset « PLF 2026, jaune opérateurs de l'État, liste des opérateurs et catégories » (data.gouv.fr, id `69665c766034b48d897c47be`), maj **13/01/2026** — **seule photographie 2026 du paysage des agences/opérateurs** (liste et catégories ; **pas les crédits par opérateur**). Retenu plutôt qu'écarté : le débat public 2026 sur les agences de l'État en fait un référentiel naturel.
- **Licence** : **confirmée le 20/08/2026** — la réponse API du dataset porte `"license": "lov2"` (Licence Ouverte 2.0).
- **Modules** : Dépenses de l'État (référentiel des opérateurs, complète l'encart de périmètre) — **non ingéré**.
- **Évaluation du 20/08/2026** : le **volet budgétaire n'existe pas en données structurées** — recherche data.gouv (9 résultats) et énumération des 606 jeux de data.economie : le dernier jeu financier des opérateurs est **PLF 2014** (166 lignes, grain programme et non opérateur × SCSP, figé en 2018) ; le jeu PLF 2019 répond 200 mais contient **0 enregistrement** (`total_count: 0` constaté) ; les jaunes PDF sont derrière l'anti-bot de budget.gouv.fr (groupe E). **Verdict : ne pas ingérer le volet budgétaire (il n'existe pas)** ; seule la liste 2026 (431 lignes, cp1252, aucun montant, 70 826 octets) peut servir de référentiel à coût quasi nul, adossée à un pipeline existant plutôt qu'un pipeline dédié ; re-vérifier chaque janvier si un jaune structuré paraît.

#### S40. Registre de transparence de l'Union européenne (évalué le 20/08/2026)
- **URL testée** (HTTP 200) : `https://data.europa.eu/api/hub/search/datasets/transparency-register` ; export XML intégral téléchargé et mesuré : **115 010 602 octets**, `<exportDate>` du 19/08/2026 (quotidien réel — la métadonnée DCAT, périmée de 2 ans, ne fait pas foi).
- **Licence** : la réponse API référence la **décision 2011/833/UE** (`COM_REUSE`, réutilisation y compris commerciale avec mention de source, sans clause de partage à l'identique) — compatible avec la Licence Ouverte 2.0 sous laquelle les agrégats sont republiés. Une note antérieure annonçait « CC BY 4.0 » : non confirmé par l'API.
- **Contenu mesuré** : 17 711 organisations inscrites dont **1 654 à siège en France** ; coûts de lobbying en fourchettes ; **aucune balise SIREN ni TVA** (77 balises inventoriées) → aucun rapprochement automatique possible avec le répertoire HATVP (S14), constat définitif.
- **Pièges éditoriaux (bloquants)** : lobbying UE et lobbying France sont **deux registres, deux cadres juridiques** — blocs jamais fusionnés, montants jamais comparés ; à titre d'illustration du contraste, 141 entités HATVP (sur 4 068) déclarent un niveau d'action « Européen » quand 1 654 organisations françaises sont inscrites à Bruxelles — **deux compteurs séparés, jamais un ratio**. Ne jamais ingérer le fichier des 8 927 accrédités (personnes physiques) ; exclure les 235 « Self-employed individuals » de toute restitution nominative. Parseur tolérant XML 1.1 ; fraîcheur lue dans `<exportDate>`.
- **Verdict : périmètre minimal cloisonné** (organisations seulement, +2 à 5 Mo en base). **Modules** : Lobbying.

**INGÉRÉE le 20/08/2026 — pipeline P16 `pipelines/ingest_registre_ue.py`.** Ce qui a été fait, et ce qui a été mesuré à cette occasion :
- **Volumétrie re-mesurée sur l'export du 19/08/2026** (115 010 602 octets, `<exportDate>` = 2026-08-19, `<numberOfIR>` = 17 711) : **17 711 inscrits**, dont **1 654 à siège en France** (3ᵉ pays derrière la Belgique, 2 761, et l'Allemagne, 2 185), dont **235 « Self-employed individuals »** au total et **16 côté France**. Le fichier annonçant lui-même son compte, le pipeline compare les deux et échoue franchement en cas d'écart : une troncature de téléchargement ne peut pas passer pour une baisse de volume.
- **Parseur** : l'export est déclaré `version='1.1'`, que la bibliothèque standard refuse, ET contient **8 références de caractères de contrôle légales en XML 1.1 mais interdites en XML 1.0** (`&#x2;` ×5, `&#xb;` ×2, `&#x1d;` ×1) — rebaptiser la déclaration en 1.0 ne suffit donc pas, le parseur échoue ensuite sur ces références. `flux_xml_tolerant()` réécrit la déclaration et retire ces références **en flux** (jamais 115 Mo en mémoire), en ne coupant jamais un bloc au milieu d'une référence. Les références légales partout (`&#xd;`, ×62 433) sont conservées telles quelles.
- **Fraîcheur** : lue dans `<exportDate>`, jamais dans la métadonnée DCAT du catalogue. Seuils `S40 |jc|6|12|20` — jours **calendaires** et non ouvrés, contrairement à S4 : le calendrier des jours fériés français ne gouverne pas un export produit par le secrétariat commun Parlement européen / Commission.
- **Tables** `ue_registre_organisations`, `ue_registre_agg_categories`, `ue_registre_agg_pays`, `ue_registre_agg_interets`, `ue_registre_agg_couts` — préfixe `ue_registre_`, jamais `lobby_`. **+4 427 776 octets en base** (4,2 Mio), dans la fourchette annoncée. Colonnes volontairement écartées après mesure : `goals` (630 o de moyenne, ~11 Mo), forme juridique, site web, bureau de liaison UE, niveaux d'intérêt — 2,1 Mo pour des champs qu'aucune restitution n'emploie.
- **Ce qui n'est PAS ingéré** : le second export du registre (8 927 personnes physiques accréditées auprès du Parlement européen) n'est ni téléchargé ni écrit. Les 235 travailleurs indépendants sont comptés dans les agrégats et **exclus de la table nominative** ; l'écart est publié (`ue_registre_agg_pays.nb_personnes_physiques`) et affiché sur la page, pas dissimulé.
- **Restitution** : bloc cloisonné en bas de `/lobbying`, séparé par une frontière explicite, avec son propre badge de fraîcheur et son propre cadrage. Les **deux compteurs sont posés côte à côte** (141 entités HATVP déclarant un niveau « Européen » sur 4 068 ; 1 654 organisations françaises inscrites à Bruxelles sur 17 711) avec la mention écrite qu'ils ne recouvrent pas le même ensemble — **aucun ratio n'est calculé entre eux**. La liste nominative complète (1 638 organisations) vit dans le fragment `/data/registre-ue/organisations.json`, chargé au clic : `/lobbying` est la page la plus lourde du site.

#### S41. Encours de dette des APU au sens de Maastricht (Eurostat `gov_10q_ggdebt`, évalué le 22/08/2026)
- **Producteur** : Eurostat (ESTAT). Datacode `gov_10q_ggdebt`. **URL** (DOI, stable) : `https://doi.org/10.2908/GOV_10Q_GGDEBT`. API filtrée (re-fetch à chaque ingestion, pas une constante figée) : `geo=FR`, `sector=S13`, `na_item=GD`, `unit=MIO_EUR`.
- **Licence relue** (copyright-notice Eurostat, HTTP 200 le 22/08/2026) : **décision 2011/833/UE** — « Reuse of statistical data … commercial or non-commercial … source is acknowledged ». Libellé `meta_sources` : `Décision 2011/833/UE (réutilisation des données statistiques Eurostat)`. **Pas CC BY 4.0** (le CC BY 4.0 de la même page couvre le contenu éditorial du site, pas les données statistiques). La France est un État membre de l'UE : l'exception « pays tiers, réutilisation commerciale » ne s'applique pas à l'extrait `geo=FR`.
- **Fréquence** : trimestrielle (~t+113 jours après la fin du trimestre). **Date des données** = dernier jour du TIME max (ex. 2026-Q1 → 2026-03-31), **jamais** le champ JSON-stat `updated` (date de diffusion).
- **Piège S13** : le secteur ESA **S13** = administrations publiques (APU : État, Odac, APUL, ASSO). La source France Transparence **S13** = situations mensuelles budgétaires DGFiP (État, flux). `source_id` Eurostat = **S41**, jamais `'S13'`. Ne pas écrire « dette de l'État » pour ce chiffre : ce n'est pas le sous-secteur S.1311, et ce n'est pas la ligne DGFiP « Charges de la dette de l'État » (intérêts, cumul YTD).
- **Piège d'unité** : native **MIO_EUR** (millions d'euros). Conversion Md€ = MIO_EUR **÷ 1000** à la lecture. Jamais ÷ 1e9 (unité des flux S13, en euros). Pas de `PC_GDP`, pas de montant par habitant, pas d'autre `na_item` que GD (pas de déficit).
- **Modules** : Dépenses de l'État (bloc cloisonné après la décomposition par titre). **INGÉRÉE** — pipeline P17 `pipelines/ingest_dette_maastricht.py`.

#### S42. Déficit public des APU au sens de Maastricht (Eurostat `gov_10dd_edpt1`, évalué le 22/08/2026)
- **Producteur** : Eurostat (ESTAT). Datacode `gov_10dd_edpt1`. **URL** (DOI, stable) : `https://doi.org/10.2908/GOV_10DD_EDPT1`. API filtrée (re-fetch à chaque ingestion) : `geo=FR`, `sector=S13`, `na_item=B9`, deux extraits `unit=MIO_EUR` et `unit=PC_GDP`.
- **Licence relue** (copyright-notice Eurostat, HTTP 200 le 22/08/2026) : **décision 2011/833/UE** — « Reuse of statistical data … commercial or non-commercial … source is acknowledged ». Libellé `meta_sources` : `Décision 2011/833/UE (réutilisation des données statistiques Eurostat)`. **Pas CC BY 4.0** (le CC BY 4.0 de la même page couvre le contenu éditorial du site, pas les données statistiques).
- **Fréquence** : annuelle (notification EDP d'avril, TIME = année civile). **Date des données** = 31 décembre du TIME max (ex. 2025 → 2025-12-31), **jamais** le champ JSON-stat `updated` (date de diffusion : 2026-04-22 pour le millésime 2025).
- **Objet** : `na_item=B9` = capacité (+) / besoin (−) de financement des administrations publiques. Un B9 négatif est un déficit ; un B9 positif est un excédent. Ce n'est **pas** le solde du budget général (S13, DGFiP, flux de l'État, cumul YTD). Ce n'est **pas** l'encours de dette (S41, na_item=GD, stock trimestriel). `source_id` = **S42**, jamais `'S13'` ni `'S41'`.
- **Piège d'unité** : native **MIO_EUR**. Conversion Md€ = MIO_EUR **÷ 1000** à la lecture. Jamais ÷ 1e9. `PC_GDP` est le pourcentage du PIB, lu à part et affiché comme un fait ; **jamais comparé au seuil de 3 %** (aucun écart, aucun coloriage). Pas de montant par habitant, pas de série trimestrielle (`gov_10q_ggnfa`), pas de sous-secteur S.1311.
- **Modules** : Dépenses de l'État (bloc cloisonné après l'encours S41). **INGÉRÉE** — pipeline P18 `pipelines/ingest_deficit_maastricht.py`.

#### S43. DILA — dossiers législatifs (DOLE, évalué le 22/08/2026 ~22:30 CEST)
- **Producteur** : DILA. Organisation data.gouv : **Premier ministre**. Dataset slug `dole-les-dossiers-legislatifs`. **URL** (index Apache, sans authentification) : `https://echanges.dila.gouv.fr/OPENDATA/DOLE/` (HTTP 200, charset ISO-8859-1, mesuré le 22/08/2026 ~22:30 CEST). Catalogue : `https://www.data.gouv.fr/datasets/dole-les-dossiers-legislatifs`.
- **Licence relue** (data.gouv `license: fr-lo` ; page `https://www.data.gouv.fr/pages/legal/licences/etalab-2.0` = Licence Ouverte 2.0 ; PDF DILA du 18/10/2018 « licence ouverte v2.0 ») : **Licence Ouverte 2.0**, paternité DILA + URL + nom de fichier. Libellé `meta_sources` : `Licence Ouverte 2.0`.
- **Fréquence** : jusqu'à 5 livraisons/semaine (fiche producteur). Le 22/08/2026 ~22:30 CEST : Freemium `Freemium_dole_global_20250713-140000.tar.gz` **18 698 444 o**, Last-Modified 13 Jul 2025, 3411 XML ; **240 incréments** postérieurs, dernier `DOLE_20260820-220411.tar.gz` (20/08 22:12) ; gap max observé **12 j**. Ces volumes dérivent.
- **Date des données** = max(`DATE_DERNIERE_MODIFICATION`) des dossiers écrits (**2026-08-20** ce soir-là). **Jamais** le `last_update` data.gouv (catalogue en retard : 2026-08-15 ce soir-là).
- **Rebuild last-write-wins** (mesuré le 22/08/2026 ~22:30 CEST) : **3578 dossiers uniques** (3411 + 167 nouveaux, 1226 mises à jour), 0 parse fail. TYPES ce jour-là : 1245 LOI_PUBLIEE, 1136 ORDONNANCE_PUBLIEE, 692 PROJET_LOI, 500 PROPOSITION_LOI, 3 TYPE vide (lois 2008), 2 PROJET_ORDONNANCE. Législature de numéro max (17, **jamais en dur**) : 332 dossiers dont 190 en navette (TYPE ouvert). 1194 « TYPE ouvert » toutes législatures : **ne pas les appeler « en cours »**.
- **Pièges** : `source_id` = **S43**, jamais `'S35'` (seau LEGI/Debats/RefOrgaAdminEtat, toujours non ingéré) ni `'S3'` (JORFSIMPLE, fenêtre 30 JO — un dossier législatif vit des mois et serait purgé). TYPE n'est pas « en navette aujourd'hui » : un PROJET_LOI d'une législature close reste typé projet. Navette affichée = type ∈ {PROJET_LOI, PROPOSITION_LOI, PROJET_ORDONNANCE} **ET** législature = max(legislature_num). TYPE vide est **licite** (trois lois 2008) — on ne le déduit pas du titre. N'ingère **pas** l'exposé des motifs ni les HTML d'échéancier : métadonnées + dernière étape (LIEN directs de ARBORESCENCE). Stock + incréments rejouable (Freemium ~19 Mo, pas 1 Go comme JORF).
- **Modules** : Documents/JO. **INGÉRÉE** — pipeline P19 `pipelines/ingest_dole.py`.

#### S44. Recettes et dépenses des APU (agrégats ESA, Eurostat `gov_10a_main`, évalué le 23/08/2026)
- **Producteur** : Eurostat (ESTAT). Datacode `gov_10a_main`. Label EN : *Government revenue, expenditure and main aggregates*. Label FR : *Principaux agrégats des administrations publiques, y compris recettes et dépenses*. **URL** (DOI, stable) : `https://doi.org/10.2908/GOV_10A_MAIN` → `https://ec.europa.eu/eurostat/databrowser/product/page/GOV_10A_MAIN`. API filtrée (re-fetch à chaque ingestion, pas une constante figée) : `geo=FR`, `sector=S13`, `na_item=TE` et `na_item=TR`, deux extraits `unit=MIO_EUR` et `unit=PC_GDP`. Re-fetch HTTP 200 le 23/08/2026, exemple : `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10a_main?format=JSON&geo=FR&sector=S13&na_item=TE&unit=MIO_EUR&lang=EN`.
- **Licence relue** (copyright-notice Eurostat `https://ec.europa.eu/eurostat/web/main/help/copyright-notice`, HTTP 200 le 23/08/2026) : **décision 2011/833/UE** du 12 décembre 2011 — « Reuse of statistical data … commercial or non-commercial … source is acknowledged ». Libellé `meta_sources` : `Décision 2011/833/UE (réutilisation des données statistiques Eurostat)`. **Pas CC BY 4.0** (le CC BY 4.0 de la même page couvre le contenu éditorial du site, pas les données statistiques).
- **Fréquence** : annuelle (TIME = année civile). **Date des données** = 31 décembre du TIME max (ex. 2025 → 2025-12-31), **jamais** le champ JSON-stat `updated` (date de diffusion : 2026-07-21T11:00:00+0200 pour le millésime mesuré le 23/08). Seuils de fraîcheur **520/600** jours calendaires, comme S42.
- **Objet** : `na_item=TE` = « Total des dépenses des administrations publiques » ; `na_item=TR` = « Total des recettes des administrations publiques ». Secteur ESA S13 FR = « Administrations publiques ». Ce n'est **pas** l'exécution YTD du budget général (S13, DGFiP, flux de l'État). Ce n'est **pas** l'encours de dette (S41, na_item=GD). Ce n'est **pas** le déficit (S42, na_item=B9). TE et TR **ne sont pas** des agrégats Maastricht — Maastricht est réservé à GD/B9. `source_id` = **S44**, jamais `'S13'` ni `'S41'` ni `'S42'`.
- **Piège S13** : le secteur ESA **S13** = administrations publiques (APU : État, Odac, APUL, ASSO). La source France Transparence **S13** = situations mensuelles budgétaires DGFiP (État, flux). Ne pas écrire « dette de l'État » pour un chiffre APU : ce n'est pas le sous-secteur S.1311, et ce n'est pas une ligne DGFiP.
- **Piège d'unité** : native **MIO_EUR** (millions d'euros). Conversion Md€ = MIO_EUR **÷ 1000** à la lecture. Jamais ÷ 1e9 (unité des flux S13, en euros). `PC_GDP` est le pourcentage du PIB, lu à part. Pas de montant par habitant, pas de sous-secteur S.1311.
- **Hors périmètre de S44** : la ventilation CFAP est **S49** (`gov_10a_exp`, millésime 2024 au 25/08/2026 ; TIME 2025 listé, 0 valeur FR). `taxag` 2025 = 0 — **non ingéré**, et **ne pas l'appeler prélèvements obligatoires** (le PO officiel est **S50**, tableau INSEE 3.216). La décomposition par sous-secteur est **S50**. S44 n'ingère pas COFOG.
- **Recomposition** : le site **ne recalcule pas B9**. Le 23/08/2026, TR 2025 − TE 2025 = 1 561 626,1 − 1 714 137,2 = −152 511,1 ≈ S42 B9 −152 511,0 (arrondi). **S42 reste la source du déficit**.
- **Relevé daté du 23/08/2026** (re-fetch HTTP 200 ; `n_values` 31 par extrait ; TIME 1975–2025 dans la dimension, observations à partir de 1995) : TE 2025 = 1 714 137,2 MIO_EUR / 57,2 PC_GDP ; TE 2024 = 1 672 708,2 / 57,0 ; TR 2025 = 1 561 626,1 MIO_EUR / 52,1 PC_GDP ; TR 2024 = 1 503 590,1 / 51,2. Ces montants décrivent ce jour-là et **dérivent** : ce n'est pas une constante du document.
- **Modules** : `/depenses` (bloc TE) et `/recettes` (bloc TR). **INGÉRÉE** — pipeline P20 `pipelines/ingest_agregats_apu.py`.

#### S45. Prestations de protection sociale (DREES, comptes de la protection sociale, évalué le 23/08/2026)
- **Producteur** : DREES (ministère des Solidarités et de la Santé). Jeu ODS `305_les-comptes-de-la-protection-sociale`. **URL dataset** : `https://www.data.gouv.fr/datasets/les-comptes-de-la-protection-sociale` (HTTP 200 le 23/08/2026). **Export** (bulk `/exports/json`, pas le plafond `/records`) : `https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/305_les-comptes-de-la-protection-sociale/exports/json` (HTTP 200 le 23/08/2026, **15 654** enregistrements, années **1959–2024**).
- **Licence relue** (23/08/2026) : métadonnées DREES « Licence Ouverte v2.0 (Etalab) » ; fiche data.gouv « Licence Ouverte / Open Licence version 2.0 » HTTP 200 ; texte légal `https://www.data.gouv.fr/pages/legal/licences/etalab-2.0` HTTP 200. Libellé `meta_sources` : `Licence Ouverte 2.0 (Etalab)`.
- **Fréquence** : annuelle. **Date des données** = 31 décembre de l'année max (**2024-12-31** au 23/08/2026), **jamais** `last_update` data.gouv (2025-12-18) ni `modified` du catalogue.
- **Objet** : flux annuel des **prestations** (ps_code E11), tous régimes (si_code S1). Ce n'est **pas** le budget général (S13), **pas** le total des dépenses des APU (S44, TE), **pas** le bilan patrimonial (S22), **pas** la LFSS (loi votée, non ingérée), **pas** ESSPROS (Eurostat `spr_exp_func`, non ingéré — recoupement seulement). `source_id` = **S45**.
- **Règle du total** : grain `total` = si_niveau=0, si_code=S1, ps_niveau=0, ps_code=E11-0. Unité native = million d'euros (`val`). Md€ = M€ **÷ 1000** à la lecture, jamais ÷ 1e9. Pas de % du PIB, pas de par habitant, pas de recettes, pas de frais de gestion.
- **Relevé daté du 23/08/2026** (export JSON HTTP 200) : total 2024 S1/E11-0 = 932 548,27 M€ (= 932,5 Md€). Six risques à ps_niveau=1, si_code=S1, somme exacte 932 548,27 : SANTÉ 338 880,82 ; VIEILLESSE-SURVIE 426 665,30 ; FAMILLE 65 806,89 ; EMPLOI 51 123,85 ; LOGEMENT 16 058,54 ; PAUVRETÉ-EXCLUSION SOCIALE 34 012,87. Neuf régimes à si_niveau=1, ps_code=E11-0, même somme, dont S13141 régime général 582 377,05 M€. Recoupement Eurostat `spr_exp_func` TOTAL 2024 = 932 548,26 M€ — **non ingéré**. Ces montants décrivent ce jour-là et **dérivent**.
- **Pièges** : les niveaux 2 et 3 recouvrent les niveaux 0 et 1 — n'ingérer que les grains exclusifs (`total` / `risque` / `regime`) ; S13141 (régime général) n'est **pas** l'ensemble de la sécurité sociale (S13142 existe à côté) ; `last_update` 2025-12-18 n'est pas `date_donnees` ; unité = million d'euros, pas l'euro ; ce n'est pas la LFSS. Ne pas nommer ce chiffre « dette de l'État ».
- **Modules** : Dépenses de l'État (bloc cloisonné). **INGÉRÉE** — pipeline P22 `pipelines/ingest_protection_sociale.py`.

#### S46. Recettes du budget général au PLF (État A, évalué le 24/08/2026)
- **Producteur** : Direction du Budget. Jeu ODS `plf25-recettes-du-budget-general`. **URL dataset** : `https://data.economie.gouv.fr/explore/dataset/plf25-recettes-du-budget-general/` (HTTP 200 le 24/08/2026). **Export CSV** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plf25-recettes-du-budget-general/exports/csv` (HTTP 200 le 24/08/2026, **19 865 o**, **156** lignes, UTF-8 BOM, séparateur `;`).
- **Licence relue** (24/08/2026) : fiche ODS `license: Licence Ouverte v2.0 (Etalab)`, HTTP 200. Libellé `meta_sources` : `Licence Ouverte 2.0 (Etalab)`.
- **Fréquence** : annuelle (open data du PLF). **Date des données** = jour de publication de *ce* jeu (**2024-10-11** pour 2025, `created`/`modified` ODS mesurés le 24/08). Ce n'est **pas** le dépôt parlementaire (AN, texte n° 324, **10/10/2024**). Un millésime nouveau sans date écrite dans le pipeline fait échouer l'ingestion : on ne relit pas `modified` à chaque run. Seuils **400/440** jours calendaires, comme S21 : aucune édition PLF 2026 en données (préfixe `plf26` = 0 le 24/08 ; seul `plf-2026-budget-vert`).
- **Objet** : État A du **Projet** de loi de finances, recettes **brutes** du budget général, année civile. Quatre types mesurés le 24/08 : Recettes fiscales (67, 500,349 Md€) ; Recettes non fiscales (56, 20,549 Md€) ; PSR collectivités (32, 44,189 Md€) ; PSR UE (1, 23,321 Md€). 156 codes uniques, 0 doublon, 17 zéros publiés, 0 négatif. `source_id` = **S46**, jamais `'S13'`.
- **Ce que la page affiche** : le détail des **non fiscales** (le trou de S13) et, parmi elles, les lignes **2110, 2116, 2199** (produits des participations / dividendes, 5,954 Md€ au 24/08). Les fiscales brutes et les PSR sont ingérés, pas additionnés à S13.
- **Pièges** : brutes ≠ nettes S13 (TVA PLF 189,9 Md€ vs TVA S13 2025 98,1 Md€) ; projet ≠ exécution (non fiscales PLF 20,5 Md€ vs S13 2025-12-31 24,0 Md€) ; pas la LFI ; pas 2026 ; pas le rapport APE (aucun jeu APE sur data.gouv / data.economie le 24/08) ; PSR ≠ encaissement conservé ; un zéro publié est un zéro ; Md€ = euros ÷ 1e9, jamais ÷ 1000. Un millésime nouveau sans date écrite dans `DATES_PUBLICATION` fait échouer l'ingestion.
- **Relevé daté du 24/08/2026** (export CSV HTTP 200) : non fiscales 20 548 548 212 € dont 2110 = 1 467 M€, 2116 = 4 472 M€, 2199 = 15 M€. Ces montants décrivent ce jour-là et **dérivent**.
- **Modules** : `/recettes` (bloc cloisonné). **INGÉRÉE** — pipeline P23 `pipelines/ingest_recettes_plf.py`.

#### S47. IRCOM — impôt sur le revenu par collectivité territoriale (évalué le 24/08/2026)
- **Producteur** : DGFiP / DESF (ministères économiques et financiers). Jeu data.gouv `limpot-sur-le-revenu-par-collectivite-territoriale-ircom` (id `536998cba3a729239d20505e`). **URL dataset** : `https://www.data.gouv.fr/datasets/limpot-sur-le-revenu-par-collectivite-territoriale-ircom` (HTTP 200 le 24/08/2026). Ressource zip du millésime courant (IRCOM 2025 = revenus 2024, 18 181 698 o, last_modified 2026-05-26), fichier `ircom_communes_complet_revenus_2024.xlsx`. Le miroir data.economie `limpot-sur-le-revenu-par-collectivite-territoriale0` est **figé** (modified 2018-12-13, 0 enregistrement) : ce n'est pas la source.
- **Licence relue** (24/08/2026) : fiche data.gouv identifiant `fr-lo`, libellé affiché « Licence Ouverte / Open Licence », HTTP 200. Libellé `meta_sources` : `Licence Ouverte / Open Licence`.
- **Fréquence** : annuelle (campagne IRCOM N+1 sur les revenus N, publication ~mai N+2). **Date des données** = 31 décembre de l'année des revenus (**2024-12-31** au 24/08/2026), **jamais** `last_update` data.gouv (2026-05-26). Seuils **650/750** jours calendaires, comme S22/S45.
- **Objet** : impôt net **sur rôle** des foyers fiscaux, par commune de résidence. Notice DESF (4 p., 26/05/2026) : payé ou restitué, hors crédit d'impôt PFU, CEHR incluse. `n.c.` = secret statistique. Un négatif est une restitution. `source_id` = **S47**, jamais `'S13'`.
- **Ce que la page affiche** : somme des communes dont l'impôt net n'est pas n.c., nombre de foyers, départements (Paris/Lyon/Marseille = arrondissements ramenés à 75/69/13). Tranches de RFR, salaires et pensions **non ingérés**. 0 page communale.
- **Pièges** : unité native = milliers d'euros (stockée en euros, × 1000) ; B31 (Autres / DINR / SPM) dans le total national, pas sur la carte ; codes B 754/757 pour Paris 1er/16e — le code commune (101–120) tranche ; ce n'est pas l'IR de caisse S13 (87,99 Md€ d'exécution 2024 vs ~91,7 Md€ d'impôt net publié IRCOM le 24/08 — deux objets, on n'additionne pas).
- **Relevé daté du 24/08/2026** (xlsx HTTP 200) : 35 156 lignes Total, 162 n.c. sur l'impôt net, 158 restitutions (négatifs), 41 634 350 foyers, somme des communes publiées 91,679 Md€. Ces montants décrivent ce jour-là et **dérivent**.
- **Modules** : `/recettes` (bloc cloisonné). **INGÉRÉE** — pipeline P24 `pipelines/ingest_ircom.py`.

#### S48. REI — fiscalité directe locale (évalué le 24/08/2026)
- **Producteur** : DGFiP / DESF (ministères économiques et financiers). Jeu data.gouv `impots-locaux-fichier-de-recensement-des-elements-dimposition-a-la-fiscalite-directe-locale-rei-4` (id `6657c57abbefc8869c7c6364`). **URL dataset** : `https://www.data.gouv.fr/datasets/impots-locaux-fichier-de-recensement-des-elements-dimposition-a-la-fiscalite-directe-locale-rei-4` (HTTP 200 le 24/08/2026). Ressource zip du millésime courant (`REI-2025-fichier-notice-trace.zip`, 18 486 782 o). Le jeu ODS tableur du même slug a **0 enregistrement** : les données sont dans les pièces jointes. Les jeux « fiscalité locale des particuliers / professionnels » sont des **taux**, pas des produits.
- **Licence relue** (24/08/2026) : fiche data.gouv « Licence Ouverte / Open Licence version 2.0 » HTTP 200 ; fiche data.economie `Licence Ouverte v2.0 (Etalab)` HTTP 200. Libellé `meta_sources` : `Licence Ouverte / Open Licence version 2.0`.
- **Fréquence** : annuelle. **Date des données** = 31 décembre de l'année d'imposition (**2025-12-31** au 24/08/2026), **jamais** `last_update` data.gouv (2026-05-11) ni last-modified du zip. Seuils **650/750** jours calendaires, comme S22/S45/S47.
- **Objet** : impositions primitives du **rôle général**, par taxe et par collectivité bénéficiaire. Ce n'est **pas** le compte OFGL (S16), **pas** l'IRCOM (S47), **pas** la caisse S13. `source_id` = **S48**.
- **Ce que la page affiche** : TFPB (somme E13+E23+E33 des communes non occultées), total FDL (TFPB, TFPNB, THS, THLV, CFE, TEOM F13, TASCOM, IFER, TSE, GEMAPI, TASA, TAFNB, TSC), détail par taxe, TFPB par département. 0 page communale. 0 taux. TIEOM* (part incitative) non additionné : déjà dans F13.
- **Pièges** : IFERREG répliqué sur chaque commune d'une région (une valeur par LIBREG) ; P33 est le total CFE intercommunal (P33_1/P33_2 non additionnés) ; F13 est le TEOM total (F23–F83 **et** TIEOM* non additionnés — TIEOM = 10–45 % de F13, CGI 1522 bis) ; cellule vide = secret statistique, pas un zéro ; compensations/fractions de TVA **non ingérées** ; chambres **non ingérées** ; TFPB publié ≠ 55,1 Md€ « dus y compris annexes et frais d'État » ; FDL REI ≠ agrégat comptable « Impôts locaux » OFGL (54,9 Md€ communes BP). Unité native = euros. Md€ = euros ÷ 1e9.
- **Relevé daté du 24/08/2026** (CSV HTTP 200, 34 907 communes) : TFPB 42,961 Md€ ; TEOM F13 9,164 Md€ ; CFE 8,221 Md€ ; THS 2,583 Md€. Ces montants décrivent ce jour-là et **dérivent**.
- **Modules** : `/collectivites` (bloc cloisonné). **INGÉRÉE** — pipeline P25 `pipelines/ingest_rei.py`.

#### S49. Dépenses des APU par fonction (Eurostat `gov_10a_exp`, CFAP / COFOG-99, évalué le 25/08/2026)
- **Producteur** : Eurostat (ESTAT). Datacode `gov_10a_exp`. Label FR : *Dépenses des administrations publiques par fonction (CFAP)*. **URL** (DOI, stable) : `https://doi.org/10.2908/GOV_10A_EXP` → `https://ec.europa.eu/eurostat/databrowser/product/page/GOV_10A_EXP`. API filtrée : `geo=FR`, `sector=S13`, `na_item=TE`, `cofog99` ∈ {TOTAL, GF01…GF10}, `unit=MIO_EUR` et `unit=PC_GDP`, `lang=FR`. Re-fetch HTTP 200 le 25/08/2026.
- **Licence relue** (copyright-notice Eurostat `https://ec.europa.eu/eurostat/web/main/help/copyright-notice`, HTTP 200 le 25/08/2026) : **décision 2011/833/UE** du 12 décembre 2011 — « Reuse of statistical data … commercial or non-commercial … source is acknowledged ». Libellé `meta_sources` : `Décision 2011/833/UE (réutilisation des données statistiques Eurostat)`. **Pas CC BY 4.0** (le CC BY 4.0 de la même page couvre le contenu éditorial du site, pas les données statistiques). EUR-Lex CELEX:32011D0833 a répondu HTTP 202 vide depuis cette machine : seconde porte = copyright-notice, comme S41/S42/S44.
- **Fréquence** : annuelle (TIME = année civile). **Date des données** = 31 décembre du TIME max de TOTAL (**2024-12-31** au 25/08/2026), **jamais** le champ JSON-stat `updated` (2026-07-21T11:00:00+0200) ni OBS_PERIOD_OVERALL_LATEST (2025 listé, **0 valeur FR**). Seuils **650/750** jours calendaires, comme S45 : millésime 2024 encore servi en 2026. 520/600 (S44) sonnerait dès que 2025 manque, alors que S44 porte déjà 2025.
- **Objet** : `na_item=TE` ventilé en TOTAL + dix divisions CFAP (GF01–GF10), ordre du producteur. Secteur ESA S13 FR = administrations publiques. Ce n'est **pas** l'exécution YTD du budget général (S13). Ce n'est **pas** le total TE de `gov_10a_main` (S44, table distincte). Ce n'est **pas** les prestations DREES (S45). `source_id` = **S49**.
- **Piège S44** : jusqu'en 2022 les totaux coïncident à l'arrondi près ; en 2024, TE `gov_10a_main` = 1 672 708,2 MIO_EUR et TOTAL CFAP = 1 671 793,8 MIO_EUR (écart 914,4 M€, 0,055 %, mesuré le 25/08/2026, même `updated` 21/07). On n'additionne pas, on ne « ventile » pas S44. TIME max S49 = 2024, TIME max S44 = 2025.
- **Piège d'unité** : native **MIO_EUR**. Md€ = MIO_EUR **÷ 1000**. Jamais ÷ 1e9. `PC_GDP` lu à part, **non additif** (somme des divisions 57,2 vs TOTAL 57,3 en 2024). Pas de montant par habitant, pas de sous-secteur S.1311.
- **Additivité** : somme GF01–GF10 = TOTAL à 0,2 M€ près en 2024 (tolérance d'ingestion 1 M€). Les groupes (GF0101…) recouvrent les divisions : **non ingérés**.
- **Relevé daté du 25/08/2026** (re-fetch HTTP 200, 330 observations TE MIO, 1995–2024) : TOTAL 2024 = 1 671 793,8 MIO_EUR / 57,3 PC_GDP. GF10 Protection sociale 693 028,8 / 23,7 ; GF07 Santé 261 156,3 / 8,9 ; GF01 Services généraux 181 103,2 / 6,2 ; GF04 Affaires économiques 166 072,8 / 5,7 ; GF09 Enseignement 148 639,6 / 5,1. 2025 : 0 valeur FR. Ces montants décrivent ce jour-là et **dérivent**.
- **Modules** : `/depenses` (bloc cloisonné). **INGÉRÉE** — pipeline P26 `pipelines/ingest_cofog_apu.py`.

#### S50. Comptes des APU (INSEE, Insee Résultats 8988845, évalué le 25/08/2026)
- **Producteur** : INSEE. Comptes nationaux annuels, base 2020. **URL** : `https://www.insee.fr/fr/statistiques/8988845?sommaire=8988934`. Fichiers : `https://www.insee.fr/fr/statistiques/fichier/8988845/t_32xx_fr.xlsx`. Cube homologue Melodi `DD_CNA_APU` (`https://api.insee.fr/melodi/catalog/DD_CNA_APU`, modified 2026-06-08 — **jamais** `date_donnees`). Re-fetch HTTP 200 le 25/08/2026 (UA projet).
- **Licence relue** (25/08/2026) : catalogue INSEE `https://www.insee.fr/fr/information/8184173` — « Les jeux de données sont mis à disposition sous les termes de la licence Licence Ouverte / Open License ». Texte légal : `https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/` (HTTP 200). Libellé `meta_sources` : `Licence Ouverte 2.0 (Etalab)`. **Pas** la décision 2011/833/UE.
- **Fréquence** : annuelle (année des comptes). **Date des données** = 31 décembre de l'année max (**2025-12-31** au 25/08/2026), **jamais** `modified` Melodi ni la parution Insee Résultats (29/05/2026). Seuils **520/600** jours calendaires, comme S44 (millésime 2025 déjà là ; 400/440 sonnerait dès février, avant mai N+1).
- **Objet** : totaux de dépenses et de recettes des tableaux 3.201 (S13), 3.202 (S1311), 3.203 (État S13111), 3.205 (S1313), 3.212 (S1314) ; prélèvements obligatoires du tableau 3.216 (S13 et S212, plus sous-secteurs). Unité native **Md€** (et % du PIB pour le PO). `source_id` = **S50**.
- **Hors périmètre** : solde B9NF (**non ingéré** — ce serait republier S42) ; Maastricht ; CFAP ; taxag ; communes / départements / régions des tableaux 3.207–3.210.
- **Pièges** : les sous-secteurs **ne s'additionnent pas** au S13 (consolidations distinctes, note 3.215). Le total S13 2025 (1 714,2 Md€ de dépenses) est proche du TE S44 2025 (1 714 137,2 MIO_EUR) : table distincte, on ne ventile pas S44. S1311 n'est pas « la dette de l'État » ni le budget général. S1314 n'est pas « la Sécu ». Le PO 2025 (1 305,1 Md€ / 43,6 % du PIB) n'est pas TR S44.
- **Relevé daté du 25/08/2026** (xlsx HTTP 200) : S13 dépenses 1 714,2 Md€ / recettes 1 561,7 Md€ ; S1311 681,1 / 550,8 ; S13111 607,7 / 479,6 ; S1313 335,5 / 319,9 ; S1314 803,3 / 796,6 ; PO S13+S212 1 305,067 Md€ / 43,63 % du PIB. Ces montants décrivent ce jour-là et **dérivent**.
- **Modules** : `/depenses` (sous-secteurs) et `/recettes` (PO). **INGÉRÉE** — pipeline P27 `pipelines/ingest_comptes_apu_insee.py`.

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

> **Encart de périmètre « argent public » (obligatoire, affiché sur l'Accueil et dans API & Données)** : le dashboard couvre le **budget général de l'État**, le **Parlement et la vie politique** (élus, lobbying, financement), la **commande publique**, les **finances locales**, et les **prestations de protection sociale** (DREES, tous régimes, millésime porté par la tuile — S45). Ce n'est **pas** la LFSS comme loi votée, **pas** la dépense propre des **opérateurs de l'État** (seuls leurs crédits budgétaires apparaissent via S20/S21 ; référentiel S39 non ingéré) et **pas** les **entreprises publiques**. Tout compteur global du budget général porte la mention « budget général de l'État » — jamais « la dépense publique » (10-critique I8) ; le total S45 porte « prestations de protection sociale », jamais « la Sécu » ni « dette de l'État ».

### Accueil synthétique
- **Sources** : S13 (compteur dépenses État), S1 (flux marchés + carte 30 j), S2 (nb d'AO en cours), S3 (derniers textes JO), S14 (compteur d'alertes HATVP), S17/S4 (bandeau de stats), S20 (top missions).
- **Fraîcheur affichable** : « Dépenses de l'État : données au 30/06/2026 (publication mensuelle DGFiP) » (01) · « Marchés publics : mise à jour quotidienne, notifications jusqu'à la veille — **en cours de consolidation** (latence légale de publication jusqu'à 2 mois) » (02) · « Journal officiel du 19/08/2026 » (07) · « Déclarations HATVP : mise à jour hebdomadaire » (04). La mention « en cours de consolidation » accompagne le flux marchés **partout où il apparaît** (10-critique M3).
- **Contenu concret** : compteur « dépenses de l'État depuis le 1er janvier » (cumul mensuel, ex. réel : 195,0 Md€ de dépenses nettes du BG au 31/05/2026, 01) avec variation vs même période 2025 ; donut par grands postes (titres, S13) ; top missions (S20, annuel, mention PLF) ; carte de France des marchés notifiés sur 30 jours (S1, lat/lng natives) ; flux « derniers marchés notifiés » (J-1) et « derniers textes au JO » (jour même) ; « X appels d'offres en cours » ; bandeau : marchés notifiés/12 mois, ~500 000 mandats d'élus (S17), 6 829 lobbyistes enregistrés (S4), 12 930 dossiers déclaratifs HATVP (S14).

### Dépenses de l'État
- **Sources** : S13 (mensuel), S20 + S21 (structure mission→action), S23 (subventions aux associations), S41 (encours APU Maastricht, bloc cloisonné), S42 (déficit public APU Maastricht, bloc cloisonné), S44 (agrégats ESA TE/TR, bloc TE sur `/depenses` et bloc TR sur `/recettes`), **S49** (dépenses des APU par fonction, CFAP, bloc cloisonné sur `/depenses`), **S50** (comptes INSEE par sous-secteur sur `/depenses`, PO 3.216 sur `/recettes`), S22 (bilan patrimonial CGE, bloc cloisonné), S45 (prestations de protection sociale DREES, bloc cloisonné), **S46** (État A du PLF, recettes non fiscales, bloc cloisonné sur `/recettes`), **S47** (IRCOM, impôt net sur rôle par territoire, bloc cloisonné sur `/recettes`), S24 (performance, non ingéré), S30 (missions mensuelles PDF, non ingéré), S39 (référentiel des opérateurs, non ingéré).
- **Fraîcheur affichable** : « Exécution mensuelle : données au 30/06/2026, ~6 semaines de décalage » (01) · « Structure du budget : PLF 2026 (déposé oct. 2025) et exécution 2024 » (01) · « Subventions aux associations : versements 2023 (dernier millésime publié) » (01).
- **Contenu concret** : courbes 2013-2026 dépenses/recettes/solde, N vs N-1 par titre ; treemap mission → programme → action (comparateur exéc. 2024 / LFI 2025 / PLF 2026 + cotation budget vert) ; recherche parmi 112 722 subventions (SIREN, programme, commune). **Avertissements obligatoires** : PLF ≠ LFI 2026 (jamais publiée en données) ; aucune donnée de paiement en temps réel n'existe (01).

### Commande publique & appels d'offres
- **Sources** : S1 (attributions + carte + fiches), S2 (AO en cours), S8 (chiffres officiels DAJ, contrôle), S9 (marchés à venir), S34 (UE, non ingéré).
- **Fraîcheur affichable** : « Attributions : consolidation quotidienne (dernière notification : la veille) ; publication légale sous 2 mois — données en cours de consolidation » (02) · « Appels d'offres : annonces du jour même » (02) · « Projets d'achats : mise à jour continue » (02).
- **Contenu concret** : 8 988 AO ouverts triés par date limite ; flux et carte des attributions (montants rationalisés, écrêtage p99) ; fiches acheteur/titulaire (PME/ETI/GE, NAF, flux géographiques) ; pipeline amont APProch (4 060 projets à venir) ; contexte des seuils 2026 (dispense 40 k€ → **60 k€ au 01/04/2026**, décret 2025-1386 ; BOAMP/JAL ≥ 90 k€ : le bas du spectre est invisible, 02).

### Élus & Institutions
- **Sources** : S5 (députés, votes nominaux, questions), S6 (sénateurs), S7 (scores Datan, crédités), S17 (RNE : tous les élus locaux), S14/S15 (déclarations HATVP), S10/S11 (fiches institutions), S26/S19 (élections, Europe ; S19 non ingéré).
- **Fraîcheur affichable** : « Données parlementaires : mises à jour quotidiennes (open data AN/Sénat) » (03) · « Répertoire des élus : 11/08/2026, post-municipales 2026 » (04) · « Dernier scrutin AN : n° 8434 du 21/07/2026 (vacances parlementaires) » (03).
- **Contenu concret** : fiches députés (mandats, groupe, commission, déports, lien direct `uri_hatvp`, scores de participation/loyauté Datan) ; votes nominaux des 8 434 scrutins ; sénateurs ; scrutins Sénat non ingérés (Dosleg) ; annuaire des ~500 000 mandats locaux avec démographie (âge, sexe, CSP) ; questions au gouvernement et questions écrites — **les délais de réponse par ministère ne se mesurent que sur les questions écrites** (les QAG ont réponse immédiate, 03 §2.4 ; 10-critique M4) ; **volet documentaire pantouflage** : chiffres agrégés du rapport annuel HATVP (641 avis de mobilité public-privé en 2025, constantes cf. S31), pas d'export open data des avis — veille active (10-critique I7). **Architecture** : paramètre `legislature`, renouvellement Sénat 27/09/2026, table des intitulés ministériels par période (03).

### Lobbying
- **Sources** : S4 (AGORA quotidien) ; à surveiller : RIE (aucun open data au 19/08/2026, 04).
- **Fraîcheur affichable** : « Répertoire des représentants d'intérêts : mise à jour quotidienne (19/08/2026) ; **dépenses et activités déclarées par exercice annuel** » (04) — la « pression par ministère » repose sur des données à maille annuelle, à dire dans l'UI (10-critique M3).
- **Contenu concret** : 6 829 entités, 118 516 activités ; pression par ministère/AAI ciblé (table 13 × exercices) ; top budgets de lobbying (fourchettes) ; activités par type de décision ; piste de croisement différenciant relevée à la recherche, non construite : calendrier d'un texte × entrées au répertoire (08, créneau n° 1).

### Financement de la vie politique
- **Sources** : S25 (comptes des partis 2021-2024), S29 (comptes de campagne par scrutin), S37 (décret d'aide publique, non ingéré).
- **Fraîcheur affichable** : « Comptes des partis : exercice 2024 (publié le 10/02/2026 — dernier possible, dépôt légal N+1, publication N+2) » (04) · « Comptes de campagne : législatives 2024 (aucun dataset municipales 2026 au 19/08/2026) » (04).
- **Contenu concret** : recettes des 575 partis (dons, cotisations, aide publique 64,26 M€, flux inter-partis) ; dépendance à l'aide publique ; coût par voix et remboursements des 4 010 candidats aux législatives 2024 ; comptes rejetés/réformés.

### Frais & train de vie
- **Sources** : S31 (constantes sourcées + rapports annuels) ; volet « boîte noire » documentaire (05) ; S38 (avis CADA — carte des verrous, **ingérée le 20/08/2026**).
- **Fraîcheur affichable** : « Barèmes en vigueur au 01/01/2026 » · « Contrôles des frais de mandat : exercice 2024 (rapports mai 2026) » · « Élysée : exercice 2024 audité (Cour des comptes, juillet 2025) — exercice 2025 non paru » (05).
- **Contenu concret** : « combien gagnent-ils » (indemnité parlementaire 7 637,39 € brut, DFP 7 238,04 €, AFM Sénat 6 600 €, PM ≈ 16 038 € « calculé ») ; résultats agrégés des contrôles (84 députés / 276 335 € reversés ; 29,9 M€ de frais déclarés au Sénat) ; sous-module Élysée (coût par déplacement : 94 déplacements = 20,1 M€) ; **marchés du sommet de l'État** (Élysée/AN/Sénat via filtre SIREN acheteur sur S1/S2 — requête à coût nul, SIREN documentés en constantes S31, 10-critique M9) ; coût des institutions (mission Pouvoirs publics 1,14 Md€) ; chronologie IRFM → DFP ; **carte des verrous juridiques** (Parlement non communicable vs élus locaux communicables — CE 08/02/2023 ; enrichie par les avis CADA S38, ingérés en agrégats) et compteur des demandes citoyennes refusées (05).
- **Boîte noire — arbitrages post-critique (documentaire assumé, aucun pipeline)** : **aides publiques aux entreprises** : ~211 Md€/an « ni lisibles, ni conditionnées, ni évaluées » (rapport Sénat 08/07/2025) et **aucune donnée consolidée** (vérifié le 19/08 : 0 dataset) → alerte documentaire + veille active ; micro-module possible sur les briques partielles (CIR via jaune, exonérations) (I2). **Hautes rémunérations de la fonction publique** : obligation « 10 plus hautes rémunérations » (art. 37, loi TFP du 06/08/2019) éclatée en **25 datasets épars sans consolidation nationale** (vérifié) → patron S32 : panel assumé, non ingéré, **jamais « national »**, + ligne documentaire « obligation légale massivement inappliquée/éclatée » (I3). **Collaborateurs parlementaires et emplois familiaux** (loi 2017) : **0 dataset** (vérifié) ; listes HTML par élu sur les sites AN/Sénat → extraction coûteuse, non ingérée ou documentaire (I10). **Comptes des groupes politiques des assemblées** : **0 dataset** (vérifié) ; PDF probables sur les sites AN/Sénat à vérifier en Phase 1 → intégrer aux constantes S31, sinon manque assumé ici (I10).

### Finances locales
- **Sources** : S16 (OFGL : comptes + dotations), **S48** (REI, fiscalité directe locale, bloc cloisonné), S27 (fonds de carte + population), S28 (balances, drill-down non ingéré), S33 (strates, non ingéré), S32 (subventions locales, panel non ingéré).
- **Fraîcheur affichable** : « Comptes 2025 provisoires (chargés juillet 2026 ; ~97 communes manquantes jusqu'en décembre 2026) » (06) · « Dotations de l'État : exercice 2026 » (06).
- **Contenu concret** : carte départementale en 1 requête `group_by` (101 départements) ; carte communale pré-calculée (34 778 communes, €/habitant natif) ; fiches collectivité (séries 2012/2018→2025, DGF 2018-2026, comparaison de strate) ; drill-down comptable par SIREN à la demande. **Jamais** de vue « subventions France entière » (aucune consolidation nationale SCDL, 06).

### Documents/JO
- **Sources** : S3 (JORFSIMPLE quotidien), **S43** (dossiers législatifs DILA, ingéré), S35 (LEGI/Debats/RefOrgaAdminEtat, non ingéré), S36 (recherche Légifrance, optionnel), S12 (BODACC/associations, non ingéré).
- **Fraîcheur affichable** : « Journal officiel du jour (disponible chaque nuit vers 00h30) » (07).
- **Contenu concret** : flux quotidien des textes (83 textes le 19/08 dont 5 lois) ; filtre **nominations** (38 textes « nominat » le 19/08) ; filtres lois/décrets/budget par rubrique du sommaire, nature et ministère ; chaque item lié vers `https://www.legifrance.gouv.fr/jorf/id/{ID}` (les liens navigateurs fonctionnent, seule la collecte est bloquée, 07).

### Alertes transparence
- **Sources** : S14 + S17 (retards déclaratifs), S4 (défauts lobbying), S1/S8 (marchés), S25/S29 (financement politique), toutes (moniteur de fraîcheur). Détail au § 4.
- **Fraîcheur affichable** : « Alertes recalculées à chaque mise à jour des sources (HATVP : hebdomadaire ; lobbying et marchés : quotidien) ».

### API & Données
- **Sources** : les métadonnées de toutes les autres + ce document.
- **Contenu concret** : catalogue public des sources avec **fraîcheur mesurée** (dernière donnée réellement ingérée, testée automatiquement — le « moniteur de santé des sources » qui n'existe nulle part, 08 leçon n° 3 et créneau n° 2) ; licences et attributions (LO 2.0, ODbL HowTheyVote, crédit Datan/consolidation DECP) ; ré-export des agrégats calculés en Licence Ouverte ; documentation des règles d'alerte et de leurs bases légales ; reprise de l'**encart de périmètre « argent public »** (en tête du § 2, 10-critique I8).

---

## 3. Ce que la donnée publique ne contient pas — et ce qui est publié à la place

Aucune source publique française ne diffuse la dépense de l'État en continu. Voici, point par point, ce que la donnée contient réellement — chaque limite étant **prouvée par un rapport** — et ce que le site publie à la place.

| # | Sujet | Ce que la donnée contient (preuve) | Ce qui est publié |
|---|---|---|---|
| 1 | **Dépenses de l'État au jour le jour** | Il n'existe **aucune donnée ouverte de paiement en temps réel** (aucun dataset Chorus, search = 0 ; Data-État réservé aux agents). Meilleure fraîcheur réelle : **mensuelle, ~5-7 semaines de décalage** (exécution au 30/06/2026 vue le 19/08) (01-budget-etat.md §1, §11) | Compteur « L'État a dépensé X Md€ depuis le 1er janvier » sur données mensuelles DGFiP, badge « données au 30/06/2026 », **variation vs même période 2025** (pas vs veille) |
| 2 | **Flux de dépenses à la minute** | Même absence de paiements temps réel (01 §11) ; les flux quotidiens réels sont contractuels (marchés notifiés J-1, latence légale de publication jusqu'à 2 mois, 02 §7) ou normatifs (JO à 00h30, 07 §1.3) | Deux flux réels et datés : « **Derniers marchés publics notifiés** » (quotidien, J-1, mention « en cours de consolidation ») et « **Derniers textes au Journal officiel** » (jour même) |
| 3 | **Notes de frais** | **Aucune note de frais du pouvoir national n'est publiée ni même communicable** : Parlement hors CADA (ord. 58-1100, confirmé CE mars 2025), refus explicites des deux chambres le 11/06/2026 ; frais de représentation des ministres jamais publiés (05-frais-indemnites.md §2.4, §4.3) | Module « **Frais & train de vie** » : barèmes exacts 2026, enveloppes (DFP/AFM), résultats agrégés des contrôles, sous-module Élysée audité (le seul détaillé), et la **« boîte noire »** documentant ce qui est caché et pourquoi — l'opacité elle-même est une information |
| 4 | **Dépense par ministère** | Le niveau **mission/programme mensuel n'existe qu'en PDF** anti-bot (SME, 403 Cloudflare) ; l'API mensuelle n'a que 26 lignes par grands titres (01 §1, §8, §11) | Publié : répartition **mensuelle par nature de dépense** (titres) + répartition **annuelle par mission** (PLF 2026/exéc. 2024, mention « PLF ») ; non ingéré : missions mensuelles via parsing des PDF SME |
| 5 | **Géolocalisation des dépenses de l'État** | Les dépenses de l'État ne sont **pas géolocalisées** en open data (Data-État restreint, 01 §11) ; en revanche les **marchés publics le sont nativement** (lat/lng acheteur et titulaire, 02 §1) et les finances locales aussi (06) | Carte réelle des **marchés publics notifiés sur 30 jours** (24 554 lignes constatées) + carte des **finances locales en €/habitant** — libellées comme telles |
| 6 | KPI quotidiens et hebdomadaires | Pas de série quotidienne/hebdomadaire de dépenses (01) | KPI mois/trimestre/année (SMB) ; les KPI « du jour » sont réservés aux flux qui le sont vraiment : textes au JO, AO clôturant aujourd'hui, marchés notifiés la veille |
| 7 | « Transactions » | Les DECP sont des **engagements contractuels (montants max), pas des paiements** (01 §7, 02 §8) | Libellé exact : « marchés notifiés », montants rationalisés, jamais « transactions » ni « dépensé » |
| 8 | Horodatage à la minute | Publication par lots (JO : 1 lot nocturne ; DECP : builds quotidiens ; HATVP : hebdo) (07, 02, 04) | Horodater **au jour de publication de la source** et afficher la latence connue de chaque flux |
| 9 | Libellés de navigation | cf. #1 et #3 | Navigation renommée : « Dépenses de l'État » et « Frais & train de vie » |
| 10 | Rythme des alertes transparence | Les sources d'alertes sont hebdomadaires (HATVP liste.csv) à quotidiennes (AGORA, DECP) (04, 02) | « Alertes recalculées à chaque mise à jour source », chacune datée |

**Ce que les sources permettent vraiment, publié tel quel** : « **Appels d'offres en cours** » (BOAMP quotidien jour même, 8 988 AO ouverts, requête testée, 02) ; recherche globale sur les entités ingérées (élus, marchés, acheteurs, textes JO, lobbyistes) ; compteur d'« élus suivis » (~500 000 mandats RNE, 04) ; « alertes transparence » en tant que telles (§ 4).

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
| **A11. Moniteur de fraîcheur des sources (méta-alerte)** | Dernière donnée réellement ingérée vs fréquence déclarée par source ; alerte si dérive (leçon : les sites morts répondent 200). **Surveillance nominative des maillons communautaires** : build quotidien S1 **et** activité du dépôt `decp-processing` (plan B C1) ; CSV Datan S7 (fallback I6) | toutes | — (engagement méthodologique du projet) | 08, 10-critique C1/I6 |

Alertes **documentaires** (sans calcul, mais sourcées) : refus de publication des justificatifs parlementaires (11/06/2026) ; disparition des rémunérations des cabinets des jaunes budgétaires depuis PLF 2024 ; absence de LFI 2026 en open data ; RIE sans open data (04, 05, 01, 08) ; **aides publiques aux entreprises : ~211 Md€/an sans donnée consolidée** (rapport Sénat 08/07/2025 ; vérifié le 19/08 : 0 dataset) ; **« 10 plus hautes rémunérations » : obligation légale (art. 37, loi TFP 2019) éclatée en 25 datasets sans consolidation nationale** ; **collaborateurs parlementaires et comptes des groupes politiques : 0 dataset** (listes/PDF sur les sites des assemblées) ; **pantouflage : 641 avis de mobilité HATVP 2025 sans export open data** ; **périmètre : les prestations de protection sociale sont désormais S45 (DREES, tous régimes) ; restent hors champ la LFSS comme loi votée, la dépense propre des opérateurs et les entreprises publiques** (10-critique I2, I3, I7, I8, I10).

---

## 5. Périmètre d'ingestion : ce qui est ingéré, ce qui ne l'est pas

### Ingéré au 19/08/2026 — 13 pipelines, meilleur rapport signal/effort, **zéro clé d'API, zéro compte**

| # | Pipeline | Sources | Fréquence | Stratégie volumétrique (période, échantillonnage, taille) |
|---|---|---|---|---|
| P1 | Budget État mensuel | S13 | mensuelle (poll hebdo) | Export CSV complet à chaque publication ; série 2013→courant ; **26 lignes, < 100 Ko** (01) |
| P2 | Structure budgétaire annuelle | S20, S21, S23 | annuelle (one-shot + veille) | Exports complets : 1 816 + 2 404 + 112 722 lignes ; qq dizaines de Mo, une fois par an (01) |
| P3 | Marchés publics | S1 | quotidienne | `decp.parquet` **243 Mo/jour**, remplacement complet (le fichier EST l'état) — **archiver le dernier parquet sain avant chaque remplacement** ; **mode nominal = parquet local + DuckDB** (l'API tabulaire, en bêta, n'est qu'un raccourci substituable) ; base locale filtrée `donneesActuelles=true` + dédup `uid` ; affichage fenêtres 30 j / 12 mois ; agrégats pré-calculés au build ; mesure du délai de publication au grain du marché (`min(datePublicationDonnees) − min(dateNotification)` par `uid`), servie par les tables `decp_publication_*` ; mode dégradé documenté dans la fiche S1 (plan B) (02, 10-critique C1/I9) |
| P4 | Appels d'offres en cours | S2 | 2-4×/jour | **Aucun stock** : requêtes API filtrées (`datelimitereponse > now`, ~9 000 lignes) + exports filtrés pour les attributions du jour ; quota 50 000/j très au-dessus du besoin (02) |
| P5 | Marchés à venir | S9 | hebdomadaire | Dataset complet : 11 388 lignes (02) |
| P6 | Journal officiel | S3 | quotidienne (cron ~06h) | Delta nocturne **~100-500 Ko/jour** ; démarrage au premier delta (pas de Freemium 1 Go) ; lister l'index, ignorer la livraison du soir ; stock cumulé de l'ordre de 15 Mo/mois (07) |
| P7 | Intégrité des élus | S14 + S17 | hebdo / trimestrielle | `liste.csv` 3,3 Mo remplacement complet ; RNE : 12 CSV **~81 Mo** remplacement complet trimestriel (04) |
| P8 | Lobbying | S4 | quotidienne | `Vues_Separees_CSV.zip` **14,2 Mo/jour**, remplacement complet ; **le JSON 137 Mo n'est pas pris** (04) |
| P9 | Parlement | S5 (AMO10 + Scrutins), S6 (ODSEN + questions), S7 (Datan) | quotidienne (nocturne) | 4,9 + 26,3 + ~0,5 Mo/jour + CSV Datan ; **Scrutins en incrémental** : le zip (172,7 Mo décompressés, 8 434 fichiers) est re-livré entier chaque nuit → ne re-parser que les nouveaux numéros de scrutin (diff) ; périmètre = législature 17 paramétrée ; prévoir renouvellement Sénat 27/09/2026 (03, 10-critique M6) |
| P10 | Financement politique | S25 + S29 | annuelle / par scrutin | One-shot : 4 CSV partis 2021-2024 (~300 Ko chacun) + législatives 2024 (1,14 Mo, `cp1252, skiprows=6`) ; aucun dataset municipales 2026 au 19/08/2026 (04) |
| P11 | Finances locales | S16 | au build + à la demande | **Jamais d'aspiration des bases 22 M lignes** : exports filtrés pré-calculés par indicateur × exercice (34 778 lignes / 1,9 Mo chacun ; ~6 indicateurs ≈ 12 Mo) + `group_by=dep_code` à la volée (cache) + dotations par requêtes ciblées (06) |
| P12 | Référentiels | S27, S10 | annuelle / à la volée | geo.api.gouv 4,7 Mo one-shot ; france-geojson 569 Ko statique ; populations INSEE 1 Mo/an ; recherche-entreprises au fil de l'eau (≤ 7 req/s) (09) |
| P13 | Train de vie (constantes) | S31 | à parution (annuelle) | **Zéro pipeline** : bloc de constantes sourcées (bloc YAML du §9 de 05-frais-indemnites.md, **à corriger avant usage** : ligne `mission_pouvoirs_publics_lfi_2026` invalide, `;` → clés/valeurs, 10-critique M2) ; revue à chaque rapport annuel (Élysée 2025 à surveiller) |

**Bilan du périmètre ingéré** : ~290 Mo/jour téléchargés (dominés par le parquet DECP), stockage vif de l'ordre de 2 Go (base + cache `data/raw`), aucune authentification, tous les modules de la navigation alimentés honnêtement, alertes A1-A11 calculables. **Périmètre arrêté le 19/08/2026 après la critique de complétude : 13 pipelines** — les ajouts d'alors (S38 avis CADA, S39 jaune opérateurs, panels rémunérations/collaborateurs) étaient non ingérés ou documentaires : aucun ne conditionnait un module ingéré, et aucun n'avait été échantillonné ni extrait. S38 a depuis été ingérée en agrégats (encadré de tête et fiche S38), et S18 l'a été le 21/08/2026 en référentiel d'attributs restreint aux SIREN cités (fiche S18) — l'un et l'autre pour quelques mébioctets en base.

### Non ingéré à ce jour — documenté et motivé

1. **S30 SME PDF** (headless + parsing) → le seul mission/programme mensuel (01).
2. **Sénat approfondi** : Dosleg (dump SQL 126,3 Mo → scrutins nominaux depuis 2006) + Ameli 154 Mo (03).
3. **AN approfondi** : amendements 296,7 Mo/j ; questions écrites 45,8 Mo ; Agenda 7,8 Mo (reconstruction de la présence en commission — plus rien d'autre ne la fournit depuis la mort de NosDéputés) (03).
4. **S28 balances collectivités** (requêtes ciblées par SIREN) + **S33 comptes individuels** (strates) + **S32 subventions SCDL** (panel Paris/Lyon/départements conformes, jamais « national ») (06).
5. **S19 HowTheyVote** (68,6 Mo hebdo, ODbL) + Europarl (09).
6. **S24 RAP** ; **S34 TED** ; **S12 BODACC/associations** ; **S35 LEGI/Debats/RefOrgaAdminEtat** ; **S36 PISTE** (one-shot humain) ; **S37 décret d'aide publique** (01, 02, 07, 04). S22 CGE est ingérée (P21, totaux de la pièce de synthèse, pas les 517 k lignes).
7. **Ajouts post-critique (19/08)** : **S39 jaune opérateurs PLF 2026** (référentiel des opérateurs) ; **panel « 10 plus hautes rémunérations »** (25 datasets épars, patron S32 : jamais « national ») ; **collaborateurs parlementaires** (extraction HTML des fiches AN/Sénat, coûteuse) ; **comptes des groupes politiques** (PDF AN/Sénat à vérifier en Phase 1 → constantes S31 ou boîte noire) (10-critique I1, I3, I4, I10).
8. **Veilles actives** (re-tester périodiquement) : open data du RIE (trimestriel) ; **export open data des avis de mobilité HATVP (pantouflage), au même rythme que la veille RIE** ; comptes de campagne municipales 2026 ; rapport Cour des comptes Élysée exercice 2025 ; jaune cabinets PLF 2027 ; jaune associations PLF 2026 ; publication éventuelle de la LFI en données ; **datasets PLF 2027** (famille destination/nature + budget vert, non parus au 19/08/2026 — même famille que S20/S21) ; **donnée consolidée « aides aux entreprises »** (0 dataset au 19/08) ; **réserve parlementaire historique** (7 datasets figés, vérifiés — chronologie IRFM → DFP / boîte noire ; successeur FDVA jamais traité) (04, 05, 01, 10-critique M8/I2/I7).

---

## 6. Tableau récapitulatif final

| Source | Fraîcheur réelle (constatée le 19/08/2026) | Licence | Module(s) | Ingéré ? |
|---|---|---|---|---|
| S1 DECP consolidées tabulaires | Quotidienne (build du jour, notifications J-1) (02) | LO 2.0 | Commande publique, Accueil, Alertes | **ingéré** |
| S2 BOAMP | Quotidienne, annonces du jour même (02) | etalab-2.0 | Commande publique (AO en cours), Accueil | **ingéré** |
| S3 DILA JORFSIMPLE | JO du jour à ~00h30 (07) | LO (fr-lo) | Documents/JO, Accueil | **ingéré** |
| S4 HATVP AGORA (lobbying) | Quotidienne (00h04) (04) | LO Etalab | Lobbying, Alertes | **ingéré** |
| S5 Open data AN (AMO, scrutins, questions) | Quotidienne (jour même) (03) | LO | Élus & Institutions | **ingéré** (amendements/agenda non ingérés) |
| S6 Open data Sénat (ODSEN, questions) | Quotidienne (jour même) (03) | LO | Élus & Institutions | **ingéré** (Dosleg/Ameli non ingérés) |
| S7 Datan (scores députés) | Quotidienne (CSV du 19/08/2026) (03) | fr-lo | Élus & Institutions | **ingéré** |
| S8 DECP data.economie (DAJ) | J-2 (02) | LO 2.0 | Commande publique (contrôle) | **ingéré** |
| S9 APProch (projets d'achats) | Continue (maj 15/08) (02) | LO 2.0 | Commande publique | **ingéré** |
| S10 API Recherche d'entreprises | Quotidienne (09) | LO 2.0 | Transverse (résolution SIRET) | **non ingéré** — `pipelines/sirene.py` sait résoudre un SIRET à l'unité et ses tests le couvrent, mais aucun pipeline ne l'appelle et `meta_sources` ne porte aucune ligne S10 (vérifié le 21/08/2026). Le besoin de masse est couvert par S18. |
| S11 Annuaire de l'administration | Vivante (94 117 fiches) (09) | DILA open data | Élus & Institutions, carte | non ingéré |
| S12 BODACC / JO associations (ODS) | Parution du jour (07) | LO | Recoupements | non ingéré |
| S13 SMB séries longues (DGFiP) | Mensuelle, données au 30/06/2026 (~6 sem.) (01) | LO 2.0 | Dépenses de l'État, Accueil | **ingéré** |
| S14 HATVP liste.csv | Hebdomadaire (14/08) (04) | LO Etalab | Alertes, Élus & Institutions | **ingéré** |
| S15 HATVP declarations.xml | Hebdomadaire (14/08) (04) | LO Etalab | Élus & Institutions (fiches) | **ingérée** (20/08/2026) |
| S16 OFGL (comptes + dotations) | Comptes 2025 (juil. 2026, provisoires) ; dotations 2026 (04/08) (06) | LO 2.0 | Finances locales, Accueil | **ingéré** |
| S17 RNE | Trimestrielle (11/08/2026, post-municipales) (04) | lov2 | Élus & Institutions, Alertes | **ingéré** |
| S18 Stock Sirene (StockUniteLegale, parquet) | Mensuelle, millésime du 1er du mois (21/08/2026) | lov2 | Transverse (attributs des unités légales citées) | **ingérée** (21/08/2026, attributs seuls, sans identité de personne physique) |
| S19 HowTheyVote.eu | Hebdomadaire (release 15/08) (09) | **ODbL** | Élus & Institutions (UE) | non ingéré |
| S20 PLF 2026 Budget vert | Annuelle (13/11/2025) (01) | LO 2.0 | Dépenses de l'État, Accueil | **ingéré** |
| S21 PLF 2025 destination/nature | Annuelle (10/2024) (01) | LO 2.0 | Dépenses de l'État | **ingéré** |
| S22 CGE bilan patrimonial | Annuelle (pièce de synthèse 31/12/2024 ; balances ligne 2016-2025) | LO 2.0 | Dépenses de l'État (patrimoine) | **ingérée** (P21, totaux de la pièce) |
| S23 Jaune associations | Annuelle, versements 2023 (01) | LO 2.0 | Dépenses de l'État (subventions) | **ingéré** |
| S24 RAP 2025 (performance) | Annuelle (04/06/2026) (01) | LO 2.0 | Dépenses de l'État | non ingéré |
| S25 CNCCFP comptes des partis | Exercice 2024 publié le 10/02/2026 (04) | LO | Financement politique, Alertes | **ingéré** |
| S26 Élections agrégées (MI) | Par scrutin (municipales 2026 incluses, 07/07/2026) (09) | lov2 | Élus & Institutions | **ingérée** (20/08/2026) |
| S27 Géo + populations INSEE | Statique/annuel (pop. réf. 2023 en vigueur 2026) (09) | LO/INSEE | Cartes, ratios | **ingéré** |
| S28 Balances collectivités DGFiP | 2025 provisoire (13/07/2026) (06) | LO 2.0 | Finances locales (drill-down) | non ingéré |
| S29 CNCCFP comptes de campagne | Législatives 2024 (29/07/2025) ; municipales 2026 : aucun compte publié à ce jour (04) | LO | Financement politique, Alertes | **ingéré** |
| S30 SME PDF (missions mensuelles) | Mensuelle (juin 2026) mais 403 anti-bot (01) | LO 2.0 | Dépenses de l'État | non ingéré |
| S31 Corpus PDF train de vie | Annuel (rapports 2026 sur exercices 2024-2025) (05) | publications officielles | Frais & train de vie | **ingéré** (constantes) |
| S32 Subventions SCDL (panel) | Hétérogène (Armor 16/08/2026 ; Paris 28/07/2026) (06) | LO 2.0 (à vérifier) | Finances locales | non ingéré |
| S33 Comptes individuels collectivités | 2024 max (01/12/2025) (06) | LO 2.0 | Finances locales (strates) | non ingéré |
| S34 TED (UE) | Quotidienne (02) | réutilisation UE | Commande publique (UE) | non ingéré |
| S35 Autres fonds DILA (LEGI/Debats/RefOrgaAdminEtat) | Quotidienne à J-1 (07) | fr-lo | Documents/JO | non ingéré |
| S36 API Légifrance (PISTE) | Temps réel (one-shot humain requis) (07) | CGU PISTE + fr-lo | Documents (recherche) | non ingéré (optionnel) |
| S37 Décret aide publique partis | Annuel (décret 03/03/2026, 403 curl) (04) | — | Financement politique | non ingéré |
| S38 Avis CADA (ensemble consolidé) | Consolidé maj 14/08/2026 + lots mensuels/trimestriels (10-critique) | fr-lo | Frais & train de vie (carte des verrous, boîte noire) | **ingérée** (agrégats seulement, 20/08/2026) |
| S39 Jaune opérateurs PLF 2026 | Annuelle (13/01/2026) (10-critique) | lov2 (confirmée 20/08/2026) | Dépenses de l'État (référentiel opérateurs) | non ingéré |
| S40 Registre de transparence UE | Export XML quotidien (exportDate) | décision 2011/833/UE (20/08/2026) | Lobbying (bloc cloisonné) | **ingérée** (P16) |
| S41 Encours de dette des APU (Maastricht) | Trimestrielle (fin de trimestre de TIME max, jamais `updated`) | décision 2011/833/UE (22/08/2026) | Dépenses (bloc cloisonné) | **ingérée** (P17) |
| S42 Déficit public des APU (Maastricht) | Annuelle (31/12 du TIME max, jamais `updated`) | décision 2011/833/UE (22/08/2026) | Dépenses (bloc cloisonné) | **ingérée** (P18) |
| S43 DILA dossiers législatifs (DOLE) | Freemium + incréments (jusqu'à 5/sem. ; gap max observé 12 j le 22/08 soir) | LO 2.0 (fr-lo) | Documents/JO | **ingérée** (P19) |
| S44 Recettes et dépenses des APU (agrégats ESA) | Annuelle (31/12 du TIME max, jamais `updated` ; 520/600) | décision 2011/833/UE (23/08/2026) | Dépenses (bloc TE) / Recettes (bloc TR) | **ingérée** (P20) |
| S45 Prestations de protection sociale (DREES CPS) | Annuelle (31/12 de l'année max, jamais last_update ; millésime 2024 au 23/08/2026) | LO 2.0 (Etalab) | Dépenses de l'État (bloc cloisonné) | **ingérée** (P22) |
| S46 Recettes du budget général au PLF (État A) | Annuelle (publication open data du millésime, pas le dépôt AN ; 2025 → 2024-10-11) | LO 2.0 (Etalab) | Recettes (bloc cloisonné, non fiscales) | **ingérée** (P23) |
| S47 IRCOM (impôt net sur rôle par commune) | Annuelle (31/12 de l'année des revenus ; 2024 → 2024-12-31 ; publication 26/05/2026) | Licence Ouverte / Open Licence | Recettes (bloc cloisonné) | **ingérée** (P24) |
| S48 REI (fiscalité directe locale) | Annuelle (31/12 de l'année d'imposition ; 2025 → 2025-12-31 ; publication 22/06/2026) | Licence Ouverte / Open Licence version 2.0 | Finances locales (bloc cloisonné) | **ingérée** (P25) |
| S49 Dépenses des APU par fonction (CFAP) | Annuelle (31/12 du TIME max de TOTAL, jamais `updated` ; millésime 2024 au 25/08/2026 ; 650/750) | décision 2011/833/UE (25/08/2026) | Dépenses (bloc cloisonné) | **ingérée** (P26) |
| S50 Comptes des APU (INSEE) | Annuelle (31/12 de l'année max, jamais `modified` Melodi ; millésime 2025 au 25/08/2026 ; 520/600) | Licence Ouverte 2.0 (Etalab, 25/08/2026) | Dépenses (sous-secteurs) / Recettes (PO) | **ingérée** (P27) |

---

*Document établi à partir des rapports 01 à 09 de `docs/recherche/`, révisé après le contre-audit `10-critique-completude.md` (tous appels réels du 19/08/2026). Toute évolution (RIE, municipales 2026 CNCCFP, rapport Élysée 2025, LFI en données, PLF 2027, export des avis de mobilité HATVP) passe par la mise à jour de ce fichier.*
