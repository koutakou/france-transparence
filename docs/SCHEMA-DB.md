# Schéma de la base data/france.db — généré le 19/08/2026 16:16 après make ingest,
# complété le 20/08/2026 (renommage collectivites_communes → collectivites_communes_top200 ;
# tables collectivites_communes_series et collectivites_communes_strates, comptages du 20/08)

```
CREATE TABLE meta_sources (
    source_id      TEXT PRIMARY KEY,          -- ex. 'S13', 'S1'
    nom            TEXT NOT NULL,             -- libellé humain de la source
    url            TEXT NOT NULL,             -- URL de référence (page ou endpoint)
    licence        TEXT NOT NULL,             -- ex. 'Licence Ouverte 2.0', 'ODbL'
    frequence      TEXT NOT NULL,             -- ex. 'quotidienne', 'mensuelle'
    date_donnees   TEXT NOT NULL,             -- ISO : date de la donnée la plus récente
    date_ingestion TEXT NOT NULL,             -- ISO : dernier passage du pipeline
    lignes         INTEGER NOT NULL DEFAULT 0,
    notes          TEXT
);
CREATE TABLE entites (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN
                  ('ministere','institution','collectivite','parti','organisme')),
    nom         TEXT NOT NULL,
    sigle       TEXT,
    siren       TEXT,
    departement TEXT
);
CREATE INDEX idx_entites_type  ON entites(type);
CREATE INDEX idx_entites_siren ON entites(siren);
CREATE TABLE elus (
    id              TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    prenom          TEXT,
    sexe            TEXT,
    date_naissance  TEXT,
    profession      TEXT,
    uid_an          TEXT,                     -- id acteur AN (PAxxxx)
    matricule_senat TEXT,
    hatvp_flag      INTEGER NOT NULL DEFAULT 0,
    mandats         TEXT CHECK (mandats IS NULL OR json_valid(mandats))
, hatvp_url TEXT);
CREATE INDEX idx_elus_nom    ON elus(nom, prenom);
CREATE INDEX idx_elus_uid_an ON elus(uid_an);
CREATE TABLE ref_departements (
    code        TEXT PRIMARY KEY,     -- code INSEE ('01'…'95', '2A', '971'…)
    nom         TEXT NOT NULL,
    code_region TEXT NOT NULL,
    nom_region  TEXT NOT NULL,
    population  INTEGER               -- PMUN, populations de référence 2023
);
CREATE TABLE ref_villes (
    code_insee     TEXT PRIMARY KEY,
    nom            TEXT NOT NULL,
    departement    TEXT NOT NULL,
    lat            REAL NOT NULL,
    lon            REAL NOT NULL,
    population     INTEGER,
    est_prefecture INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ref_villes_departement ON ref_villes(departement);
CREATE TABLE budget_mensuel (
    ligne_id         TEXT    NOT NULL,
    ordre            INTEGER NOT NULL,
    niveau           INTEGER NOT NULL,
    categorie        TEXT    NOT NULL,
    sous_categorie   TEXT    NOT NULL,
    ligne            TEXT    NOT NULL,
    date_fin_mois    TEXT    NOT NULL,
    annee            INTEGER NOT NULL,
    mois             INTEGER NOT NULL CHECK (mois BETWEEN 1 AND 12),
    montant_cumul    REAL    NOT NULL,
    montant_mois     REAL,
    montant_cumul_n1 REAL,
    montant_mois_n1  REAL,
    PRIMARY KEY (ligne_id, date_fin_mois)
);
CREATE INDEX idx_budget_mensuel_annee_mois
    ON budget_mensuel(annee, mois);
CREATE TABLE budget_vert (
    type_depense       TEXT NOT NULL,
    mission            TEXT NOT NULL,
    numero_programme   INTEGER,
    programme          TEXT,
    code_action        TEXT,
    action             TEXT,
    affectataire       TEXT,
    impot              TEXT,
    code_depense       TEXT,
    libelle            TEXT,
    cotation_globale   TEXT,
    categorie_generale TEXT,
    attenuation_climat REAL,
    adaptation_climat  REAL,
    eau                REAL,
    dechets            REAL,
    pollutions         REAL,
    biodiversite       REAL,
    execution_2024_cp  REAL,
    lfi_2025_cp        REAL,
    plf_2026_cp        REAL,
    etiquette_2026     TEXT NOT NULL
);
CREATE INDEX idx_budget_vert_mission ON budget_vert(mission);
CREATE INDEX idx_budget_vert_type ON budget_vert(type_depense);
CREATE TABLE budget_destination_2025 (
    exercice                INTEGER NOT NULL,
    loi                     TEXT NOT NULL,
    etiquette_montants      TEXT NOT NULL,
    typebudget              TEXT,
    ministere               TEXT,
    libelle_ministere       TEXT,
    mission                 TEXT,
    libelle_mission         TEXT,
    programme               TEXT,
    libelle_programme       TEXT,
    action                  TEXT,
    libelle_action          TEXT,
    sous_action             TEXT,
    libelle_sous_action     TEXT,
    categorie               TEXT,
    titre                   TEXT,
    autorisation_engagement REAL,
    credit_de_paiement      REAL
);
CREATE INDEX idx_budget_dest_ministere
    ON budget_destination_2025(libelle_ministere);
CREATE INDEX idx_budget_dest_mission
    ON budget_destination_2025(libelle_mission);
CREATE TABLE subventions_associations (
    annee_versement             INTEGER NOT NULL,
    programme                   TEXT,
    siren                       TEXT,
    nic                         TEXT,
    denomination                TEXT,
    montant                     REAL,
    objet                       TEXT,
    convention                  TEXT,
    date_creation_etablissement TEXT,
    etat_administratif          TEXT,
    categorie_juridique         TEXT,
    cog_code                    TEXT,
    cog_libelle                 TEXT,
    departement                 TEXT
);
CREATE INDEX idx_subv_assos_siren ON subventions_associations(siren);
CREATE INDEX idx_subv_assos_dept ON subventions_associations(departement);
CREATE INDEX idx_subv_assos_programme ON subventions_associations(programme);
CREATE INDEX idx_subv_assos_montant ON subventions_associations(montant);
CREATE TABLE decp_marches (
    uid                       TEXT PRIMARY KEY,
    id                        TEXT,
    objet                     TEXT,
    montant                   REAL,
    montant_rationalise       REAL,
    montant_retenu            REAL,
    montant_anomalie          TEXT,
    montant_suspect           INTEGER NOT NULL DEFAULT 0,
    acheteur_siret            TEXT,
    acheteur_nom              TEXT,
    acheteur_departement_code TEXT,
    acheteur_departement_nom  TEXT,
    titulaire_siret           TEXT,
    titulaire_nom             TEXT,
    nb_titulaires             INTEGER NOT NULL DEFAULT 0,
    titulaires_json           TEXT,
    date_notification         TEXT NOT NULL,
    duree_mois                INTEGER,
    procedure                 TEXT,
    nature                    TEXT,
    type_marche               TEXT,
    techniques                TEXT,
    code_cpv                  TEXT,
    lieu_execution_code       TEXT,
    lieu_execution_typecode   TEXT
);
CREATE INDEX idx_decp_marches_date  ON decp_marches(date_notification);
CREATE INDEX idx_decp_marches_ach   ON decp_marches(acheteur_siret);
CREATE INDEX idx_decp_marches_tit   ON decp_marches(titulaire_siret);
CREATE INDEX idx_decp_marches_dep   ON decp_marches(acheteur_departement_code);
CREATE TABLE decp_agg_departement (
    departement_code   TEXT PRIMARY KEY,
    departement_nom    TEXT,
    nb_marches         INTEGER NOT NULL,
    montant_total      REAL,
    nb_marches_ecretes INTEGER NOT NULL
);
CREATE TABLE decp_agg_mois (
    mois          TEXT PRIMARY KEY,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);
CREATE TABLE decp_top_acheteurs (
    rang          INTEGER PRIMARY KEY,
    siret         TEXT,
    nom           TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);
CREATE TABLE decp_top_titulaires (
    rang          INTEGER PRIMARY KEY,
    siret         TEXT,
    nom           TEXT,
    categorie     TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);
CREATE TABLE decp_repartition (
    dimension     TEXT NOT NULL,
    valeur        TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);
CREATE INDEX idx_decp_repartition_dim ON decp_repartition(dimension);
CREATE TABLE decp_derniers_marches (
    rang INTEGER PRIMARY KEY,
    
    uid                       TEXT NOT NULL,
    id                        TEXT,
    objet                     TEXT,
    montant                   REAL,
    montant_rationalise       REAL,
    montant_retenu            REAL,
    montant_anomalie          TEXT,
    montant_suspect           INTEGER NOT NULL DEFAULT 0,
    acheteur_siret            TEXT,
    acheteur_nom              TEXT,
    acheteur_departement_code TEXT,
    acheteur_departement_nom  TEXT,
    titulaire_siret           TEXT,
    titulaire_nom             TEXT,
    nb_titulaires             INTEGER NOT NULL DEFAULT 0,
    titulaires_json           TEXT,
    date_notification         TEXT NOT NULL,
    duree_mois                INTEGER,
    procedure                 TEXT,
    nature                    TEXT,
    type_marche               TEXT,
    techniques                TEXT,
    code_cpv                  TEXT,
    lieu_execution_code       TEXT,
    lieu_execution_typecode   TEXT

);
CREATE TABLE ao_en_cours (
    idweb               TEXT PRIMARY KEY,
    objet               TEXT,
    acheteur            TEXT,
    nature              TEXT NOT NULL,
    nature_libelle      TEXT,
    famille             TEXT,
    famille_libelle     TEXT,
    type_marche         TEXT CHECK (type_marche IS NULL OR json_valid(type_marche)),
    type_procedure      TEXT,
    procedure_libelle   TEXT,
    descripteurs        TEXT CHECK (descripteurs IS NULL OR json_valid(descripteurs)),
    departements        TEXT CHECK (departements IS NULL OR json_valid(departements)),
    montant_estime      REAL,              -- NULL = non publié dans l'annonce
    devise              TEXT,
    date_parution       TEXT NOT NULL,     -- ISO date
    date_limite_reponse TEXT NOT NULL,     -- ISO datetime (UTC)
    url_avis            TEXT,
    annulee             INTEGER NOT NULL DEFAULT 0,
    rectifiee_par       TEXT               -- idweb du dernier RECTIFICATIF lié
);
CREATE INDEX idx_ao_date_limite ON ao_en_cours(date_limite_reponse);
CREATE INDEX idx_ao_famille     ON ao_en_cours(famille);
CREATE TABLE annonces_recentes (
    idweb               TEXT PRIMARY KEY,
    objet               TEXT,
    acheteur            TEXT,
    nature              TEXT,
    nature_libelle      TEXT,
    famille             TEXT,
    famille_libelle     TEXT,
    type_marche         TEXT CHECK (type_marche IS NULL OR json_valid(type_marche)),
    titulaires          TEXT CHECK (titulaires IS NULL OR json_valid(titulaires)),
    departements        TEXT CHECK (departements IS NULL OR json_valid(departements)),
    date_parution       TEXT NOT NULL,
    date_limite_reponse TEXT,
    url_avis            TEXT
);
CREATE INDEX idx_annonces_parution ON annonces_recentes(date_parution);
CREATE INDEX idx_annonces_nature   ON annonces_recentes(nature);
CREATE TABLE annonces_par_famille (
    famille         TEXT,
    famille_libelle TEXT,
    nature          TEXT,
    nb              INTEGER NOT NULL
);
CREATE TABLE annonces_par_jour (
    jour             TEXT PRIMARY KEY,
    nb               INTEGER NOT NULL,
    nb_appels_offre  INTEGER NOT NULL,
    nb_attributions  INTEGER NOT NULL
);
CREATE TABLE marches_a_venir (
    code                     TEXT PRIMARY KEY,
    intitule                 TEXT,
    description              TEXT,
    statut                   TEXT,
    acheteur_siren           TEXT,          -- 9 chiffres, pas de nom dans la source
    categorie_achat          TEXT,          -- Travaux / Fournitures / Services
    code_cpv                 TEXT,
    montant_estime_tranche   TEXT,          -- tranche texte, NULL = non publié
    date_prev_publication    TEXT NOT NULL, -- ISO date (future à l'ingestion)
    date_cible_remise_offres TEXT,
    type_procedure           TEXT,
    duree_prev_mois          INTEGER,
    departements             TEXT CHECK (departements IS NULL OR json_valid(departements)),
    lien_consultation        TEXT
);
CREATE INDEX idx_mav_date_publication
    ON marches_a_venir(date_prev_publication);
CREATE INDEX idx_mav_siren ON marches_a_venir(acheteur_siren);
CREATE TABLE jorf_textes (
    texte_id        TEXT PRIMARY KEY,
    conteneur_id    TEXT,
    num_jo          TEXT,
    date_publi      TEXT NOT NULL,
    date_texte      TEXT,
    nature          TEXT,
    nor             TEXT,
    titre           TEXT NOT NULL,
    ministere       TEXT,
    rubrique        TEXT,
    is_nomination   INTEGER NOT NULL DEFAULT 0,
    lien_legifrance TEXT NOT NULL,
    id_eli          TEXT,
    num_sequence    INTEGER
);
CREATE INDEX idx_jorf_textes_date       ON jorf_textes(date_publi);
CREATE INDEX idx_jorf_textes_nature     ON jorf_textes(nature);
CREATE INDEX idx_jorf_textes_nomination ON jorf_textes(is_nomination);
CREATE TABLE jorf_par_jour_nature (
    date_publi TEXT NOT NULL,
    nature     TEXT NOT NULL,
    nb         INTEGER NOT NULL,
    PRIMARY KEY (date_publi, nature)
);
CREATE TABLE jorf_nominations_ministere (
    ministere TEXT PRIMARY KEY,
    nb        INTEGER NOT NULL
);
CREATE TABLE deputes (
    uid_an              TEXT PRIMARY KEY,      -- PAxxxx (open data AN)
    legislature         INTEGER NOT NULL,
    nom                 TEXT NOT NULL,
    prenom              TEXT,
    departement         TEXT,                  -- nom du département d'élection
    num_departement     TEXT,
    num_circo           TEXT,
    groupe_ref          TEXT,                  -- organe GP (POxxxx)
    groupe_sigle        TEXT,
    groupe_nom          TEXT,
    commission_ref      TEXT,                  -- organe COMPER (POxxxx)
    commission          TEXT,
    date_debut_mandat   TEXT,                  -- mandat ASSEMBLEE en cours
    date_prise_fonction TEXT,
    date_fin_mandat     TEXT,                  -- NULL tant que le mandat court
    url_fiche_an        TEXT,
    url_hatvp           TEXT,                  -- uri_hatvp du JSON AN si présent
    -- calcul France Transparence (scrutins AN, 12 derniers mois)
    taux_participation_12m REAL,               -- 0-100 (%)
    nb_votes_12m        INTEGER,
    nb_scrutins_12m     INTEGER,               -- dénominateur (scrutins du mandat)
    participation_source TEXT,
    participation_maj   TEXT,
    -- scores Datan (source créditée, coexistent avec le calcul ci-dessus)
    datan_score_participation            REAL, -- 0-1 (tel que publié)
    datan_score_participation_specialite REAL,
    datan_score_loyaute                  REAL,
    datan_score_majorite                 REAL,
    datan_source        TEXT,
    datan_date          TEXT
);
CREATE INDEX idx_deputes_groupe ON deputes(groupe_sigle);
CREATE INDEX idx_deputes_departement ON deputes(num_departement);
CREATE TABLE groupes_an (
    organe_ref  TEXT PRIMARY KEY,
    legislature INTEGER NOT NULL,
    sigle       TEXT NOT NULL,
    nom         TEXT NOT NULL,
    effectif    INTEGER NOT NULL,
    couleur     TEXT,
    position    TEXT                            -- préséance AN (ordre d'affichage)
);
CREATE TABLE senateurs (
    matricule         TEXT PRIMARY KEY,
    nom               TEXT NOT NULL,
    prenom            TEXT,
    sexe              TEXT,
    circonscription   TEXT,                     -- département (série non publiée)
    groupe            TEXT,
    groupe_appartenance TEXT,                   -- Membre / Rattaché / Apparenté
    commission        TEXT,
    date_debut_mandat TEXT,                     -- ODSEN_ELUSEN si publié
    date_fin_mandat   TEXT,                     -- NULL : mandat en cours
    date_naissance    TEXT,
    profession        TEXT,
    email             TEXT,                     -- 'Non public' possible
    url_fiche_senat   TEXT
);
CREATE INDEX idx_senateurs_groupe ON senateurs(groupe);
CREATE TABLE scrutins (
    uid                TEXT PRIMARY KEY,        -- VTANR5L17Vnnnn
    legislature        INTEGER NOT NULL,
    numero             INTEGER NOT NULL,
    date_scrutin       TEXT NOT NULL,
    titre              TEXT,
    type_vote          TEXT,
    sort               TEXT,                    -- 'adopté' / 'rejeté'
    demandeur          TEXT,
    nombre_votants     INTEGER,
    suffrages_exprimes INTEGER,
    pour               INTEGER,
    contre             INTEGER,
    abstentions        INTEGER,
    non_votants        INTEGER,
    adopte             INTEGER NOT NULL DEFAULT 0,
    UNIQUE (legislature, numero)
);
CREATE INDEX idx_scrutins_date ON scrutins(date_scrutin);
CREATE TABLE votes_recents (
    scrutin_uid     TEXT NOT NULL,
    scrutin_numero  INTEGER NOT NULL,
    uid_an          TEXT NOT NULL,
    position        TEXT NOT NULL CHECK (position IN
                      ('pour','contre','abstention','nonVotant')),
    par_delegation  INTEGER NOT NULL DEFAULT 0,
    cause_position  TEXT,                       -- ex. PAN/PSE pour les non-votants
    PRIMARY KEY (scrutin_uid, uid_an)
);
CREATE INDEX idx_votes_recents_acteur ON votes_recents(uid_an);
CREATE TABLE alertes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    gravite     TEXT NOT NULL,
    titre       TEXT NOT NULL,
    detail      TEXT,
    regle       TEXT,
    base_legale TEXT,
    source_url  TEXT,
    date_calcul TEXT NOT NULL
);
CREATE INDEX idx_alertes_type ON alertes(type);
CREATE TABLE hatvp_declarations (
    id                 INTEGER PRIMARY KEY,
    civilite           TEXT,
    prenom             TEXT,
    nom                TEXT,
    classement         TEXT,
    type_mandat        TEXT,
    qualite            TEXT,
    type_document      TEXT,
    departement        TEXT,
    date_publication   TEXT,
    date_depot         TEXT,
    statut_publication TEXT NOT NULL,
    nom_fichier        TEXT,
    url_dossier        TEXT,
    url_fiche          TEXT,
    open_data          TEXT,
    id_origine         TEXT,
    url_photo          TEXT
);
CREATE INDEX idx_hatvp_decl_statut ON hatvp_declarations(statut_publication);
CREATE INDEX idx_hatvp_decl_nom    ON hatvp_declarations(nom, prenom);
CREATE TABLE hatvp_agregats (
    categorie TEXT NOT NULL,
    cle       TEXT NOT NULL,
    nb        INTEGER NOT NULL,
    PRIMARY KEY (categorie, cle)
);
CREATE TABLE rne_cm_agregats (
    code_departement    TEXT PRIMARY KEY,
    libelle_departement TEXT,
    nb_conseillers      INTEGER NOT NULL,
    nb_femmes           INTEGER NOT NULL,
    nb_hommes           INTEGER NOT NULL,
    age_moyen           REAL
);
CREATE TABLE lobby_entites (
    id                           TEXT PRIMARY KEY,
    identifiant_national         TEXT,
    type_identifiant             TEXT,
    denomination                 TEXT NOT NULL,
    nom_usage                    TEXT,
    sigle                        TEXT,
    categorie                    TEXT,
    ville                        TEXT,
    pays                         TEXT,
    active                       INTEGER NOT NULL DEFAULT 1,
    date_cessation               TEXT,
    date_premiere_publication    TEXT,
    derniere_publication_activite TEXT,
    secteurs                     TEXT,
    niveaux_intervention         TEXT,
    nb_activites_total           INTEGER NOT NULL DEFAULT 0,
    nb_activites_12m             INTEGER NOT NULL DEFAULT 0,
    budget_periode_debut         TEXT,
    budget_periode_fin           TEXT,
    budget_libelle               TEXT,
    budget_min                   REAL,
    budget_max                   REAL,
    effectifs                    REAL,
    ca_libelle                   TEXT,
    ca_min                       REAL,
    ca_max                       REAL,
    defaut_declaration           INTEGER NOT NULL DEFAULT 0,
    declaration_incomplete       INTEGER NOT NULL DEFAULT 0,
    url_fiche                    TEXT
);
CREATE INDEX idx_lobby_entites_categorie ON lobby_entites(categorie);
CREATE INDEX idx_lobby_entites_defaut    ON lobby_entites(defaut_declaration);
CREATE TABLE lobby_activites (
    activite_id       TEXT PRIMARY KEY,
    entite_id         TEXT NOT NULL,
    exercice_id       TEXT,
    periode_debut     TEXT,
    periode_fin       TEXT,
    date_publication  TEXT,
    identifiant_fiche TEXT,
    objet             TEXT,
    domaines          TEXT,
    decisions         TEXT,
    institutions      TEXT,
    ministeres        TEXT,
    actions           TEXT
);
CREATE INDEX idx_lobby_activites_entite ON lobby_activites(entite_id);
CREATE INDEX idx_lobby_activites_date   ON lobby_activites(date_publication);
CREATE TABLE lobby_agg_institutions (
    institution        TEXT PRIMARY KEY,
    groupe             TEXT NOT NULL,
    nb_activites_total INTEGER NOT NULL,
    nb_activites_12m   INTEGER NOT NULL,
    nb_entites         INTEGER NOT NULL
);
CREATE TABLE lobby_agg_ministeres (
    ministere          TEXT PRIMARY KEY,
    nb_activites_total INTEGER NOT NULL,
    nb_activites_12m   INTEGER NOT NULL,
    nb_entites         INTEGER NOT NULL
);
CREATE TABLE lobby_agg_top_entites (
    rang             INTEGER PRIMARY KEY,
    entite_id        TEXT NOT NULL,
    denomination     TEXT NOT NULL,
    categorie        TEXT,
    nb_activites_12m INTEGER NOT NULL
);
CREATE TABLE lobby_agg_budgets (
    fourchette TEXT PRIMARY KEY,
    borne_min  REAL,
    borne_max  REAL,
    nb_entites INTEGER NOT NULL
);
CREATE TABLE lobby_agg_trimestres (
    trimestre    TEXT PRIMARY KEY,
    nb_activites INTEGER NOT NULL,
    nb_entites   INTEGER NOT NULL
);
CREATE TABLE partis (
    id               TEXT PRIMARY KEY REFERENCES entites(id),
    code_cnccfp      TEXT NOT NULL UNIQUE,
    nom              TEXT NOT NULL,
    sigle            TEXT,
    dernier_exercice INTEGER NOT NULL
);
CREATE TABLE partis_comptes (
    parti_id               TEXT NOT NULL REFERENCES partis(id),
    exercice               INTEGER NOT NULL,
    nom_declare            TEXT NOT NULL,
    unite                  TEXT NOT NULL DEFAULT 'EUR',
    produits_total         REAL,
    dons                   REAL,
    cotisations_adherents  REAL,
    cotisations_elus       REAL,
    aide_publique_f1       REAL,
    aide_publique_f2       REAL,
    autres_aides_publiques REAL,
    contributions_recues   REAL,
    charges_total          REAL,
    resultat               REAL,
    PRIMARY KEY (parti_id, exercice)
);
CREATE INDEX idx_partis_comptes_exercice ON partis_comptes(exercice);
CREATE TABLE campagnes_2024 (
    candidat_id        TEXT PRIMARY KEY,
    nom                TEXT NOT NULL,
    scrutin            TEXT,
    circonscription    TEXT NOT NULL,
    departement        TEXT,
    code_departement   TEXT,
    nuance             TEXT,
    depenses_declarees REAL,
    depenses_retenues  REAL,
    recettes_declarees REAL,
    recettes_retenues  REAL,
    remboursement_etat REAL,
    decision           TEXT NOT NULL,
    decision_famille   TEXT NOT NULL
);
CREATE INDEX idx_campagnes_2024_decision ON campagnes_2024(decision_famille);
CREATE TABLE partis_aide_annuelle (
    annee             INTEGER PRIMARY KEY,
    montant_total_eur REAL NOT NULL,
    fraction1_eur     REAL,          -- NULL = non dépouillée dans le décret consulté
    fraction2_eur     REAL,
    perimetre         TEXT NOT NULL,
    reference         TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    note              TEXT
);
-- Une ligne par décret RÉELLEMENT consulté : aucune année n'est interpolée.
-- Remplace partis_aide_2026, qui ne portait qu'une année et faisait passer
-- pour comparables l'enveloppe nationale et la somme des aides déclarées par
-- les partis dans leurs comptes — deux grandeurs de nature différente.
CREATE VIEW v_partis_top_produits AS
            SELECT p.id AS parti_id, p.code_cnccfp, p.nom, p.sigle, c.exercice,
                   c.produits_total, c.charges_total, c.resultat,
                   COALESCE(c.aide_publique_f1,0) + COALESCE(c.aide_publique_f2,0)
                     + COALESCE(c.autres_aides_publiques,0) AS aide_publique,
                   c.dons,
                   COALESCE(c.cotisations_adherents,0)
                     + COALESCE(c.cotisations_elus,0)       AS cotisations
            FROM partis_comptes c
            JOIN partis p ON p.id = c.parti_id
            WHERE c.exercice = (SELECT MAX(exercice) FROM partis_comptes)
              AND c.unite = 'EUR'
            ORDER BY c.produits_total DESC
/* v_partis_top_produits(parti_id,code_cnccfp,nom,sigle,exercice,produits_total,charges_total,resultat,aide_publique,dons,cotisations) */;
CREATE VIEW v_partis_aide_publique_evolution AS
            SELECT exercice,
                   ROUND(SUM(COALESCE(aide_publique_f1,0)), 2)        AS aide_f1,
                   ROUND(SUM(COALESCE(aide_publique_f2,0)), 2)        AS aide_f2,
                   ROUND(SUM(COALESCE(autres_aides_publiques,0)), 2)  AS autres_aides_publiques,
                   ROUND(SUM(COALESCE(aide_publique_f1,0)
                           + COALESCE(aide_publique_f2,0)), 2)        AS aide_f1_f2,
                   SUM(CASE WHEN COALESCE(aide_publique_f1,0)
                              + COALESCE(aide_publique_f2,0) > 0
                        THEN 1 ELSE 0 END)                            AS nb_partis_aides
            FROM partis_comptes
            WHERE unite = 'EUR'
            GROUP BY exercice
            ORDER BY exercice
/* v_partis_aide_publique_evolution(exercice,aide_f1,aide_f2,autres_aides_publiques,aide_f1_f2,nb_partis_aides) */;
CREATE VIEW v_partis_ressources_par_type AS
            SELECT exercice,
                   ROUND(SUM(COALESCE(dons,0)), 2)                   AS dons,
                   ROUND(SUM(COALESCE(cotisations_adherents,0)), 2)  AS cotisations_adherents,
                   ROUND(SUM(COALESCE(cotisations_elus,0)), 2)       AS cotisations_elus,
                   ROUND(SUM(COALESCE(aide_publique_f1,0)
                           + COALESCE(aide_publique_f2,0)
                           + COALESCE(autres_aides_publiques,0)), 2) AS aide_publique,
                   ROUND(SUM(COALESCE(contributions_recues,0)), 2)   AS contributions_recues,
                   ROUND(SUM(COALESCE(produits_total,0))
                       - SUM(COALESCE(dons,0))
                       - SUM(COALESCE(cotisations_adherents,0))
                       - SUM(COALESCE(cotisations_elus,0))
                       - SUM(COALESCE(aide_publique_f1,0)
                           + COALESCE(aide_publique_f2,0)
                           + COALESCE(autres_aides_publiques,0))
                       - SUM(COALESCE(contributions_recues,0)), 2)   AS autres_produits,
                   ROUND(SUM(COALESCE(produits_total,0)), 2)         AS produits_total
            FROM partis_comptes
            WHERE unite = 'EUR'
            GROUP BY exercice
            ORDER BY exercice
/* v_partis_ressources_par_type(exercice,dons,cotisations_adherents,cotisations_elus,aide_publique,contributions_recues,autres_produits,produits_total) */;
CREATE VIEW v_campagnes_2024_agregats AS
            SELECT nb_candidats, depenses_declarees, depenses_retenues,
                   recettes_declarees, recettes_retenues, remboursement_etat,
                   nb_approuves, nb_reformes, nb_rejetes, nb_absences_depot,
                   nb_hors_delai, nb_dispenses_depot,
                   ROUND(1.0 * nb_rejetes
                         / NULLIF(nb_candidats - nb_dispenses_depot
                                  - nb_absences_depot, 0), 4)
                       AS taux_rejet_comptes_deposes
            FROM (
                SELECT COUNT(*)                                          AS nb_candidats,
                       ROUND(SUM(COALESCE(depenses_declarees,0)), 2)     AS depenses_declarees,
                       ROUND(SUM(COALESCE(depenses_retenues,0)), 2)      AS depenses_retenues,
                       ROUND(SUM(COALESCE(recettes_declarees,0)), 2)     AS recettes_declarees,
                       ROUND(SUM(COALESCE(recettes_retenues,0)), 2)      AS recettes_retenues,
                       ROUND(SUM(COALESCE(remboursement_etat,0)), 2)     AS remboursement_etat,
                       SUM(decision_famille = 'approuve')                AS nb_approuves,
                       SUM(decision_famille = 'approuve_apres_reformation') AS nb_reformes,
                       SUM(decision_famille = 'rejete')                  AS nb_rejetes,
                       SUM(decision_famille = 'absence_depot')           AS nb_absences_depot,
                       SUM(decision_famille = 'hors_delai')              AS nb_hors_delai,
                       SUM(decision_famille = 'dispense_depot')          AS nb_dispenses_depot
                FROM campagnes_2024
            )
/* v_campagnes_2024_agregats(nb_candidats,depenses_declarees,depenses_retenues,recettes_declarees,recettes_retenues,remboursement_etat,nb_approuves,nb_reformes,nb_rejetes,nb_absences_depot,nb_hors_delai,nb_dispenses_depot,taux_rejet_comptes_deposes) */;
CREATE VIEW v_campagnes_2024_par_decision AS
            SELECT decision, decision_famille, COUNT(*) AS nb,
                   ROUND(SUM(COALESCE(depenses_retenues,0)), 2)  AS depenses_retenues,
                   ROUND(SUM(COALESCE(remboursement_etat,0)), 2) AS remboursement_etat
            FROM campagnes_2024
            GROUP BY decision, decision_famille
            ORDER BY nb DESC
/* v_campagnes_2024_par_decision(decision,decision_famille,nb,depenses_retenues,remboursement_etat) */;
CREATE VIEW v_campagnes_2024_top_depenses AS
            SELECT candidat_id, nom, circonscription, departement, nuance,
                   depenses_declarees, depenses_retenues, remboursement_etat,
                   decision, decision_famille
            FROM campagnes_2024
            ORDER BY COALESCE(depenses_retenues, 0) DESC
/* v_campagnes_2024_top_depenses(candidat_id,nom,circonscription,departement,nuance,depenses_declarees,depenses_retenues,remboursement_etat,decision,decision_famille) */;
CREATE TABLE collectivites_departements (
    code_dep           TEXT NOT NULL,
    nom                TEXT NOT NULL,
    dep_fonctionnement REAL,
    dep_investissement REAL,
    euros_par_hab      REAL,      -- (fonctionnement + investissement) / population
    population         INTEGER,   -- somme des ptot communaux (population totale INSEE)
    nb_communes        INTEGER,
    exercice           INTEGER NOT NULL,
    PRIMARY KEY (code_dep, exercice)
);
CREATE TABLE collectivites_regions (
    code_region   TEXT NOT NULL,
    nom           TEXT NOT NULL,
    siren         TEXT,
    est_ctu       INTEGER NOT NULL DEFAULT 0,
    exercice      INTEGER NOT NULL,
    agregat       TEXT NOT NULL,
    montant       REAL,
    euros_par_hab REAL,
    population    INTEGER,
    PRIMARY KEY (code_region, exercice, agregat)
);
CREATE TABLE collectivites_conseils_departementaux (
    code_dep      TEXT NOT NULL,
    nom           TEXT NOT NULL,
    siren         TEXT,
    exercice      INTEGER NOT NULL,
    agregat       TEXT NOT NULL,
    montant       REAL,
    euros_par_hab REAL,
    population    INTEGER,
    PRIMARY KEY (code_dep, exercice, agregat)
);
CREATE TABLE collectivites_communes_top200 (
    code_insee          TEXT NOT NULL,
    nom                 TEXT NOT NULL,
    dep_code            TEXT,
    dep_nom             TEXT,
    siren               TEXT,
    population          INTEGER,
    dep_fonctionnement  REAL,
    fonct_euros_par_hab REAL,
    dep_investissement  REAL,
    inv_euros_par_hab   REAL,
    exercice            INTEGER NOT NULL,
    PRIMARY KEY (code_insee, exercice)
);
CREATE TABLE collectivites_communes_series (
    code_insee         TEXT NOT NULL,
    nom                TEXT NOT NULL,
    siren              TEXT,
    tranche_population TEXT,      -- strate OFGL codée '0'..'10' (population au 01/01/2025)
    epci_nom           TEXT,      -- groupement à fiscalité propre 2025 (NULL si isolée)
    exercice           INTEGER NOT NULL,
    agregat            TEXT NOT NULL,
    montant            REAL,
    euros_par_hab      REAL,
    population         INTEGER,
    PRIMARY KEY (code_insee, exercice, agregat)
);
CREATE TABLE collectivites_communes_strates (
    tranche_population    TEXT NOT NULL,   -- strate OFGL codée '0'..'10'
    exercice              INTEGER NOT NULL,
    agregat               TEXT NOT NULL,
    mediane_euros_par_hab REAL,
    nb_communes           INTEGER,         -- effectif de la strate (budgets principaux)
    PRIMARY KEY (tranche_population, exercice, agregat)
);
CREATE TABLE dotations_dgf (
    niveau      TEXT NOT NULL CHECK (niveau IN ('national', 'departement', 'commune')),
    code        TEXT NOT NULL,
    nom         TEXT NOT NULL,
    exercice    INTEGER NOT NULL,
    dgf_montant REAL NOT NULL,
    population  INTEGER,
    dgf_par_hab REAL,
    rang        TEXT CHECK (rang IN ('top', 'flop') OR rang IS NULL),
    nb_communes INTEGER,
    PRIMARY KEY (niveau, code, exercice)
);
CREATE INDEX idx_dgf_niveau_exercice ON dotations_dgf(niveau, exercice);
CREATE TABLE trainvie_faits (
    id          TEXT PRIMARY KEY,
    categorie   TEXT NOT NULL CHECK (categorie IN
                  ('indemnites_parlementaires', 'frais_mandat', 'controles', 'elysee', 'institutions', 'cabinets', 'elus_locaux')),
    libelle     TEXT NOT NULL,
    valeur      REAL NOT NULL CHECK (valeur > 0),
    unite       TEXT NOT NULL,
    periode     TEXT NOT NULL,
    institution TEXT NOT NULL,
    source_nom  TEXT NOT NULL,
    source_url  TEXT NOT NULL CHECK (source_url LIKE 'http%'),
    date_source TEXT NOT NULL,
    notes       TEXT
);
CREATE INDEX idx_trainvie_faits_categorie
    ON trainvie_faits(categorie);
CREATE TABLE trainvie_opacites (
    id            TEXT PRIMARY KEY,
    sujet         TEXT NOT NULL,
    ce_qui_manque TEXT NOT NULL,
    base_du_refus TEXT NOT NULL,
    source_nom    TEXT NOT NULL,
    source_url    TEXT NOT NULL CHECK (source_url LIKE 'http%'),
    date          TEXT NOT NULL
);
```

