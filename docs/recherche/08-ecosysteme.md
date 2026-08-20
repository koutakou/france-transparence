# 08 — Écosystème & état de l'art de la transparence civique française

> **Date de vérification : 19 août 2026.** Chaque statut « vivant / mort / gelé » ci-dessous a été **testé en réel** ce jour (curl : code HTTP + contenu, ou WebFetch quand un anti-bot bloquait curl), complété par des recherches web en français. Les affirmations non testables directement sont sourcées. Convention : 🟢 vivant et à jour · 🟡 en ligne mais gelé/dégradé · 🔴 mort ou inexistant.

---

## 1. Projets citoyens et associatifs : vivants, morts, leçons

### 1.1 La galaxie Regards Citoyens — l'acteur historique en extinction lente

| Site | Test 19/08/2026 | Verdict |
|---|---|---|
| regardscitoyens.org | HTTP 200 | 🟡 asso vivante, projets phares gelés |
| **nosdeputes.fr** | HTTP 200 | 🟡 **figé sur la 16e législature** (données arrêtées à la dissolution du 09/06/2024) |
| **nossenateurs.fr** | HTTP 200 | 🔴 **officiellement arrêté** — page d'adieu ; archive figée oct. 2004 → mars 2023 sur archive.nossenateurs.fr (testée, 200) |
| lafabriquedelaloi.fr | HTTP 200 | 🔴 gelé : 1 531 dossiers, **dernier dossier daté du 11/01/2022** (testé via `/api/dossiers.csv`), assets front de 2018 |
| nosfinanceslocales.fr | SSL invalide, HTTP 404 | 🔴 mort |
| 2017-2022.nosdeputes.fr | HTTP 200 | 🟡 archive de la 15e législature |
| 2022-2024.nosdeputes.fr | NXDOMAIN | 🔴 n'existe pas (la 16e reste sur le domaine principal) |

Constats précis testés :
- Bandeau affiché sur nosdeputes.fr le 19/08/2026 : « *Ce site présente les travaux des députés de la précédente législature. NosDéputés.fr reviendra d'ici quelques mois avec une nouvelle version pour les députés élus en 2024* ». **Plus de deux ans après la dissolution de juin 2024, la 17e législature n'est toujours pas couverte.** L'API répond mais `deputes/enmandat/json` renvoie `{"deputes":[]}` (plus personne « en mandat » dans la base).
- GitHub (api.github.com, testé) : `nosdeputes.fr` dernier push 14/11/2024 ; un nouveau front `nosdeputes-front` en chantier (dernier push 02/07/2025) ; l'asso reste active ailleurs (`suivi-documents-parlementaires` pushé le 02/07/2026, `professions-foi-candidats-2026` pour les municipales, 23/03/2026). Une annonce de fermeture de NosDéputés circulant en ligne était un poisson d'avril.
- Réutilisable : l'API historique JSON/CSV (2007→juin 2024) reste servie ; données historiquement en ODbL (partage à l'identique — la page `/licences` redirige vers l'archive, à re-vérifier avant réutilisation), code AGPL. Excellent gisement **historique**, inutilisable pour du temps réel.

**Leçon n° 1 (la plus importante de ce rapport) : la rupture institutionnelle tue le scraping bénévole.** La dissolution de juin 2024 a servi de crash-test : tout ce qui reposait sur des parseurs maison entretenus à la main (NosDéputés, NosSénateurs, Fabrique de la Loi) s'est figé ; tout ce qui consomme l'open data officiel avec un pipeline automatisé (Datan, Tricoteuses, Pappers) a absorbé la 17e législature sans interruption.

### 1.2 Les vivants qui marchent

