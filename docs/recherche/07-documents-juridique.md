# 07 — Documents officiels & juridique : DILA, Journal officiel, Légifrance

**Vérifié le 19 août 2026** par appels réels (curl, téléchargements, extraction de tarballs) et recherche web. Aucune source déclarée exploitable sans avoir été appelée. Fichiers de test conservés dans `/Users/koutakou/france-transparence/data/tmp/`.

**Conclusion d'ensemble** : les dumps open data de la DILA sur `echanges.dila.gouv.fr` sont la voie royale — sans authentification, sans quota, licence ouverte, fraîcheur du jour même (JO du 19/08 disponible le 19/08 à 00h30). Le site Légifrance est bloqué au scraping (403 Datadome), l'API PISTE exige une inscription humaine one-shot. Le module « Documents » peut être alimenté quotidiennement par un seul tarball de ~100 Ko–500 Ko par jour.

---

## 1. Dumps open data DILA — echanges.dila.gouv.fr/OPENDATA/ ★ voie royale

### 1.1 Accès et inventaire

- **URL testée** : `https://echanges.dila.gouv.fr/OPENDATA/` → **HTTP 200**, listing Apache HTML (ISO-8859-1). Aucune authentification, aucun user-agent requis, aucun quota constaté. Accès FTPS également annoncé (`ftps://echanges.dila.gouv.fr`) — inutile, HTTPS suffit.
- **34 répertoires** constatés le 19/08/2026 (avec date de dernière modification du listing racine) :

