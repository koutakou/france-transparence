# 05 · Frais, indemnités & train de vie du pouvoir

> **Axe** : indemnités parlementaires, frais de mandat, cabinets ministériels, frais de représentation, budget de l'Élysée, budgets des assemblées, indemnités des élus locaux.
> **Vérifié le 19 août 2026** par recherches web en français, WebFetch des pages officielles et **appels curl réels** sur chaque fichier cité (code HTTP indiqué). Aucune source déclarée exploitable sans avoir été appelée.
> **Verdict global** : la France publie des **barèmes, des enveloppes et des rapports de contrôle agrégés**, mais **aucune note de frais individuelle** du pouvoir national n'est publiée ni même communicable pour le Parlement. Le module « Notes de frais » façon flux en direct est **impossible à alimenter en données réelles** : il devient un module pédagogique « ce qu'on vous montre / ce qu'on vous cache », ce que cette note documente précisément.

---

## 1. Parlementaires : indemnités (publié, chiffres exacts 2026)

### Ce qui est publié
Les montants sont publiés et tenus à jour par les deux assemblées elles-mêmes (pas d'open data, mais fiches officielles chiffrées).

**Indemnité parlementaire (identique députés/sénateurs), valeur au 1er janvier 2024, toujours en vigueur en 2026** — source : fiche de synthèse n° 7 de l'AN (mise à jour janvier 2026, WebFetch OK) et page senat.fr :

| Composante | Montant mensuel brut |
|---|---|
| Indemnité de base | 5 931,95 € |
| Indemnité de résidence (3 %) | 177,96 € |
| Indemnité de fonction (25 % base+résidence) | 1 527,48 € |
| **Total brut** | **7 637,39 €** |
| Net avant impôt — député | 5 953,34 € |
| Net avant impôt — sénateur (cotisation pension plus élevée) | 5 676,12 € |

**Indemnités spéciales de fonction (mensuel brut, publiées)** :
- AN : présidente 7 698,50 € ; questeurs 5 300,36 € ; vice-présidents 1 099,79 € ; présidents de commission / rapporteurs généraux 931,76 €.
- Sénat : président 7 591,58 € ; questeurs 4 444,97 € ; présidents de groupe et de commission 2 184,30 €.
- Plafond d'écrêtement des indemnités de mandats locaux cumulés : 2 965,98 €/mois. Attention au
  multiplicateur : le plafond légal de **1,5 × l'indemnité de base** porte sur le **total**,
  indemnité parlementaire de base comprise (art. 4 de l'ordonnance n° 58-1210 du 13/12/1958). La
  base occupant déjà 5 931,95 €, il reste **0,5 × la base** pour les seules indemnités locales,
  soit les 2 965,98 € que publie l'Assemblée nationale. Écrire « 1,5 × l'indemnité de base » en
  face de 2 965,98 € fait tomber le lecteur qui vérifie sur 8 897,93 € : les deux formulations
  sont exactes, mais elles ne décrivent pas le même objet.

**Moyens annexes publiés (montants d'enveloppes, pas de détail d'usage)** :
- Crédit collaborateurs AN : **11 463 €/mois** (jusqu'à 5 collaborateurs), revalorisé comme la fonction publique.
- Facilités de transport (SNCF illimité, plafonds aériens), prises en charge directes (courrier, taxis parisiens au Sénat) : régimes décrits, coûts individuels non publiés.

### Ce qui n'est pas publié
- Aucun fichier open data des indemnités réellement versées par parlementaire (retenues pour absences, cumuls) ; seules les grilles le sont.

### Sources testées
- https://www.assemblee-nationale.fr/dyn/synthese/deputes-groupes-parlementaires/la-situation-materielle-du-depute (WebFetch OK, fiche à jour janvier 2026)
- https://www.senat.fr/connaitre-le-senat/role-et-fonctionnement/lindemnite-parlementaire.html (WebFetch OK)

---

## 2. Parlementaires : frais de mandat (le cœur du sujet)

### 2.1 Assemblée nationale — la DFP remplace l'AFM au 1er janvier 2026

**Fait nouveau vérifié** : depuis le **1er janvier 2026**, l'avance de frais de mandat (AFM) et la dotation matérielle des députés (DMD, enveloppe gérée par l'AN pour courrier/téléphone/taxis) sont **fusionnées** en une **« dotation de fonctionnement parlementaire » (DFP)**, en application de l'**arrêté du Bureau n° 34/XVII du 2 juillet 2025**.

Montants mensuels DFP publiés (fiche pratique déontologie AN, WebFetch OK) :
- Métropole : **7 238,04 €**
- Outre-mer et collectivités du Pacifique : 7 512,75 € à 7 720,17 €
- Français établis hors de France : 7 768,85 € à 8 239,10 €

Règles publiées : 9 catégories de dépenses éligibles (permanence, transports, communication, représentation, formation…), dépenses personnelles/patrimoniales/politiques interdites, caractère « raisonnable », compte bancaire dédié, expert-comptable obligatoire, reversement des soldes non consommés, exonération d'impôt sur le revenu (assimilée à des frais professionnels).

**Historique des montants AN** : IRFM 5 372,80 € net/mois (2017) → AFM 5 373 € (01/01/2018) → 5 645 € → **5 950 €** (Bureau du 24 janvier 2024, +305 €, « contexte inflationniste », 17 voix pour / 2 abstentions — LCP, WebFetch OK) → DFP 7 238,04 € (2026, par intégration de l'ex-DMD).

### 2.2 Sénat — AFM 6 600 € + avances dédiées

Page officielle senat.fr (WebFetch OK) :
- **Avance générale : 6 600 €/mois** (majorée outre-mer/Français de l'étranger) — portée de 5 900 € à 6 600 € par décision du Bureau du 16 novembre 2023, mise en œuvre par le Conseil de Questure le 12 décembre 2023, effet 2024.
- Avances dédiées : informatique **6 000 € / 3 ans** ; hébergement parisien **1 500 €/mois** (sauf élus parisiens ou logés) ; frais de représentation des autorités du Sénat (vice-présidents, questeurs…) **750 €/mois**.
- Justification a posteriori de chaque dépense dans l'application **JULIA**, contrôle annuel de tous les sénateurs.

### 2.3 Les contrôles : publiés, mais agrégés et anonymes

**AN — rapport du déontologue** (Rémi Schenberg, en fonction depuis le 1er mai 2025), **publié le 13 mai 2026**, 80 pages — PDF téléchargé et dépouillé (curl 200) :
- Exercice 2024, contrôlé en 2025 : « **100 % des députés contrôlés sur près de 100 % de leurs dépenses** » (effet dissolution : contrôles de solde XVIe législature + relevés bancaires XVIIe).
- **311 députés** ont reçu une demande de renseignements/justificatifs ; **84** ont reçu une demande de reversement complémentaire pour **276 335 € au total** (arrêté au 31/12/2025) — soit moins de 1 % de l'AFM versée.
- Nouveaux élus de juillet 2024 (relevés juillet–décembre 2024) : seulement 10 demandes de remboursement ; 6,6 % des députés contrôlés concernés, pour 0,3 % de l'AFM versée sur la période.
- Exemples de dépenses litigieuses (rapportés par Projet Arcadie) : sachets de baguette promotionnels, cours de chant, contrats avec des proches. Recommandations : interdire les contrats avec soi-même ou ses proches, code de déontologie des collaborateurs, sanctions renforcées.
- **Anonymat absolu** des députés épinglés ; aucune ventilation statistique des dépenses par nature n'est possible avec la méthode actuelle (le rapport le dit lui-même).

**Sénat — rapport d'activité 2024-2025 du Comité de déontologie parlementaire** (45 pages, PDF téléchargé, curl 200) :
- Campagne 2025 sur l'exercice 2024 : **362 sénateurs contrôlés** (73 contrôles approfondis couvrant 40-60 % des dépenses, 289 transversaux couvrant 20-30 %), sous supervision de la CNCC, avec ~20 experts-comptables.
- **149 685 justificatifs** enregistrés dans JULIA (moyenne 413 par sénateur) ; **frais déclarés nets 2024 : 29,9 M€** (+6,7 %, après revalorisation de l'avance ; +14,6 % sur 2018-2024, inférieur à l'inflation de 16,2 %).
- 7 contrôles complémentaires seulement (39 pour 2023) ; décisions arrêtées le 9 juillet 2025, communiquées le 15 septembre 2025. **Aucun montant de reversement n'est publié** côté Sénat.
- Le **référentiel de contrôle** des frais de mandat est public (PDF senat.fr).

### 2.4 Ce qui n'est PAS publié — et pourquoi (le manque documenté)

- **Aucun justificatif, aucune note de frais, aucun relevé individuel** de député ou sénateur n'est publié, ni sur les sites des assemblées, ni en open data (vérifié : la recherche « frais de mandat » sur l'API data.gouv.fr ne renvoie **aucun dataset** — appel curl du 19/08/2026).
- **Base juridique du verrou** : les assemblées échappent au droit d'accès CADA/CRPA ; la communication de leurs documents relève exclusivement de l'**ordonnance n° 58-1100 du 17 novembre 1958** (autonomie des assemblées), ce qu'une décision du **Conseil d'État de mars 2025** a confirmé (rapportée par la presse) — chaque chambre fixe librement ses règles.
- **Épisode récent vérifié (2026)** : l'association **Transparence Citoyenne** a demandé le 20 mai 2026 aux deux présidents la communication des justificatifs des 577 députés et 348 sénateurs. **Refus des deux chambres par courriers du 11 juin 2026** : l'AN invoque le **secret professionnel du déontologue**, le Sénat la **confidentialité prévue par son Règlement**. Réponses rendues publiques début juillet 2026.
- Contraste : pour les **élus locaux**, le Conseil d'État a jugé le **8 février 2023** (affaire des notes de frais de la maire de Paris) que notes de frais et reçus de déplacement/restauration/représentation sont des **documents administratifs communicables** à toute personne — le Parlement est donc l'exception, pas la règle.
- La **HATVP** demandait dès son rapport d'activité 2017 (publié en mai 2018) la publication **en open data des relevés des comptes dédiés** aux frais de mandat, sur les modèles britannique (IPSA) et américain : jamais suivi d'effet. Aucune proposition de loi aboutie 2024-2026 imposant la publication n'a été identifiée (une PPL du 28/10/2025 modifiant l'ordonnance de 1958 est en commission des lois, objet non détaillé dans le dossier législatif).

### Sources testées
- https://www.assemblee-nationale.fr/dyn/deontologie/fiches-pratiques/frais-de-mandat (WebFetch OK)
- https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1110434/file/Rapport_Deontologue_2025.pdf (curl 200, 80 p., dépouillé)
- https://www.senat.fr/connaitre-le-senat/role-et-fonctionnement/les-frais-de-mandat.html (WebFetch OK)
- https://www.senat.fr/fileadmin/cru-1783325159/Organisation_interne/Comite_de_deontologie/Rapports_d_activite/RapportActivite2024-2025.pdf (curl 200, 45 p., dépouillé)
- Refus juin 2026 : https://www.lecourrierdesstrateges.fr/notes-de-frais-des-parlementaires-lassemblee-et-le-senat-opposent-le-secret/ ; pétition : https://transparencecitoyenne.fr (site protégé, 403 en fetch automatique, existence vérifiée par recherche)
- CE 8 février 2023 : https://blog.juspoliticum.com/2023/02/23/a-propos-de-la-decision-du-conseil-detat-du-8-fevrier-2023-sur-la-communication-des-notes-de-frais-de-la-maire-de-paris-breves-reflexions-sur-la-deontologie-de-lexecutif-local-p/ et https://www.seban-associes.avocat.fr/les-notes-de-frais-des-elus-locaux-et-agents-publics-sont-des-documents-administratifs-communicables/

---

## 3. Historique : de l'IRFM (supprimée 2017) à aujourd'hui

- **IRFM** : indemnité forfaitaire **sans aucun justificatif ni contrôle** — 5 372,80 € net/mois par député en 2017 (~39 M€/an pour l'AN en 2016). Campagnes de Regards Citoyens (irfm.regardscitoyens.org) pour sa transparence.
- **Loi n° 2017-1339 du 15 septembre 2017** « confiance dans la vie politique » (art. 20) : suppression au 01/01/2018, remplacement par prise en charge directe / remboursement / **avance sur justificatifs**, régime défini par le Bureau de chaque assemblée (nouvel art. 4 sexies de l'ordonnance de 1958).
- **Ce que la réforme a changé** : des justificatifs existent désormais, conservés et contrôlés (déontologue AN / comité + experts-comptables Sénat), soldes non consommés reversés.
- **Ce qu'elle n'a PAS changé** : aucune publication. L'usage de l'enveloppe n'est pas plus visible du citoyen qu'avant 2017 — seule la probabilité de contrôle interne a changé. Les montants d'enveloppe ont par ailleurs augmenté plus vite que l'indemnité elle-même (AN : +34,7 % entre l'AFM 2018 et la DFP 2026, fusion DMD comprise ; Sénat : +11,9 % en 2024).

---

## 4. Gouvernement : ministères & cabinets

### 4.1 Traitements des membres du Gouvernement (barème public, montants courants non publiés officiellement)
- Base légale : **décret n° 2012-983 du 23 août 2012** (Légifrance — page existante, mais protection anti-robot : curl 403 ; contenu confirmé par presse spécialisée), indexé sur le point de la fonction publique.
- Montants 2026 (presse spécialisée, calculés depuis le décret) : Premier ministre **≈ 16 038 € brut/mois** (aligné sur le président de la République) ; ministre et ministre délégué **≈ 10 692 €** ; secrétaire d'État **≈ 10 157 €** (base 7 890 € + résidence 237 € + fonction 2 032 €).
- **Constat transparence** : aucune page officielle ne publie les montants courants actualisés — il faut recalculer depuis le décret. C'est un « publié en droit, opaque en fait ».

### 4.2 Jaune budgétaire « Personnels affectés dans les cabinets ministériels » — une transparence en recul
**Édition PLF 2026** (annexe officielle, situation au 1er juillet 2025, gouvernement Bayrou) — PDF téléchargé (curl 200, 377 Ko, **11 pages**) :
- **521 membres de cabinet** (36 directeurs, 47 directeurs adjoints, 55 chefs/chefs adjoints, 379 conseillers, 4 autres) + **2 220 agents « fonctions support »** (dont 1 244 assistance, 325 intendance, 249 sécurité bâtiments, 225 chauffeurs, 177 protection) = **2 741 personnes**.
- Statuts : 275 membres de cabinet recrutés sur contrat, 152 mis à disposition, 85 affectés par le ministère, 9 détachés.
- **Indemnité pour sujétions particulières (ISP)** : enveloppes annuelles 2025 par cabinet publiées, **total 27 361 062 €** (cabinet du Premier ministre : 6,3 M€ pour 494 personnes dont 75 membres ; Intérieur : 1,49 M€ ; etc. — tableau complet dans le PDF).
- **RECUL DOCUMENTÉ (vérifié par téléchargement des 3 dernières éditions)** : les tableaux de **rémunérations brutes annuelles par cabinet ont disparu** du document. Jaune PLF 2024 : 6-7 pages ; PLF 2025 : 7 pages ; PLF 2026 : 11 pages — aucun ne contient les rémunérations, alors que la note d'introduction 2026 continue d'en décrire le principe (avec la règle : pas de montant quand il ne concerne qu'un agent). Les dernières données riches datent du **jaune PLF 2023** (exercice 2022) : rémunération moyenne **8 495 € brut/mois** (+3,3 %), cabinet Borne 9 979 €, ~20 % des conseillers mieux payés que leur ministre, coût annuel total ~174 M€ (analyse R. Dosière / Observatoire de l'éthique publique, Capital, 25/10/2022).

### 4.3 Frais de représentation des ministres : opacité quasi totale
- Enveloppes annuelles connues **uniquement** par réponses aux questions écrites et par la presse (Next INpact, 23/07/2019 ; Observatoire de l'éthique publique) : **150 000 €/an** (ministre), **120 000 €** (ministre délégué), **100 000 €** (secrétaire d'État), attribuées par le cabinet du Premier ministre.
- **Aucun texte réglementaire publié** ne fixe ces enveloppes (recommandation OEP d'un décret jamais suivie), **aucune publication de l'usage** ; réponse officielle : Chorus ne permet pas d'extraire le détail par traitement automatisé standard.
- Différence clef avec le Parlement : les ministères sont des administrations soumises au CRPA — les documents sont **communicables sur demande CADA au cas par cas** (jurisprudence CE 2023 sur les notes de frais), mais rien n'est publié d'office et les demandes (Next, 2018-2019) sont restées largement sans effet.

### 4.4 Voyages ministériels
- **Aucune publication systématique** des coûts de déplacements des ministres (avions ETEC, déplacements officiels). Seuls existent : des règles de prise en charge pour les agents (arrêtés 2024-2025, Légifrance), des révélations ponctuelles (presse, questions écrites), et l'audit annuel de la Cour des comptes **pour les seuls déplacements présidentiels** (cf. § 5). Poste entièrement « non publié ».

### Sources testées
- https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1090016/file/20-Jaune2026_Cabinets.pdf (curl 200, PDF 11 p., dépouillé) ; éditions PLF 2025 (www2.assemblee-nationale.fr/static/17/Annexes-DL/PLF2025-Jaunes/20-Jaune_cabinets.pdf, curl 200, 7 p.) et PLF 2024 (budget.gouv.fr/documentation/file-download/22083, curl 200, 7 p.)
- https://www.budget.gouv.fr/documentation/jaunes-budgetaires-2026/personnels-affectes-dans-les-cabinets-ministeriels (curl 200)
- https://next.ink/6725/108060-frais-representation-ministres-demandes-cada-pour-plus-transparence/ (WebFetch OK)
- https://www.legifrance.gouv.fr/loda/id/JORFTEXT000026310466 (décret 2012-983 — curl 403 anti-bot, page référencée)

---

## 5. Présidence de la République : le mieux documenté de tous

### Ce qui est publié
- **Dotation LFI** (mission « Pouvoirs publics ») : **122 563 852 €** en 2024 (+11 % après des années de dérapage), **reconduite à l'identique en 2025 et 2026**.
- **Rapport annuel de la Cour des comptes « Les comptes et la gestion des services de la présidence de la République »** — le SEUL audit public annuel détaillé d'un « train de vie » au sommet de l'État :
  - **Exercice 2024** (publié le 18 juillet 2025, 74 pages — PDF téléchargé et dépouillé, curl 200) : produits 130 M€ (dont dotation 122,6 M€), **charges 123,3 M€** (-2 %), **résultat +6,7 M€** (après -8,3 M€ en 2023 et l'alerte sur les dérapages).
  - Granularité réelle : **94 déplacements présidentiels pour 20,1 M€** (34 internationaux = 10,5 M€ ; métropole 5,3 M€ ; 3 déplacements outre-mer 2,1 M€ ; les 5 voyages les plus chers = 4,88 M€, 46 % du coût international) ; remboursements au ministère des Armées (avions) 1,4 M€ ; masse salariale, réceptions, dîners d'État, **déplacements privés remboursés par le Président** — chaque poste est audité et chiffré.
  - Exercice 2023 (publié juillet 2024) : charges 124,2 M€, déficit -8,3 M€, dotation 110,5 M€.
- **Trésorerie** : 4,49 M€ au 01/01/2025 (rapport sénatorial PLF 2026).

### Ce qui n'est pas publié
- **Le rapport sur l'exercice 2025 n'est PAS paru au 19 août 2026** (l'URL type renvoie 302 vers l'accueil ccomptes.fr ; aucune trace en recherche) : le dernier rapport publié porte sur l'exercice 2024 (18/07/2025).
- Pas de données infra-annuelles ni d'open data : un rapport PDF par an, ~12-18 mois après les dépenses. L'Élysée lui-même ne publie pas de page budget à jour (elysee.fr/la-presidence/le-budget-de-l-elysee : **404 testé**).
- Notes de frais individuelles (président, conseillers) : non publiées ; l'Élysée est une administration (CADA applicable en théorie).

### Sources testées
- https://www.ccomptes.fr/fr/publications/les-comptes-et-la-gestion-des-services-de-la-presidence-de-la-republique-exercice-2024 (curl 200)
- https://www.ccomptes.fr/sites/default/files/2025-07/20250716-Comptes-et-gestion-presidence-de-la-Republique-2024.pdf (curl 200, dépouillé)
- https://www.ccomptes.fr/sites/default/files/2024-07/20240729-S2024-1053-Comptes-et-gestion-de-la-presidence-de-la-Republique_2023.pdf (curl 200)

---

## 6. Assemblée & Sénat en tant qu'institutions : budgets publiés

### Dotations LFI 2026 — mission « Pouvoirs publics » (loi n° 2026-103 du 19 février 2026, JO du 20/02/2026 ; montants du PLF reconduits, détail du rapport sénatorial n° 139 (2025-2026), tome III annexe 32, WebFetch OK)

| Institution | LFI 2025 | LFI 2026 |
|---|---|---|
| Présidence de la République | 122 563 852 € | 122 563 852 € (0 %) |
| Assemblée nationale | 607 647 569 € | 607 647 569 € (0 %) |
| Sénat (institution + jardin + musée du Luxembourg) | 353 470 900 € | 353 470 900 € (0 %) |
| Chaînes parlementaires (LCP-AN + Public Sénat) | 35 245 822 € | 35 596 900 € (+1 %) |
| Conseil constitutionnel | 17 930 000 € | 20 000 000 € (+11,5 %) |
| Cour de justice de la République | 984 000 € | 900 000 € (-8,5 %) |
| **Total mission** | 1 137 842 143 € | **1 140 179 221 € (+0,21 %)** |

- Les dotations gelées sont complétées par des **prélèvements sur réserves** : AN — réserves 183,3 M€ au 31/08/2024, prélèvement 33,4 M€ en 2025, solde budgétaire 2026 prévu **-34,14 M€** ; Sénat — prélèvement 2026 de 22,14 M€, réserves projetées à 96,1 M€ fin 2026 (32,6 M€ fin 2028 : trajectoire non soutenable, dit le rapporteur).

### Comptes publiés et certifiés (oui, réellement)
- **AN** : page « Les comptes de l'Assemblée nationale » (testée 200) — pour chaque exercice 2020→**2025** : rapport des questeurs, rapport de la commission spéciale d'apurement, **rapport de certification de la Cour des comptes** (depuis l'exercice 2013), états financiers, plus la présentation du budget 2026. Format : PDF uniquement.
- **Sénat** : rapport annuel « Les comptes du Sénat » (exercice 2024 : rapport n° 603, déposé le 7 mai 2025, testé 200) + **certification Cour des comptes exercice 2024** (PDF du 30/05/2025, page testée 200).

### Ce qui n'est pas publié
- Pas de données budgétaires en open data (PDF seulement), pas de détail par député/sénateur des dépenses institutionnelles les concernant.

### Sources testées
- https://www.senat.fr/rap/l25-139-322/l25-139-322_mono.html (WebFetch OK) ; LFI 2026 : https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053508155 (curl 403 anti-bot ; promulgation confirmée par KPMG/Weka/LégiFiscal)
- https://www.assemblee-nationale.fr/dyn/compte-an (curl 200)
- https://www.senat.fr/rap/r24-603/r24-603.html (curl 200)
- https://www.ccomptes.fr/fr/publications/certification-des-comptes-du-senat-exercice-2024 (curl 200)

---

## 7. Élus locaux : barèmes nationaux publiés, indemnités réelles éparpillées

### Ce qui est publié
**Barème officiel DGCL au 1er janvier 2026** (PDF collectivites-locales.gouv.fr, curl 200, mis à jour 17/02/2026, dépouillé) — plafonds bruts mensuels en % de l'indice brut terminal 1027, dont la valeur au 01/01/2026 est **4 110,52 €/mois** (décret n° 2023-519 pour le point d'indice) :

| Strate (habitants) | Maire (% IB1027) | Maire (€) | Adjoint max (€) |
|---|---|---|---|
| < 500 | 28,1 % | 1 155,06 | 447,64 |
| 500 – 999 | 44,3 % | 1 820,96 | 483,81 |
| 1 000 – 3 499 | 55,7 % | 2 289,56 | 878,83 |
| 3 500 – 9 999 | 58,3 % | 2 396,44 | 958,57 |
| 10 000 – 19 999 | 67,6 % | 2 778,71 | 1 175,61 |
| 20 000 – 49 999 | 90 % | 3 699,47 | 1 356,47 |
| 50 000 – 99 999 | 110 % | 4 521,58 | 1 808,63 |
| ≥ 100 000 (dont Marseille, Lyon) | 145 % (+40 % possible) | 5 960,26 | 2 712,95 – 2 980,13 |

Conseillers municipaux : 6 % = 246,63 €. Le même PDF couvre EPCI, départements et régions (annexes suivantes). Base : art. L. 2123-20 et s. du CGCT.

### Ce qui n'est pas publié (ou mal)
- **Indemnités réellement votées et versées** : chaque commune/EPCI établit un **« état récapitulatif annuel des indemnités »** (art. L. 2123-24-1-1 CGCT, créé par la loi Engagement et proximité n° 2019-1461, art. 92-93), **communiqué aux conseillers avant le vote du budget** — mais **aucune obligation de mise en ligne, aucune centralisation nationale, aucun open data**. La donnée existe dans 34 000+ communes sans être agrégeable.
- Le Répertoire national des élus (data.gouv.fr) liste les mandats **sans les indemnités**. Les datasets « indemnités des élus » sur data.gouv sont des publications volontaires éparses (ex. région Île-de-France) — vérifié par appel API le 19/08/2026.
- En revanche, **les notes de frais des exécutifs locaux sont communicables sur demande** (CE, 8 février 2023) : levier citoyen réel, mais au cas par cas.

### Sources testées
- https://www.collectivites-locales.gouv.fr/files/files/1.%20Connaitre%20les%20acteurs%20et%20les%20institutions/2.%20Fonction%20publique%20territoriale/La%20lettre%20FPT/ANNEXE%201%20-%20montants%20plafonds%20indemnit%C3%A9s%20%C3%A9lus%20locaux%202026%20-%20VF.pdf (curl 200, dépouillé)
- Fiche DGCL état récapitulatif : https://www.collectivites-locales.gouv.fr/files/files/1.%20Connaitre%20les%20acteurs%20et%20les%20institutions/3.%20Elus%20locaux/fiche_pratique_%C3%A9tat_r%C3%A9capitulatif_annuel_des_indemnit%C3%A9s_per%C3%A7ues_par_les_%C3%A9lus.pdf (curl 200)
- API data.gouv.fr : https://www.data.gouv.fr/api/1/datasets/?q=frais%20de%20mandat (0 résultat) et ?q=indemnités%20élus (résultats locaux épars) — appels du 19/08/2026

---

## 8. Tableau récapitulatif

| Élément | Publié ? | Granularité / fraîcheur | Format | Exploitable dashboard ? | Module cible |
|---|---|---|---|---|---|
| Indemnité parlementaire (barème) | OUI | € exact, à jour (01/2024) | Fiches HTML AN/Sénat | OUI (chiffres statiques sourcés) | « Combien gagnent-ils » |
| DFP députés / AFM sénateurs (enveloppes) | OUI | € exact, 01/01/2026 | Fiches HTML | OUI | Frais & train de vie |
| **Justificatifs / notes de frais parlementaires** | **NON** (refus explicite 11/06/2026 ; ord. 58-1100 ; CE mars 2025) | — | — | NON — impubliable en l'état | Module pédagogique « la boîte noire » |
| Contrôle des frais (déontologue AN / CDP Sénat) | OUI, agrégé & anonyme | Annuel, N+1 (mai 2026 pour 2024/2025) | PDF | OUI (indicateurs agrégés : 276 335 € reversés, 84 députés, 29,9 M€ déclarés Sénat…) | Frais & train de vie |
| Traitements du Gouvernement | Barème en droit (décret 2012-983), montants courants recalculés par la presse | Indexé point FP | Légifrance | OUI avec précaution (marquer « calculé ») | « Combien gagnent-ils » |
| Cabinets ministériels (effectifs, ISP) | OUI (jaune PLF, annuel) | Photographie au 1er juillet, par cabinet | PDF (11 p.) | OUI | Cabinets |
| Cabinets ministériels (rémunérations) | **PLUS DEPUIS PLF 2024** (dernières données : 2022) | — | — | Seulement en historique 2022 + signaler le recul | Cabinets (alerte régression) |
| Frais de représentation des ministres | NON (enveloppes 150/120/100 k€ connues par QE/presse, usage jamais publié) | — | — | NON (pédagogique) | La boîte noire |
| Voyages ministériels | NON | — | — | NON (pédagogique) | La boîte noire |
| Budget/dépenses Élysée | OUI (audit Cour des comptes annuel) | Par poste, jusqu'au voyage près ; N+7 mois ; exercice 2025 pas encore paru | PDF 74 p. | OUI — le poste le plus riche | Train de vie de l'Élysée |
| Dotations AN/Sénat/Élysée (LFI) | OUI | € exact, annuel | Rapports parlementaires, LFI | OUI | Coût des institutions |
| Comptes AN/Sénat certifiés | OUI | Annuel, N+5 mois | PDF | OUI (montants clés) | Coût des institutions |
| Barèmes élus locaux | OUI (DGCL, 01/01/2026) | € exact par strate | PDF | OUI | Élus locaux |
| Indemnités locales réellement versées | NON centralisé (état annuel local non mis en ligne) | — | — | NON (pédagogique + CE 2023 comme levier) | Élus locaux |

---

## 9. Chiffres officiels réutilisables (bloc data, tous sourcés ci-dessus)

```yaml
indemnite_parlementaire_2026:  { brut_mensuel: 7637.39, base: 5931.95, residence: 177.96, fonction: 1527.48,
                                 net_depute: 5953.34, net_senateur: 5676.12, valeur_depuis: "2024-01-01" }
frais_mandat:
  dfp_depute_metropole_2026: 7238.04        # fusion AFM (5950) + DMD, arrêté Bureau 34/XVII du 02/07/2025
  dfp_depute_outremer: [7512.75, 7720.17]
  dfp_depute_hors_de_france: [7768.85, 8239.10]
  afm_senateur: 6600                        # depuis 01/2024 (5900 avant) ; + hébergement 1500/mois, informatique 6000/3 ans
  credit_collaborateurs_an_mensuel: 11463
controle_2024_2025:
  an: { deputes_controles_pct: 100, demandes_renseignements: 311, demandes_reversement: 84,
        total_reversements_eur: 276335, rapport: "Déontologue, 13/05/2026" }
  senat: { senateurs_controles: 362, approfondis: 73, transversaux: 289, justificatifs_julia: 149685,
           frais_declares_2024_eur: 29900000, rapport: "CDP 2024-2025" }
gouvernement:
  traitement_brut_mensuel: { premier_ministre: 16038, ministre: 10692, secretaire_etat: 10157 }  # décret 2012-983, indexé
  frais_representation_annuels: { ministre: 150000, ministre_delegue: 120000, secretaire_etat: 100000 }  # non publiés officiellement
  cabinets_2025: { membres: 521, support: 2220, total: 2741, isp_total_eur: 27361062 }  # jaune PLF 2026, au 01/07/2025
  cabinets_remuneration_moyenne_2022: 8495  # dernière donnée publiée (jaune PLF 2023)
elysee:
  dotation_lfi: { 2024: 122563852, 2025: 122563852, 2026: 122563852 }
  exercice_2024: { charges: 123300000, resultat: 6700000, deplacements: 20100000, nb_deplacements: 94 }
  exercice_2023: { charges: 124200000, resultat: -8300000 }
mission_pouvoirs_publics_lfi_2026:
  total: 1140179221 ; an: 607647569 ; senat: 353470900 ; chaines: 35596900 ; cc: 20000000 ; cjr: 900000
elus_locaux_2026: { ib1027_mensuel: 4110.52, maire_moins_500: 1155.06, maire_1000_3499: 2289.56,
                    maire_100000_plus: 5960.26, adjoint_max: 2980.13, conseiller: 246.63 }
irfm_2017: { net_mensuel: 5372.80, supprimee: "loi 2017-1339 du 15/09/2017, effet 01/01/2018" }
```

---

## 10. Conséquences pour le module « Notes de frais »

1. **Aucun flux de notes de frais n'existe en données publiques françaises** : aucune note de frais du pouvoir national n'est publiée, et pour le Parlement elle n'est même pas communicable (ord. 58-1100 ; refus explicites du 11/06/2026). L'honnêteté du dashboard impose de le dire tel quel.
2. Le module devient **pédagogique et documentaire** : (a) les enveloppes exactes 2026 par élu (DFP/AFM, indemnités) ; (b) les résultats agrégés des contrôles (chiffres §9) ; (c) la chronologie IRFM→DFP ; (d) la carte des verrous juridiques (qui est communicable, qui ne l'est pas — le contraste CE 2023 élus locaux vs Parlement est très parlant) ; (e) le compteur des demandes citoyennes refusées (HATVP 2018, Next 2019, Transparence Citoyenne 2026).
3. **Une vraie exception exploitable : l'Élysée.** Le rapport annuel de la Cour des comptes permet un sous-module riche (coût par déplacement présidentiel, réceptions, masse salariale, trajectoire dotation/charges 2019-2024) ; le dernier rapport publié porte sur l'exercice 2024, celui de l'exercice 2025 n'est pas paru au 19/08/2026.
4. Benchmark utile en une ligne : le Royaume-Uni (IPSA) publie chaque note de frais individuelle des députés — c'est le modèle que la HATVP citait dès 2018.

---

## 11. Points à re-vérifier périodiquement
- Rapport Cour des comptes Élysée **exercice 2025** : non paru au 19/08/2026.
- Suite de la démarche Transparence Citoyenne (recours contentieux éventuel après les refus du 11/06/2026).
- PPL du 28/10/2025 modifiant l'ordonnance 58-1100 (commission des lois AN) — objet à préciser.
- Jaune « cabinets ministériels » PLF 2027 (retour éventuel des tableaux de rémunérations).
- Barème DGCL en cas de revalorisation du point d'indice.