- **Datan** (datan.fr) — 🟢 le survivant exemplaire. HTTP 200, couvre la 17e législature, scores et statistiques pédagogiques par député/groupe, suit déjà les municipales 2026 (311 députés candidats recensés). Publie ses propres jeux retraités sur data.gouv.fr : **vérifié par API le 19/08/2026, `last_update = 2026-08-19` (le jour même), licence `fr-lo` (Licence Ouverte)**. Modèle : petite équipe, périmètre resserré (votes + participation), consommation de l'open data AN. Nos croisements peuvent réutiliser ses datasets directement.
- **Les Tricoteuses** (tricoteuses.fr, git.tricoteuses.fr, assemblee.tricoteuses.fr) — 🟢 l'infrastructure de l'écosystème. Testé : 200, derrière l'anti-bot Anubis (à prévoir pour nos sondes). Sert la **17e législature en cours** (amendements `AMANR5L17…`), APIs REST PostgREST (AN, Sénat, Légifrance), bibliothèques npm (`@tricoteuses/assemblee` v3.3.3, **AGPL-3.0-or-later** — viralité à considérer si on réutilise le code ; les données restent celles des assemblées, licence ouverte). Depuis 2026, le projet est alimenté/financé en partie par Legiwatch (voir 1.4) : symbiose commun ↔ produit commercial.
- **Projet Arcadie** (projetarcadie.com) — 🟢 vivant et actif : articles de juillet 2026 vérifiés (budget 2026, 49.3 Lecornu, canicule à l'AN). Base de données sur les parlementaires + média, tenu par Tris Acatrinei depuis 2015. Financement par dons, fragilité assumée publiquement. Données non ouvertes en masse : c'est une source éditoriale, pas une API.
- **Ma Dada** (madada.fr) — 🟢 la brique CADA de l'écosystème (basée sur le logiciel libre Alaveteli) : plus de 51 000 demandes d'accès aux documents administratifs adressées à ~52 000 autorités, blog actif, offre « pro » pour journalistes/chercheurs. C'est l'outil à utiliser (pas à refaire) quand une donnée du dashboard butera sur un document non publié.
- **Anticor** (anticor.org + **observatoire.anticor.org**, testés 200) — 🟢. L'Observatoire recense affaires et manquements à la probité par territoire. À jour de sa saga judiciaire : agrément 2021 jugé rétroactivement illégal (Conseil d'État), **nouvel agrément accordé par arrêté du 5 septembre 2024 pour trois ans** (JORF).
- **Transparency International France** (transparency-france.org, 200) — 🟢 pour le plaidoyer. Son outil data **Integrity Watch France** (integritywatch.fr, 200) est 🟡 : un seul module en ligne (« Déclarations d'intérêts » HATVP, dataviz d3/dc.js), les anciennes sous-pages lobbying sont en 404, date de mise à jour injectée dynamiquement — fraîcheur incertaine. Le créneau « exploration des déclarations » est donc mal occupé.
- **Observatoire de l'éthique publique** (observatoireethiquepublique.com, 200) — 🟢 think tank (parlementaires + universitaires), assises annuelles (Nevers avril 2025, Bruxelles et « éthique du numérique » programmées 2026). Production : notes et propositions, pas de données.
- **Contexte** (contexte.com, 200) — 🟢 presse professionnelle payante, référence de la veille législative/politique. Concurrent indirect haut de gamme ; pas un modèle réplicable pour un commun citoyen, mais un standard de qualité de sourçage.
- **Transparence Citoyenne** (transparencecitoyenne.fr, 200) — 🟢 association récente de lutte contre la corruption, active sur la **publication des justificatifs de frais de mandat** (pétition ; voir § 3.3 le refus opposé par les deux chambres en juin 2026).

### 1.3 Les morts et gelés — ce qui les a tués

| Projet | État testé | Cause de la mort (leçon) |
|---|---|---|
| NosSénateurs.fr | 🔴 arrêt officiel, archive mars 2023 | Coût d'entretien du scraping Sénat sans bras bénévoles ; l'asso a préféré un arrêt propre avec archive — rare et à saluer |
| La Fabrique de la Loi | 🔴 gelée à janv. 2022 | Projet de recherche (Sciences Po médialab + RC) sans financement pérenne après la fin du programme ; la dataviz sophistiquée n'a pas survécu à ses créateurs |
| NosFinancesLocales.fr | 🔴 SSL cassé, 404 | Domaine à l'abandon ; les finances locales citoyennes n'ont jamais trouvé leur public face aux portails d'État (OFGL, § 2.5) |
| decp_augmente (data.economie) | 🟡 en ligne, marqué « [DÉPRÉCIÉ] / [Obsolète] » | Réorganisation étatique du circuit DECP en 2024 ; les réutilisateurs qui pointaient dessus sont orphelins |
| api.gouv.fr | 🔴 décommissionné courant 2025 | Absorbé par data.gouv.fr (redirection testée en réel vers data.gouv.fr/dataservices) |
| transparence.gouv.fr | 🔴 NXDOMAIN | N'a jamais existé — le mot « transparence » n'a pas de portail d'État dédié |

**Leçon n° 2 : le financement est le tueur silencieux.** Bénévolat pur (Regards Citoyens) = extinction lente ; dons (Arcadie) = survie précaire revendiquée ; les robustes ont un modèle économique (Contexte, Pappers freemium, Legiwatch 380 €/siège) ou un adossement institutionnel (OFGL, HATVP).

**Leçon n° 3 : « en ligne » ≠ « vivant ».** Tous les morts testés répondent HTTP 200 avec une page propre (NosSénateurs, Fabrique de la Loi, decp_augmente). La fraîcheur ne se déclare pas, elle se mesure sur les données. C'est un argument produit central pour nous : **afficher la fraîcheur mesurée de chaque source**.

### 1.4 Les nouveaux entrants 2023-2026

- **Pappers Politique** (politique.pappers.fr, testé 200) — lancé en février-mars 2023 par Pappers. Agrégateur **gratuit** (freemium) de toute la documentation législative française et européenne, mise à jour quotidienne, moteur avancé (TAL + IA). Le plus gros concurrent « grand public » sur la veille parlementaire brute.
- **Legiwatch** (legiwatch.fr) — lancé **février 2026**. « IA parlementaire » pour affaires publiques : indexation temps réel AN/Sénat/Légifrance/registre HATVP, questions en langage naturel, 11 flux de données (13 en intégration). Payant (dès 380 €/siège) et **contribue au commun Tricoteuses**. Cible pro, pas citoyenne.
- **Poligraph** (poligraph.fr, testé 200 ; GitHub `ironlam/poligraph`) — observatoire citoyen « mandats, votes, patrimoine, affaires » : repo **créé le 18/01/2026, dernier push le 18/08/2026 (la veille de ce rapport), AGPL-3.0**, 37 étoiles. Jeune, open source, très actif — à surveiller comme cousin direct de notre projet.
- **PoliTrust** (politrust.fr, 200) — cartographie des affaires/controverses des élus, « scores d'intégrité », données HATVP/CNCCFP, horizon présidentielle 2027. Méthodologie et sourçage à auditer avant toute citation.
- **Demoscope** (demoscope.fr, 200) et **CivicDash/Objectif 2027** (objectif2027.fr, 200) — plateformes 2025-2026 orientées pédagogie/participation. Sérieux inégal, à traiter avec prudence (vague de sites « présidentielle 2027 », parfois générés avec beaucoup d'IA et peu de garanties de sourçage).
- **hatvp-exploration.vercel.app** (200) — explorateur tiers du répertoire HATVP : preuve que l'open data HATVP est réutilisable facilement… et que personne ne l'a industrialisé.

**Leçon n° 4 : la donnée brute sans éditorialisation ne trouve pas son public.** Les survivants interprètent (scores Datan, média Arcadie, journalisme Contexte, IA Legiwatch). Les plateformes d'État elles-mêmes s'y mettent (dataviz des comptes de l'État : ~120 000 consultations en 2024).

**Leçon n° 5 : l'argent public reste l'angle mort citoyen.** Le Parlement est sur-outillé (5 projets vivants) ; les finances locales (NosFinancesLocales mort), la commande publique (DECP enrichies dépréciées sans successeur citoyen) et les aides aux entreprises (211 Md€/an, § 3.4) n'ont **aucun** outil citoyen vivant.

---

## 2. Outils d'État « transparence » (testés le 19/08/2026)

### 2.1 data.gouv.fr — désormais le point d'entrée unique
- 🟢 HTTP 200. **api.gouv.fr a été décommissionné courant 2025** : redirection réelle constatée vers `data.gouv.fr/dataservices` (« Catalogue des API publiques »). Toute doc qui cite encore api.gouv.fr est périmée.
- Nouveautés 2025-2026 (billet officiel « Perspectives 2026 ») : amélioration continue de la recherche, pages d'organisations personnalisables ; **API tabulaire** (`tabular-api.data.gouv.fr`, bêta) qui permet de requêter en REST n'importe quelle ressource tabulaire hébergée — très utile pour nous (limite ~100 req/s, périmètre bêta à surveiller).
- Reste la plateforme de dépôt **obligatoire** de plusieurs flux transparence (DECP depuis 2024, § 3.5).

### 2.2 budget.gouv.fr — pédagogique, mais hostile aux robots
- 🟢 HTTP 200, **derrière l'anti-bot Incapsula** : curl et WebFetch récupèrent un iframe de challenge, pas le contenu. **Ne jamais scraper budget.gouv.fr** ; passer par les jeux de données (data.gouv.fr / data.economie.gouv.fr).
- Le grand public y trouve : « **Le budget de l'État en quelques clics** » (URL `/budget-etat-clics`, testée 200), les « chiffres clés » du budget 2025, le panorama des finances publiques, et la **datavisualisation des comptes de l'État 2015-2024** (module DGFiP lancé 2021, refondu 2024, ~120 000 consultations en 2024). `dataviz.budget.gouv.fr` n'existe pas (NXDOMAIN).

### 2.3 HATVP — le gisement le plus riche et le plus frais
- 🟢 hatvp.fr 200 ; moteur public de consultation des déclarations 200 ; `hatvp.fr/open-data` 200.
- **Testé en réel** : `agora_repertoire_opendata.json` (répertoire des représentants d'intérêts) = **137 Mo** téléchargés ; `livraison/merge/declarations.xml` (déclarations publiées) = **88 Mo**. Deux flux massifs, ouverts, exploitables (prévoir parsing en flux, pas en mémoire).
- **Nouveau depuis le 1er octobre 2025 : le répertoire des influences étrangères** (loi du 25/07/2024, § 3.1) — personne ne l'exploite encore côté civic tech.
- repertoire.hatvp.fr 200 (interface AGORA). Rapport d'activité 2025 publié en mai 2026 (§ 3.2).

### 2.4 Parlement et juridictions
- **data.assemblee-nationale.fr** 🟢 200 (open data officiel AN : acteurs, scrutins, amendements, agendas — la matière première de Datan/Tricoteuses).
- **data.senat.fr** 🟢 200 (données Sénat, base Dosleg).
- **ccomptes.fr** 🟢 200 — publications en ligne, rapports téléchargeables (voir § 3.4) ; la Cour publie aussi ses données sur data.gouv.fr.

### 2.5 Finances locales et commande publique
- **data.ofgl.fr** 🟢 200 — Observatoire des finances et de la gestion publique locales : LA référence finances locales (exploration cartographique, API Opendatasoft). Rend inutile toute résurrection de NosFinancesLocales.
- **data.economie.gouv.fr** 🟢 200 (portail Opendatasoft du MEF). Attention : le jeu historique `decp_augmente` y est marqué **[DÉPRÉCIÉ]/[Obsolète]** — le flux vivant est sur data.gouv.fr (§ 3.5).
- **transparence.gouv.fr n'existe pas** (NXDOMAIN testé) : il n'y a pas de portail d'État unifié « transparence » — c'est exactement l'espace symbolique qu'un dashboard citoyen peut occuper.
- **code.gouv.fr** : catalogue DINUM des codes sources publics (lié aux obligations d'ouverture des algorithmes, § 3.6).

---

## 3. Nouveautés législatives et réglementaires 2024-2026 (sourcées)

### 3.1 Loi « ingérences étrangères » du 25 juillet 2024 → nouveau répertoire public
La loi n° 2024-850 du 25/07/2024 crée un répertoire numérique public des activités d'influence pour le compte de mandants étrangers, tenu par la HATVP, **accessible depuis le 1er octobre 2025** (annonce HATVP). Première extension majeure du périmètre « lobbying » depuis Sapin 2. Donnée neuve, encore inexploitée par l'écosystème.

### 3.2 HATVP : bilan « 12 ans » et 43 propositions (mai 2026)
Avec son rapport d'activité 2025 (5 795 déclarations contrôlées, 641 avis de mobilité public/privé), la HATVP a publié en mai 2026 « *Douze ans au service de l'intégrité publique* » : **43 propositions** sur le pantouflage, le lobbying (refonte du répertoire, données plus précises par action), l'influence étrangère et les cryptoactifs des déclarants. C'est la feuille de route probable des prochaines réformes — à suivre dans le dashboard (source : hatvp.fr/presse).

### 3.3 Frais de mandat parlementaires : réforme… et refus de publication
- Avances de frais de mandat relevées : Sénat 5 900 → 6 600 €/mois (nov. 2023), AN → 5 950 €/mois (janv. 2024) (source : Club des juristes).
- **2 juillet 2025** : le Bureau de l'AN adopte une réforme des frais de mandat — simplification, légère baisse des moyens, **contrôle du déontologue élargi** (communiqué de la Présidente, presidence.assemblee-nationale.fr).
- **Juin 2026** : l'AN et le Sénat **refusent la publication des justificatifs** de frais (secret des travaux du déontologue / confidentialité du règlement intérieur), face aux demandes citoyennes (dont Transparence Citoyenne) ; la HATVP demande publiquement davantage de transparence sur ces frais (Public Sénat). ⇒ Pour le dashboard : les montants et règles sont publiables, **les justificatifs ne sont pas accessibles** — l'afficher honnêtement comme « zone d'opacité maintenue en 2026 » est en soi une information.

### 3.4 L'argent public sous le feu des rapports 2025
- **Commission d'enquête du Sénat sur les aides publiques aux grandes entreprises** (rapport du 8 juillet 2025, rapporteur F. Gay) : **~211 Md€/an** d'aides « ni lisibles, ni conditionnées, ni évaluées », **26 recommandations**, demande d'un « **choc de transparence** » (création d'un suivi consolidé). Suites gouvernementales toujours en débat (QAG nov. 2025). Aucun outil public ou citoyen ne permet aujourd'hui de suivre ces aides de façon consolidée.
- **Cour des comptes, février 2025** : rapport sur les missions, le financement et le contrôle des associations (champ immigration/intégration) — 2,3 Md€ en 2023 (+23 % depuis 2019), contrôle et transparence insuffisants ; constat récurrent d'un « jaune budgétaire » des subventions éclaté et inexploitable par politique publique.
- **IGF, mai 2025** : revue des dépenses publiques en direction des associations (rapport 2025-E-002-04) — même diagnostic d'illisibilité.
- Rappel du cadre : les associations recevant > 153 k€ de subventions doivent publier leurs comptes au JO — application inégale.

### 3.5 Commande publique : centralisation 2024, seuils 2025
- Depuis le **1er janvier 2024**, les données essentielles de la commande publique (DECP) doivent être publiées **directement sur data.gouv.fr** (arrêtés du 22/12/2022), au format unique ; l'AIFE y republie le flux PES Marché ; les anciens jeux enrichis de data.economie sont dépréciés. Jeux vivants : « DECP transmises via le PES Marché depuis 2024 » et « DECP — fichiers consolidés » sur data.gouv.fr.
- **Décret n° 2025-1386 du 29 décembre 2025** : seuil de dispense de publicité et mise en concurrence relevé de 40 k€ à **60 k€ HT** (fournitures/services) — sans changement des obligations de transmission DECP (source : DAJ/economie.gouv.fr). Effet pervers à surveiller (et à visualiser) : davantage de marchés sous le radar de la publicité préalable.

### 3.6 Algorithmes publics et IA
- Cadre inchangé côté français : loi pour une République numérique (2016) — codes sources = documents administratifs communicables, mention explicite obligatoire des décisions algorithmiques individuelles, registres locaux recommandés. **Application toujours très lacunaire** (dossier Acteurs Publics « nœud gordien de la transparence administrative » ; engagement OGP FR0035 ; travaux code.gouv.fr sur l'« explicabilité automatisée »). Aucune loi française nouvelle 2024-2026 spécifique aux algorithmes publics n'a été identifiée.
- Côté UE : le **2 août 2026** devait être la date pivot du règlement IA pour les systèmes à haut risque (dont administrations, avec base de données européenne publique d'enregistrement) ; le paquet « **Digital Omnibus** » (PE 16/06/2026, Conseil 29/06/2026) **reporte de 16 mois** les obligations les plus lourdes ; les obligations de transparence de l'art. 50 restent applicables.

### 3.7 Anticorruption : statu quo législatif
- La proposition de loi « **Sapin 3** » (O. Marleix, déposée le 29/10/2024 : extension des obligations de conformité, transfert vers la HATVP de missions de l'AFA) **n'a pas été inscrite à l'ordre du jour** à ce jour — pas de nouvelle loi anticorruption 2024-2026.
- **Anticor** : agrément « partie civile » 2021 jugé rétroactivement illégal (Conseil d'État), mais **nouvel agrément par arrêté du 5 septembre 2024** (3 ans, JORFTEXT000050185140) ; la réforme du dispositif d'agrément (réclamée par Sherpa et Anticor) reste en suspens.
- Répertoire lobbying HATVP : le périmètre issu de Sapin 2 couvre désormais aussi les exécutifs locaux (> 150 000 hab.), d'où un répertoire beaucoup plus large qu'en 2017.

---

## 4. Positionnement recommandé pour « France Transparence »

### 4.1 Les vides que personne n'occupe (nos créneaux)
1. **Le croisement multi-sources.** Chaque vivant est un silo : Datan = votes AN ; Arcadie = fiches parlementaires ; Integrity Watch = déclarations (à moitié) ; HATVP/budget/DECP = portails séparés. **Personne ne croise élus × lobbying × argent public** (ex. : calendrier d'un texte × entrées au répertoire HATVP × marchés/subventions du secteur concerné). C'est le cœur différenciant.
2. **La fraîcheur affichée et mesurée.** Leçon n° 3 : les sites morts ont l'air vivants. Un « moniteur de santé des sources » (dernière donnée réellement ingérée, testée automatiquement — exactement ce qui a été fait pour ce rapport) n'existe nulle part et crédibilise tout le reste.
3. **Les aides publiques aux entreprises (211 Md€/an)** : le Sénat a réclamé un « choc de transparence » en juillet 2025 ; aucun outil, ni d'État ni citoyen, ne les consolide. Même un tableau partiel sourcé (crédits d'impôt + exonérations + subventions data.gouv) serait une première.
4. **La commande publique lisible** : les DECP consolidées sur data.gouv sont vivantes mais brutes, et l'explorateur enrichi historique est déprécié. Alertes calculables : attributaire récurrent, avenant tardif, marché juste sous 60 k€ (nouveau seuil du décret 2025-1386 — indicateur à créer dès 2026).
5. **Le répertoire des influences étrangères** (ouvert 01/10/2025) : donnée neuve, zéro réutilisation connue. Coût d'entrée faible, visibilité forte.
6. **Les zones d'opacité elles-mêmes** : documenter ce qui n'est PAS publiable (justificatifs de frais de mandat refusés en juin 2026, jaune budgétaire éclaté) est un contenu de transparence à part entière.

### 4.2 Ce qu'il ne faut PAS réinventer
- **Scraper l'AN/le Sénat** : consommer l'open data officiel (data.assemblee-nationale.fr, data.senat.fr) et/ou les APIs Tricoteuses (attention AGPL pour le code) ;
- **Les statistiques de votes/participation** : Datan le fait bien et publie en Licence Ouverte sur data.gouv (réutiliser, créditer) ;
- **Un moteur CADA** : pointer vers Ma Dada (voire s'y intégrer pour les documents manquants) ;
- **Des fiches biographiques d'élus** : Arcadie et Wikipédia occupent le terrain ;
- **Une dataviz « le budget de l'État » généraliste** : budget.gouv.fr le fait avec des moyens sans commune mesure ; ne prendre que l'angle croisement/alertes ;
- **Les finances locales génériques** : OFGL fournit exploration + API ; se contenter de l'intégrer.

### 4.3 Briques réutilisables et licences (vérifiées)
| Source | Accès testé | Licence | Usage dashboard |
|---|---|---|---|
| Open data AN / Sénat | 200 | Licence Ouverte | matière première parlementaire |
| HATVP (répertoire 137 Mo JSON, déclarations 88 Mo XML) | 200, téléchargés partiellement | Licence Ouverte | lobbying, déclarations, influence étrangère |
| Datasets Datan | API data.gouv, MAJ 19/08/2026 | `fr-lo` | scores votes prêts à l'emploi |
| DECP consolidées (data.gouv) | référencées, flux vivant | Licence Ouverte | commande publique |
| OFGL (data.ofgl.fr) | 200, API ODS | Licence Ouverte | finances locales |
| API tabulaire data.gouv (bêta) | dispo | — | requêtes SQL-like sans ETL |
| Tricoteuses (code + APIs) | 200 (anti-bot Anubis) | **AGPL-3.0** | attention viralité si code réutilisé |
| NosDéputés (API historique 2007-2024) | 200 | ODbL (share-alike, à confirmer) | historique uniquement |
| budget.gouv.fr | 200 mais **anti-bot Incapsula** | — | ne pas scraper ; passer par data.gouv/data.economie |

### 4.4 Risques et vigilances
- **Dépendance aux bénévoles** : si on s'appuie sur Tricoteuses, prévoir un fallback open data officiel (leçon Regards Citoyens).
- **Anti-bots** (Incapsula sur budget.gouv, Anubis sur Tricoteuses) : nos sondes de fraîcheur doivent gérer ces cas sans conclure à tort « mort ».
- **Vague 2027** : la profusion de nouveaux « observatoires » (PoliTrust, Demoscope, CivicDash…) à l'approche de la présidentielle va brouiller le paysage ; notre différenciation = tout sourcé, fraîcheur prouvée, méthodo publiée — l'inverse des sites vitrine.
- **Concurrence sérieuse à surveiller** : Poligraph (open source AGPL, très actif, né janv. 2026) et Pappers Politique (gratuit, quotidien) sont les plus proches de notre terrain.

---

## Annexe — Relevé brut des tests du 19/08/2026 (curl, UA navigateur)

```
200  nosdeputes.fr                 (16e législature figée ; enmandat=[] ; bandeau « précédente législature »)
200  nossenateurs.fr               (page d'arrêt officielle → archive.nossenateurs.fr, 200)
200  regardscitoyens.org
200  datan.fr                      (datasets data.gouv MAJ 2026-08-19, fr-lo)
200  madada.fr                     (>51 000 demandes CADA)
200  contexte.com                  (média pro payant)
200  projetarcadie.com             (articles 07/2026)
200  lafabriquedelaloi.fr          (gelé : max(date initiale)=2022-01-11 ; 1 531 dossiers)
200  tricoteuses.fr / git. / assemblee.  (anti-bot Anubis ; données L17)
200  anticor.org / observatoire.anticor.org
200  transparency-france.org / integritywatch.fr  (module unique déclarations)
200  observatoireethiquepublique.com  (événements 2025-2026)
200  transparencecitoyenne.fr
200  politique.pappers.fr / politrust.fr / poligraph.fr / demoscope.fr / objectif2027.fr
200  hatvp.fr (+open-data +repertoire.hatvp.fr ; agora JSON 137 Mo ; declarations.xml 88 Mo)
200  hatvp-exploration.vercel.app  (explorateur tiers)
200  data.gouv.fr                  (api.gouv.fr → redirigé /dataservices, décommission 2025)
200  budget.gouv.fr                (anti-bot Incapsula ; /budget-etat-clics = 200)
200  data.economie.gouv.fr         (decp_augmente marqué déprécié)
200  data.assemblee-nationale.fr / data.senat.fr / ccomptes.fr / data.ofgl.fr
200  2017-2022.nosdeputes.fr       (archive 15e)
000  transparence.gouv.fr          (NXDOMAIN — n'existe pas)
000  dataviz.budget.gouv.fr        (NXDOMAIN)
000  2022-2024.nosdeputes.fr       (NXDOMAIN)
ERR  nosfinanceslocales.fr         (SSL invalide ; http → 404 : mort)
```

Sources principales : sites testés ci-dessus ; regardscitoyens.org ; github.com/regardscitoyens ; data.gouv.fr (posts « Perspectives 2026 », dataservices, API tabulaire) ; hatvp.fr (rapport 2025, « Douze ans », répertoire influence étrangère) ; senat.fr (rapport commission d'enquête aides publiques r24-808, 08/07/2025) ; ccomptes.fr (rapport associations 02/2025, rapport annuel 2025) ; igf.finances.gouv.fr (revue subventions associations 05/2025) ; economie.gouv.fr/daj (DECP, décret 2025-1386) ; legifrance.gouv.fr (loi 2024-850 ; arrêté agrément Anticor 05/09/2024) ; conseil-etat.fr (agrément Anticor) ; presidence.assemblee-nationale.fr (communiqués 04/2025 et 02/07/2025) ; publicsenat.fr (frais de mandat, HATVP) ; leclubdesjuristes.com (AFM) ; archimag.com (Pappers Politique) ; legiwatch.fr ; touteleurope.eu / quantic-avocats.com (AI Act, Digital Omnibus 06/2026) ; blog.madada.fr.
