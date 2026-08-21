# Budget & dépenses de l'État — état des sources au 19 août 2026

Axe « Budget & dépenses de l'État » du dashboard France Transparence.
Méthode : chaque source ci-dessous a été **réellement appelée le 19/08/2026** (curl sur les API/fichiers, WebFetch quand curl était bloqué, recherches web croisées). Aucun verdict ne repose sur un souvenir : tout est constaté. Les extraits JSON/CSV sont des copies de réponses réelles.

Contexte 2026 vérifié (recherche web) : le PLF 2026 a été déposé le 14/10/2025, rejeté en 1re lecture le 21/11/2025, une **loi de finances spéciale** a été promulguée fin décembre 2025, et la **LFI 2026 n'a été promulguée que le 19/02/2026** (JO du 20/02/2026, après 49.3 et validation du Conseil constitutionnel). Ce calendrier chaotique explique plusieurs absences de données ci-dessous (sources : senat.fr « la loi en clair PLF 2026 », kpmg.com/av/fr 02/2026, assemblee-nationale.fr dossier PLF_2026).

Portail principal : **data.economie.gouv.fr** (Opendatasoft, 606 datasets au total constatés via l'API catalogue), API **Explore v2.1**, licence **Ouverte v2.0 Etalab** sur tous les jeux testés. En-têtes observés : `x-ratelimit-limit: 50000` requêtes/jour (anonyme).

---

## 1. Situations mensuelles budgétaires de l'État — séries longues (DGFiP) ★ source « dépenses en direct »

- **URL testée (records)** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/situations-mensuelles-budgetaires-series-longues/records?limit=3` → HTTP 200
- **URL testée (export CSV)** : `.../situations-mensuelles-budgetaires-series-longues/exports/csv` → HTTP 200, `content-type: text/csv`
- **Page** : https://data.economie.gouv.fr/explore/dataset/situations-mensuelles-budgetaires-series-longues/
- **Miroir data.gouv.fr** : `jeux-de-donnees-des-situations-mensuelles-budgetaires-de-letat-des-exercices-2013-a-nos-jo...` (maj 07/08/2026)
- **Accès** : API Explore v2.1 (records, facets) + exports `csv, json, jsonl, parquet, xlsx…` ; pièce jointe « Séries longues SMB_DGFiP_2013-2023.csv » + notice explicative PDF (constatées via l'endpoint `/attachments`).
- **Format** : tableau de **26 lignes** (hiérarchie niveau 0/1/2 : solde budgétaire, dépenses, recettes, comptes spéciaux) × **une colonne par mois** depuis 01/2024 (2013-2023 dans le CSV attaché).
- **Granularité** : agrégats nationaux — solde, total dépenses nettes du BG, puis par **titre agrégé** (personnel, fonctionnement, investissement, intervention, charge de la dette, pouvoirs publics, opérateurs…), recettes fiscales/non fiscales, PSR, comptes spéciaux. **Pas de détail mission/programme** dans ce dataset.
- **Période couverte** : 2013 → **30/06/2026** (constaté : dernière colonne `30_06_2026`).
- **Fraîcheur réelle constatée** : dataset modifié le **07/08/2026** avec les données au **30/06/2026** → **mensuel, ~5-7 semaines de décalage**. Description officielle : « Les données du mois de décembre 2025 sont désormais définitives » (les mois infra-annuels sont provisoires). Publication née du « plan d'amélioration du pilotage des finances publiques du 3 mars 2025 ».
- **Licence** : Licence Ouverte v2.0 (Etalab) — constatée dans les métadonnées.
- **Volumétrie** : minuscule (26 lignes) — parfait pour un front.
- **Extrait réel (export CSV, 19/08/2026)** :
  ```csv
  categorie;sous_categorie;ligne_d_information;31_03_2026;30_04_2026;31_05_2026
  Solde budgétaire;Solde budgétaire;Solde budgétaire;-42864859134.71;-69602098341.61;-93309004423.87
  Dépenses;Budget général;Total dépenses nettes du budget général;101233300979.47;145583555624.33;195032711726.17
  Dépenses;Budget général;Dépenses de personnel;40641673145.78;53752844121.32;67026833014.72
  ```
- **Pièges** :
  - noms de colonnes commençant par un chiffre (`31_03_2026`) → à échapper en ODSQL (backticks), sinon `ODSQLSyntaxError` (erreur reproduite) ;
  - anomalie constatée : la colonne d'avril 2024 s'appelle `24_04_2024` (et non `30_04_2024`) → ne pas parser les dates de colonnes naïvement ;
  - montants en euros avec ~10 décimales flottantes ;
  - un ancien dataset jumeau `series-longues-smb_dgfip-vdef` répond avec des métadonnées vides → utiliser uniquement le slug ci-dessus.
- **Verdict** : **EXPLOITABLE DIRECT** — c'est la **meilleure fraîcheur machine-readable** existante pour les dépenses de l'État.
- **Module cible** : « Dépenses de l'État en (quasi) direct » — compteur mensuel dépenses/solde, courbes cumulées 2013-2026, comparaison N vs N-1.

---

## 2. PLF 2026 — Budget vert (seule donnée structurée portant sur 2026 par action)

- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plf-2026-budget-vert/records?limit=2` → HTTP 200
- **Page** : https://data.economie.gouv.fr/explore/dataset/plf-2026-budget-vert/ (aussi sur data.gouv.fr : `plf-2026-budget-vert`)
- **Accès** : API Explore v2.1 + exports. **Licence** : Ouverte v2.0 (constatée).
- **Format/granularité** : 1 816 lignes, **46 missions** (facette vérifiée) × programme × action × sous-action (`code_depense` type `178-05-83`), avec pour chaque ligne : cotations environnementales ET trois colonnes de montants : `execution_2024_cp`, `lfi_2025_cp_ou_prevision_2025...`, `plf_2026_cp_ou_prevision_2026...`. Couvre crédits budgétaires + taxes affectées + dépenses fiscales.
- **Fraîcheur constatée** : modifié le 13/11/2025 (dépôt PLF 2026). Annuel.
- **Extrait réel** :
  ```json
  {"mission": "Défense", "numero_programme": 178, "programme": "Préparation et emploi des forces",
   "code_depense": "178-05-83", "libelle": "Soutiens complémentaires", "cotation_globale": "Neutre",
   "execution_2024_cp": 167597162.57, "lfi_2025_cp_ou_prevision_2025_si_depense_fiscale": 168804965.0,
   "plf_2026_cp_ou_prevision_2026_si_depense_fiscale": 119898227.0}
  ```
- **Pièges** :
  - les montants 2026 sont ceux du **PLF déposé en octobre 2025**, PAS de la **LFI promulguée le 19/02/2026** après amendements/49.3 → écarts certains, à afficher avec la mention « PLF » ;
  - la colonne `execution_2024_cp` fait de ce dataset la source d'**exécution 2024 réelle par action** la plus fine disponible en open data (voir §« manques ») ;
  - périmètre budget vert : crédits budgétaires cotés (y compris « Neutre »), donc quasi-exhaustif mais pas garanti exhaustif au centime.
- **Verdict** : **EXPLOITABLE DIRECT** (avec l'avertissement PLF ≠ LFI).
- **Module cible** : treemap mission → programme → action 2026 ; comparateur exécution 2024 / LFI 2025 / PLF 2026 ; module budget vert (cotation environnementale des dépenses).

---

## 3. PLF 2025 — dépenses selon destination et nature (famille complète de datasets)

- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plf25-depenses-2025-selon-destination/records?limit=2` → HTTP 200
- **Page** : https://data.economie.gouv.fr/explore/dataset/plf25-depenses-2025-selon-destination/
- **Famille constatée** (tous maj 11/10/2024) : `plf25-depenses-2025-selon-destination` (2 404 lignes), `plf25-depenses-2025-du-bg-et-des-ba-selon-nomenclatures-destination-et-nature` (2 415), `plf25-depenses-pluriannuelles-par-titre-des-programmes` (2 415), recettes BG/BA/CAS-CCF, comptes spéciaux, fonctionnement/investissement.
- **Granularité** : **ministère → mission → programme → action → sous-action × titre × catégorie**, AE et CP. La plus fine nomenclature budgétaire publiée.
- **Fraîcheur** : annuelle, au dépôt du PLF (oct. N-1). Millésime le plus récent de cette famille = **PLF 2025**. **Aucun équivalent PLF 2026/LFI 2026** (vérifié par requêtes catalogue `startswith(dataset_id,"plf-2026")`, `"plf26"`, `"lfi-2026"` → seul `plf-2026-budget-vert` existe).
- **Extrait réel** :
  ```json
  {"exercice": 2025, "loi": "PLF", "ministere": "36", "libelle_ministere": "Travail et emploi",
   "programme": "103", "action": "103-01", "sous_action": "103-01-02",
   "libelle_sous_action": "Aides aux employeurs d'apprentis", "titre": "6",
   "autorisation_engagement": 3243144901.0, "credit_de_paiement": 3464537422.0}
  ```
- **Pièges** : champ `loi` = « PLF » (pas la LFI votée) ; les datasets « crédits votés LFI » s'arrêtent à **LFI 2023** (`credits-ae-et-cp-votes-nomenclature-par-destination-et-nature-lfi-2023`, constaté).
- **Verdict** : **EXPLOITABLE DIRECT** (référence structurelle 2025).
- **Module cible** : navigation détaillée du budget voté/proposé, moteur de recherche par programme/action.

---

## 4. Balances des comptes de l'État — comptabilité générale (CGE) 2016-2025

- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/balances_des_comptes_etat/records?limit=2` → HTTP 200 ; facette `annee` vérifiée.
- **Pages** : https://data.economie.gouv.fr/explore/dataset/balances_des_comptes_etat/ + dataviz officielle https://data.economie.gouv.fr/pages/comptabilite-generale/ (annoncée par budget.gouv.fr, « datavisualisation des comptes de l'État »).
- **Accès** : API Explore v2.1 + exports. **Licence** : Ouverte v2.0.
- **Format/granularité** : **517 489 lignes** ; par **compte (10 chiffres) × programme × mission × année**, avec postes/sous-postes (actif/passif/charges/produits), `balance_sortie`, libellés ministère/mission.
- **Période/fraîcheur constatées** : facette `annee` = 2016 (48 517 lignes) → **2025 (54 095 lignes)** ; annuel, le CGE N est publié au printemps N+1 (le CGE 2025 est déjà là au 19/08/2026).
- **Extrait réel** :
  ```json
  {"libellemission": "Défense", "postes": "Créances", "sous_postes": "Clients",
   "compte": "4111100000", "programme": "0212", "annee": "2020", "balance_sortie": 7977.37}
  ```
- **Pièges** : comptabilité **générale** (droits constatés, patrimoniale) ≠ comptabilité budgétaire (caisse) — ne pas additionner avec les SMB ; volumétrie (utiliser exports parquet ou filtres API).
- **Miroir data.gouv.fr** : `donnees-de-comptabilite-generale-de-letat` (CSV statiques 2012-2022, maj 22/03/2025 — moins frais que data.economie).
- **Verdict** : **EXPLOITABLE DIRECT**.
- **Module cible** : bilan/compte de résultat de l'État, dette, immobilisations, provisions — vue patrimoniale.

---

## 5. Subventions de l'État aux associations — jaune budgétaire (PLF 2025, versements 2023)

- **URL testée** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/plf25-donnees-de-l-annexe-jaune-effort-financier-de-l-etat-en-faveur-des-associations/records?limit=2` → HTTP 200
- **Pages** : data.economie (slug ci-dessus) ; data.gouv.fr `plf-2025-donnees-de-lannexe-jaune-effort-financier-de-letat-en-faveur-des-associations-1` (maj 23/12/2024).
- **Format/granularité** : **112 722 lignes** — une ligne par subvention : `siren`, `nic`, `denomination`, `montant`, `programme` budgétaire, `objet_2023`, commune (`cog_code/cog_libelle`), état administratif, catégorie juridique.
- **Période/fraîcheur constatées** : millésime = subventions **versées en 2023** (champ `objet_2023`), publié en **décembre 2024** avec le PLF 2025 → **décalage ~2 ans, annuel**. **Le jaune associations du PLF 2026 n'est PAS publié en données au 19/08/2026** (recherches data.gouv « jaune 2026 » : seul le jaune **opérateurs** PLF 2026 existe, publié 13/01/2026).
- **Extrait réel** (plus gros montants 2023, tri `montant desc`) :
  ```json
  {"denomination": "ASS  INTERNATIONALE DE DEVELOPPEMEN", "montant": 1004021932.85, "programme": "110", "cog_libelle": "États-Unis"}
  {"denomination": "UNION NATIONALE DES CARPA", "montant": 596908638.0, "programme": "101", "cog_libelle": "Paris 6e Arrondissement"}
  ```
- **Pièges** : qualité brute Chorus — `siren` parfois « NR\nCHORUS », dénominations avec retours ligne et espaces insécables (U+00A0), doublons possibles par établissement ; « associations » au sens large (l'AID/Banque mondiale y figure) ; croiser avec le programme budgétaire pour le contexte.
- **Alternative testée** : **API Data.Subvention** (`api.datasubvention.beta.gouv.fr`) → `access_type: restricted` (réservée aux agents publics, constaté via l'API dataservices de data.gouv.fr). Le dataset « Financement des associations par l'état » (NosDonnées.fr) date de 2010.
- **Verdict** : **EXPLOITABLE DIRECT** (meilleure source nationale, fraîcheur limitée à N-2/N-3).
- **Module cible** : « Qui l'État subventionne » — recherche par association (SIREN), carte par commune, ventilation par programme.

---

## 6. Performance de la dépense — RAP 2025 et RAP 2024 (indicateurs d'exécution)

- **URLs testées** : `.../datasets/performance-de-la-depense-rap-2025/records?limit=1` → HTTP 200 (2 140 lignes, maj **04/06/2026**) ; `.../datasets/performance-de-la-depense/records` (RAP 2024, 2 177 lignes) ; + `performance-execution-cible-n-1-...-sous-indicateur` (6 531 lignes, maj 02/07/2025).
- **Format/granularité** : par mission/programme/objectif/indicateur/sous-indicateur : réalisations `exec_2023`, `exec_2024`, **`exec_2025`**, cibles 2025/2026, `atteinte_de_la_cible_2025`.
- **Extrait réel (RAP 2025)** :
  ```json
  {"mission": "Action extérieure de l'État", "exec_2024": "21 883 082", "exec_2025": "23 000 000",
   "2025_cible": "25 000 000", "atteinte_de_la_cible_2025": "amélioration"}
  ```
- **Pièges** : montants/valeurs en **texte** avec espaces insécables (U+202F, U+00A0) → parsing obligatoire ; ce sont des **indicateurs de performance** (pas des € de crédits pour la plupart).
- **Verdict** : **EXPLOITABLE DIRECT** (module performance, pas module dépenses).
- **Module cible** : performance budgétaire — réalisations et cibles par mission telles que publiées dans les RAP.

---

## 7. Données essentielles de la commande publique (DECP) — fichiers consolidés

- **URL testée** : `https://www.data.gouv.fr/api/1/datasets/donnees-essentielles-de-la-commande-publique-fichiers-consolides/` → HTTP 200
- **Ressources constatées** : `decp-2026-08.json` (maj **17/08/2026**, 106 671 310 octets), decp-2026-07/06/05, `decp-global.json`, `decp-2026.json` — 40 ressources (39 JSON + 1 XML), fréquence déclarée **daily**, licence **fr-lo** (Licence Ouverte).
- **Contenu** : marchés publics (arrêté du 22/03/2019 « données essentielles ») de **tous les acheteurs publics** (ministères, collectivités, hôpitaux, EP) : acheteur, titulaire (SIRET), objet, montant, date de notification, durée…
- **Granularité/fraîcheur** : au marché notifié ; consolidation mensuelle mise à jour plusieurs fois par mois (constaté : fichier du mois courant maj J-2).
- **Pièges** : ~107 Mo de JSON par mois (prévoir pipeline, pas d'appel front direct) ; qualité hétérogène selon les profils d'acheteurs ; champ montant = valeur du marché (engagement), **pas un paiement** ; filtrer les acheteurs « État » par SIREN/catégorie pour l'axe budget de l'État.
- **Verdict** : **EXPLOITABLE AVEC EFFORT** (volume + nettoyage), fraîcheur excellente.
- **Module cible** : « Les contrats de l'État en quasi temps réel » — flux des marchés notifiés, top fournisseurs.

---

## 8. DGFiP — Situation mensuelle de l'État (SME, PDF mensuels)

- **URLs testées** : dataset `situation-mensuelle-de-l-etat` (211 documents, maj **14/08/2026**) → HTTP 200 ; PDF `https://www.economie.gouv.fr/files/files/directions_services/dgfip/media-document/SME_2026-06.pdf` → **HTTP 403** en curl (challenge Cloudflare, `cf-mitigated: challenge`), 403 aussi via WebFetch et avec User-Agent navigateur. Accessible en navigateur humain uniquement.
- **Contenu** (description officielle du dataset) : solde d'exécution ; **dépenses nettes du BG par titre et catégorie** ; **dépenses du budget général par mission et programme** ; recettes ; PSR ; comptes spéciaux ; dette.
- **Format/granularité** : **PDF uniquement** — c'est la seule publication **mensuelle au niveau mission/programme**, mais non machine-readable.
- **Fraîcheur constatée** : SME juin 2026 référencée au 19/08/2026 (dernier PDF listé) ; « décembre 2025 définitive » publiée en avril 2026. Mensuel, ~M+6 semaines.
- **Extrait réel (record API)** :
  ```json
  {"titre_document": "Situation mensuelle de l'État - Juin 2026",
   "url_fichier": "https://www.economie.gouv.fr/files/files/directions_services/dgfip/media-document/SME_2026-06.pdf"}
  ```
- **Pièges** : champ `date_publication` incohérent (ex. « Avril 2026 » daté 06/04/2026) → se fier au titre ; téléchargement automatisé bloqué par l'anti-bot d'economie.gouv.fr (contournement : récupération manuelle mensuelle ou navigateur headless, à assumer dans le pipeline).
- **Verdict** : **EXPLOITABLE AVEC EFFORT** (parsing PDF + anti-bot) — unique voie vers du mission/programme mensuel.
- **Module cible** : enrichissement mensuel du module « dépenses en direct » au niveau mission.

---

## 9. Projets d'achats publics (APProch, DAE)

- **URL testée** : `.../datasets/projets-dachats-publics/records?limit=1` → HTTP 200 ; 11 388 lignes, maj **15/08/2026**.
- **Contenu réel** : projets d'achats **à venir** (ex. constaté : « 06 – MENTON – PAF – ST LOUIS – Restructuration », publication prévisionnelle 09/01/2027, tranche « 1M - 5M€ », CPV travaux).
- **Verdict** : **EXPLOITABLE DIRECT** mais **prévisionnel** (intentions d'achat, pas des dépenses).
- **Module cible** : « Ce que l'État s'apprête à acheter ».

---

## 10. Marchés publics de la plateforme des achats de l'État (PLACE) — PIÈGE DE FRAÎCHEUR

- **URL testée** : `.../datasets/marches-publics-conclus-recenses-sur-la-plateforme-des-achats-de-letat-/records?limit=2&order_by=date_de_notification desc` → HTTP 200.
- **Constat décisif** : métadonnée `modified: 2026-01-26` MAIS **dernière notification réelle = 30/12/2017** ; facette `annee_de_notification` = {2013…2017} uniquement. 53 604 lignes.
- **Verdict** : **INEXPLOITABLE pour du récent** (série close 2013-2017 ; historique seulement). Leçon générale : **ne jamais confondre date de modification du dataset et fraîcheur des données** — toujours vérifier par tri sur le champ date.

---

## 11. Ce qui N'EST PAS publié (manques documentés, sources à l'appui)

| Manque | Preuve constatée le 19/08/2026 |
|---|---|
| **Détail Chorus des paiements** (ligne à ligne, fournisseur, engagement/paiement) | Aucun dataset « chorus » sur data.economie (`search("chorus")` → total 0). Le produit **Data-État** (beta.gouv.fr/startups/data.etat.html) branche Chorus/ADEME avec géolocalisation fine mais est **« réservé aux agents autorisés »** (constaté par WebFetch ; instances via dataregion.interieur.gouv.fr). |
| **LFI 2026 en données structurées** (crédits votés par destination/nature) | Catalogue data.economie : aucun `plf-2026-*` hors budget vert, aucun `lfi-2026-*`, aucun `plf26-*` ; data.gouv « PLF 2026 » → 2 datasets seulement (budget vert, jaune opérateurs). Les crédits votés LFI s'arrêtent à **LFI 2023**. Conséquence de la promulgation tardive (19/02/2026) — non rattrapée depuis. |
| **Exécution annuelle fine par action post-2017 (PLR)** | Datasets « données de l'exécution budgétaire » des PLR : dernier complet = **PLR 2017** (data.gouv) ; PLR 2019/2020 présents mais **0 enregistrement** (constaté). Substitut partiel : `execution_2024_cp` par action dans le budget vert PLF 2026. |
| **data.budget.gouv.fr / datafin.budget.gouv.fr** | **NXDOMAIN** (résolution DNS testée) — ces portails n'existent pas. L'organisation « datafin » sur data.gouv.fr ne contient qu'1 dataset (enquête hackathon 2018). |
| **budget.gouv.fr en accès automatisé** | Protégé par **Incapsula** (page de 957 octets avec `_Incasula_Resource`, constatée) ; WebFetch renvoie vide. Les documents budgétaires (PAP/RAP/jaunes PDF) sont consultables en navigateur uniquement. |
| **Jaune « associations » du PLF 2026** | Non publié en open data (dernier millésime : PLF 2025 = versements 2023). |
| **Cartes achats de l'État** | Aucun dataset (recherches web + catalogue : seuls des guides de procédure existent, ex. collectivites-locales.gouv.fr). |
| **Frais de représentation des ministres** | Non publiés ; le gouvernement s'est déclaré **incapable de les détailler** malgré demandes CADA (next.ink « Le gouvernement incapable de détailler les frais de représentation des ministres » ; enveloppes théoriques 100-150 k€/an citées dans QE Assemblée nationale n°30813). |
| **API Data.Subvention** | `access_type: restricted` (API data.gouv.fr dataservices) — réservée aux administrations. |
| **SME machine-readable au niveau mission** | Le mission/programme mensuel n'existe qu'en PDF (cf. §8) ; le dataset séries longues n'a que 26 lignes agrégées. |

Piste non testée (signalée sans verdict) : séries mensuelles INSEE du solde d'exécution (série 001717255) via l'API BDM — redondante avec la source §1.

---

## Tableau récapitulatif

| # | Source | URL (testée) | Accès | Granularité | Fraîcheur réelle | Licence | Verdict | Module |
|---|---|---|---|---|---|---|---|---|
| 1 | SMB séries longues (DGFiP) | data.economie…/situations-mensuelles-budgetaires-series-longues | API ODS v2.1 + exports | 26 lignes agrégées (titres) | **Mensuel, données au 30/06/2026 vues le 19/08 (~6 sem.)** | LO v2.0 | **EXPLOITABLE DIRECT** | Dépenses en direct |
| 2 | PLF 2026 Budget vert | data.economie…/plf-2026-budget-vert | API + exports | mission→action (46 missions, 1 816 l.) ; exéc. 2024 CP | Annuel (13/11/2025) | LO v2.0 | **EXPLOITABLE DIRECT** (PLF≠LFI) | Treemap 2026, budget vert |
| 3 | PLF 2025 dépenses destination/nature | data.economie…/plf25-depenses-2025-selon-destination | API + exports | ministère→sous-action×titre (2 404 l.) | Annuel (10/2024) | LO v2.0 | **EXPLOITABLE DIRECT** | Navigation budget |
| 4 | Balances CGE 2016-2025 | data.economie…/balances_des_comptes_etat | API + exports | compte×programme×année (517 489 l.) | Annuel, 2025 dispo | LO v2.0 | **EXPLOITABLE DIRECT** | Bilan de l'État |
| 5 | Jaune associations (PLF 2025) | data.economie…/plf25-donnees-de-l-annexe-jaune-…-associations | API + exports | subvention unitaire, SIREN (112 722 l.) | Annuel, versements **2023** | LO v2.0 | **EXPLOITABLE DIRECT** | Subventions assos |
| 6 | Performance RAP 2025 | data.economie…/performance-de-la-depense-rap-2025 | API + exports | sous-indicateur (2 140 l.) | Annuel (04/06/2026, exéc. 2025) | LO v2.0 | **EXPLOITABLE DIRECT** | Performance |
| 7 | DECP consolidées | data.gouv…/donnees-essentielles-de-la-commande-publique-fichiers-consolides | Dump JSON mensuels | marché unitaire (~107 Mo/mois) | **Quasi-quotidien** (17/08/2026) | LO (fr-lo) | **EXPLOITABLE AVEC EFFORT** | Contrats publics |
| 8 | SME PDF mensuelle | data.economie…/situation-mensuelle-de-l-etat (+PDF economie.gouv.fr) | Liste API ; PDF bloqué bots (403 CF) | mission/programme mensuel | Mensuel ~M+6 sem. (juin 2026 dispo) | LO v2.0 | **EXPLOITABLE AVEC EFFORT** | Détail mensuel missions |
| 9 | Projets d'achats (APProch) | data.economie…/projets-dachats-publics | API + exports | projet d'achat (11 388 l.) | Continu (15/08/2026) | LO v2.0 | EXPLOITABLE DIRECT (prévisionnel) | Achats à venir |
| 10 | Marchés PLACE 2013-2017 | data.economie…/marches-publics-…-plateforme-des-achats-de-letat- | API | marché unitaire (53 604 l.) | **Figé fin 2017** | LO v2.0 | **INEXPLOITABLE** (récent) | — |

**Réponse à la question clé (« dépenses en direct »)** : la meilleure fraîcheur réellement disponible pour l'exécution des dépenses de l'État est **mensuelle avec ~5-7 semaines de décalage** (au 19/08/2026 : exécution au 30/06/2026), en agrégats nationaux par grands titres via l'API des séries longues SMB ; le niveau **mission/programme mensuel n'existe qu'en PDF** (SME) ; le niveau **action** n'existe qu'en **annuel** (exécution 2024 via le budget vert PLF 2026). Il n'existe **aucune donnée ouverte de paiement Chorus en temps réel** — un compteur de dépenses de l'État ne peut donc être daté que « mensuel M+6 semaines ».
