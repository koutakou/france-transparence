# Axe 4 — Élus & intégrité (HATVP, RNE, CNCCFP)

**Date de vérification : 19 août 2026.** Toutes les URLs ci-dessous ont été appelées réellement ce jour (curl : code HTTP, Content-Type, taille, extraits) sauf mention contraire. Sources classées par ordre d'exploitabilité.

---

## 1. HATVP — Liste des déclarations publiées (`liste.csv`) — EXPLOITABLE DIRECT ⭐ pièce maîtresse des alertes

- **URL testée** : `https://www.hatvp.fr/livraison/opendata/liste.csv`
- **Accès** : HTTP 200, `application/octet-stream`, **3 312 738 octets (3,3 Mo)**, `Last-Modified: Fri, 14 Aug 2026 10:03:29` — publication hebdomadaire (jeudi/vendredi, confirmé par la doctrine HATVP).
- **Format** : CSV `;`, UTF-8 avec BOM, 16 colonnes, **12 930 lignes** (une ligne = un dossier déclaratif attendu ou publié pour un couple personne × mandat × type de document).
- **Colonnes** : `civilite;prenom;nom;classement;type_mandat;qualite;type_document;departement;date_publication;date_depot;nom_fichier;url_dossier;open_data;statut_publication;id_origine;url_photo`
- **Extrait réel** (têtes de fichier, 19/08/2026) :
  ```
  M.;Abdelaziz;HAMIDA;HAMIDA Abdelaziz18939;commune;Maire de Goussainville;di;95;;2026-06-09;;/pages_nominatives/hamida-abdelaziz-18939;;Déclaration déposée - publication à venir;;
  M.;Abdelkader;LAHMAR;LAHMAR Abdelkader27452;depute;Député du Rhône;dia;69;2025-06-17;2024-08-04;lahmar-abdelkader-dia31320-depute-69.pdf;/pages_nominatives/lahmar-abdelkader-27452;lahmar-abdelkader-dia31320-depute-69.xml;Livrée;841729;https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/841729.jpg
  ```
- **Distribution réelle des statuts (comptée le 19/08/2026)** :
  | statut_publication | n |
  |---|---|
  | Livrée | 8 884 |
  | Déclaration déposée - publication à venir | 2 461 |
  | **En cours** (attendue, non déposée) | **1 241** |
  | Déclaration déposée - publication en préfecture à venir | 229 |
  | dispense | 111 |
  | **Déclaration non déposée** (constat HATVP) | **4** |