## Volumes par table

- alertes : 1590 lignes
- annonces_par_famille : 19 lignes
- annonces_par_jour : 31 lignes
- annonces_recentes : 9426 lignes
- ao_en_cours : 9011 lignes
- budget_destination_2025 : 2404 lignes
- budget_mensuel : 4212 lignes
- budget_vert : 1816 lignes
- campagnes_2024 : 4010 lignes
- collectivites_communes_series : 3200 lignes
- collectivites_communes_strates : 176 lignes
- collectivites_communes_top200 : 200 lignes
- collectivites_conseils_departementaux : 13170 lignes
- collectivites_departements : 101 lignes
- collectivites_regions : 1990 lignes
- decp_agg_departement : 107 lignes
- decp_agg_mois : 36 lignes
- decp_derniers_marches : 200 lignes
- decp_marches : 586229 lignes
- decp_repartition : 15 lignes
- decp_top_acheteurs : 50 lignes
- decp_top_titulaires : 50 lignes
- deputes : 577 lignes
- dotations_dgf : 618 lignes
- elus : 36018 lignes
- entites : 1059 lignes
- groupes_an : 12 lignes
- hatvp_agregats : 37 lignes
- hatvp_declarations : 12930 lignes
- jorf_nominations_ministere : 19 lignes
- jorf_par_jour_nature : 216 lignes
- jorf_textes : 2778 lignes
- lobby_activites : 41601 lignes
- lobby_agg_budgets : 23 lignes
- lobby_agg_institutions : 9 lignes
- lobby_agg_ministeres : 366 lignes
- lobby_agg_top_entites : 50 lignes
- lobby_agg_trimestres : 34 lignes
- lobby_entites : 4067 lignes
- marches_a_venir : 4060 lignes
- meta_sources : 25 lignes
- partis : 718 lignes
- partis_aide_annuelle : 2 lignes
- partis_comptes : 2179 lignes
- ref_departements : 101 lignes
- ref_villes : 184 lignes
- rne_cm_agregats : 104 lignes
- scrutins : 8434 lignes
- senateurs : 348 lignes
- subventions_associations : 112722 lignes
- trainvie_faits : 56 lignes
- trainvie_opacites : 8 lignes
- votes_recents : 13796 lignes

