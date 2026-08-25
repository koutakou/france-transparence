# 10 — Critique de complétude (contre-audit de la Phase 0)

**Date : 19 août 2026.** Contre-lecture intégrale de `docs/SOURCES.md` et des 9 rapports `docs/recherche/01` à `09`, avec la grille : trous de couverture, incohérences internes, risques d'ingestion perdus, modules faibles, manques d'honnêteté. **9 appels API réels de vérification** ont été joués ce jour (data.gouv.fr et data.economie.gouv.fr — détail en annexe) pour trancher les trous suspectés au lieu de les reporter. Ce document ne modifie rien : chaque trouvaille porte une action recommandée, à arbitrer avant de figer SOURCES.md.

---

## 1. CRITIQUE

### C1. S1 (DECP consolidées Colin Maudry) est un point de défaillance unique — sans plan B écrit
- **Constat** : la source n° 1 du module vitrine (carte, attributions, fiches, alertes A6-A10) est une **consolidation communautaire maintenue par une personne** (projet `decp-processing`, 02-commande-publique.md §1). Or le rapport 08 démontre lui-même que c'est exactement le profil qui meurt : leçon n° 1 (« la rupture institutionnelle tue le scraping bénévole »), leçon n° 2 (« le financement est le tueur silencieux »), et deux précédents **dans cette niche précise** : `decp_augmente` marqué [Obsolète] sans successeur, `decp.info` redirigé 301 vers l'offre commerciale colibre.fr (02 §1). SOURCES.md (P3, S1) ne prévoit **aucune stratégie de repli** : S8 (officiel DAJ) n'a ni noms ni géocodage, la carte et les fiches s'effondreraient avec S1.
- **Preuve** : `docs/SOURCES.md` §1 S1 et §5 P3 (aucune mention de fallback) ; `02-commande-publique.md` §1 (producteur) ; `08-ecosysteme.md` §1.1, §1.3, §4.4.
- **Action** : ajouter à SOURCES.md un plan B explicite : (a) mode dégradé documenté = S8 + fichiers consolidés DAJ bruts (02 §6) avec résolution des noms via S18 Sirene et géoloc par `lieuexecution`/annuaire — carte en agrégats départementaux au lieu de points ; (b) inscrire le build quotidien S1 **et** l'activité du dépôt `decp-processing` dans le moniteur A11 ; (c) archiver localement le dernier parquet sain (le fichier EST l'état : un build cassé écrase tout).

### C2. A1 « déclaration HATVP en retard » : l'alerte nominative la plus sensible du projet est spécifiée sans ses garde-fous
- **Constat** : SOURCES.md §4 A1 énonce la règle brute (`date de début de fonction RNE + 60 j` × `statut "En cours"`) alors que le rapport source impose trois réserves qui ont **disparu** de la synthèse : (1) pour les **VP d'EPCI élus en 2026, le délai court à compter de la transmission de la délégation de fonction à la préfecture** (04 §1, base légale) — date **absente de tout open data** → faux positifs mécaniques sur une catégorie entière (2 248 dossiers `epci` dans liste.csv) ; (2) la jointure HATVP↔RNE se fait par nom+prénom+département **sans date de naissance côté HATVP** (04 §4) → homonymes ; (3) le RNE est **trimestriel** (dernier : 11/08/2026) → dates de fonction périmées jusqu'à ~3 mois. Le rapport 04 dit « retard **présumé** » ; SOURCES.md a perdu le mot. Publier nominativement « X est en retard » à tort = risque juridique et de crédibilité maximal pour un site de transparence.
- **Preuve** : `docs/SOURCES.md` §4 A1 (règle sans réserve) vs `04-elus-integrite.md` §1 (« retard présumé », délai VP EPCI, communiqué HATVP), §4 (pièges jointure, trimestriel).
- **Action** : corriger A1 dans SOURCES.md : libellé UI « retard présumé » obligatoire ; **exclure ou classer à part** les mandats EPCI dont le point de départ du délai n'est pas observable ; n'afficher nominativement en « constat » que les 4 « Déclaration non déposée » (constat officiel HATVP) ; le reste en agrégats + fiche individuelle avec toutes les réserves ; documenter la règle de matching (normalisation accents/casse, gestion homonymes = non-alerte).