| Répertoire | Contenu | Dernière modif constatée |
|---|---|---|
| **JORF/** | JO « Lois et décrets », XML complet (format « global ») | 2026-08-19 00:30 |
| **JORFSIMPLE/** | JO « Lois et décrets », XML autocontenu (1 fichier = 1 texte) | 2026-08-19 00:30 |
| **LEGI/** | Codes, lois et règlements consolidés | 2026-08-18 22:44 |
| **DOLE/** | Dossiers législatifs | 2026-08-18 22:43 |
| **Debats/** | Débats parlementaires AN + Sénat (comptes rendus) | AN : session du 31/07/2026 |
| **BODACC/** | Annonces civiles et commerciales | FluxAnneeCourante : 2026-08-19 08:02 |
| **ASSOCIATIONS/** | Annonces JOAFE (créations, dissolutions) | FluxHistorique 2026-05 |
| **COMPTES_DES_ASSOCIATIONS/** | Comptes annuels des associations | FLUX : 2026-08-19 14:29 |
| **RefOrgaAdminEtat/** | Référentiel de l'organisation administrative de l'État | FluxAnneeCourante : 2026-08-19 08:30 |
| **BALO/** | Bulletin des annonces légales obligatoires | 2026-08-19 09:00 |
| **BOAMP/** | Marchés publics (annonces) | 2026-02-19 (répertoire racine) |
| **AMF/** | Décisions AMF | derniers tarballs vus : 31/12/2025 |
| CASS/, CAPP/, INCA/, JADE/, CONSTIT/, CNIL/ | Jurisprudence (Cassation, appel, Conseil d'État, Conseil constit., CNIL) | CASS : 2026-08-17 |
| KALI/, ACCO/, BOCC/ | Conventions collectives, accords d'entreprise | 2026-08 / 2026-02 |
| CIRCULAIRES/ | Circulaires (gelé depuis 2017) | 2017-08-31 |
| DTD_LEGIFRANCE/ | DTD + documentation technique | 2023-2024 |
| Autres : DISCOURS_PUBLICS/, RAPPORTS_PUBLICS/, Questions-Reponses/, SARDE/, SERVICE-PUBLIC/, ENTREPRENDRE_SERVICE-PUBLIC/, Protocole_du_Gouvernement/, Protocole_des_JAAI/, Liste_Greffes_BODACC/, Base_données_locales/, test/ | — | — |

### 1.2 Fonctionnement général : « Freemium » + deltas

Chaque fonds suit le même schéma, vérifié sur JORF/JORFSIMPLE/LEGI/DOLE :

- **Un dump complet** (« Freemium »), instantané re-généré périodiquement :
  - `Freemium_jorf_global_20250713-140000.tar.gz` — **1,6 Go** (13/07/2025) ;
  - `Freemium_jorf_simple_20250713-140000.tar.gz` — **1,0 Go** ;
  - `Freemium_legi_global_20250713-140000.tar.gz` — **1,1 Go** ;
  - `Freemium_dole_global_20250713-140000.tar.gz` — 18 Mo.
- **Des deltas incrémentaux** `JORF_YYYYMMDD-HHMMSS.tar.gz` depuis la date du Freemium (738 tarballs présents dans JORF/ au 19/08/2026). État = Freemium + application des deltas dans l'ordre chronologique.

### 1.3 Rythme réel observé (JORF, listing du 05 au 19/08/2026)

**Deux livraisons par jour**, aux rôles différents — vérifié par téléchargement des deux :

1. **Livraison nocturne ~00h20–00h45** (petite : 76 Ko–440 Ko) = **le JO du jour**. Testé : `JORF_20260819-003035.tar.gz` (440 Ko, téléchargé le 19/08) contient exactement le **JORF n°0192 du 19 août 2026** — 1 conteneur (sommaire), 83 textes, 418 articles. C'est la livraison à surveiller pour le flux quotidien.
2. **Livraison du soir ~21h–22h45** (grosse : 2,8–13 Mo) = **mises à jour rétroactives**. Testé : `JORF_20260818-223511.tar.gz` (13 Mo) contient 237 conteneurs dont des JO très anciens (ids JORFCONT00002xxx) — consolidations, corrections de liens. Inutile pour un flux « derniers textes », indispensable seulement pour maintenir un miroir exact.

**Trous observés** : pas de livraison nocturne les 10, 16 et 17 août (lundis/dimanche suivant férié) — le JO ne paraît pas tous les jours. Les horodatages varient (00:21 à 00:41) : **l'URL n'est pas prédictible**, il faut lister le répertoire (index HTML trivial à parser) et détecter les nouveaux fichiers.

### 1.4 Structure interne d'un tarball JORF (testé réellement)

`JORF_20260819-003035.tar.gz` (440 Ko compressé, 1 431 entrées) :

```
20260819-003035/jorf/global/
├── conteneur/JORF/CONT/00/00/54/70/68/JORFCONT000054706874.xml   (1)  ← le sommaire du JO n°0192
├── section_ta/JORF/SCTA/.../JORFSCTA*.xml                        (49) ← sections du sommaire
├── texte/version/JORF/TEXT/.../JORFTEXT*.xml                     (83) ← métadonnées + visas/signataires
├── texte/struct/JORF/TEXT/.../JORFTEXT*.xml                      (83) ← squelette (liens vers articles)
├── article/JORF/ARTI/.../JORFARTI*.xml                           (418) ← corps des articles
└── eli/{loi,decret,arrete,decision,jo}/2026/M/J/NOR/jo/.../versions.xml (299) ← alias ELI
```

Arborescence par id découpé en paires (`00/00/54/70/68/`). Encodage UTF-8, DTD dans `DTD_LEGIFRANCE/` (archive 7z de 2018 + notes de migration 2023 et doc NOR 2024).

**Le conteneur (JORFCONT) = le sommaire du jour, structuré** — extrait réel :

```xml
<JO>
 <META>…<ID>JORFCONT000054706874</ID>
   <ID_ELI>https://www.legifrance.gouv.fr/eli/jo/2026/8/19/0192</ID_ELI>
   <TITRE>JORF n°0192 du 19 août 2026</TITRE><NUM>0192</NUM><DATE_PUBLI>2026-08-19</DATE_PUBLI>…</META>
 <STRUCTURE_TXT>
  <TM niv="2"><TITRE_TM>LOIS</TITRE_TM>
    <LIEN_TXT idtxt="JORFTEXT000054706877" titretxt="LOI n° 2026-794 du 18 août 2026 relative au droit à l'aide à mourir (1)"/>
    …</TM>
  <TM niv="3"><TITRE_TM>Mesures nominatives</TITRE_TM>
    <TM niv="4"><TITRE_TM>Premier ministre</TITRE_TM>
      <LIEN_TXT idtxt="JORFTEXT000054708776" titretxt="Décret du 17 août 2026 portant nomination (Cour des comptes)"/>
      <LIEN_TXT idtxt="JORFTEXT000054708793" titretxt="Décret du 17 août 2026 portant nomination (chambres régionales des comptes) - M. LAUNAY (Vincent)"/>…
```

La hiérarchie `TM` (niv 1→4) reproduit les rubriques officielles : **LOIS**, **Décrets, arrêtés, circulaires > Textes généraux** (par ministère), **Mesures nominatives** (par ministère), Conseil constitutionnel, Sénat, etc. Le JO n°0192 du 19/08 comptait 38 textes contenant « nominat » sur 83.

**Un texte (JORFTEXT, fichier texte/version)** — champs réels constatés : `ID`, `ID_ELI`, `NATURE` (LOI/DECRET/ARRETE/DECISION), `NOR`, `NUM_PARUTION` (n° du JO), `NUM_SEQUENCE`, `DATE_PUBLI`, `DATE_TEXTE`, `TITRE`, `TITREFULL`, `MINISTERE`, `LIENS` (citations d'autres textes avec ids), puis `VISAS`, `SIGNATAIRES` (HTML simple dans `<CONTENU>`). Le corps est dans les fichiers `JORFARTI` (`BLOC_TEXTUEL/CONTENU`, avec `CONTEXTE` rappelant le texte parent).

### 1.5 JORFSIMPLE — le format recommandé pour le dashboard

`JORFSIMPLE_20260819-003035.tar.gz` (392 Ko, 786 entrées, mêmes horodatages que JORF) — testé :

```
20260819-003035/jorf/simple/JORF/CONT/00/00/54/70/68/JORFCONT000054706874/
├── JORFCONT000054706874.xml   ← même sommaire structuré (83 LIEN_TXT, rubrique « Mesures nominatives »)
└── JORFTEXT0000547xxxxx.xml   ← 83 fichiers : 1 texte = 1 XML AUTOCONTENU
```

Chaque `JORFTEXT*.xml` (racine `<TEXTE>`) contient **tout** : métadonnées à plat (ID, ID_ELI, NATURE, NOR, NUM_PARUTION, DATE_PUBLI, DATE_TEXTE, TITREFULL, MINISTERE, ORIGINE_PUBLI avec id du conteneur), VISAS, puis `<STRUCT>` avec les `<ARTICLE>` complets (NUM, ID_ELI, BLOC_TEXTUEL) et SIGNATAIRES. Extrait réel (arrêté de délégation de signature) :

```xml
<TEXTE>
 <ID>JORFTEXT000054708438</ID>
 <ID_ELI>https://www.legifrance.gouv.fr/eli/arrete/2026/8/11/ARMM2621619A/jo/texte</ID_ELI>
 <NATURE>ARRETE</NATURE><NOR>ARMM2621619A</NOR>
 <NUM_PARUTION>0192</NUM_PARUTION><DATE_PUBLI>2026-08-19</DATE_PUBLI><DATE_TEXTE>2026-08-11</DATE_TEXTE>
 <TITREFULL>Arrêté du 11 août 2026 portant délégation de signature (cabinet de la ministre déléguée…)</TITREFULL>
 <MINISTERE>Ministère des armées et des anciens combattants</MINISTERE>
 …<STRUCT><ARTICLE><NUM>1</NUM><BLOC_TEXTUEL><CONTENU><p>Délégation permanente est donnée à M. Léo LESNE…
```

**Avantage décisif** : pas de jointure conteneur/section/texte/article à reconstruire — un parseur de ~50 lignes suffit. C'est le format à retenir.

### 1.6 Licence, volumétrie, pièges

- **Licence** : Licence Ouverte / Open Licence (champ `license: fr-lo` du dataset data.gouv.fr « JORF », producteur « Premier ministre »). Réutilisation libre avec mention de la source. Attention ponctuelle : PDF `AVERTISSEMENT-metadonnees_textes_entreprise` (métadonnées « entreprise » sous conditions — champ `<ENTREPRISE texte_entreprise="non">` vu dans les XML).
- **Volumétrie quotidienne** : 76 Ko–440 Ko (nuit) + 2,8–13 Mo (soir, ignorable pour le flux). Historique complet : 1,0–1,6 Go one-shot.
- **Pièges** : URLs non prédictibles (lister l'index) ; jours sans JO ; la livraison du soir réécrit l'historique (ne pas la confondre avec du neuf) ; listing HTML en ISO-8859-1 ; DTD anciennes (2018) mais notes de migration 2023 à lire si parsing strict ; le nom du dossier interne du tarball = horodatage de livraison.

**Verdict : EXPLOITABLE DIRECT** — module « Documents » (JO quotidien, nominations, lois, décrets), et au-delà : LEGI (consolidé), DOLE (suivi des lois), Debats, BODACC/ASSOCIATIONS (recoupements), RefOrgaAdminEtat (référentiel ministères, flux quotidien constaté le 19/08 08:30).

---

## 2. API Légifrance via PISTE (piste.gouv.fr)

- **Endpoint OAuth testé réellement** : `POST https://oauth.piste.gouv.fr/api/oauth/token` (client_credentials, identifiants bidons) → **HTTP 400 `invalid_client`** : l'endpoint est vivant et le flux est bien OAuth2 client_credentials. Sandbox : `sandbox-oauth.piste.gouv.fr`.
- **Conditions 2026** (FAQ officielle Légifrance + page d'inscription PISTE, lues le 19/08/2026) :
  1. créer un compte sur `https://piste.gouv.fr/registration` (nom, email, mot de passe 12+ caractères ; **activation par lien email sous 5 jours** ; pas de CAPTCHA ni validation manuelle documentés — portail AIFE) ;
  2. **accepter les CGU** de l'API Légifrance (menu « API > Consentement CGU API »), sinon 403 ;
  3. créer une application (sandbox et/ou production) et cocher la consommation de l'API Légifrance ; récupérer Client_Id/Client_Secret (« APPLICATIONS > API souscrites > Identifiants Oauth ») ;
  4. token Bearer valable 3600 s ; quotas par environnement (production > sandbox, chiffres non publiés).
- **Verdict faisabilité sans humain : NON en autonomie totale** — la création de compte, l'activation email et le clic de consentement CGU sont des actions de portail web (~10–15 min, one-shot, aucune file d'attente de validation administrative documentée). **Après ce one-shot, tout est automatisable** (client_credentials sans interaction). 
- **Utile pour** : recherche plein texte, consultation ponctuelle (`/consult/jorfCont` rend le sommaire d'un JO), textes consolidés à la demande. **Non nécessaire au module « Documents »** : les dumps DILA couvrent le besoin sans compte.

**Verdict : AVEC EFFORT** (one-shot humain), et **optionnel** vu la section 1.

---

## 3. Site Légifrance — JO électronique authentifié

- **Tests réels du 19/08/2026** : `https://www.legifrance.gouv.fr/jorf/jo/2026/08/19/0192` et `https://www.legifrance.gouv.fr/jorf/jo` (sommaire du dernier JO) → **HTTP 403** (page anti-bot ~5,6 Ko), même avec user-agent navigateur. Protection Datadome : **le scraping HTML de Légifrance est INEXPLOITABLE** en 2026.
- Ces URLs restent **valables pour un navigateur humain** — à utiliser comme **liens sortants** du dashboard :
  - sommaire d'un JO : `https://www.legifrance.gouv.fr/jorf/jo/AAAA/MM/JJ/NNNN` (ex. `/jorf/jo/2026/08/19/0192`) ;
  - un texte par id : `https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054708438` ;
  - ELI (fourni tel quel par les XML DILA, champ `ID_ELI`) : `https://www.legifrance.gouv.fr/eli/arrete/2026/8/11/ARMM2621619A/jo/texte`.
- Le JO « authentifié » (PDF signé) se télécharge depuis ces pages — même protection : ne pas tenter en batch.

**Verdict : INEXPLOITABLE en collecte, EXPLOITABLE comme cible de liens** (ids et ELI présents dans chaque XML DILA).

---

## 4. Portails Opendatasoft de la DILA

- **`https://journal-officiel-datadila.opendatasoft.com`** — testé : API Explore v2.1 **HTTP 200 sans clé**. **18 datasets**, tous périphériques au JO « associations/annonces » : `jo_associations` (**5 645 043 enregistrements, dernière parution : 2026-08-19** — testé), `joafe_*`, `balo`, `osop-comptes-de-resultats`, `osop-entites`… **Aucun dataset JORF « Lois et décrets »** : ce portail ne remplace PAS les dumps pour le JO.
- **`https://bodacc-datadila.opendatasoft.com`** — testé : **9 datasets**, dont `annonces-commerciales` (**50 393 102 enregistrements, dernière parution : 2026-08-19** — testé). API riche (filtres `where=`, facettes, export JSON/CSV).
- Exemple d'appel testé : `/api/explore/v2.1/catalog/datasets/jo_associations/records?limit=1&order_by=dateparution DESC` → JSON propre.

**Verdict : EXPLOITABLE DIRECT** pour modules « Associations » et « Vie des entreprises » (BODACC) ; hors périmètre pour le flux JO lois-décrets.

---

## 5. data.gouv.fr

- **API testée** : `https://www.data.gouv.fr/api/1/datasets/jorf-les-donnees-de-l-edition-lois-et-decrets-du-journal-officiel/` → 200. Licence **fr-lo**, organisation « Premier ministre », dernière mise à jour 2026-08-18. Les 5 ressources **pointent toutes vers echanges.dila.gouv.fr** (JORF/, JORFSIMPLE/, DTD, PDF de présentation) : data.gouv.fr n'est qu'un **catalogue**, pas un miroir. Datasets frères : LEGI, DOLE, KALI, CAPP, JADE, INCA…
- data.gouv.fr référence aussi l'API Légifrance (fiche « dataservice »).

**Verdict : EXPLOITABLE comme catalogue/licence de référence** ; la donnée elle-même reste chez DILA.

---

## 6. Alimentation quotidienne recommandée du module « Documents »

**Pipeline (cron quotidien vers 06h00 Europe/Paris, une seule source)** :

1. `GET https://echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/` → parser l'index HTML (regex `JORFSIMPLE_\d{8}-\d{6}\.tar\.gz`), retenir les fichiers plus récents que le dernier traité (état local). Ignorer les livraisons du soir (~21h) si l'on ne veut que le neuf : la livraison de la nuit (~00h30) du jour J contient le JO du jour J.
2. Télécharger (≤ 500 Ko), extraire. Le(s) `JORFCONT*.xml` = sommaire officiel ; les `JORFTEXT*.xml` = textes complets autocontenus.
3. Indexer chaque texte : `NATURE`, `NOR`, `TITREFULL`, `MINISTERE`, `DATE_PUBLI`, `DATE_TEXTE`, `NUM_PARUTION`, `ID`, `ID_ELI`, rubrique du sommaire (chemin des `TITRE_TM` menant au `LIEN_TXT`).
4. Filtres du dashboard, d'après les rubriques réelles constatées :
   - **Nominations** : textes sous `TM « Mesures nominatives »` (sous-arbre par ministère) — le corps (`BLOC_TEXTUEL`) contient les noms des personnes ; le titre suffit souvent (« Décret du 17 août 2026 portant nomination (Cour des comptes) - M. LAUNAY (Vincent) »).
   - **Lois** : `TM « LOIS »` ou `NATURE=LOI` (5 lois publiées le 19/08, dont LOI 2026-794 « droit à l'aide à mourir »).
   - **Budget/marchés** : `NATURE=DECRET|ARRETE` + mots-clés dans `TITREFULL` (crédits, ouverture/annulation, marchés, subvention…) + `MINISTERE` économie/comptes publics.
5. Lien officiel de chaque item : `https://www.legifrance.gouv.fr/jorf/id/{ID}` (et/ou `ID_ELI`).
6. Tolérance : jours sans JO (aucun nouveau fichier) ; reprise = rejouer les fichiers manqués dans l'ordre (l'index les garde tous).

**Historique initial** (facultatif) : `Freemium_jorf_simple_*.tar.gz` (1,0 Go) + deltas depuis le 13/07/2025 ; ou simplement démarrer au premier delta utile.

---

## 7. Tableau récapitulatif

| Source | URL testée | Accès | Format | Fraîcheur constatée (19/08/2026) | Licence | Verdict | Module |
|---|---|---|---|---|---|---|---|
| Dumps DILA JORFSIMPLE | echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/ | HTTP 200, sans auth | tar.gz de XML autocontenus, ~100–500 Ko/j (nuit) | JO n°0192 du 19/08 dispo le 19/08 00h30 | Licence Ouverte (fr-lo) | **EXPLOITABLE DIRECT** ★ | Documents (flux JO, nominations, lois, décrets) |
| Dumps DILA JORF (global) | …/OPENDATA/JORF/ | HTTP 200 | tar.gz XML éclatés (conteneur/section/texte/article/eli) | idem | fr-lo | EXPLOITABLE DIRECT (plus lourd à parser) | Documents (variante) |
| Dumps LEGI / DOLE / Debats | …/OPENDATA/{LEGI,DOLE,Debats}/ | HTTP 200 | tar.gz XML (Debats AN : .taz par séance) | LEGI/DOLE : 18/08 ; AN : 31/07 (vacances) | fr-lo | EXPLOITABLE DIRECT | Lois consolidées, suivi législatif, débats |
| BODACC / ASSOCIATIONS / COMPTES / RefOrgaAdminEtat | …/OPENDATA/… | HTTP 200 | XML (taz/tar.gz), flux année courante | BODACC 19/08 08:02 ; Comptes assos 19/08 14:29 ; RefOrga 19/08 08:30 | fr-lo | EXPLOITABLE DIRECT | Entreprises, associations, référentiel État |
| API Légifrance (PISTE) | oauth.piste.gouv.fr/api/oauth/token | OAuth2 client_credentials — testé : 400 invalid_client (vivant) | JSON | temps réel | CGU PISTE + fr-lo | **AVEC EFFORT** (compte + CGU + app : one-shot humain ~15 min, pas de validation admin documentée) | Recherche/consultation à la demande (optionnel) |
| Site Légifrance (HTML/PDF authentifié) | legifrance.gouv.fr/jorf/jo/2026/08/19/0192 | **403 Datadome** (testé) | HTML/PDF | — | — | **INEXPLOITABLE en collecte** ; liens sortants OK (`/jorf/id/{ID}`, ELI) | Liens officiels |
| ODS DILA JO | journal-officiel-datadila.opendatasoft.com | HTTP 200 sans clé (testé) | JSON API Explore v2.1 (18 datasets) | jo_associations : parution 19/08 (5,6 M enreg.) | Licence Ouverte | EXPLOITABLE DIRECT (assos/BALO seulement, pas de JORF) | Associations |
| ODS DILA BODACC | bodacc-datadila.opendatasoft.com | HTTP 200 sans clé (testé) | JSON (9 datasets) | annonces-commerciales : parution 19/08 (50,4 M enreg.) | Licence Ouverte | EXPLOITABLE DIRECT | Entreprises |
| data.gouv.fr (datasets DILA) | data.gouv.fr/api/1/datasets/jorf-… | HTTP 200 (testé) | JSON (catalogue) | maj 18/08 | fr-lo | EXPLOITABLE (catalogue ; ressources = liens vers DILA) | Référence licence |

---

## 8. Fichiers de test conservés

Dans `/Users/koutakou/france-transparence/data/tmp/` (24 Mo) : `JORF_20260819-003035.tar.gz` (+ extraction `20260819-003035/`), `JORFSIMPLE_20260819-003035.tar.gz` (+ extraction `simple/`), `JORF_20260818-223511.tar.gz` (livraison du soir, 13 Mo), listings HTML (`dila-opendata-root.html`, `dila-jorf-listing.html`).
