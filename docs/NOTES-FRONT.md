# Notes des pipelines pour le frontend — compilées le 19/08/2026

Condensé des avertissements « pour le front » remontés par chaque pipeline après épreuve réelle. À lire avec docs/SCHEMA-DB.md (schéma exact + counts). **Les volumétries et les montants cités sont ceux constatés à cette date** : les sources publient quotidiennement, ces valeurs dérivent à chaque ingestion, et seule celle qu'affiche le site fait foi. Ce qui ne dérive pas — les pièges de données, les conventions de calcul, les interdits d'affichage — est l'objet réel de ces notes. Règle générale : **chaque module affiche son FreshnessBadge** (date_donnees, source, fréquence, url — depuis `meta_sources`) et ne montre JAMAIS un montant sans source.

## Budget de l'État (S13, S20, S21, S23)
- `budget_mensuel` : montants = **cumuls depuis le 1er janvier** (`montant_mois` = flux mensuel) ; dernier mois = `max(date_fin_mois)` (= 2026-06-30). Décomposition par titre : `categorie='Dépenses' AND sous_categorie='Budget général' AND niveau=2`. Colonnes `*_n1` pour la variation vs N−1.
- Dépenses nettes cumulées au 30/06/2026 = 240,54 Md€ (+5,44 %). PAS de temps réel : afficher « exécution mensuelle, données au 30/06/2026 ».
- `budget_vert` : montants **PLF 2026** (≠ LFI promulguée, jamais publiée en données) → afficher l'`etiquette_2026`. Top missions : filtrer `type_depense='Crédits budgétaires'` (total CP 479,5 Md€).
- `budget_destination_2025` : CP **bruts**, ne pas comparer aux « dépenses nettes » de S13.
- `subventions_associations` : versements **2023** (décalage structurel de 2 ans, le dire).