- Types de documents : `di` (intérêts) 5 698, `dim` (intérêts modificative) 2 310, `diam` 1 360, `dspm` 1 184, `dsp` (patrimoine) 1 053, `dia` (intérêts et activités, parlementaires) 927, `dspfm` (fin de mandat) 398. Types de mandat : departement 3 069, depute 2 571, epci 2 248, senateur 2 104, commune 1 015, region 1 012, ctsp 403, europe 326, gouvernement 134.
- **Fraîcheur** : la vague post-municipales de mars 2026 est dedans — **3 234 dépôts datés 2026** ; des maires élus le 15/03/2026 apparaissent avec dépôts de juin 2026.
- **Licence** : Licence Ouverte Etalab (page https://www.hatvp.fr/open-data/).
- **Pièges** : pas d'identifiant personne stable et documenté (la clé `classement` = « NOM Prénom + numéro interne », `id_origine` rempli seulement pour les parlementaires) ; dates vides quand « En cours » ; miroir data.gouv (`liste-des-responsables-publics-ayant-effectue-des-declarations…`) moins frais (maj 01/07/2026) → **toujours tirer la source hatvp.fr**.
- **Verdict : EXPLOITABLE DIRECT.** Module cible : « Intégrité des élus » — suivi déclaratif + moteur d'alertes retards.

### Base légale de l'alerte « déclaration manquante/en retard »
- Loi n° 2013-907 du 11 octobre 2013 (art. 4 et 11) et art. LO 135-1 du code électoral : dépôt **dans les 2 mois** suivant l'entrée en fonction (et 2 mois avant/après la fin). Pour les VP d'EPCI élus en 2026, le délai court à compter de la transmission de la délégation de fonction à la préfecture (communiqué HATVP « Élections municipales et intercommunales 2026 : vos obligations déclaratives », hatvp.fr/presse/).
- Sanction du non-dépôt : **3 ans d'emprisonnement, 45 000 € d'amende**, inéligibilité jusqu'à 10 ans (art. 26 loi 2013-907 ; LO 135-1 pour les parlementaires).
- Calcul : croiser `date de début de la fonction` (RNE, source 4) + `statut_publication` de liste.csv ; les statuts « En cours » à J+60 = retard présumé ; « Déclaration non déposée » = constat officiel HATVP (4 cas au 19/08/2026).

---

## 2. HATVP — Contenu intégral des déclarations (`declarations.xml`) — EXPLOITABLE DIRECT (parsing lourd)

- **URL testée** : `https://www.hatvp.fr/livraison/merge/declarations.xml` (⚠ l'ancienne URL `livraison/opendata/declarations.xml` renvoie **404**)
- **Accès** : HTTP 200, `text/xml`, **88 825 812 octets (88,8 Mo)**, `Last-Modified: 14 Aug 2026` (même rythme hebdomadaire que liste.csv).
- **Contenu réel** : **texte intégral structuré**, pas des métadonnées — testé sur les 3 premiers Ko :
  ```xml
  <declaration>
    <dateDepot>29/11/2024 18:54:22</dateDepot>
    <uuid>40c65083-094f-4170-9e21-b9c95f4390d6</uuid>
    ...
    <description>Ministre des Solidarités de l'Autonomie et des Personnes handicapées</description>
    <remuneration><brutNet>Net</brutNet><montant><montant><annee>2022</annee><montant>10 312</montant></montant></montant></remuneration>
    ...
    <descriptionMandat>DEPUTE</descriptionMandat>
    <montant><annee>2021</annee><montant>70 676</montant></montant>
  ```
  Rubriques DTO : activités professionnelles 5 dernières années (employeur, rémunération nette/brute par année), activités de consultant, activités du conjoint, fonctions bénévoles, mandats électifs (rémunérations annuelles), participations financières, etc. Les champs non publiables portent la mention `[Données non publiées]`.
- **Volumétrie comptée** : **6 611 déclarations** (`grep -c "</declaration>"` sur le flux complet).
- **Pièges** : (a) 88 Mo d'un seul tenant → parser en streaming (SAX/iterparse) ; (b) delta avec liste.csv : 8 882 lignes annoncent un XML unitaire (`colonne open_data`), le merge n'en contient que 6 611 — versions remplacées/dépubliées non incluses ; (c) montants en chaînes « 70 676 » avec espaces ; (d) déclarations modificatives successives d'une même personne = plusieurs `<declaration>` ; (e) structure imbriquée `items/items`. Documentation structure : `https://www.hatvp.fr/wordpress/wp-content/uploads/2017/07/opendata-structure.xlsx`. Les XML unitaires par déclaration sont aussi téléchargeables individuellement (chemin donné par la colonne `open_data` de liste.csv).
- **Licence** : Licence Ouverte Etalab.
- **Verdict : EXPLOITABLE DIRECT** (effort de parsing réel mais sans obstacle). Module : fiches élus (patrimoine/intérêts, rémunérations annuelles, participations), comparaisons entrée/sortie de mandat.

---

## 3. HATVP — Répertoire des représentants d'intérêts (AGORA, lobbying) — EXPLOITABLE DIRECT ⭐ mis à jour chaque nuit

- **URLs testées** :
  - JSON intégral : `https://www.hatvp.fr/agora/opendata/agora_repertoire_opendata.json` → HTTP 200, `application/json`, **137 653 052 octets (137,7 Mo)**, `Last-Modified: Wed, 19 Aug 2026 00:04:12` (**quotidien**, vérifié le jour même).
  - Vues séparées CSV : `https://www.hatvp.fr/agora/opendata/csv/Vues_Separees_CSV.zip` → 200, zip **14 151 432 o**, Last-Modified 19/08/2026 04:26.
  - Vues fusionnées CSV : `https://www.hatvp.fr/agora/opendata/csv/Vues_Fusionnees.zip` → 200, zip **104 068 175 o**, 19/08/2026.
  - Variantes XLSX : `https://www.hatvp.fr/agora/opendata/xls/Vues_Separees_XLS.zip` ; intermédiaires : `.../csv/Vues_Intermediaires.zip`.
  - ⚠ `agora_repertoire_opendata.csv` et `_csv.zip` : 404 (n'existent pas).
- **Contenu du zip vues séparées (listé le 19/08/2026)** — 15 tables + doc xlsx :
  `1_informations_generales.csv` (6 829 entités), `2_dirigeants`, `3_collaborateurs`, `4_clients`, `5_affiliations`, `6_niveaux_intervention`, `7_domaines_intervention`, `8_objets_activites.csv` (**118 516 fiches d'activités**), `9_secteurs_activites`, `10_actions_menees.csv` (23,4 Mo), `11_beneficiaires`, `12_decisions_concernees.csv` (types de décisions visées), `13_ministeres_aai_api.csv` (37,8 Mo — **institutions ciblées par action**), `14_observations`, `15_exercices.csv` (24 568 exercices).
- **En-têtes réels** :
  ```
  15_exercices: exercices_id;representants_id;date_debut;date_fin;exercice_sans_activite;nombre_activites;publicationCourante_dispenseDeclaration;publicationCourante_activitesRIE;declaration_incomplete;date_publication;exercice_sans_CA;montant_depense;nombre_salaries;...;chiffre_affaires;...;montant_depense_inf;montant_depense_sup;ca_inf;ca_sup
  8_objets_activites: activite_id;exercices_id;date_publication_activite;identifiant_fiche;objet_activite
  → ex. réel : « Rendez-vous de présentation des analyses du syndicat auprès de la Direction générale de l'énergie et du climat concernant le secteur des CEE... »
  12_decisions_concernees: decision_concernee;action_representation_interet_id (ex. « Actes réglementaires »)
  ```
- Le JSON intégral contient en plus, par entité : SIREN, catégorie (entreprise, cabinet, ONG, syndicat...), dirigeants et collaborateurs nominatifs, clients, affiliations, et par exercice le flag **`defautDeclaration: true/false`** (constaté sur le premier enregistrement : SUNROCK, `defautDeclaration: true` pour l'exercice 2025).
- **Granularité** : fiche d'activité (objet, décisions visées, ministères/AAI/API rencontrés, catégories de responsables publics) + moyens annuels (fourchettes de dépenses de lobbying `montant_depense_inf/sup`, nb de salariés, CA).
- **Licence** : Licence Ouverte Etalab. Doc JSON : `https://www.hatvp.fr/wordpress/wp-content/uploads/2024/01/descriptif_JSON_AGORA.xlsx` ; code : gitlab.com/hatvp-open/agora. Miroir data.gouv (`repertoire-des-representants-dinterets`, maj 19/08/2026) synchrone.
- **Pièges** : JSON de 137 Mo sur une seule ligne → parser en streaming (ijson) ou préférer les vues CSV ; budgets en **fourchettes**, pas en montants exacts ; identités ciblées = institutions et fonctions, jamais le nom de l'élu rencontré ; `exercice_sans_CA` / dispenses à gérer.
- **Verdict : EXPLOITABLE DIRECT.** Module : « Lobbying » — pression par secteur/ministère, top budgets, activités par texte de loi, alertes `defautDeclaration`/`declaration_incomplete`.

---

## 4. Répertoire National des Élus (RNE, ministère de l'Intérieur via data.gouv.fr) — EXPLOITABLE DIRECT — à jour post-municipales 2026

- **Dataset** : `https://www.data.gouv.fr/datasets/repertoire-national-des-elus-1/` (API interrogée le 19/08/2026). Licence **lov2** (Licence Ouverte v2), fréquence trimestrielle. `last_update: 2026-08-11`.
- **12 fichiers CSV, tous mis à jour le 11/08/2026** (sauf mention) — URLs stables `static.data.gouv.fr` testées :
  | Fichier | Taille | MAJ |
  |---|---|---|
  | elus-conseillers-municipaux-cm.csv | 65,3 Mo | 11/08/2026 |
  | elus-conseillers-communautaires-epci.csv | 10,0 Mo | 11/08/2026 |
  | elus-maires-mai.csv | 4,26 Mo | 11/08/2026 |
  | elus-conseillers-departementaux-cd.csv | 534 Ko | 11/08/2026 |
  | elus-conseillers-regionaux-cr.csv | 219 Ko | 11/08/2026 |
  | elus-conseillers-darrondissements-ca.csv | 153 Ko | 11/08/2026 |
  | elus-membres-assemblee-ma.csv (assemblées CTU) | 86 Ko | 11/08/2026 |
  | elus-deputes-dep.csv | 73 Ko | 11/08/2026 |
  | elus-senateurs-sen.csv | 35 Ko | 11/08/2026 |
  | elus-representants-Parlement-européen-rpe.csv | 6,6 Ko | 11/08/2026 |
  | elus-conseillers-des-francais-de-letranger | 80 Ko | 05/05/2026 (renouvellement en cours) |
  | elus-assemblee-des-francais-de-letranger-afe.csv | 11 Ko | 05/05/2026 |
- **Exemple d'URL testée** (maires) : `https://static.data.gouv.fr/resources/repertoire-national-des-elus-1/20260811-155100/elus-maire-mai.csv` → 200. ⚠ le chemin contient l'horodatage de version : re-résoudre via l'API à chaque ingestion.
- **Extrait réel (maires)** — le renouvellement de mars 2026 est bien intégré :
  ```
  Code du département;Libellé du département;...;Code de la commune;Libellé de la commune;Nom de l'élu;Prénom de l'élu;Code sexe;Date de naissance;Code de la catégorie socio-professionnelle;Libellé...;Date de début du mandat;Date de début de la fonction
  01;Ain;;;01001;L'Abergement-Clémenciat;EVALET TAPONAT;Line;F;1967-07-22;38;Ingénieur et cadre technique d'entreprise;2026-03-15;2026-03-23
  ```
  (députés : mandats du 08/07/2024, législatives anticipées — cohérent)
- **Granularité** : 1 ligne = 1 mandat, avec date de naissance, CSP, dates de début de mandat ET de fonction, nuance absente (contrairement aux fichiers candidatures).
- **Pièges** : pas d'identifiant national d'élu partagé avec la HATVP → jointure par nom+prénom+département (homonymes à arbitrer, la HATVP ne publie pas la date de naissance) ; volumes municipaux (~500 000 lignes) ; caractères accentués dans les libellés de communes ; AFE/consulaires encore en cours de mise à jour (annonce data.gouv).
- **Verdict : EXPLOITABLE DIRECT.** Module : référentiel « qui est élu où » + dénominateur des alertes HATVP (qui DOIT déclarer) + démographie des élus (âge, sexe, CSP).

---

## 5. CNCCFP — Comptes des partis politiques — EXPLOITABLE DIRECT — exercice 2024 publié le 10/02/2026

- **Dataset** : `https://www.data.gouv.fr/datasets/comptes-des-partis-et-groupements-politiques/` (org. CNCCFP, 40 ressources, licence ouverte). Vérifié par API le 19/08/2026.
- **Série** : CSV pour les exercices **2021 à 2024**, XLSX/ODS pour 2014-2020, PDF (avis JO) pour chaque exercice. Comptes déposés au 30 juin N+1, publiés début N+2 → **l'exercice 2024 est le plus récent publié** (paru le 10/02/2026).
- **URL testée** : `https://static.data.gouv.fr/resources/comptes-des-partis-et-groupements-politiques/20260210-110641/comptes-partis-exercice-2024.csv` → 200, **298 078 o**, **576 lignes (575 partis), 166 colonnes**.
- **Colonnes décisives (positions vérifiées)** : bilan complet + compte de résultat dont
  `101 Cotisations_des_adherents ; 102 Cotisations_des_elus ; 103 Aide_publique_1ere_fraction ; 104 Aide_publique_2nde_fraction ; 105 Autres_aides_publiques ; 106 Dons_de_personne_physique ; 109 Contributions_financieres_de_partis_ou_groupements_politiques ; 117 Contributions_versees_aux_candidats`
  → **dons, cotisations, aide publique et flux inter-partis par parti et par an, directement dans le fichier.**
- **Extrait réel** : `13;CENTRE NATIONAL DES INDÉPENDANTS ET PAYSANS;EUR;2024;...` (montants en euros, encodage UTF-8 BOM, séparateur `;`).
- **Pièges** : formats hétérogènes avant 2021 (xlsx/ods, intitulés différents) → harmonisation nécessaire pour les séries longues ; petites structures nombreuses (575 entités dont micro-partis) ; l'avis CNCCFP (PDF JO, ex. `joe-20260210-0034-0039.pdf`, 696 Ko) liste les partis **n'ayant pas respecté leurs obligations** (perte de l'aide publique) — information en PDF seulement.
- **Verdict : EXPLOITABLE DIRECT** (2021-2024) / AVEC EFFORT (séries antérieures). Module : « Argent des partis ».

### 5 bis. Aide publique aux partis (répartition annuelle)
- Montants attribués par parti = **décret annuel** : décret n° 2026-149 du 3 mars 2026 (JO 04/03/2026), total **64 262 871,05 €** partagé en 2 fractions (1ère : suffrages législatives 2024, sous réserve du respect des obligations comptables 2024 ; 2nde : rattachements parlementaires de novembre 2025). `https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053613045` — ⚠ curl renvoie **403** (anti-bot Légifrance) : passer par navigateur/WebFetch ou par l'API PISTE ; pas de CSV, tableau dans le corps du décret.
- Alternative données : colonnes 103-104 du CSV comptes des partis (aide effectivement perçue, historique par exercice). **Verdict : AVEC EFFORT** (extraction du tableau du décret) ; le CSV CNCCFP couvre l'essentiel du besoin.

---

## 6. CNCCFP — Comptes de campagne — EXPLOITABLE AVEC EFFORT (encodage) — dernier scrutin publié : législatives 2024

- **Organisation CNCCFP sur data.gouv : 26 datasets** (un par scrutin, testé par API le 19/08/2026). Les plus récents :
  - **Législatives 2024** : `https://static.data.gouv.fr/resources/elections-legislatives-generales-des-30-juin-et-7-juillet-2024/20250729-150633/comptes-campagne-legislatives-2024.csv` → 200, **1 144 122 o**, maj 29/07/2025.
  - **Européennes 2024** : `.../20250505-074017/publication-tableau-eg-2024-pour-pubjo-titre-1-.xlsx` → xlsx 30 598 o (tableau JO), maj 05/05/2025.
  - Sénatoriales 2023, législatives 2022, régionales/départementales 2021, municipales 2020, etc.
- **Structure réelle du CSV législatives 2024 (vérifiée)** : **4 010 candidats** ; par candidat : dépenses totales déclarées puis détail par nature en double colonne « (déclaré) / (retenu) » (matériels, locations, personnel, honoraires, communication, réunions…), recettes (apport personnel, dons, contributions de partis), **montant remboursé par l'État** et **décision CNCCFP** (A = approbation, AR = approbation après réformation, R = rejet…).
  ```
  candidat;nom;scrutin;circonscription;département;code département;nuance;dépenses totales déclarées;...
  202408090;M. BRETON Xavier;202401075;Ain - 1re circonscription;Ain;1;Les Républicains;21571;...;A
  ```
- **Pièges MAJEURS (constatés)** : fichier en **cp1252/ISO-8859-1 avec CRLF**, **6 lignes quasi vides avant l'en-tête** (ligne 7), et mojibake résiduel (« mise Ã  disposition ») : ingestion = `skiprows=6, sep=';', encoding='cp1252'` + nettoyage des libellés. Pas de dataset « dons aux candidats » nominatif (interdit — seuls les agrégats par compte sont publics).
- **Municipales mars 2026 : AUCUN dataset au 19/08/2026** — normal : dépôt des comptes ~fin mai 2026, instruction CNCCFP en cours. Rien n'est publié sur l'organisation CNCCFP de data.gouv à cette date.
- **Verdict : EXPLOITABLE AVEC EFFORT.** Module : « Argent des campagnes » (coût par voix, remboursements, comptes rejetés/réformés).

---

## 7. HATVP — Répertoire de l'influence étrangère (RIE) — PAS ENCORE EXPLOITABLE (à surveiller)

- Créé par la **loi n° 2024-850 du 25 juillet 2024** (ingérences étrangères) : toute personne agissant pour un **mandant étranger** afin d'influencer la décision publique doit s'inscrire ; téléservice ouvert le **01/10/2025**, première campagne de déclaration trimestrielle janvier 2026, publicité des informations depuis 2026 (consultation : `https://www.hatvp.fr/repertoire-de-linfluence-etrangere/`).
- **Tests réels du 19/08/2026** : aucun export open data localisable — URLs candidates (`/rie/opendata/...`, `/influence-etrangere/opendata/...`, sous-domaines) toutes en 404/NXDOMAIN ; la page de consultation est une appli JS sans lien d'export dans le HTML. Le lien AGORA existe déjà (champ `publicationCourante_activitesRIE` dans `15_exercices.csv`).
- **Verdict : INEXPLOITABLE EN L'ÉTAT (open data non publié ou non découvrable au 19/08/2026)** — re-tester trimestriellement ; croisement futur AGORA × RIE très différenciant.

---

## 8. Nouveautés législatives 2024-2026 (contexte et bases d'alertes)

- **Loi n° 2024-850 du 25/07/2024** : répertoire de l'influence étrangère confié à la HATVP (cf. § 7) — décret d'application publié, campagnes trimestrielles depuis janvier 2026.
- **Loi du 22 décembre 2025 portant statut de l'élu local** : suppression du conflit d'intérêts « public-public » pour les élus locaux (redéfinition du périmètre des déports) — impacte la lecture des déclarations d'intérêts locales à partir de 2026 (source : Seban & associés, analyse HATVP).
- **Municipales/intercommunales des 15 et 22 mars 2026** : nouvelle vague déclarative massive (maires ≥ 20 000 hab., adjoints ≥ 100 000 hab., présidents/VP d'EPCI…, délai 2 mois — communiqué HATVP) → c'est la vague visible dans liste.csv (3 234 dépôts 2026) et le terrain de la 1ère alerte « retards ».
- **Mai 2026** : rapport HATVP « Douze ans au service de l'intégrité publique — bilan et propositions » + rapport d'activité 2025 (matière éditoriale pour le dashboard).
- Rappel du socle : lois n° 2013-906/907 du 11/10/2013 (déclarations), n° 2016-1691 « Sapin II » (répertoire des représentants d'intérêts, étendu aux collectivités depuis le 01/07/2022), n° 88-227 du 11/03/1988 (financement des partis).

---

## Tableau récapitulatif

| # | Source | URL racine testée | Code/format | Volumétrie réelle | Fraîcheur constatée | Licence | Verdict | Module |
|---|---|---|---|---|---|---|---|---|
| 1 | HATVP liste des déclarations | hatvp.fr/livraison/opendata/liste.csv | 200, CSV | 3,3 Mo, 12 930 dossiers | 14/08/2026 (hebdo) | LO Etalab | EXPLOITABLE DIRECT | Intégrité élus + alertes |
| 2 | HATVP contenu des déclarations | hatvp.fr/livraison/merge/declarations.xml | 200, XML | 88,8 Mo, 6 611 déclarations | 14/08/2026 (hebdo) | LO Etalab | EXPLOITABLE DIRECT | Fiches élus |
| 3 | HATVP AGORA lobbying | hatvp.fr/agora/opendata/… (JSON + 3 zips CSV/XLSX) | 200, JSON/CSV | 137,7 Mo JSON ; 6 829 entités ; 118 516 activités ; 24 568 exercices | 19/08/2026 00:04 (quotidien) | LO Etalab | EXPLOITABLE DIRECT | Lobbying |
| 4 | RNE (12 fichiers par mandat) | data.gouv.fr/datasets/repertoire-national-des-elus-1 | 200, CSV | ~81 Mo cumulés, maires 34 969+ | 11/08/2026, post-municipales 2026 | LOv2 | EXPLOITABLE DIRECT | Référentiel élus |
| 5 | CNCCFP comptes des partis | data.gouv (slug comptes-des-partis-…) | 200, CSV 2021-24 | 575 partis × 166 col./exercice | Exercice 2024 publié 10/02/2026 | LO | EXPLOITABLE DIRECT | Argent des partis |
| 5b | Aide publique (décret annuel) | legifrance JORFTEXT000053613045 | 403 curl (OK navigateur) | 64,26 M€, tableau in-texte | Décret 2026-149 du 03/03/2026 | — | AVEC EFFORT | Argent des partis |
| 6 | CNCCFP comptes de campagne | data.gouv org CNCCFP (26 datasets) | 200, CSV/XLSX | Législatives 2024 : 4 010 candidats | maj 29/07/2025 ; municipales 2026 à venir | LO | AVEC EFFORT (cp1252, 6 lignes de garde) | Argent des campagnes |
| 7 | HATVP influence étrangère (RIE) | hatvp.fr/repertoire-de-linfluence-etrangere/ | consultation seule | — | ouvert 10/2025, opendata introuvable | — | INEXPLOITABLE (au 19/08/2026) | Veille |

## Alertes transparence calculables (données + base légale vérifiées)

1. **Déclaration en retard** : RNE `date de début de la fonction` + 60 jours vs liste.csv `statut_publication` ∈ {En cours} — base : loi 2013-907 art. 4/11, LO 135-1 ; 1 241 « En cours » et 4 « Déclaration non déposée » au 19/08/2026.
2. **Défaut de déclaration lobbying** : AGORA `defautDeclaration=true` / `declaration_incomplete=true` par exercice (flags natifs).
3. **Pression lobbying sur une décision** : nb d'actions × fourchettes de dépenses par ministère/AAI visé (`13_ministeres_aai_api` × `15_exercices`).
4. **Partis privés d'aide publique** pour manquement comptable (avis CNCCFP annuel, PDF) + dépendance à l'aide publique (colonnes 103-105 vs total recettes).
5. **Comptes de campagne rejetés/réformés** : colonne décision (R/AR) des CSV par scrutin.