---

## 2. IMPORTANT

### I1. Avis CADA : un gisement « transparence » majeur, totalement absent des 9 rapports — vérifié, il existe et il est frais
- **Constat** : aucun rapport ne mentionne les avis de la Commission d'accès aux documents administratifs, alors que le projet a un module « boîte noire » qui documente les refus de communication (05 §10). **Vérification réelle du 19/08/2026** : dataset « Avis et conseils de la CADA » (org. CADA, licence **fr-lo**), ressource « Ensemble consolidé des avis et conseils de la CADA » = **CSV de 198,4 Mo**, dernière modification **14/08/2026**, plus des lots mensuels/trimestriels.
- **Preuve** : `GET https://www.data.gouv.fr/api/1/datasets/avis-et-conseils-de-la-cada/` → 200 (annexe, appel n° 6).
- **Action** : ajouter au catalogue — non ingéré à ce jour : sens des avis par administration mise en cause (qui refuse quoi), lien direct avec la « carte des verrous juridiques » du module Frais & train de vie et avec Ma Dada (08 §1.2). Volumétrie exploitable non mesurée à ce jour.

### I2. Aides publiques aux entreprises (211 Md€/an) : le créneau n° 3 du rapport 08 est perdu dans SOURCES.md — et il est réellement sans donnée
- **Constat** : le rapport 08 §4.1 en fait le créneau différenciant n° 3 (« même un tableau partiel sourcé serait une première ») ; SOURCES.md reprend les créneaux n° 1 (croisement) et n° 2 (moniteur de fraîcheur) mais **abandonne celui-ci sans arbitrage** — il n'apparaît ni dans un module, ni parmi les sources non ingérées recensées, ni en veille, ni en Groupe E. Vérifications réelles du 19/08 : `q=fonds de solidarité entreprises` sur data.gouv → **0 dataset** ; recherche plein texte data.economie → seul `aide-publique-au-developpement` (figé 2023, hors sujet). Le constat sénatorial (« ni lisibles, ni conditionnées, ni évaluées ») est donc toujours vrai au niveau donnée.
- **Preuve** : `08-ecosysteme.md` §3.4 et §4.1(3) ; `docs/SOURCES.md` §2 et §5 (absence) ; annexe appels n° 4, 8.
- **Action** : trancher explicitement dans SOURCES.md : soit alerte documentaire (« 211 Md€ sans donnée consolidée — rapport Sénat 08/07/2025 ») dans la boîte noire + veille, soit micro-module sur les briques partielles (CIR par le jaune, exonérations). Ne pas laisser le sujet disparaître en silence.