## Marchés publics (S1) et annonces (S2, S9)
- **Datation** : `decp_marches.date_notification` est la date de la notification **initiale** du marché (`min(dateNotification)` sur toutes ses lignes, avenants compris) — un avenant ne redate pas le marché et ne le change pas de mois. Toutes les fenêtres portent sur elle : détail 24 mois, agrégats 12 mois, série 36 mois, et le « 30 derniers jours » que le front calcule lui-même. Les attributs affichés (montant, titulaires, objet, procédure) sont ceux de la **version courante**. À dire au visiteur partout où une fenêtre est annoncée.
- Carte : `decp_agg_departement(departement_code, departement_nom, nb_marches, montant_total, nb_marches_ecretes)` — codes '01'…'2A'/'2B'…'988' ; `montant_total` déjà écrêté (plafond 100 M€/marché) ; NULL = aucun montant connu (ne pas afficher 0).
- `decp_agg_mois` (36 mois), `decp_top_acheteurs`/`decp_top_titulaires` (12 mois, montant réparti entre co-titulaires), `decp_repartition` (dimension ∈ {procedure, nature}, valeur NULL = non renseigné), `decp_derniers_marches` (200, J-1).
- **Les deux classements portent sur l'ENTREPRISE, pas sur l'établissement** : colonne `siren` (9 chiffres), jamais `siret`. Une ligne réunit tous les établissements d'une même personne morale — sans quoi une entreprise à réseau d'agences est émiettée sur des dizaines de SIRET dont aucun n'atteint le seuil d'entrée, et disparaît d'un classement dont elle peut être la première. À dire au visiteur là où le classement s'affiche : c'est l'unité comptée qui change, pas seulement une colonne. `nb_etablissements` = établissements **vus dans la fenêtre 12 mois**, jamais la taille de l'entreprise. `nb_marches` = marchés **distincts** (deux établissements co-titulaires d'un même marché ne le comptent qu'une fois) : ne pas le recalculer en sommant des lignes titulaires. Le regroupement s'arrête à la personne morale et ne remonte pas au groupe — deux filiales restent deux lignes, jamais additionnées.
- **Nom et catégorie affichés** : `sirene_unites_legales.denomination` / `.categorie_entreprise`, joints en `LEFT JOIN` sur `siren` à la lecture ; repli sur `nom`/`categorie` du DECP, qui sont les valeurs DÉCLARÉES et nomment souvent l'établissement (« … (ETABLISSEMENT DE MERIGNAC) », « … (MAIRIE) ») ; nom absent partout → afficher le SIREN, jamais un nom deviné. Le référentiel Sirene peut manquer en base (autre pipeline) : la requête retombe alors sur les libellés DECP, sans erreur de page.
- `decp_titulaires_qualite` (1 ligne, `CHECK (id = 1)`, même fenêtre 12 mois que le classement) : une « ligne » y est un couple marché × titulaire. Les identifiants de titulaire non conformes (autre chose que 14 chiffres) sont écartés du classement et comptés là, avec leur montant : à afficher à côté du classement — un montant écarté qui n'est attribué à personne se dit, il ne se tait pas. Invariants utilisables tels quels : `nb_lignes = nb_lignes_identifiables + nb_lignes_ecartees`, et `montant_identifiable + montant_ecarte` = montant de toutes les lignes titulaires (≠ `decp_qualite_montants.montant_total`, qui compte aussi les marchés sans titulaire déclaré). Table absente de la base = section non rendue, jamais un zéro.
- `decp_acheteurs_qualite` (1 ligne, même fenêtre) : le pendant côté acheteurs, **plus court et volontairement pas symétrique** — un marché n'a qu'UN acheteur, donc l'unité comptée est le **marché** et il n'existe aucune colonne `nb_lignes`. Invariant : `nb_marches_avec_acheteur = nb_marches_identifiables + nb_marches_ecartes`, et non `nb_marches`, qui compte aussi les marchés sans acheteur renseigné — les deux colonnes coïncident sur la base servie (acheteur renseigné partout, relevé du 21/08/2026) et ne doivent pas être lues l'une pour l'autre. **Ne jamais aligner `montant_ecarte` des deux tables** : côté acheteurs le montant compte en entier, côté titulaires il est divisé entre co-titulaires.
- **Ce qu'est un identifiant écarté** : la règle est unique (n'est pas un SIRET de 14 chiffres). La page le dit, et ventile par forme à la lecture (`formesIdentifiantsEcartes` : sans chiffre, lettres, SIREN nu, SIREN avec espaces, 13 chiffres) sur la même fenêtre, reconstituée à l'unité près comme `decompositionSuspects`. Un numéro à 13 chiffres n'est PAS complété d'un zéro de tête. Ne pas lister les valeurs brutes.
- Mentions obligatoires : crédit consolidation decp-processing (C. Maudry), montants d'accords-cadres = **maximums**, latence légale ≤ 2 mois.
- `ao_en_cours` : filtrer `annulee=0` ET re-filtrer `date_limite_reponse > now` à l'affichage (snapshot) ; montant NULL = « non publié » (70 % des cas) ; outliers réels (8,3 Md€) → étiqueter, ne pas tronquer silencieusement. `departements` BOAMP non zéro-paddés (« 4 ») vs APProch paddés (« 04 »).
- `marches_a_venir` (APProch) : SIREN seul (pas de nom d'acheteur → joindre `entites` si possible), montants = tranches texte non sommables.

## JO / Documents (S3)
- `jorf_textes` : 30 derniers JO ; le JO ne paraît PAS tous les jours → sparkline tolérante aux trous ; liens Légifrance = liens sortants uniquement (jamais de fetch serveur, anti-bot) ; ~13 % sans ministère (lois, CC — réel) ; `rubrique` NULL possible (1 cas).
- Agrégat nominations par ministère = fenêtre 30 JO entière (recalculer par jour depuis `jorf_textes` si besoin).

## Élus & intégrité (S5, S6, S7, S14, S17)
- Jointures : `elus.uid_an ↔ deputes.uid_an ↔ votes_recents.uid_an` ; `deputes.groupe_ref ↔ groupes_an.organe_ref` ; `elus.matricule_senat ↔ senateurs.matricule`.
- 577 députés, 348 sénateurs, ~36 000 élus au total (maires, présidents CD/CR/EPCI ; conseillers municipaux = agrégats `rne_cm_agregats` seulement).
- Scores : taux de participation calculé (12 mois) ET scores Datan — **les deux étiquetés avec leur méthode** ; créditer datan.fr ; Braun-Pivet 0,63 % = normal (préside).
- `deputes.url_hatvp` fourni par l'AN ; `elus.hatvp_flag`/`hatvp_url` posés par le pipeline intégrité.
- Alertes A1 : `A1_hatvp_non_deposee` = 4 cas nominatifs (constats natifs HATVP) ; `A1_hatvp_retard_presume` = agrégats NON nominatifs, libellé « présumé » + réserve (RNE trimestriel). Ne jamais nominaliser les présumés.
- Renouvellement du Sénat le 27/09/2026 → à mentionner sur le module Sénat.

## Lobbying (S4)
- Bandeau : **4 067 entités** (3 692 actives) — pas 6 829 (artefact corrigé) ; 112 450 activités historiques, détail 24 mois dans `lobby_activites`.
- Fourchettes budgets telles quelles ; `budget_max` NULL = non borné (« ≥ 10 000 000 € ») ; la donnée ne sépare pas AN/Sénat (« Parlement (AN + Sénat) ») ; pics T1 saisonniers réels.
- 316 alertes `lobbying_defaut_declaration` (flag natif HATVP).

## Financement politique (S25, S29)
- Top produits 2024 : PCF 31,6 M€, Renaissance 19,49, Ensemble! 19,47. Aide publique par les comptes : 66,2 → 70,3 M€ (2021→2024) ; aide 2026 = total national seul (64,26 M€, décret 2026-149), répartition par parti inexistante en données.
- Écarter `unite='XPF'` des agrégats € ; réformation parfois À LA HAUSSE (retenu > déclaré — réel) ; municipales 2026 non publiées (instruction en cours, fin 2026/2027).

## Frais & train de vie (S31)
- `trainvie_faits` (56) : chaque ligne porte source_nom/source_url/date_source affichables ; notes = contexte. `trainvie_opacites` (8) : la « boîte noire » — refus AN/Sénat du 11/06/2026, contraste CE 2023 (élus locaux communicables). Le déficit Élysée 2023 est stocké positif avec libellé « Déficit ».
- Surveiller la parution du rapport Cour des comptes Élysée exercice 2025 (opacité dédiée).

## Finances locales (S16)
- Carte : `collectivites_departements(code_dep, …, euros_par_hab, population, nb_communes, exercice=2025)` ; €/hab = (fonct+inv)/pop ; min 1 055 (Orne), max 4 493 (Paris).
- `dotations_dgf` : niveau='national' (2018-2026), 'departement' (2026), 'commune' (≥ 20 000 hab, rangs top/flop réels — Paris 0 € = écrêtement réel assumé).
- Régions/départements en format long `(code, nom, siren, exercice, agregat, montant, euros_par_hab, population)` ; « Epargne brute » peut être négative (légitime).
- Communes : `collectivites_communes_top200` (200 lignes, le nom porte le périmètre) ; séries 2018-2025 en format long `collectivites_communes_series` (3 200 lignes, fonctionnement/investissement, budgets principaux, avec strate `tranche_population` codée '0'..'10' et `epci_nom`) ; médianes d'€/hab par strate × exercice × agrégat dans `collectivites_communes_strates` (176 lignes, médiane calculée par l'API OFGL sur toutes les communes). Cadre éditorial : comparer UNIQUEMENT à la médiane de strate, aucun classement ni jugement ; un exercice absent s'affiche « donnée non disponible », jamais 0 (2025 provisoire, ~97 communes manquantes à la source).
- **Communes « suivies » (participation électorale)** : union `ref_villes` ∪ `collectivites_communes_top200` — préfectures et communes de plus de 50 000 habitants, plus les 200 plus peuplées. Le compte dérive ; le critère, lui, se dit à côté du chiffre. Ce n'est pas « les communes de France ».

