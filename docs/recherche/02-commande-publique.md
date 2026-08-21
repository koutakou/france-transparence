# Commande publique & appels d'offres — état des sources au 19 août 2026

Recherche pour le dashboard « France Transparence », axe commande publique. **Toutes les URLs ci-dessous ont été appelées en réel (curl) le 19/08/2026** ; les codes HTTP, volumétries et extraits sont constatés, pas supposés. Ordre : exploitabilité décroissante.

Rappel des besoins du dashboard sur cet axe : (a) attributions récentes + carte de France des marchés, (b) module « appels d'offres en cours », (c) contexte (seuils, acheteurs, titulaires).

> **Rectification datée du 21/08/2026 — ce document est un relevé du 19/08/2026 et n'est pas
> réécrit ; ce qu'il prescrivait sur un point est faux et le voici corrigé.** Deux de ses
> « pièges » (§ 1 *Pièges* et § *Pièges de méthode* n° 3) prescrivent de dédoublonner un marché
> par `uid` **en filtrant `donneesActuelles = true` avant tout comptage**. Appliqué à la DATE,
> ce geste date le marché de son DERNIER AVENANT : à la source, la ligne d'un avenant porte
> comme `dateNotification` la date de l'avenant, et `donneesActuelles` ne vaut que sur la
> dernière modification. La règle qui fait autorité aujourd'hui est celle de `docs/SOURCES.md`
> (fiche S1) : les ATTRIBUTS (montant, titulaires, objet, procédure) se lisent bien sur la
> version courante, mais la DATE du marché est `min(dateNotification)` sur TOUTES ses lignes,
> avenants compris. `dateNotification` identifie une VERSION du marché, pas le marché — c'est
> le modèle de données amont, assumé et documenté dans le code de `decp-processing` ; l'erreur
> était de notre côté, à la lecture.

---

## 1. DECP consolidées au format tabulaire (data.gouv.fr) — la source n° 1 pour les attributions et la carte