### I3. Rémunérations de la haute fonction publique : angle absent, alors que des données éparses existent (vérifié)
- **Constat** : aucun des 9 rapports ne traite les rémunérations des hauts fonctionnaires (directeurs d'administration, agences, collectivités), pourtant au cœur de « l'argent public ». Vérification réelle : **25 datasets « (dix) plus hautes rémunérations »** sur data.gouv (obligation de l'art. 37 de la loi TFP du 06/08/2019), publiés en ordre dispersé par ministères et collectivités — ex. MESR (maj 10/07/2026), Éducation nationale (07/07/2026), Région Hauts-de-France 2018-2025 (maj 18/08/2026) — **aucune consolidation nationale**.
- **Preuve** : annexe appels n° 5, 7 (`q=plus hautes rémunérations` → total 25).
- **Action** : traiter comme S32 (subventions SCDL) : panel assumé, jamais « national », module Frais & train de vie ; a minima une ligne documentaire (« obligation légale massivement inappliquée / éclatée » — même patron que les subventions locales).

### I4. Jaune « opérateurs » PLF 2026 : cité comme existant par le rapport 01, absent du catalogue sans justification
- **Constat** : 01 §5 et §11 notent que « seul le jaune **opérateurs** PLF 2026 existe, publié 13/01/2026 » — puis la source disparaît : ni retenue (S-numéro), ni écartée (Groupe E) dans SOURCES.md. Vérifié le 19/08 : dataset « PLF 2026, jaune opérateurs de l'État, liste des opérateurs et catégories », maj 13/01/2026. C'est la seule photographie 2026 du paysage des agences/opérateurs (liste et catégories ; pas les crédits par opérateur).
- **Preuve** : `01-budget-etat.md` §5 ; annexe appels n° 2, 3 (page `data.gouv.fr/datasets/projet-de-loi-de-finances-pour-2026-plf-2026-jaune-operateurs-de-letat-liste-des-operateurs-et-categories`).
- **Action** : l'ajouter au catalogue hors périmètre ingéré (module Dépenses de l'État — référentiel des opérateurs) ou l'inscrire au Groupe E avec la raison. Le débat public 2026 sur les agences de l'État en fait un candidat naturel.

### I5. Alerte A6 : la branche « juste sous 40 k€ avant le 01/04/2026 » n'est pas observable dans les DECP
- **Constat** : SOURCES.md §4 A6 propose de détecter la concentration « < 40 k€ avant le 01/04/2026, < 60 k€ ensuite ». Or l'obligation DECP démarre à **≥ 40 000 € HT** (02 §7) : les marchés sous 40 k€ ne sont, en règle générale, **pas publiés** — la bande « juste sous 40 k€ » est invisible (ou visible sur un sous-ensemble auto-sélectionné d'acheteurs volontaires, donc biaisé). Seule la bande **40-60 k€ après le 01/04/2026** est réellement mesurable (publiée en DECP mais dispensée de publicité préalable) — c'est d'ailleurs la version du rapport 08 (§3.5, « indicateur à créer dès 2026 »).
- **Preuve** : `docs/SOURCES.md` §4 A6 vs `02-commande-publique.md` §7 (obligation DECP ≥ 40 k€) et `08-ecosysteme.md` §3.5.
- **Action** : réécrire A6 : périmètre = marchés fournitures/services 40-60 k€ notifiés après le 01/04/2026 ; en méthodo, dire que le « sous 40 k€ » est un angle mort structurel de la donnée.

### I6. Scores de participation/loyauté : dépendance à Datan, un bénévole de plus — le fallback existe mais n'est pas écrit
- **Constat** : le module Élus affiche participation/loyauté via S7 (Datan), petit projet communautaire (65 étoiles GitHub) exactement dans la catégorie que la leçon n° 1 du rapport 08 déclare mortelle. Contrairement au cas S1, le repli est simple — **recalculer depuis S5 Scrutins.json (votes nominaux, déjà en P9)** — mais SOURCES.md ne le mentionne nulle part, et le rapport 08 §4.4 exigeait pourtant « prévoir un fallback open data officiel ».
- **Preuve** : `docs/SOURCES.md` S7/P9 ; `03-parlement.md` §5 ; `08-ecosysteme.md` §4.4.
- **Action** : noter dans S7 : « fallback = taux de participation recalculé depuis S5 (dénominateur = scrutins de la période de mandat) » ; inscrire le CSV Datan dans le moniteur A11.

### I7. Pantouflage / mobilité public-privé (HATVP) : dimension entière du contrôle d'intégrité, absente des modules
- **Constat** : le rapport 08 §3.2 cite lui-même « **641 avis de mobilité public/privé** » dans le rapport HATVP 2025, et le contrôle des reconversions (art. 23 loi 2013-907, ex-commission de déontologie) est un sujet central de la transparence. Ni 04, ni SOURCES.md n'en parlent : le module « Élus & intégrité » couvre déclarations et lobbying, pas les allers-retours public-privé. Aucun export en masse des avis n'est connu (publication individuelle sur hatvp.fr) — à confirmer en Phase 1.
- **Preuve** : `08-ecosysteme.md` §3.2 ; absence dans `04-elus-integrite.md` et `docs/SOURCES.md`.
- **Action** : au minimum un volet documentaire (chiffres agrégés du rapport annuel HATVP, sourcés comme S31) + veille « export open data des avis » au même rythme que la veille RIE.