## Conventions de valeurs — ce que le DDL ne dit pas

Le bloc `CREATE TABLE` ci-dessus est un dump : il donne les types, pas le
sens des valeurs. Les normalisations suivantes sont appliquées **à
l'ingestion** et ne sont donc lisibles nulle part dans le schéma. Elles
datent du 20/08/2026 (§ 5 de `doc/QUALITE-DONNEES.md`) : les tables
produites avant cette date ne les portent pas.

| Table.colonne | Convention appliquée | Pourquoi |
|---|---|---|
| `ao_en_cours` (table entière) | Un avis dont la date limite dépasse la parution de plus de **15 ans** n'est pas ingéré (`ECART_MAX_LIMITE_ANNEES`) | Coquilles de millésime de l'acheteur (« 2924 » pour « 2024 ») qui laissaient des avis de 2017 dans le compteur « AO en cours » |
| `campagnes_2024.code_departement` | Code **COG** : zéro initial rétabli (`01`…`09`), `2A`/`2B`, `977` pour Saint-Barthélemy. **NULL** pour les Français établis hors de France | Le CSV CNCCFP publie des codes non INSEE, et rattachait 125 lignes « hors de France » au département 75 (Paris). Joignable à `ref_departements` depuis cette normalisation |
| `campagnes_2024.departement` | `ZZ` → `Français établis hors de France` | Sentinelle de la source, illisible telle quelle |
| `campagnes_2024.circonscription` | Ordinaux ramenés à `1re` / `Ne` (jamais `1ère` / `Nème`) | Quatre conventions typographiques coexistaient, et deux d'entre elles s'affichaient côte à côte en page Alertes |
| `decp_marches.duree_mois` | **NULL** hors de l'intervalle `[0, 600]` mois | La source livre des durées négatives et jusqu'à 32 000 mois. NULL dit « non renseigné » ; une durée négative ment |
| `decp_marches.objet` / `.acheteur_nom` / `.titulaire_nom` | Mojibake réparé, espaces normalisés (insécables et retours ligne → une espace, bords rognés) | Double encodage UTF-8→cp1252 de la source ; les espaces parasites cassaient tris, `GROUP BY` et recherche |
| `decp_marches.titulaires_json` | Mojibake réparé, espaces **non** touchés | C'est du JSON : ses espaces sont de la syntaxe |
| `hatvp_declarations` (table entière) | Lignes strictement identiques sur les **seize** colonnes écartées | 50 doublons dans `liste.csv`, qui comptaient double dans les agrégats servis sur `/elus` |
| `subventions_associations.etat_administratif` | Le `0` littéral → **NULL** | 3 638 lignes où Chorus écrit un zéro pour dire « inconnu ». `Non déterminé` est une vraie valeur de la nomenclature et est conservé |
| `subventions_associations.*` (colonnes texte) | Mojibake réparé | `Côte dâ€™Ivoire` dans le CSV publié du jaune budgétaire |

Ce qui n'est **pas** normalisé, et pourquoi :

- **`decp_marches.titulaire_siret`** — 6 738 SIRET malformés conservés tels
  quels : c'est le seul identifiant disponible pour ces marchés, et il sert
  de clé de regroupement aux agrégats par titulaire. La réponse est un
  rapprochement SIRENE, pas un effacement.
- **`campagnes_2024.departement`** (libellés désaccentués) — une fois le
  code ramené au COG, le libellé canonique s'obtient par jointure sur
  `ref_departements`, sans coupler le pipeline financement au référentiel.
- **`partis_comptes`** — les incohérences comptables (produits totaux
  négatifs, `produits − charges ≠ résultat`) sont **journalisées** à chaque
  ingestion mais jamais réécrites : ce sont les comptes publiés par la
  CNCCFP.
- **`hatvp_declarations.date_depot` / `.date_publication`** — les dates
  impossibles sont journalisées, jamais corrigées : toute correction serait
  une devinette.