## Référentiels (S27, S11, S35)
- Carte : `data/geo/departements.geojson` (101 features, `properties.code` = `ref_departements.code`) ; projection Lambert-93 conique conforme (déjà dans MapFrance) ; **outre-mer hors rendu** (documenté).
- Points : `ref_villes` (184 : préfectures `est_prefecture=1` + villes > 50 000 hab), (lon, lat).
- `entites` : 20 ministères Lecornu II (RefOrgaAdminEtat DILA 19/08) + 7 institutions + 314 collectivités + 718 partis.

## Alertes (table partagée)
- `alertes(id, type, gravite, titre, detail, regle, base_legale, source_url, date_calcul)` — TOUJOURS afficher règle + base légale (dépliable AlertItem) ; gravités : haute/moyenne/info ; types préfixés par domaine (`A1_*`, `lobbying_*`, `financement_*`).

## Design system (rappels)
- Imports nommés `@/components/ui/*`, `@/lib/format` ; pages = Server Components (seule SearchBox est client) ; `getDb()` peut renvoyer null → message honnête « base non construite, lancer make ingest ».
- Chaque page crée ses requêtes dans `app/src/lib/queries/<module>.ts` (fichier PAR module, jamais partagé entre agents).
- Ne PAS toucher : layout.tsx, MainNav, globals.css, composants ui/* (signaler un besoin, ne pas modifier).
- Vue tableau jumelle pour chaque graphique (règle DATAVIZ) ; deltas de dépense = neutres par défaut (upIsGood null).
- **Appareil pédagogique** : page `/comprendre` (fonctionnement de chaque publication, glossaire, provenance labellée « D’où ça vient » sur chaque module, limites, journal daté des lectures, hors nav principale — 11 onglets déjà justes). Canal public des signalements d’erreur de lecture : `CONTACT_ISSUES_URL` (issues du dépôt) ; une demande qui porte sur une personne reste le canal privé de `/donnees-personnelles`. Chaque module de données porte `NoticeLecture` (comment lire / d’où viennent / ce que ça ne dit pas) renvoyant vers `/comprendre/#…` — y compris `/alertes` et `/depenses/destination`. Les fiches d’élus et les pages de mission renvoient vers l’ancre correspondante. Pied de page + `/donnees` + accueil y renvoient. L’ancre `#recettes` existe : ne pas la faire pointer vers `#depenses`. L’ancre `#lectures` porte le journal. Un chiffre borné d’une tuile porte sa borne (`perimetre`) : la fenêtre du croisement lobbying × marchés (24 mois), le caractère provisoire des totaux communaux, et le fait que la « DGF nationale » affichée est celle des communes, n’étaient dits que plus bas sur la page. « Entités actives » du répertoire HATVP veut dire encore inscrites.

## Référencement et cartes de partage (rappels)
Le raisonnement complet vit dans les commentaires de `app/src/lib/seo.ts` — ne rien réimplémenter ailleurs. Ce qui suit est ce qu'une page doit savoir.
- Une page indexable appelle `metadonneesPage({ chemin, titre, description })` — jamais `alternates`/`openGraph` à la main : c'est ce passage unique qui garantit `canonical == og:url` (contrôlé par `ft-localiser`). Une fiche de personne appelle `metadonneesFicheProfil()` : même chose, plus `og:type=profile` et `profile:first_name`/`last_name` pris **tels qu'en base** (`elus.prenom`, `elus.nom`), jamais découpés d'un nom complet.
- **Budget de 70 caractères** pour un titre, suffixe `— France Transparence` compris (`LONGUEUR_TITRE_PARTAGE`, `SUFFIXE_TITRE`) : X coupe là, Facebook vers 88. Un libellé de source trop long se raccourcit **dans les métadonnées seulement**, à la limite de mot (`tronqueMots()`) — le `<h1>` porte toujours le libellé entier. Cas de référence : les 46 missions de `budget_destination_2025`, dont un libellé fait 116 caractères.
- JSON-LD : `jsonLdPage({ chemin, nom, description, ariane })` pose `WebPage` + `BreadcrumbList` (le fil d'Ariane est le seul balisage que Google restitue visiblement). Les jeux de données sont décrits **une seule fois**, par `jsonLdCatalogueDonnees()` sur /donnees : ne pas les redéclarer page par page. Aucun `dateModified` dans un balisage de page — la fraîcheur réelle est par source, elle s'affiche avec les FreshnessBadge.
- L'image de partage est la constante `IMAGE_PARTAGE` de `seo.ts`, url **et** texte alternatif — la carte X la reprend en objet `{ url, alt }`, sans quoi `twitter:image:alt` disparaît (X ne retombe pas sur `og:image:alt`).
