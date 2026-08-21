# 03 — Parlement (Assemblée nationale + Sénat)

> Recherche menée le **19 août 2026** pour le dashboard France Transparence.
> Méthode : recherches web (contexte politique), puis **tests réels** de chaque source par `curl` (codes HTTP, headers `last-modified`/`content-length`, téléchargement et inspection du contenu). Aucune source n'est déclarée exploitable sans avoir été appelée ce jour.

---

## 1. Contexte politique en août 2026 (vérifié le 19/08/2026)

### Législature

- **17e législature de l'Assemblée nationale, toujours en cours**, issue des élections législatives anticipées des 30 juin et 7 juillet 2024 (après la dissolution du 9 juin 2024). **Aucune nouvelle dissolution n'a eu lieu au 19 août 2026.** Preuves d'activité continue de la 17e législature : dernier scrutin public n° 8434 du 21/07/2026 (dump open data AN téléchargé ce jour), comptes rendus de séance de juin 2026 ([AN, séance du 17/06/2026](https://www.assemblee-nationale.fr/dyn/17/comptes-rendus/seance/session-ordinaire-de-2025-2026/premiere-seance-du-mercredi-17-juin-2026-annexe)), PLF 2026 déposé le 14/10/2025 et promulgué le 19/02/2026 ([dossier PLF 2026](https://www.assemblee-nationale.fr/dyn/17/dossiers/PLF_2026)).
- Le droit de dissolution est constitutionnellement rouvert depuis le 8 juillet 2025 et fait l'objet de spéculations politiques récurrentes ([Public Sénat](https://www.publicsenat.fr/actualites/politique/a-quelle-date-emmanuel-macron-pourra-t-il-a-nouveau-dissoudre-lassemblee-nationale)) : **le dashboard doit être architecturé pour survivre à un changement de législature** (paramètre `legislature=17` partout, jamais en dur).
- Présidente de l'Assemblée nationale : **Yaël Braun-Pivet** (réélue le 18 juillet 2024, toujours en fonction — vœux 2026 sur [LCP](https://lcp.fr/actualites/2026-doit-etre-une-annee-d-action-declare-yael-braun-pivet-en-presentant-ses-voeux)).
- **Sénat : renouvellement par moitié (178 sièges sur 348) le 27 septembre 2026** ([ministère de l'Intérieur](https://www.interieur.gouv.fr/actualites/actualites-du-ministere/elections-senatoriales-27-septembre-2026), [franceinfo](https://www.franceinfo.fr/elections/senatoriales/les-elections-senatoriales-auront-lieu-le-27-septembre-2026_7956497.html), [senatoriales2026.senat.fr](https://senatoriales2026.senat.fr/)). Impact direct : la composition du Sénat affichée par le dashboard changera fin septembre 2026 — prévoir le rechargement.

### Gouvernement en place (août 2026)

**Premier ministre : Sébastien Lecornu** — gouvernement **Lecornu II** (48e gouvernement de la Ve République), nommé les 10-12 octobre 2025, **remanié par décret du 26 février 2026** ([Légifrance JORFTEXT000053586369](https://www.legifrance.gouv.fr/loda/id/JORFTEXT000053586369), [Élysée](https://www.elysee.fr/emmanuel-macron/2026/02/26/nomination-du-gouvernement-7), [info.gouv.fr](https://www.info.gouv.fr/actualite/la-nouvelle-composition-du-gouvernement-de-sebastien-lecornu)). Toujours en fonction au 19/08/2026 (aucune censure ni démission).

Intitulés exacts des ministères de plein exercice (vérifiés sur [Wikipédia — Gouvernement Lecornu II](https://fr.wikipedia.org/wiki/Gouvernement_Lecornu_II), croisés avec le décret Légifrance du 26/02/2026) :

| Ministère (intitulé exact) | Titulaire |
|---|---|
| Premier ministre, chargé de la Planification écologique et énergétique | Sébastien Lecornu |
| Ministre de l'Intérieur | Laurent Nuñez |
| Ministre des Armées et des Anciens combattants | Catherine Vautrin |
| Ministre du Travail et des Solidarités | Jean-Pierre Farandou |
| Ministre de la Transition écologique, de la Biodiversité et des Négociations internationales sur le climat et la nature | Monique Barbut |
| Garde des Sceaux, ministre de la Justice | Gérald Darmanin |
| Ministre de l'Économie, des Finances et de la Souveraineté industrielle, énergétique et numérique | Roland Lescure |
| Ministre des Petites et Moyennes Entreprises, du Commerce, de l'Artisanat, du Tourisme et du Pouvoir d'achat | Serge Papin |
| Ministre de l'Agriculture, de l'Agro-alimentaire et de la Souveraineté alimentaire | Annie Genevard |
| Ministre de l'Éducation nationale | Édouard Geffray |
| Ministre de l'Europe et des Affaires étrangères | Jean-Noël Barrot |
| Ministre de la Santé, des Familles, de l'Autonomie et des Personnes handicapées | Stéphanie Rist |
| Ministre de la Culture | Catherine Pégard (nommée au 26/02/2026) |
| Ministre des Outre-mer | Naïma Moutchou |
| Ministre de l'Aménagement du territoire et de la Décentralisation | Françoise Gatel |
| Ministre de l'Action et des Comptes publics | David Amiel |
| Ministre de l'Enseignement supérieur, de la Recherche et de l'Espace | Philippe Baptiste |
| Ministre des Sports, de la Jeunesse et de la Vie associative | Marina Ferrari |
| Ministre des Transports | Philippe Tabarot |
| Ministre de la Ville et du Logement | Vincent Jeanbrun |

Ministres délégués notables ajoutés/confirmés au 26/02/2026 (décret Légifrance) : Maud Bregeon (porte-parole du Gouvernement, chargée de l'Énergie), Marie-Pierre Vedrenne (Citoyenneté), Sabrina Roubache (Enseignement et Formation professionnels et Apprentissage), Camille Galliard-Minier (Autonomie et Personnes handicapées), Jean-Didier Berger (auprès de l'Intérieur).

> Piège pour le dashboard : les intitulés ministériels ont changé à chaque gouvernement (Barnier 2024, Bayrou 2024-2025, Lecornu I puis II 2025-2026). Ne jamais coder d'intitulé en dur ; les questions écrites (AN/Sénat) portent le ministère d'attribution dans la donnée elle-même.

---

## 2. data.assemblee-nationale.fr — portail open data de l'Assemblée nationale

**Accès testé le 19/08/2026 : HTTP 200.** Portail de dumps statiques (pas d'API REST) sous `https://data.assemblee-nationale.fr/static/openData/repository/17/...` (le `17` = législature courante ; archives 14e/15e/16e disponibles).

**Licence : Licence Ouverte / Open Licence** (page `/licence-ouverte-open-licence` vérifiée). Contact : opendata@assemblee-nationale.fr.

### 2.1 Acteurs / mandats / organes (députés)

| Jeu | URL testée | Taille | Fraîcheur (last-modified) |
|---|---|---|---|
| **AMO10** députés actifs, mandats actifs, organes (JSON) | `https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip` | 4,9 Mo zip | **19/08/2026 01:50 GMT** (quotidien) |
| **AMO40** députés actifs « divisé » (JSON/XML/**CSV**) | `.../amo/deputes_actifs_mandats_actifs_organes_divises/AMO40_...csv.zip` | 6,8 Mo (csv.zip) | **18/08/2026 23:07 GMT** (quotidien) |
| **AMO30** historique tous acteurs/mandats/organes | `.../amo/tous_acteurs_mandats_organes_xi_legislature/AMO30_...json.zip` | 13,6 Mo | **19/08/2026 00:34 GMT** |
| AMO50 tous acteurs « divisé » | `.../amo/acteurs_mandats_organes_divises/AMO50_...json.zip` | 14,3 Mo | ⚠️ **figé au 11/07/2024** |

Contenu vérifié (AMO10 téléchargé et décompressé) : `json/acteur/PA*.json` (**577 fichiers** = 577 sièges), `json/organe/` (**7 125 organes** : groupes, commissions, partis…), `json/deport/` (**déports/déclarations de conflit d'intérêts**). Structure d'une fiche réelle (PA841605, Antoine Golliot) : `uid`, `etatCivil`, `profession`, **`uri_hatvp`** (lien direct vers la déclaration HATVP — jointure précieuse pour le dashboard), `adresses` (dont réseaux sociaux), `mandats` (20 mandats typés `PARPOL`/`GP`/`COMPER`/`GE` avec `organeRef`, `dateDebut`, `dateFin`).

**Pièges** : AMO50 n'est plus régénéré depuis le 11/07/2024 (utiliser AMO10/AMO30/AMO40) ; fichiers JSON un-par-acteur (préférer un chargement batch) ; certains champs passent de objet→liste selon le nombre d'éléments (mandat unique = dict, sinon list — vu dans le test).

**Verdict : EXPLOITABLE DIRECT** — module « Élus » (fiches députés, groupes, commissions, cumul de mandats, déports, lien HATVP).

### 2.2 Scrutins (votes nominaux)

- URL testée : `https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip` (XML idem).
- Headers réels : HTTP 200, **26,3 Mo** zip, last-modified **19/08/2026 04:25 GMT** (régénéré chaque nuit).
- Contenu vérifié après téléchargement : **8 434 fichiers JSON** (172,7 Mo décompressés), un par scrutin, numérotés `VTANR5L17V1..V8434`. **Dernier scrutin : n° 8434 du 21/07/2026** (« l'ensemble de la proposition de loi visant à moderniser la gestion du patrimoine immobilier de l'État », adopté, 364 votants) — le Parlement est en vacances d'été, d'où l'absence de scrutin en août.
- Granularité : `syntheseVote` (totaux), `ventilationVotes → organe → groupes → groupe → vote → decompteNominatif` : **position nominale de chaque député** (pour/contre/abstention/non-votant), par groupe (`organeRef` à joindre avec AMO).
- Piège : métadonnée du portail erronée (« Les scrutins AN … pour la XV législature » alors que le dépôt est bien `repository/17`) ; la clé de jointure député est `acteurRef` (PA…).

**Verdict : EXPLOITABLE DIRECT** — module « Votes » (votes nominaux, cohésion de groupe, participation aux scrutins).

### 2.3 Amendements

- URL testée : `https://data.assemblee-nationale.fr/static/openData/repository/17/loi/amendements_div_legis/Amendements.json.zip` (trouvée sous `/travaux-parlementaires/amendements/tous-les-amendements`).
- Headers réels : HTTP 200, **296,7 Mo zip**, last-modified **19/08/2026 08:21 GMT**.
- Piège : volumétrie lourde (au moins ×6 décompressé, un fichier par amendement) — à traiter en pipeline batch, pas à chaud.

**Verdict : EXPLOITABLE AVEC EFFORT** (volumétrie) — module « Activité législative » (amendements par député/groupe, taux d'adoption).

### 2.4 Questions

| Jeu | URL testée | Taille | Fraîcheur |
|---|---|---|---|
| Questions écrites | `.../repository/17/questions/questions_ecrites/Questions_ecrites.json.zip` | 45,8 Mo | **19/08/2026 01:11 GMT** |
| Questions au gouvernement | `.../repository/17/questions/questions_gouvernement/Questions_gouvernement.json.zip` | 5,4 Mo | **19/08/2026 00:50 GMT** |
| Questions orales sans débat | page `/questions/questions-orales-sans-debat` (même dépôt) | — | quotidien |

Les questions portent le **ministère interrogé** et la date/présence de réponse → module « Contrôle du gouvernement » (délais de réponse par ministère — d'où l'importance des intitulés exacts du § 1).

**Verdict : EXPLOITABLE DIRECT.**

### 2.5 Réunions / agenda (présence en commission)

- URL testée : `https://data.assemblee-nationale.fr/static/openData/repository/17/vp/reunions/Agenda.json.zip` — HTTP 200, 7,8 Mo, last-modified **19/08/2026 04:40 GMT**. CSV thématiques également (`reunions_init_depute_*.csv`…).
- Les comptes rendus de commission listent les participants : c'est **la seule voie open data officielle pour reconstruire la présence en commission** depuis que NosDéputés est figé (cf. § 4). Reconstruction non triviale (jointure réunions ↔ acteurs).

**Verdict : EXPLOITABLE AVEC EFFORT** — module « Présence/activité ».

---

## 3. data.senat.fr — open data du Sénat

**Accès testé le 19/08/2026 : HTTP 200.** Pas d'API REST : **fichiers CSV/JSON/XLS + dumps PostgreSQL (`.sql` zippés)**, régénérés quotidiennement. **Licence : reprise de la Licence Ouverte data.gouv.fr** (page `/licence/` vérifiée).

### 3.1 Sénateurs

- `https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv` — testé : HTTP 200, 427 Ko, **1 965 lignes** (tous sénateurs, actifs et anciens : matricule, état ACTIF/ANCIEN, groupe politique, commission, circonscription, dates de naissance/décès, email public). Last-modified **19/08/2026 10:32 GMT**.
- ~19 autres CSV `ODSEN_*` (commissions `ODSEN_CUR_COMS`, délégations, groupes historiques `ODSEN_HISTOGROUPES`, études…), mêmes fraîcheurs.
- Dump complet : `https://data.senat.fr/data/senateurs/export_sens.zip` — testé : 8,5 Mo zip contenant **`export_sens.sql` (59,5 Mo, dump PostgreSQL)**, last-modified **19/08/2026 10:32 GMT**.
- **Pièges vérifiés** : encodage **ISO-8859-1** (pas UTF-8) ; les CSV commencent par des **lignes de commentaire `%` contenant la requête SQL d'export** (à sauter au parsing) ; séparateur `;`.

**Verdict : EXPLOITABLE DIRECT** (CSV) — module « Élus » côté Sénat. Attention au renouvellement du 27/09/2026.

### 3.2 Dosleg — travaux législatifs et **scrutins nominaux**

- `https://data.senat.fr/data/dosleg/dosleg.zip` — testé : 16 Mo zip → **`dosleg.sql` (126,3 Mo, dump PostgreSQL)**, last-modified **19/08/2026 01:24 GMT**. CSV d'appoint (`dossiers-legislatifs.csv`, `ppl.csv`, `promulguees.csv`…).
- Tables vérifiées dans le dump : **`scr`** (scrutins : session, numéro, intitulé, date, pour/contre/votants) et **`votsen`** (**vote nominal par sénateur** : matricule `senmat`, position `posvotcod`, délégation de vote `senmatdel`) — couvre **tous les scrutins publics depuis le 01/10/2006** ([notice Dosleg](https://data.senat.fr/aide/travaux-legislatifs-base-dosleg/)).
- Contenu réel vérifié : **337 scrutins pour la session 2025-2026**, dernier visible daté du **22/06/2026** (« l'ensemble du projet de loi portant approbation des comptes de la sécurité sociale de l'année 2025 », 226 pour / 106 contre). Complément lisible : [senat.fr/scrutin-public/scr2025.html](https://www.senat.fr/scrutin-public/scr2025.html).
- Piège : nécessite un PostgreSQL pour charger le dump (ou parsing des blocs `COPY`) ; modèle relationnel ancien (noms de colonnes courts type `scrdat`, `sesann`).

**Verdict : EXPLOITABLE AVEC EFFORT** (dump SQL à intégrer) — modules « Votes Sénat » et « Dossiers législatifs ».

### 3.3 Ameli (amendements Sénat) et questions

- `https://data.senat.fr/data/ameli/ameli.zip` — testé : HTTP 200, **154 Mo**, last-modified **19/08/2026 10:26 GMT** (dump SQL). Jeux CSV par texte également.
- Questions : `https://data.senat.fr/data/questions/questions-depuis-un-an.csv` — testé, contenu réel décodé : colonnes `Sort;Nature;Numéro;…;Ministère de dépôt;Ministère de réponse;Date de réponse JO;Thème(s);URL` (exemple réel : QE 05975 du 21/08/2025, réponse du 13/11/2025 du ministère « Sports, jeunesse et vie associative »). Dump complet `questions.zip` : **282 Mo**, last-modified **19/08/2026 01:45 GMT**.
- Base comptes rendus (`/la-base-comptes-rendus/`, format Akoma Ntoso) disponible pour les débats.

**Verdict : EXPLOITABLE DIRECT** (CSV questions) / **AVEC EFFORT** (dumps SQL ameli, comptes rendus).

---

## 4. NosDéputés.fr / NosSénateurs.fr (Regards Citoyens)

### NosDéputés.fr — figé sur la 16e législature

- Site vivant (HTTP 200) mais **bandeau vérifié le 19/08/2026** : « Ce site présente les travaux des députés de la **précédente législature**. NosDéputés.fr reviendra d'ici quelques mois avec une nouvelle version pour les députés élus en 2024. » — annonce faite il y a plus de deux ans, restée sans suite à ce jour.
- Tests API réels : `https://www.nosdeputes.fr/deputes/json` → HTTP 200 mais mandats clos au **09/06/2024** (`ancien_depute: 1`) ; `https://www.nosdeputes.fr/deputes/enmandat/json` → **0 député** ; `https://www.nosdeputes.fr/synthese/2026-06/json` → `{}` vide.
- Regards Citoyens avait annoncé dès 2022 chercher un repreneur ([regardscitoyens.org](https://www.regardscitoyens.org/nosdeputes-fr-cest-reparti-pour-un-dernier-tour/)).
- Les indicateurs de présence (semaines de présence, interventions) qui faisaient sa valeur **n'existent nulle part ailleurs en API pour la 17e législature**.

**Verdict : INEXPLOITABLE pour la législature courante.** Exploitable uniquement en **historique 2022-2024** (et instances archivées 2007-2012 / 2012-2017 / 2017-2022.nosdeputes.fr) — à étiqueter comme tel dans le dashboard.

### NosSénateurs.fr — arrêté

- Test réel du 19/08/2026 : la page d'accueil affiche « **Le site NosSénateurs.fr est désormais arrêté.** » Archive statique 10/2004-03/2023 sur `archive.nossenateurs.fr`. Les endpoints `/senateurs/json` renvoient du HTML (plus d'API).

**Verdict : INEXPLOITABLE** (archive historique uniquement).

---

## 5. Datan (datan.fr) — vivant et à jour

- Site testé : HTTP 200, page [datan.fr/votes/legislature-17](https://datan.fr/votes/legislature-17) active (votes de la 17e législature). Pas d'API publique (`/api` → 404).
- **Données réutilisables sur data.gouv.fr** (organisation « Datan », licence `fr-lo`) : jeu « [Députés actifs de l'Assemblée nationale — Informations et statistiques](https://www.data.gouv.fr/datasets/deputes-actifs-de-lassemblee-nationale-informations-et-statistiques) », ressource `deputes-active.csv` — **testée et téléchargée : mise à jour du 19/08/2026 même** (`dateMaj=2026-08-19`), colonnes réelles : `id (PA…), legislature=17, nom, groupe, circo, datePriseFonction, job, mail, twitter, nombreMandats, scoreParticipation, scoreParticipationSpecialite, scoreLoyaute, scoreMajorite`.
- Code source ouvert : [github.com/datanFR/datan](https://github.com/datanFR/datan) — dernier push **01/08/2026** (vérifié via l'API GitHub), 65 étoiles.
- Piège : couvre l'Assemblée seulement (pas le Sénat) ; les scores sont des indicateurs calculés par Datan (méthodologie à citer si affichés).

**Verdict : EXPLOITABLE DIRECT** — raccourci précieux pour le module « Activité des députés » (participation aux scrutins, loyauté au groupe), en citant Datan. L'id `PA…` joint directement avec l'open data AN.

---

## 6. Scrutins publics les plus récents — où les trouver

| Chambre | Source primaire (testée) | Dernier vote nominal constaté |
|---|---|---|
| Assemblée nationale | dump `Scrutins.json.zip` (§ 2.2) + consultation web [assemblee-nationale.fr/dyn/17/scrutins](https://www.assemblee-nationale.fr/dyn/17/scrutins) | **n° 8434 du 21/07/2026** |
| Sénat | dump `dosleg.zip`, tables `scr`+`votsen` (§ 3.2) + [senat.fr/scrutin-public/scr2025.html](https://www.senat.fr/scrutin-public/scr2025.html) | **22/06/2026** (session 2025-2026 : 337 scrutins) |

Reprise des scrutins attendue à la rentrée parlementaire (octobre 2026, ou session extraordinaire de septembre).

---

## 7. Tableau récapitulatif

| Source | URL racine | Accès | Format | Fraîcheur réelle (19/08/2026) | Licence | Verdict | Module cible |
|---|---|---|---|---|---|---|---|
| AN — acteurs/mandats/organes (AMO10/30/40) | data.assemblee-nationale.fr `.../repository/17/amo/...` | HTTP 200, direct | JSON/XML/CSV zippés | mis à jour **le jour même** | Licence Ouverte | **EXPLOITABLE DIRECT** | Élus, cumuls, déports, lien HATVP |
| AN — scrutins | `.../repository/17/loi/scrutins/Scrutins.json.zip` | HTTP 200, 26,3 Mo | JSON/XML zippés (8 434 fichiers) | **le jour même** (dernier scrutin 21/07/2026) | Licence Ouverte | **EXPLOITABLE DIRECT** | Votes nominaux AN |
| AN — amendements | `.../repository/17/loi/amendements_div_legis/Amendements.json.zip` | HTTP 200, **297 Mo** | JSON/XML zippés | **le jour même** | Licence Ouverte | **AVEC EFFORT** (volumétrie) | Activité législative |
| AN — questions (écrites/QAG/orales) | `.../repository/17/questions/...` | HTTP 200 | JSON/XML zippés (45,8 / 5,4 Mo) | **le jour même** | Licence Ouverte | **EXPLOITABLE DIRECT** | Contrôle du gouvernement |
| AN — réunions/agenda | `.../repository/17/vp/reunions/Agenda.json.zip` | HTTP 200, 7,8 Mo | JSON/XML/CSV | **le jour même** | Licence Ouverte | **AVEC EFFORT** | Présence en commission |
| Sénat — sénateurs (ODSEN_*) | data.senat.fr `/data/senateurs/` | HTTP 200 | CSV/JSON/XLS + dump SQL | **le jour même** | Licence Ouverte | **EXPLOITABLE DIRECT** | Élus Sénat |
| Sénat — Dosleg (scrutins nominaux dès 2006) | `/data/dosleg/dosleg.zip` | HTTP 200, 16 Mo | **dump PostgreSQL** + CSV | **le jour même** (dernier scrutin 22/06/2026) | Licence Ouverte | **AVEC EFFORT** (SQL) | Votes Sénat, dossiers législatifs |
| Sénat — Ameli (amendements) | `/data/ameli/ameli.zip` | HTTP 200, 154 Mo | dump PostgreSQL + CSV | **le jour même** | Licence Ouverte | **AVEC EFFORT** | Amendements Sénat |
| Sénat — questions | `/data/questions/` | HTTP 200 | CSV (ISO-8859-1, `;`) + zip 282 Mo | **le jour même** | Licence Ouverte | **EXPLOITABLE DIRECT** | Contrôle du gouvernement |
| NosDéputés.fr (API) | nosdeputes.fr | HTTP 200 | JSON/XML/CSV | **figé au 09/06/2024** (16e lég.), `enmandat` = 0 | ODbL | **INEXPLOITABLE** (lég. courante) | Historique 2022-2024 seulement |
| NosSénateurs.fr | nossenateurs.fr | HTTP 200 mais **service arrêté** | archive statique 2004-2023 | arrêté (03/2023) | ODbL | **INEXPLOITABLE** | — |
| Datan | datan.fr + data.gouv.fr + GitHub | HTTP 200 | CSV (data.gouv.fr) | **le jour même** (CSV du 19/08/2026) | Licence Ouverte (fr-lo) | **EXPLOITABLE DIRECT** | Participation/loyauté députés |

## 8. Conséquences d'architecture

1. **Sources primaires = les deux portails officiels**, tous deux rafraîchis quotidiennement (vérifié par `last-modified` du jour sur chaque fichier) : pipeline d'ingestion nocturne suffisant.
2. **Le couple NosDéputés/NosSénateurs est mort pour la période courante** : les indicateurs de présence devront être **recalculés** depuis l'Agenda/réunions AN et les comptes rendus Sénat, ou remplacés par les scores Datan (AN uniquement, à créditer).
3. Prévoir dès maintenant : paramètre de législature (17 → 18 en cas de dissolution), gestion du **renouvellement sénatorial du 27/09/2026**, table de correspondance des **intitulés ministériels par période** (les questions écrites y font référence).
4. Encodages : AN = UTF-8 ; **Sénat = ISO-8859-1 avec en-têtes `%` à sauter**.