### I8. Le périmètre « argent public » n'est jamais défini : la sécurité sociale (~600 Md€) et les opérateurs sont hors champ sans que ce soit dit
- **Constat** : le dashboard annonce « la transparence de l'argent public » mais ne couvre que budget de l'État + finances locales. Les administrations de sécurité sociale — le premier poste de la dépense publique — et la dépense des opérateurs n'apparaissent nulle part, **pas même comme manque assumé** (le tableau §3 traite le « comment », jamais le « quoi »). Un compteur « L'État a dépensé 195 Md€ depuis le 1er janvier » sans cadrage laisse croire que c'est « la dépense publique ».
- **Preuve** : `docs/SOURCES.md` §2 (aucun module ni avertissement de périmètre) ; §3 « Ce que la donnée publique ne contient pas — et ce qui est publié à la place » (la liste n'inclut pas le périmètre).
- **Action** : ajouter un encart de périmètre (Accueil + API & Données) : « couvre l'État (budget général) et les collectivités ; hors champ : sécurité sociale, opérateurs (sauf S20/S21 crédits), entreprises publiques » — et l'ajouter à la liste des alertes documentaires.

### I9. Le statut « bêta » de l'API tabulaire data.gouv (support de S1) a été perdu entre le rapport 08 et SOURCES.md
- **Constat** : 08 §2.1 signale l'API tabulaire comme **bêta** (« périmètre bêta à surveiller ») ; SOURCES.md S1 et la requête prête à l'emploi « carte 30 jours » (24 554 lignes) s'appuient dessus sans ce caveat. Une API bêta peut changer de contrat sans préavis.
- **Preuve** : `08-ecosysteme.md` §2.1 vs `docs/SOURCES.md` S1 et §1 « Requêtes prêtes à l'emploi ».
- **Action** : reporter le statut bêta dans S1 ; préciser que le mode nominal de P3 est le parquet local (déjà le cas) et que l'API tabulaire n'est qu'un raccourci substituable par des requêtes DuckDB locales.

### I10. Collaborateurs parlementaires / emplois familiaux : zéro donnée consolidée (vérifié) — angle à assumer
- **Constat** : la loi de 2017 (interdiction des emplois familiaux, obligation de publicité des collaborateurs) n'est traitée dans aucun rapport. Vérification réelle : `q=collaborateurs députés` sur data.gouv → **0 dataset**. Les listes existent en HTML sur les fiches des sites AN/Sénat (non testées en masse) ; le crédit collaborateurs (11 463 €/mois) est dans 05 §1, mais « qui emploie qui » n'est nulle part. De même, les **comptes des groupes politiques** des assemblées (dotations publiques aux groupes) : `q=groupes parlementaires comptes` → **0 dataset** ; publication PDF sur les sites des assemblées à confirmer en Phase 1.
- **Preuve** : annexe appels n° 4bis, 9 (totaux = 0) ; `05-frais-indemnites.md` §1 (enveloppe seule).
- **Action** : classer les deux sujets : collaborateurs = extraction HTML possible mais coûteuse (hors périmètre ingéré, ou documentaire) ; comptes des groupes = vérifier les PDF AN/Sénat puis intégrer aux constantes S31 ou assumer le manque dans la boîte noire.

---

## 3. MINEUR

- **M1. Les « Requêtes prêtes à l'emploi » contredisent la convention §0.3** : la commande CNCCFP colle en dur `static.data.gouv.fr/.../20260210-110641/comptes-partis-exercice-2024.csv` alors que la convention impose de re-résoudre les URLs horodatées via l'API (idem S29). Ajouter la note « URL de millésime, re-résoudre » dans le bloc.
- **M2. Le « bloc YAML prêt à l'emploi » (05 §9) n'est pas du YAML valide** sur la ligne `mission_pouvoirs_publics_lfi_2026: total: 1140179221 ; an: …` (les `;` en font une chaîne unique ; P13 le présente pourtant comme prêt à l'emploi). Corriger en clés/valeurs avant d'en faire le fichier de constantes.
- **M3. Fraîcheurs d'accueil un peu trop flatteuses** : la ligne Accueil « Marchés publics : mise à jour quotidienne, notifications jusqu'à la veille » omet la mention « en cours de consolidation » (latence légale 2 mois) présente dans le module Commande publique — la reporter partout où le flux apparaît. De même « Lobbying : mise à jour quotidienne » : le répertoire est quotidien mais les **dépenses/activités sont déclarées par exercice annuel** ; « pression par ministère » repose sur des données à maille annuelle, à dire.
- **M4. « Questions au gouvernement et délais de réponse par ministère »** (module Élus) : les délais de réponse ne se mesurent que sur les **questions écrites** (03 §2.4) ; les QAG ont réponse immédiate. Corriger le libellé.
- **M5. Incohérences cosmétiques** : france-geojson « 569 Ko » (SOURCES S27) vs « 556 Ko » (09 §8 — 569 299 octets, confusion Ko/KiB) ; nom de fichier RNE `elus-maire-mai.csv` (URL réelle, 04 §4) vs `elus-maires-mai.csv` (tableau du même rapport) — sans conséquence si la convention « re-résoudre via l'API » est suivie.
- **M6. P9 sans stratégie incrémentale** : le zip Scrutins (26,3 Mo → 172,7 Mo décompressés, 8 434 fichiers) est re-livré entier chaque nuit ; re-parser l'intégralité quotidiennement est faisable mais coûteux — prévoir un diff (nouveaux numéros de scrutin uniquement).
- **M7. A4 dépend d'un PDF que personne n'ingère** : la liste des partis privés d'aide publique n'existe que dans l'avis CNCCFP publié au JO (04 §5). Aucun pipeline ne le prévoit — mitigation gratuite : l'avis paraît au **JO**, donc P6/S3 peut le détecter par NOR/titre et déclencher un traitement manuel annuel. L'écrire dans A4.
- **M8. Veille incomplète sur les sources non ingérées** : ajouter les datasets **PLF 2027** (famille destination/nature et budget vert, non parus au 19/08/2026, même famille que S20/S21) ; et la **réserve parlementaire historique** (7 datasets figés, ex. « Réserve parlementaire » AN, vérifié le 19/08) utilisable dans la chronologie IRFM→DFP / boîte noire (supprimée en 2017, successeur FDVA jamais traité).
- **M9. Marchés de l'Élysée / AN / Sénat** : couverts de fait par S1/S2 via filtre SIREN acheteur (Présidence, assemblées) — aucun rapport ne le note alors que c'est une requête différenciante à coût nul pour le module Frais & train de vie. Documenter les SIREN dans les constantes.
- **M10. Condamnations d'élus et inéligibilités** : réellement **sans donnée ouverte** (pas de casier public ; les inéligibilités prononcées par la CNCCFP/juge n'existent qu'en décisions éparses). Seul recensement : l'observatoire Anticor (08), méthodologie à auditer avant citation. Si le sujet est affiché un jour, ce sera éditorial et sourcé au cas par cas — à dire dans la boîte noire, ou ne pas traiter.

---

## 4. Passage en revue systématique des angles « transparence » (verdicts)

| Angle | Verdict | Détail |
|---|---|---|
| Rémunérations hauts fonctionnaires | **OUBLIÉ — données éparses réelles** | 25 datasets « 10 plus hautes rémunérations », aucune consolidation (I3) |
| Réserve parlementaire / dotation d'action parl. | Sans donnée courante (supprimée 2017) | historique open data figé, vérifié ; successeur FDVA non traité (M8) |
| Fonds Marianne | Épisode clos, rapports PDF (IGA/Sénat) | matière éditoriale boîte noire, pas un flux |
| Frais/comptes des groupes politiques | **OUBLIÉ — 0 dataset (vérifié)** | PDF probables sur sites AN/Sénat, à confirmer (I10) |
| Marchés de l'Élysée | Couvert de fait (S1/S2, filtre SIREN) | non documenté (M9) |
| Sponsoring/mécénat public | Sans donnée ouverte consolidée | assumer si évoqué |
| Aides COVID / aides aux entreprises | **OUBLIÉ dans SOURCES — réellement sans donnée consolidée (vérifié)** | créneau n° 3 du rapport 08 perdu (I2) |
| Patrimoine des ministres | Couvert (S14/S15, `type_mandat=gouvernement`, 134 dossiers) | — |
| Cumul des mandats | Couvert (S5 mandats AMO + S17 RNE) | — |
| Absentéisme / présence | Partiel : Datan (AN, fragile, I6) ; agenda AN non ingéré ; **Sénat : rien** | dire l'asymétrie AN/Sénat |
| Questions au gouvernement | Couvert (S5/S6) — libellé délais à corriger (M4) | — |
| Emplois familiaux / collaborateurs | **OUBLIÉ — 0 dataset (vérifié)** | listes HTML par élu (I10) |
| HATVP mobilité public-privé / pantouflage | **OUBLIÉ** | 641 avis 2025 cités par 08, pas d'export bulk (I7) |
| Avis CADA | **OUBLIÉ — open data réel et frais (vérifié)** | CSV consolidé 198 Mo, maj 14/08/2026 (I1) |
| Condamnations d'élus | Réellement sans donnée ouverte | Anticor seul recensement, à auditer (M10) |
| Sécurité sociale / PLFSS | **HORS CHAMP JAMAIS DIT** | à assumer dans l'UI (I8) |
| Opérateurs de l'État | Partiel : jaune 2026 publié mais hors catalogue | à ajouter ou écarter (I4) |

> **Addendum 25/08/2026.** La ligne « Absentéisme / présence — Sénat : rien »
> décrivait le 19/08. S6-DOSLEG ingère depuis le 25/08 `scr` + `votsen`
> (taux calculé ici, votes exprimés, pas une présence, pas Datan). Le
> constat du 19/08 n'est pas réécrit.

---

## Annexe — Appels réels de vérification (19/08/2026, curl, tous HTTP 200)

1. `https://www.data.gouv.fr/api/1/datasets/?q=avis+cada&page_size=6` → « Avis et conseils de la CADA » (org. CADA), last_update **2026-08-14**.
2. `https://www.data.gouv.fr/api/1/datasets/?q=jaune+opérateurs&page_size=6` → jaunes opérateurs PLF 2024/2025/**2026** (2026 : maj 13/01/2026).
3. `https://www.data.gouv.fr/api/1/datasets/?q=PLF+2026&page_size=6` → 2 datasets : budget vert + jaune opérateurs (confirme 01 §11) ; détail du jaune 2026 : id `69665c766034b48d897c47be`.
4. `https://www.data.gouv.fr/api/1/datasets/?q=collaborateurs+députés&page_size=6` → **0 résultat**.
5. `https://www.data.gouv.fr/api/1/datasets/?q=hautes+rémunérations&page_size=6` → datasets épars ministères/collectivités (MESR 10/07/2026, EN 07/07/2026, Hauts-de-France 18/08/2026…).
6. `https://www.data.gouv.fr/api/1/datasets/avis-et-conseils-de-la-cada/` → licence fr-lo ; « Ensemble consolidé » CSV **198 398 592 o**, modifié 14/08/2026 ; lots trimestriels 2022-2024.
7. `https://www.data.gouv.fr/api/1/datasets/?q=plus+hautes+rémunérations&page_size=1` → **total : 25**.
8. `https://www.data.gouv.fr/api/1/datasets/?q=fonds+de+solidarité+entreprises` → **total : 0** ; `data.economie…/catalog/datasets?where=search("fonds de solidarité")` → 1 seul hit hors sujet (`aide-publique-au-developpement`, figé 2023).
9. `https://www.data.gouv.fr/api/1/datasets/?q=groupes+parlementaires+comptes` → **total : 0** ; `?q=réserve+parlementaire` → 7 datasets historiques figés (AN 2015, Bercy 2014).

*Contre-audit établi sans modification de SOURCES.md ; les corrections C1-C2, I1-I10 et M1-M10 sont à reporter dans SOURCES.md par son mainteneur.*