- **Page** : <https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire>
- **Producteur** : consolidation communautaire maintenue par Colin Maudry (projet `decp-processing`, code public : <https://github.com/ColinMaudry/decp-processing>), à partir de ~53 sources officielles (AIFE/DUME, PES Marché 2024 DGFiP, Mégalis Bretagne, profils Atexo/AWS/Dematis, etc.).
- **Accès testés** :
  - `decp.parquet` (243 116 227 octets ≈ 243 Mo) : `https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432` → HTTP 302 vers `https://static.data.gouv.fr/resources/.../20260819-051546/decp.parquet` → **HTTP 200, build du jour même (19/08/2026 05:15)**.
  - `decp.csv` (2,54 Go) : `https://www.data.gouv.fr/api/1/datasets/r/22847056-61df-452d-837d-8b8ceadbfc52`.
  - **API tabulaire data.gouv.fr (gratuite, sans clé)** : `https://tabular-api.data.gouv.fr/api/resources/22847056-61df-452d-837d-8b8ceadbfc52/data/` → HTTP 200. Filtres par suffixes (`__exact`, `__greater`, `__less`, `__contains`), `page_size` jusqu'à 200 testé, total dans `meta.total`.
- **Fraîcheur constatée** : mise à jour **quotidienne** (frequency: daily) ; dernière MAJ 2026-08-19 ; marché le plus récent vu : notifié le **2026-08-18** (la veille).
- **Volumétrie** : **3 238 492 lignes** (une ligne par marché × titulaire × modification) ; 10 541 fichiers sources agrégés au build du jour.
- **Format / granularité** (constatés sur enregistrement réel) : `uid`, `id`, `acheteur_id` (SIRET) + **`acheteur_nom`, commune/département/région (codes + noms), latitude/longitude, population, catégorie**, `titulaire_id` (SIRET) + **nom, code NAF + libellé, commune/département/région, latitude/longitude, catégorie (PME/ETI/GE)**, `montant`, **`montant_rationalise`, `montant_anomalie` (+ raisons)**, `dateNotification`, `datePublicationDonnees`, `lieuExecution_code/typeCode`, `codeCPV`, `procedure`, `offresRecues`, `dureeMois`, considérations sociales/environnementales, `origineUE`/`origineFrance`, `modification_id`, **`donneesActuelles`** (booléen : version courante), `sourceDataset`, `sourceFile`, `titulaire_distance`.
- **Extrait réel** (1re ligne, 19/08/2026) :

  ```json
  {"uid":"120014048000741000198090_66000000","acheteur_nom":"DIRECTION DE L'EVALUATION DE LA PERFORMANCE ...",
   "titulaire_nom":"VERSPIEREN","montant":63416.05,"dateNotification":"2026-08-18",
   "acheteur_departement_code":"75","acheteur_latitude":48.831912,"acheteur_longitude":2.388676,
   "titulaire_categorie":"ETI","montant_rationalise":63416.05,"montant_anomalie":null,
   "donneesActuelles":true,"sourceDataset":"aife_dume"}
  ```

- **Requête « marchés notifiés ces 30 derniers jours » testée** :
  `https://tabular-api.data.gouv.fr/api/resources/22847056-61df-452d-837d-8b8ceadbfc52/data/?dateNotification__greater=2026-07-20&donneesActuelles__exact=true`
  → HTTP 200, **`meta.total` = 24 554 lignes**.
- **Licence** : Licence Ouverte / Open Licence v2.0 (lov2).
- **Pièges** :
  - 1 marché = n lignes (multi-titulaires, modifications) → dédoublonner par `uid` + filtrer `donneesActuelles=true`. ⚠ **Rectifié le 21/08/2026, voir l'encadré en tête : ce filtre vaut pour les ATTRIBUTS, jamais pour la DATE.**
  - Montants d'accords-cadres = montants **maximum**, pas dépensés ; champ `montant_anomalie` fourni pour les aberrations — l'utiliser.
  - Doublons inter-sources suivis dans la ressource `statistiques-doublons-sources.parquet` (publiée à côté) ; `schema.json` documente les colonnes.
  - decp.info (ancienne interface) → **redirection 301 vers colibre.fr** (« Outils pour l'exploration des marchés publics ») ; l'API « premium » de colibre est sur abonnement, mais l'API tabulaire data.gouv.fr ci-dessus est gratuite.
  - Consolidation communautaire (pas MEF) — code ouvert et sources officielles, mais à mentionner dans le sourcing du dashboard.
- **Verdict : EXPLOITABLE DIRECT.** Module cible : **attributions récentes + carte de France** (lat/lng et codes département/région déjà fournis pour acheteur ET titulaire — aucun join SIRENE nécessaire), fiches acheteurs/titulaires, flux géographiques acheteur→titulaire.

---

## 2. BOAMP — annonces de marchés (API DILA / Opendatasoft) — la source du module « appels d'offres en cours »

- **API** : `https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records` → HTTP 200, JSON. Page open data : <https://www.boamp.fr/pages/donnees-ouvertes-et-api/> (HTTP 200).
- **Producteur** : DILA. **Licence : etalab-2.0** (affichée sur boamp.fr). Sans clé.
- **Fraîcheur constatée** : `data_processed` = 2026-08-18T20:41Z et annonces avec `dateparution` = **2026-08-19 (jour même)** déjà présentes → **alimentation quotidienne, J le matin**.
- **Volumétrie** : **1 698 829 annonces** (total_count).
- **Champs à plat (40)** : `idweb`, `objet`, `nomacheteur`, `dateparution` (date), **`datelimitereponse` (datetime)**, `datefindiffusion`, `nature` (facettes réelles : APPEL_OFFRE 1 154 552, ATTRIBUTION 463 698, RECTIFICATIF 70 970, INTENTION_CONCLURE 4 125, PRE-INFORMATION 2 828, MODIFICATION 1 698, ANNULATION 464), `famille` (JOUE 830 460, FNS 650 825, MAPA 203 902, DSP 11 959), `code_departement` (liste), `type_marche` (TRAVAUX/FOURNITURES/SERVICES), `type_procedure`, `criteres`, `descripteur_libelle`, `titulaire` (liste — rempli sur les attributions), `annonce_lie`, `url_avis`, `gestion` (JSON), **`donnees` (JSON eForms complet, en texte)**.
- **Extrait réel** (annonce la plus récente, 19/08/2026) :

  ```json
  {"idweb":"26-81117","objet":"Fournitures de spécialités pharmaceutiques ... Gard",
   "famille":"JOUE","dateparution":"2026-08-19","nomacheteur":"Conseil départemental du Gard",
   "titulaire":["PHARMACIE DIAZ S.E.L.A.R.L","PFIZER S.A.S","MSD FRANCE S.A.S"],
   "nature":"ATTRIBUTION","type_marche":["FOURNITURES"],"source_schema":"3.2.5"}
  ```

- **Requête « appels d'offres en cours » (clôture future) TESTÉE — le module est réellement alimentable** :
  `https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records?where=datelimitereponse>date'2026-08-19' AND nature='APPEL_OFFRE'&order_by=datelimitereponse asc&limit=20`
  → HTTP 200, **8 988 annonces en cours**, ex. : « Aménagement d'une aire de jeux » (Commune de Bièvres, clôture 2026-08-20 08:00), « Accord-cadre habillements » (Département-Région de Mayotte, 2026-08-20 09:00).
- **Export en masse filtré testé** : `/exports/csv?where=dateparution>=date'2026-08-18' AND nature='APPEL_OFFRE'&select=idweb,objet,nomacheteur,datelimitereponse` → HTTP 200 `text/csv` (streaming, non soumis au plafond 10 000).
- **Pièges** :
  - **Pas de champ montant à plat** : le montant, quand il existe, est enfoui dans `donnees` (eForms, ex. `efbc:OverallMaximumFrameworkContractsAmount` vu à 500 000 EUR sur 26-81117) — parsing hétérogène (schémas 3.x + eForms) = effort ; pour le module « en cours », objet/acheteur/dates suffisent.
  - `/records` : **offset + limit ≤ 10 000** (testé : HTTP 400 à 10 001) → pagination profonde via `/exports/*`.
  - `datelimitereponse` est nulle sur les attributions ; les rectificatifs/annulations doivent être joints via `annonce_lie` pour ne pas afficher un AO annulé.
  - `code_departement` est une liste (annonces multi-départements).
- **Verdict : EXPLOITABLE DIRECT.** Module cible : **« appels d'offres en cours »** (clôtures futures, tri par urgence), fil des attributions du jour, comptages par département/nature.

---

## 3. DECP officielles data.economie.gouv.fr (DAJ/OECP) — la référence « État » avec agrégations serveur

- **API** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp-2022-marches-valides/records` → HTTP 200. Interface : <https://data.economie.gouv.fr/explore/dataset/decp-2022-marches-valides/table/>
- **Producteur** : ministères économiques et financiers (DAJ — arrêté du 22/12/2022) ; contact `oecp-recensement.daj[@]finances.gouv.fr`. **Licence Ouverte v2.0 (Etalab)**.
- **Contenu** : uniquement les marchés **conformes** au schéma réglementaire (« valides ») ; les non conformes sont publiés à part (`decp-2022-marches-exclus`), par transparence.
- **Fraîcheur constatée** : `data_processed` = **2026-08-17T12:41Z** (J-2) ; marché le plus récent : notifié **2026-08-17**.
- **Volumétrie** : **689 062 marchés** (1 ligne par marché ; titulaires en colonnes `titulaire_id_1..3`).
- **Granularité** : `id`, `acheteur_id` (SIRET), `titulaire_id_1..3` (SIRET), `objet`, `codecpv`, `procedure`, `montant`, `datenotification`, `datepublicationdonnees`, `dureemois`, `lieuexecution_code` + `lieuexecution_typecode`, `offresrecues`, considérations sociales/environnementales, `origineue`/`originefrance`, sous-traitance, modifications, `source`.
- **Requête « marchés notifiés ces 30 derniers jours » TESTÉE** :
  `.../decp-2022-marches-valides/records?where=datenotification>=date'2026-07-20'&order_by=datenotification desc&limit=100`
  → HTTP 200, **total_count = 6 657 marchés**. Extrait réel : `{"id":"2026T06966","objet":"Réhabilitation ... Plomberie","acheteur_id":"21220295600018","montant":57988.0,"datenotification":"2026-08-17","lieuexecution_code":"22"}`.
- **Agrégation serveur pour la carte TESTÉE** :
  `...?where=datenotification>=date'2026-07-20'&group_by=lieuexecution_code&select=lieuexecution_code,count(*) as nb,sum(montant) as total&order_by=total desc`
  → HTTP 200. **Le résultat illustre les deux pièges majeurs** : département « 60 » = 4,33 Md€ en 30 jours (montants max d'accords-cadres/aberrations non rationalisés) et `lieuexecution_code` à granularité mixte (« 60 », « FR », « 14000 »).
- **Export en masse** : `/exports/parquet` testé → HTTP 200 (`decp-2022-marches-valides.parquet`). En-têtes vus : `x-ratelimit-limit: 50000` (appels/jour/IP). `/records` plafonné à offset+limit ≤ 10 000.
- **Datasets frères sur la même plateforme** (catalogue testé) : `decp-2022-concessions-valides` (**589 enregistrements seulement — couverture concessions très faible**), `decp-2022-marches-exclus`, `decp-2022-concessions-exclues`, `decp-v3-*` (ancien schéma, historique pré-2024), `decp_augmente` (**[Obsolète]**, ne pas utiliser), `decp_aws`.
- **Pièges** : valeur de remplissage **`"CDL"`** dans les colonnes vides (à traiter comme null) ; montants bruts non rationalisés ; ~4× moins de lignes récentes que la consolidation n° 1 (périmètre « valides » + 1 ligne/marché) ; pas de géocodage ni de noms d'acheteurs/titulaires (SIRET seuls → join SIRENE nécessaire pour les noms).
- **Verdict : EXPLOITABLE DIRECT.** Module cible : chiffres « officiels DAJ » (compteurs, agrégats serveur group_by sans télécharger), croisement/contrôle de la source n° 1.

---

## 4. APProch — projets d'achats publics (marchés À VENIR)

- **Portail** : <https://projets-achats.marches-publics.gouv.fr/> (DAE/AIFE). **Open data** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/records` → HTTP 200 (aussi sur data.gouv.fr : « Projets d'achats publics »).
- **Contenu** : intentions d'achat publiées en amont de la consultation (sourcing) — un étage que ni BOAMP ni DECP ne couvrent.
- **Fraîcheur constatée** : modified **2026-08-15** ; **11 388 projets** ; Licence Ouverte v2.0.
- **Champs** : `libelle`, `statut`, `siren_de_l_entite_acheteuse`, `code_s_cpv`, **`date_previsionnelle_de_publication`**, `date_cible_de_remise_des_offres`, `type_de_procedure`, **`montant_estime_du_marche`** (tranches texte : « 100k - 500k€ »), `departement_s_d_execution_du_marche` (liste séparée par `|`), `lien_vers_la_consultation`, considérations sociales/environnementales.
- **Requête « projets à publication future » TESTÉE** :
  `...?where=date_previsionnelle_de_publication>=date'2026-08-19'&order_by=date_previsionnelle_de_publication asc`
  → HTTP 200, **4 060 projets à venir**. Extrait réel : « Mise aux normes électriques - Multi-sites (54-57) », SIREN 110014016, publication prévue 2026-08-19, 100k-500k€.
- **Pièges** : SIREN stocké en entier (zéros de tête perdus → re-padder à 9 chiffres) ; montant en tranche texte (pas de somme possible) ; liste de départements parfois « tous » ; couverture surtout État/hôpitaux (collectivités volontaires).
- **Verdict : EXPLOITABLE DIRECT.** Module cible : **« marchés à venir »** (pipeline amont), complément différenciant du module « en cours ».

---

## 5. TED — Tenders Electronic Daily (UE)

- **API v3 (testée)** : `POST https://api.ted.europa.eu/v3/notices/search` (JSON, **sans clé**) → HTTP 200. Docs : <https://docs.ted.europa.eu/> ; swagger : `https://api.ted.europa.eu/swagger`.
- **Syntaxe « expert query » testée** : `{"query":"(buyer-country IN (FRA)) AND (publication-date>=20260101)","fields":[...],"limit":...}` → réponse `notices[]` + `totalNoticeCount` + `iterationNextToken` (pagination profonde) + liens XML/PDF/HTML multilingues par notice.
- **Volumétrie constatée** : **58 379 avis « France » publiés en 2026** (au 19/08). Clôtures futures FR : `(buyer-country IN (FRA)) AND (deadline-receipt-tender-date-lot >= 20260820) AND (notice-type IN (cn-standard))` → **6 365 avis** (champ deadline par lot, valeurs parfois lointaines : ex. 2034 sur accords-cadres — à manier par lot).
- **Fraîcheur** : publication quotidienne (JO S) ; avis du 2026-08-10 vus lors du test.
- **Licence** : réutilisation libre des données TED (politique de réutilisation UE).
- **Intérêt vs BOAMP** : pour la France, les avis européens (famille JOUE = 830 460 annonces) sont **déjà dans BOAMP** avec des champs plus simples ; TED ne couvre que le dessus des seuils UE. TED vaut pour : eForms normalisés (montants structurés), recoupement, comparaisons européennes.
- **Verdict : EXPLOITABLE DIRECT mais NON PRIORITAIRE** (partiellement redondant avec BOAMP pour un dashboard France). Module cible : enrichissement/comparaison UE ; non ingéré à ce jour.

---

## 6. DECP « fichiers consolidés » officiels (JSON, DAJ) et flux amont

- **Page** : <https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-fichiers-consolides> — producteur MEF/DAJ, ~40 fichiers **JSON de 66 Mo à 970 Mo**, dernière MAJ **17/08/2026**, Licence Ouverte. C'est la matière première (déjà intégrée aux sources n° 1 et 3).
  **Verdict : EXPLOITABLE AVEC EFFORT** (gros JSON bruts, schéma imbriqué) — inutile si l'on prend n° 1/n° 3.
- **« API DECP » AIFE** : <https://www.data.gouv.fr/datasets/api-decp> — 1 943 fichiers JSON, MAJ **19/08/2026**, LO 2.0. L'API de dépôt/consultation associée est hébergée sur **PISTE (piste.gouv.fr, inscription + clé requises)** ; mise en production fin nov. 2025, ouverture T1 2026, PLACE premier consommateur. **Verdict : EXPLOITABLE AVEC EFFORT** (clé PISTE ; le miroir data.gouv suffit).
- **PES Marché ≥ 2024 (DGFiP)** : <https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-transmises-via-le-pes-marche-depuis-2024> — flux comptable qui a beaucoup amélioré la couverture des collectivités depuis 2024 ; déjà agrégé dans n° 1. **Verdict : AVEC EFFORT / redondant.**
- **PLACE** (<https://www.marches-publics.gouv.fr/>, AIFE) : plateforme de dématérialisation des consultations de l'État. **Pas d'API open data des consultations** ; ses données remontent via AIFE (DECP) et ses avis via BOAMP/TED. **Verdict : INEXPLOITABLE en direct (pas d'API publique) — passer par BOAMP/DECP/APProch.**
- **Schéma en vigueur** : arrêtés du 22/12/2022 (modifiés 22/12/2023), applicables depuis le 01/01/2024 — publication obligatoire **sur data.gouv.fr** ; schéma technique `139bercy/format-commande-publique` **v2.0.x** : <https://schema.data.gouv.fr/139bercy/format-commande-publique/>.

---

## 7. Seuils 2026 (contexte à afficher dans le dashboard)

Vérifiés le 19/08/2026 (la page DAJ economie.gouv.fr renvoie 403 anti-bot en fetch direct ; chiffres recoupés via marche-public.fr, Centre Inffo, La Vie Communale — références réglementaires citées) :

- **Seuils européens de procédure formalisée au 01/01/2026** (règlements délégués UE 2025/2150, 2151, 2152 et 2487 ; avis NOR ECOM2600976V du 13/01/2026) :
  - Fournitures & services, État : **140 000 € HT** ; collectivités : **216 000 € HT** ; entités adjudicatrices et défense/sécurité : **432 000 € HT** ;
  - Travaux et concessions : **5 404 000 € HT**.
- **Seuils nationaux de dispense de publicité/mise en concurrence** : travaux **100 000 € HT** (pérennisé au 01/01/2026) ; fournitures & services **40 000 € HT jusqu'au 31/03/2026 puis 60 000 € HT à partir du 01/04/2026** (décret n° 2025-1386 du 29/12/2025).
- **Publicité BOAMP ou JAL obligatoire ≥ 90 000 € HT** (MAPA) → en-dessous, publicité libre : le BOAMP ne voit pas tout le bas du spectre.
- **Obligation DECP : ≥ 40 000 € HT, publication sous 2 mois après notification** (arrêté du 22/12/2022) → conséquence directe pour le dashboard : un « notifiés ces 30 derniers jours » est **structurellement incomplet** (latence légale) ; l'afficher avec la mention « données en cours de consolidation ».

---

## 8. Pièges transverses (synthèse qualité)

1. **Latence légale DECP** : jusqu'à 2 mois entre notification et publication → biais de récence sur toute fenêtre courte.
2. **Montants** : les accords-cadres portent des montants **maximum** ; erreurs de saisie fréquentes (démonstration réelle : 4,33 Md€/30 j sur l'Oise en sommant les montants bruts) → utiliser `montant_rationalise`/`montant_anomalie` (source n° 1) ou écrêter (p99) côté dashboard.
3. **Multi-lignes** : 1 marché = n lignes (titulaires, modifications) dans la source n° 1 → `donneesActuelles=true` + dédup `uid` avant tout comptage. ⚠ **Rectifié le 21/08/2026, voir l'encadré en tête : « avant tout comptage » ne s'applique pas à la datation, qui prend `min(dateNotification)` sur toutes les lignes.**
4. **Lieu d'exécution** : `lieuexecution_code` mélange départements, communes, pays (« 60 », « 14000 », « FR ») → pour la carte, utiliser `acheteur_departement_code`/lat-lng (source n° 1) ou normaliser.
5. **Exhaustivité** : couverture DECP incomplète (acheteurs défaillants), nettement améliorée depuis 2024 (PES Marché) ; concessions quasi absentes (589 enregistrements « valides »).
6. **Plateformes Opendatasoft** (BOAMP + data.economie) : `/records` plafonné à **offset+limit ≤ 10 000** (constaté), quota **50 000 appels/jour** (en-tête constaté) → bulk via `/exports/{csv,parquet,json}` (streaming filtrable, testé).
7. **data.economie** : valeur de remplissage `"CDL"` = null.
8. **BOAMP** : montant non à plat (JSON eForms à parser) ; joindre `annonce_lie` pour rectificatifs/annulations.

---

## 9. Tableau récapitulatif

| # | Source | URL d'accès testée | Accès | Fraîcheur constatée (19/08/2026) | Volumétrie | Licence | Verdict | Module cible |
|---|--------|--------------------|-------|-------------------------------|-----------|---------|---------|--------------|
| 1 | DECP consolidées tabulaires | `tabular-api.data.gouv.fr/api/resources/22847056-.../data/` + Parquet 243 Mo | API REST sans clé + fichiers | MAJ quotidienne, build du jour, notif. J-1 | 3 238 492 lignes | LO 2.0 | **EXPLOITABLE DIRECT** | Attributions + **carte de France** (géoloc incluse) |
| 2 | BOAMP (DILA) | `boamp-datadila.opendatasoft.com/api/explore/v2.1/.../boamp/records` | API sans clé + exports | Quotidienne, annonces du jour même | 1 698 829 annonces | etalab-2.0 | **EXPLOITABLE DIRECT** | **Appels d'offres en cours** (8 988 ouverts) |
| 3 | DECP data.economie (DAJ) | `data.economie.gouv.fr/api/explore/v2.1/.../decp-2022-marches-valides/records` | API sans clé + exports + group_by | J-2 (17/08) | 689 062 marchés | LO 2.0 | **EXPLOITABLE DIRECT** | Chiffres officiels, agrégats serveur |
| 4 | APProch (projets d'achats) | `data.economie.gouv.fr/.../projets-dachats-publics/records` | API sans clé | J-4 (15/08) | 11 388 projets (4 060 à venir) | LO 2.0 | **EXPLOITABLE DIRECT** | **Marchés à venir** |
| 5 | TED (UE) | `POST api.ted.europa.eu/v3/notices/search` | API sans clé | Quotidienne | 58 379 avis FR 2026 | Réutilisation libre UE | EXPLOITABLE DIRECT (non prioritaire) | Comparaison UE, non ingéré |
| 6 | DECP fichiers consolidés JSON (DAJ) | data.gouv.fr (40 JSON 66 Mo–970 Mo) | Téléchargement | 17/08 | ~40 fichiers | LO | AVEC EFFORT (redondant avec 1/3) | — |
| 7 | API DECP AIFE (PISTE) | piste.gouv.fr + miroir data.gouv (1 943 JSON) | Clé PISTE requise | 19/08 (miroir) | 1 943 fichiers | LO 2.0 | AVEC EFFORT | — |
| 8 | PLACE (consultations État) | marches-publics.gouv.fr | Pas d'API publique | — | — | — | **INEXPLOITABLE en direct** (données via BOAMP/DECP/APProch) | — |
| 9 | Concessions (decp-2022-concessions-valides) | data.economie.gouv.fr | API sans clé | — | **589** seulement | LO 2.0 | AVEC EFFORT (couverture trop faible) | Mention méthodo |
| 10 | decp_augmente | data.economie.gouv.fr | — | marqué **[Obsolète]** | — | — | INEXPLOITABLE (remplacé par 1/3) | — |

---

## 10. Requêtes-clés prêtes à l'emploi (toutes testées HTTP 200 le 19/08/2026)

```bash
# 1. Marchés notifiés ces 30 derniers jours — officiel DAJ (6 657 résultats)
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp-2022-marches-valides/records?where=datenotification%3E%3Ddate'2026-07-20'&order_by=datenotification%20desc&limit=100"

# 2. Idem, version enrichie géolocalisée pour la carte (24 554 lignes)
curl "https://tabular-api.data.gouv.fr/api/resources/22847056-61df-452d-837d-8b8ceadbfc52/data/?dateNotification__greater=2026-07-20&donneesActuelles__exact=true&page_size=200"

# 3. Appels d'offres EN COURS (clôture future) — alimente le module du même nom (8 988 résultats)
curl --compressed "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records?where=datelimitereponse%3Edate'2026-08-19'%20AND%20nature%3D'APPEL_OFFRE'&order_by=datelimitereponse%20asc&limit=20"

# 4. Agrégat carte : nb + montant par lieu d'exécution sur 30 jours (écrêter les montants !)
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp-2022-marches-valides/records?where=datenotification%3E%3Ddate'2026-07-20'&group_by=lieuexecution_code&select=lieuexecution_code,count(*)%20as%20nb,sum(montant)%20as%20total&order_by=total%20desc"

# 5. Projets d'achats à venir — APProch (4 060 résultats)
curl --compressed "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/records?where=date_previsionnelle_de_publication%3E%3Ddate'2026-08-19'&order_by=date_previsionnelle_de_publication%20asc&limit=20"

# 6. TED : avis France 2026 (58 379) / clôtures futures cn-standard (6 365)
curl -X POST "https://api.ted.europa.eu/v3/notices/search" -H "Content-Type: application/json" \
  -d '{"query":"(buyer-country IN (FRA)) AND (publication-date>=20260101)","fields":["publication-number","notice-title","publication-date"],"limit":10}'

# 7. Bulk quotidien recommandé pour la base locale du dashboard (243 Mo, build du jour)
curl -L -o decp.parquet "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"
```

**Architecture recommandée** : ingestion quotidienne du `decp.parquet` (n° 1) pour la carte et les fiches ; appels API BOAMP (n° 2) rafraîchis plusieurs fois par jour pour les AO en cours ; APProch (n° 4) hebdomadaire pour « à venir » ; data.economie (n° 3) en contrôle de cohérence ; TED non ingéré.
