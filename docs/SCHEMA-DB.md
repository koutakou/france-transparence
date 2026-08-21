# Schéma de la base data/france.db — généré le 19/08/2026 16:16 après make ingest,
# complété le 20/08/2026 (renommage collectivites_communes → collectivites_communes_top200 ;
# tables collectivites_communes_series et collectivites_communes_strates, comptages du 20/08)
# et le 21/08/2026 (table sirene_unites_legales, S18 ; puis decp_qualite_montants,
# elections_participation_departement, elections_participation_ville et les quatre
# tables hatvp_decl_*, jusque-là absentes ; corrections campagnes_2024.marqueur_etoile
# et trainvie_faits.assiette)

> **Extrait daté.** Ce document décrit **les 70 tables**, **les 6 vues** et **les 55 index** que
> `sqlite_master` recense au 21/08/2026 : la couverture du schéma y est entière à cette date. Le DDL
> reproduit a été confronté objet par objet à celui de la base servie — noms, types, `NOT NULL`,
> valeurs par défaut et clés primaires coïncident colonne à colonne pour les 70 tables, et les noms
> d'index coïncident un à un. Les comptages de lignes cités décrivent le jour de leur mesure et
> **dérivent à chaque ingestion** ; le catalogue vivant est la page `/donnees`, régénérée à chaque
> publication. Le schéma qui fait foi reste celui de la base elle-même :
> `sqlite3 -readonly data/france.db ".schema"`.
>
> **La base servie est une base migrée.** Trois colonnes y ont été posées par `ALTER TABLE` plutôt
> que par le `CREATE TABLE` du pipeline : `elus.hatvp_url`, `campagnes_2024.marqueur_etoile` et
> `trainvie_faits.assiette`. Elles se reconnaissent au fragment `, colonne …);` détaché en fin de
> DDL, elles arrivent en **dernière position** de la table — ce qui suffit à décaler un
> `SELECT *` — et elles ne portent **pas** les contraintes du schéma de création, SQLite ne sachant
> pas attacher un `CHECK` à une colonne ajoutée après coup. Le DDL ci-dessous reproduit l'état de la
> base servie, jamais celui d'une base neuve : sur une base fraîchement créée, ces trois colonnes
> sont à leur place nominale et `trainvie_faits.assiette` y porte son `CHECK`.

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
CREATE TABLE decp_qualite_montants (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),  -- table à ligne unique
    nb_marches            INTEGER NOT NULL,   -- marchés de la fenêtre, montant NULL compris
    montant_total         REAL,               -- somme des montants ÉCRÊTÉS (= le total affiché)
    nb_ecretes            INTEGER NOT NULL,   -- marchés dont le montant retenu dépasse plafond
    montant_ecretes       REAL,               -- leur contribution APRÈS écrêtage (nb × plafond)
    nb_suspects           INTEGER NOT NULL,   -- decp_marches.montant_suspect = 1
    montant_suspects      REAL,               -- leur contribution écrêtée
    montant_hors_suspects REAL,               -- montant_suspect = 0 — BORNE BASSE, cf. § pièges
    montant_brut          REAL,               -- somme des montants retenus SANS écrêtage
    nb_sans_montant       INTEGER NOT NULL,   -- montant_retenu IS NULL (comptés, jamais sommés)
    plafond               REAL NOT NULL       -- PLAFOND_ECRETAGE_EUR du pipeline, en euros
);
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
-- ---------------------------------------------------------------------------
-- S15 — CONTENU des déclarations d'intérêts HATVP (declarations.xml),
-- pipeline `pipelines/ingest_hatvp_declarations.py`. À ne pas confondre avec
-- S14 / `hatvp_declarations`, qui dit qu'une déclaration EXISTE et à quelle
-- date ; ces quatre tables-ci disent ce qu'elle CONTIENT.
-- PÉRIMÈTRE : INTÉRÊTS SEULEMENT. Seuls les types DI et DIA sont acceptés ;
-- les déclarations de situation PATRIMONIALE (DSP, DSPM, DSPFM) et les
-- quatorze balises patrimoniales sont refusées deux fois, par type ET par nom
-- de balise — leur divulgation est punie par l'article LO 135-2 du code
-- électoral. Ni employeur du conjoint ni identité des collaborateurs.
-- AUCUNE COLONNE NUMÉRIQUE de montant : les sommes déclarées sont stockées
-- verbatim en TEXT, ce qui rend structurellement impossibles un total, un
-- classement ou une moyenne construits sur des libellés qui ne les supportent
-- pas. L'affichage est verbatim, daté, et rien d'autre.
-- ---------------------------------------------------------------------------
CREATE TABLE hatvp_decl_interets (
    uuid                     TEXT PRIMARY KEY,   -- uuid natif de la déclaration
    elu_id                   TEXT NOT NULL,      -- elus.id (appariement nom+prénom+naissance)
    type_declaration         TEXT NOT NULL,      -- 'DI' | 'DIA', jamais autre chose
    type_declaration_libelle TEXT,               -- label natif HATVP
    date_depot               TEXT,               -- ISO (jour), depuis dateDepot
    modificative             INTEGER NOT NULL DEFAULT 0,
    qualite_declarant        TEXT,               -- « Vice-président délégué à… », verbatim
    organe_libelle           TEXT,               -- « Ain (01) », « Assemblée nationale »…
    type_mandat              TEXT,               -- codTypeMandatFichier natif
    nb_lignes                INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_hatvp_decl_interets_elu ON hatvp_decl_interets(elu_id);
CREATE TABLE hatvp_decl_rubriques (
    declaration_uuid TEXT NOT NULL,
    rubrique         TEXT NOT NULL,
    rubrique_ordre   INTEGER NOT NULL,
    -- 1 = « néant » déclaré par la personne (un FAIT, affichable) ;
    -- 0 = rubrique renseignée ; NULL = rubrique absente de la déclaration.
    -- Une rubrique absente de cette table = donnée que NOUS n'avons pas.
    neant            INTEGER,
    nb_lignes        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (declaration_uuid, rubrique)
);
CREATE TABLE hatvp_decl_lignes (
    id                   INTEGER PRIMARY KEY,
    declaration_uuid     TEXT NOT NULL,
    elu_id               TEXT NOT NULL,
    rubrique             TEXT NOT NULL,
    rubrique_ordre       INTEGER NOT NULL,
    rang                 INTEGER NOT NULL,   -- ordre d'apparition dans la rubrique
    libelle              TEXT,               -- société, employeur, structure, mandat
    description          TEXT,               -- activité exercée / texte libre
    date_debut           TEXT,               -- verbatim ('11/2019'), jamais recomposé
    date_fin             TEXT,
    commentaire          TEXT,
    conservee            INTEGER,            -- 1/0/NULL — activité conservée pendant le mandat
    evaluation           TEXT,               -- participation financière : évaluation déclarée
    capital_detenu       TEXT,               -- … part du capital détenue
    nombre_parts         TEXT,               -- … nombre de parts
    remuneration_libre   TEXT,               -- … champ texte libre (« Néant », « 0 », « NS »)
    activite_conseil     TEXT,               -- 'Oui' | 'Non' natifs
    organisation_conseil TEXT
);
CREATE INDEX idx_hatvp_decl_lignes_elu  ON hatvp_decl_lignes(elu_id);
CREATE INDEX idx_hatvp_decl_lignes_decl ON hatvp_decl_lignes(declaration_uuid, rubrique_ordre, rang);
CREATE TABLE hatvp_decl_montants (
    ligne_id INTEGER NOT NULL,
    annee    TEXT NOT NULL,
    montant  TEXT NOT NULL,   -- verbatim, ex. '70 676' (espace fine insécable native)
    brut_net TEXT,            -- 'Net' | 'Brut' natifs
    PRIMARY KEY (ligne_id, annee)
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
-- ---------------------------------------------------------------------------
-- S40 — Registre de transparence de l'Union européenne (pipeline P16).
-- Le préfixe `ue_registre_` marque un CLOISONNEMENT VOULU : ces tables
-- décrivent un AUTRE registre, adossé à un AUTRE cadre juridique (accord
-- interinstitutionnel du 20/05/2021) que les tables `lobby_*` (loi
-- « Sapin II »). Elles ne doivent jamais être jointes à celles-ci ni leurs
-- montants comparés — et la jointure serait impossible de toute façon :
-- l'export européen ne publie AUCUN identifiant national d'entreprise,
-- d'aucun pays (ni SIREN, ni TVA), son seul identifiant est le code du
-- registre lui-même.
-- Les inscrits « Self-employed individuals » (personnes physiques) sont
-- comptés dans les tables d'agrégats et ABSENTS de la table nominative ;
-- l'écart est publié par `ue_registre_agg_pays.nb_personnes_physiques`.
-- ---------------------------------------------------------------------------
CREATE TABLE ue_registre_organisations (
    id                  TEXT PRIMARY KEY,   -- identificationCode du registre UE
    nom                 TEXT NOT NULL,
    nom_latin           TEXT,
    acronyme            TEXT,
    categorie           TEXT,
    siege_ville         TEXT,
    siege_code_postal   TEXT,
    siege_pays          TEXT,               -- libellé anglais natif ('FRANCE')
    date_inscription    TEXT,
    date_maj            TEXT,
    etp                 REAL,               -- membersFTE : ETP consacrés
    accredites_pe       INTEGER,            -- nb d'accréditations au PE (compte seul)
    exercice_debut      TEXT,
    exercice_fin        TEXT,
    cout_libelle        TEXT,               -- fourchette rendue en euros
    cout_min            REAL,               -- borne native, NULL si non bornée
    cout_max            REAL
);
CREATE INDEX idx_ue_registre_orgs_pays ON ue_registre_organisations(siege_pays);
CREATE TABLE ue_registre_agg_categories (
    categorie        TEXT PRIMARY KEY,
    nb_organisations INTEGER NOT NULL,
    nb_france        INTEGER NOT NULL
);
CREATE TABLE ue_registre_agg_pays (
    pays                  TEXT PRIMARY KEY,
    nb_organisations      INTEGER NOT NULL,
    nb_personnes_physiques INTEGER NOT NULL
);
CREATE TABLE ue_registre_agg_interets (
    domaine          TEXT PRIMARY KEY,
    nb_organisations INTEGER NOT NULL,
    nb_france        INTEGER NOT NULL
);
CREATE TABLE ue_registre_agg_couts (
    fourchette       TEXT PRIMARY KEY,
    borne_min        REAL,
    borne_max        REAL,
    nb_organisations INTEGER NOT NULL,
    nb_france        INTEGER NOT NULL
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
-- Ajoutée par migration (ALTER TABLE) : marqueur « (*) » sorti du nom CNCCFP.
-- Sa signification n'est PAS documentée par le jeu de données amont ; la
-- colonne le restitue sans l'interpréter.
, marqueur_etoile INTEGER NOT NULL DEFAULT 0);
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
-- ---------------------------------------------------------------------------
-- S26 — Participation électorale (résultats agrégés du ministère de
-- l'Intérieur), pipeline `pipelines/ingest_elections.py`. Sept scrutins :
-- municipales 2026 T1/T2, législatives 2024 T1/T2, européennes 2024,
-- présidentielle 2022 T1/T2.
-- CE QUI EST INGÉRÉ : la participation, et rien d'autre. Pas de nuance
-- politique (attribuée par les préfectures, vide à 25,2 % aux municipales
-- 2026, grille changée entre 2020 et 2026 — aucune série possible), pas de
-- nom de candidat (la ressource nominative n'est ni téléchargée ni lue), pas
-- de bureau de vote (grain natif de 3,16 M de lignes, exposé nulle part).
-- AUCUN TAUX N'EST STOCKÉ : les ratios se calculent à l'affichage sur les
-- effectifs bruts, pour qu'une donnée absente reste absente — un taux stocké
-- se lirait comme un zéro.
-- ---------------------------------------------------------------------------
CREATE TABLE elections_participation_departement (
    id_election         TEXT NOT NULL,     -- ex. '2026_muni_t1' (identifiant natif MI)
    code_departement    TEXT NOT NULL,     -- DÉRIVÉ de code_commune (cf. piège 1)
    libelle_departement TEXT NOT NULL,
    inscrits            INTEGER NOT NULL,
    votants             INTEGER NOT NULL,
    blancs              INTEGER NOT NULL,
    nuls                INTEGER NOT NULL,
    exprimes            INTEGER NOT NULL,
    PRIMARY KEY (id_election, code_departement)
);
CREATE TABLE elections_participation_ville (
    id_election      TEXT NOT NULL,
    code_commune     TEXT NOT NULL,        -- code INSEE 5 caractères
    libelle_commune  TEXT NOT NULL,
    code_departement TEXT NOT NULL,        -- DÉRIVÉ de code_commune (cf. piège 1)
    inscrits         INTEGER NOT NULL,
    votants          INTEGER NOT NULL,
    blancs           INTEGER NOT NULL,
    nuls             INTEGER NOT NULL,
    exprimes         INTEGER NOT NULL,
    PRIMARY KEY (id_election, code_commune)
);
CREATE INDEX idx_elections_ville_commune
    ON elections_participation_ville(code_commune);
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
CREATE TABLE cada_administrations (
    id             INTEGER PRIMARY KEY,       -- surface, réattribué à chaque ingestion
    libelle        TEXT    NOT NULL,          -- graphie majoritaire, telle que publiée
    categorie      TEXT    NOT NULL CHECK (categorie IN
                     ('ministere', 'prefecture', 'commune', 'departement_region', 'sante', 'enseignement', 'securite_sociale', 'finances', 'justice_police', 'autorite_independante', 'autre')),
    nb_dossiers    INTEGER NOT NULL CHECK (nb_dossiers > 0),
    premiere_annee INTEGER NOT NULL,
    derniere_annee INTEGER NOT NULL
);
CREATE INDEX idx_cada_admin_categorie
    ON cada_administrations(categorie, nb_dossiers DESC);
CREATE TABLE cada_saisines (            -- LE DÉNOMINATEUR : nombre de dossiers
    administration_id INTEGER NOT NULL REFERENCES cada_administrations(id),
    annee             INTEGER NOT NULL,
    type_saisine      TEXT    NOT NULL CHECK (type_saisine IN ('Avis', 'Conseil', 'Sanction')),
    nb_dossiers       INTEGER NOT NULL CHECK (nb_dossiers > 0),
    PRIMARY KEY (administration_id, annee, type_saisine)
) WITHOUT ROWID;
CREATE TABLE cada_sens (                -- LE FAIT : dossiers portant ce sens
    administration_id INTEGER NOT NULL REFERENCES cada_administrations(id),
    annee             INTEGER NOT NULL,
    type_saisine      TEXT    NOT NULL CHECK (type_saisine IN ('Avis', 'Conseil', 'Sanction')),
    sens              TEXT    NOT NULL CHECK (sens IN
                        ('Favorable', 'Défavorable', 'Irrecevable', 'Incompétence', 'Sans objet')),
    nb_dossiers       INTEGER NOT NULL CHECK (nb_dossiers > 0),
    PRIMARY KEY (administration_id, annee, type_saisine, sens)
) WITHOUT ROWID;
CREATE TABLE cada_motifs (              -- le fondement opposé au demandeur
    annee        INTEGER NOT NULL,
    type_saisine TEXT    NOT NULL CHECK (type_saisine IN ('Avis', 'Conseil', 'Sanction')),
    sens         TEXT    NOT NULL CHECK (sens IN
                   ('Favorable', 'Défavorable', 'Irrecevable', 'Incompétence', 'Sans objet')),
    motivation   TEXT,                  -- NULL = sens publié sans motivation
    nb_dossiers  INTEGER NOT NULL CHECK (nb_dossiers > 0)
);
CREATE UNIQUE INDEX idx_cada_motifs_cle
    ON cada_motifs(annee, type_saisine, sens, ifnull(motivation, ''));
CREATE INDEX idx_cada_motifs_sens ON cada_motifs(sens, motivation);
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
-- Ajoutée par migration (ALTER TABLE), d'où la dernière position ET l'absence
-- de contrainte : SQLite ne sait pas attacher un CHECK à une colonne ajoutée
-- après coup. Le schéma de création porte bien
-- `CHECK (assiette IS NULL OR assiette IN ('brut','net'))`, mais une base
-- migrée — dont la base servie — ne l'a PAS. Le vocabulaire ('brut' | 'net' |
-- NULL) n'est tenu que par le pipeline et ses tests : le vérifier en lecture.
, assiette TEXT);
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
-- ---------------------------------------------------------------------------
-- S18 — Stock Sirene (INSEE), pipeline `pipelines/ingest_sirene.py`.
-- Référentiel d'ATTRIBUTS, pas de noms : il qualifie les SIREN que les AUTRES
-- tables citent déjà (decp_marches, subventions_associations, lobby_entites,
-- marches_a_venir, entites, collectivites_*, decp_top_*). Table DÉRIVÉE : son
-- périmètre est celui de la base à l'instant de l'ingestion, jamais le stock
-- amont — d'où un pipeline qui doit passer APRÈS les autres.
-- Minimisation : aucun nom, prénom, pseudonyme ni sexe de personne physique
-- n'est lu du fichier amont, et les unités non diffusibles
-- (statutDiffusionUniteLegale <> 'O', droit d'opposition de l'article A123-96
-- du code de commerce) ne sont pas écrites.
-- ---------------------------------------------------------------------------
CREATE TABLE sirene_unites_legales (
    siren                      TEXT PRIMARY KEY,  -- 9 chiffres, tel que publié
    denomination               TEXT,      -- raison sociale ; NULL pour les personnes physiques
    sigle                      TEXT,      -- sigle déclaré, NULL si absent
    est_personne_physique      INTEGER NOT NULL DEFAULT 0,  -- 1 = entrepreneur individuel
    categorie_juridique        TEXT,      -- code INSEE à 4 chiffres, TEXTE (jamais un entier)
    activite_principale        TEXT,      -- code NAF/APE, tel que publié ('84.11Z')
    nomenclature_activite      TEXT,      -- nomenclature du code ci-dessus : 'NAFRev2', 'NAP'…
    tranche_effectifs          TEXT,      -- CODE de tranche INSEE ('00', '01'… '53'), pas un effectif
    annee_effectifs            INTEGER,   -- année de validité de la tranche ci-dessus
    categorie_entreprise       TEXT,      -- 'PME' / 'ETI' / 'GE'
    etat_administratif         TEXT,      -- 'A' active / 'C' cessée
    date_creation              TEXT,      -- date du parquet rendue en texte (ISO)
    economie_sociale_solidaire INTEGER,   -- 1 / 0 / NULL (non renseigné)
    societe_mission            INTEGER    -- 1 / 0 / NULL (non renseigné)
);
CREATE INDEX idx_sirene_cat_juridique
    ON sirene_unites_legales(categorie_juridique);
CREATE INDEX idx_sirene_activite
    ON sirene_unites_legales(activite_principale);
CREATE INDEX idx_sirene_etat
    ON sirene_unites_legales(etat_administratif);
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
- decp_qualite_montants : 1 ligne, et une seule — `CHECK (id = 1)` (structurel)
- decp_top_acheteurs : 50 lignes
- decp_top_titulaires : 50 lignes
- deputes : 577 lignes
- dotations_dgf : 618 lignes
- elections_participation_departement : 740 lignes (comptage du 21/08/2026 —
  7 scrutins × 102 à 107 départements et collectivités ; volume borné par le
  nombre de scrutins ingérés, non par un flux quotidien)
- elections_participation_ville : 1524 lignes (comptage du 21/08/2026 —
  233 communes distinctes, celles que le site connaît déjà, présentes dans
  156 à 233 scrutins selon le scrutin)
- elus : 36018 lignes
- entites : 1059 lignes
- groupes_an : 12 lignes
- hatvp_agregats : 37 lignes
- hatvp_declarations : 12930 lignes
- hatvp_decl_interets : 2261 lignes (comptage du 21/08/2026)
- hatvp_decl_rubriques : 15827 lignes (comptage du 21/08/2026 — exactement
  7 × 2261 : le grain est complet, cf. § dédié)
- hatvp_decl_lignes : 27711 lignes (comptage du 21/08/2026)
- hatvp_decl_montants : 94487 lignes (comptage du 21/08/2026 ; de l'ordre de
  33 500 portent une valeur autre que le zéro littéral)
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
- cada_administrations : 16593 lignes (comptage du 20/08/2026)
- cada_motifs : 2034 lignes (comptage du 20/08/2026)
- cada_saisines : 32614 lignes (comptage du 20/08/2026)
- cada_sens : 47297 lignes (comptage du 20/08/2026)
- meta_sources : 30 lignes (une par source tracée, S18 comprise depuis le 21/08/2026)
- sirene_unites_legales : de l'ordre de 163 000 lignes (21/08/2026 — c'est le
  nombre de SIREN cités par le reste de la base, et il dérive avec elle ;
  ~24 Mio en base, index compris)
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
- ue_registre_agg_categories : 13 lignes (comptage du 20/08/2026)
- ue_registre_agg_couts : 32 lignes (comptage du 20/08/2026)
- ue_registre_agg_interets : 40 lignes (comptage du 20/08/2026)
- ue_registre_agg_pays : 140 lignes (comptage du 20/08/2026)
- ue_registre_organisations : 17476 lignes (comptage du 20/08/2026 — 17 711
  inscrits au registre moins 235 personnes physiques non nommées ;
  +4 427 776 octets en base, index compris)
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

## Les tables `cada_*` (S38) — ce qu'il faut savoir avant de s'en servir

### 1. Le corpus n'est ingéré qu'en agrégats, et c'est une décision

Le CSV consolidé publié par la CADA pèse 198 Mo, dont **93 % pour la seule
colonne « Avis »** (176,6 Mio sur 189,2 Mio, mesuré au passage du pipeline) : le texte intégral de chaque décision. Ce texte n'entre
jamais en base — poids, et prudence : les demandeurs sont anonymisés à la
source (« X, député »), mais les motivations citent nommément des
responsables publics. Les quatre tables ne contiennent que des
dénombrements, un libellé d'administration et le vocabulaire fermé de la
commission. Les colonnes « Objet », « Mots clés » et « Numéro de dossier »
ne sont pas ingérées non plus. Coût réel mesuré : **3,61 Mio** de base.

### 2. `cada_saisines` est le seul dénominateur légitime

Une décision porte souvent plusieurs sens (favorable sur une pièce,
défavorable sur une autre). `cada_sens` compte un dossier **une fois par
sens présent** : sa somme dépasse donc le nombre de dossiers d'environ un
cinquième et ne peut jamais servir de total. Toute part se calcule sur
`cada_saisines`, et la somme des parts dépasse 100 % — c'est correct, et
l'UI le dit.

Corollaire : **n'additionnez jamais « Défavorable + Incompétence +
Irrecevable »** pour obtenir « les refus ». Les décisions composites
seraient comptées deux fois. La page `/frais` s'en tient au seul sens
« Défavorable » pour cette raison.

### 3. `cada_administrations` est un cinquième vocabulaire d'administrations,
et c'est assumé

La base n'a **aucun référentiel unifié d'administrations**. Elle en porte
déjà quatre, disjoints (mesurés le 20/08/2026 sur la base servie) :

| Vocabulaire | Volume | Identifiants |
|---|---|---|
| `entites` (`type='ministere'`) | 20 lignes | 2 SIREN sur 20 |
| `lobby_agg_ministeres` | 357 libellés HATVP historiques | aucun |
| `jorf_nominations_ministere` | 19 libellés, casse propre au JO | aucun |
| `trainvie_faits.institution` | 11 libellés | aucun |

Ils ne se joignent pas : sur les 357 libellés AGORA confrontés à `entites`,
**un seul** correspond exactement.

```sql
select count(*), sum(exists(select 1 from entites e where e.type='ministere'
       and upper(e.nom)=upper(m.ministere))) from lobby_agg_ministeres m;
-- 357|1
```

`cada_administrations` en ajoute un cinquième, délibérément :

- **le champ source est du texte libre**, sans code ni SIREN, et il court sur
  **quarante ans** (1984→2024) de dénominations superposées ;
- sa distribution réelle interdit un référentiel : **16 984 libellés bruts**,
  dont **plus de dix mille n'apparaissent qu'une fois** (« Mairie de
  Dœuil-sur-le-Mignon »). Ce n'est pas un référentiel à retrouver, c'est une
  longue traîne de communes et d'établissements ;
- replier casse, accents et ponctuation ne ramène qu'à **16 593** entrées :
  cela réunit « Ministère de la Justice » et « Ministère de la justice », et
  rien de plus.

Ce repli est **le seul** appliqué. Deux dénominations différentes restent
deux entrées : « Ministère de la défense » (197 dossiers) et « Ministère
des Armées » (544) désignent le même ministère à deux époques, mais les
fusionner serait une reconstitution historique, pas une normalisation — et
sur quarante ans d'intitulés ministériels, une normalisation hasardeuse
produirait des agrégats faux, ce qui est bien pire que des libellés bruts.

Les cinq vocabulaires restent donc **distincts** : aucun rapprochement n'est
fait avec les quatre autres, et aucun référentiel unifié n'existe. Ce n'est pas
une dette cachée : c'est écrit ici pour que la table ne devienne pas un
vocabulaire orphelin dont personne ne sait plus pourquoi il existe.

### 4. `cada_administrations.categorie` est une typologie, pas un classement officiel

Onze catégories, obtenues par **préfixe explicite** de la clé normalisée
(règles littérales, relisibles une à une dans `pipelines/ingest_cada.py`).
Ce qui n'entre dans aucune règle reste en **`autre`** — 5 426 libellés,
**14 130 dossiers, soit 23,2 % du corpus**, affichés comme « non classés » et
jamais répartis d'office. Une seule exclusion explicite : « Conseil
départemental de l'**ordre** des médecins » est un ordre professionnel, pas
une collectivité (48 libellés, 80 dossiers, sans quoi ils gonfleraient
`departement_region`).

### 5. `cada_motifs.motivation` — le séparateur appartient au vocabulaire

Le champ source « Sens et motivation » concatène des éléments
`Sens/Motivation` séparés par des virgules, **et certaines motivations
contiennent une virgule** (« Irrecevable/Documentation, établissement de
document », 262 dossiers). Une découpe naïve fabriquerait un sens
« établissement de document » qui n'existe pas. La règle appliquée : un
fragment n'ouvre un nouvel élément que s'il commence par l'un des **cinq**
sens du vocabulaire fermé suivi d'un `/` ou de la fin ; sinon il est recollé
au précédent. Contrôle sur le corpus entier : **zéro fragment orphelin**,
cinq sens, **89 motivations distinctes** (165 avant normalisation des
espaces autour du `/` : « Favorable / Sauf vie privée » et
« Favorable/Sauf vie privée » sont la même règle de droit).

`motivation` est **NULL** — jamais chaîne vide — quand la CADA publie un sens
sans motivation (« Défavorable » seul, 749 dossiers ; « Favorable » nu, 22 808). D'où l'unicité par
index d'expression plutôt que par clé primaire, qui interdirait le NULL.

### 6. La colonne « Thème et sous thème » n'est PAS ingérée

Même défaut, mais irréparable : les thèmes eux-mêmes contiennent des
virgules (« Justice, Ordre Public Et Sécurité », « Economie, Industrie,
Agriculture ») et le vocabulaire n'est pas publié. La découpe est ambiguë
dès qu'une décision porte plusieurs thèmes (1 274 lignes sur 60 941).
Reconstituer la nomenclature à la main serait de l'invention : colonne
écartée.

### 7. `meta_sources.date_donnees` porte la SÉANCE, jamais la date du dataset

C'est tout l'intérêt éditorial de cette source : le jeu amont porte une date
de modification récente alors que sa dernière séance a plus de deux ans. La
fraîcheur enregistrée est celle de la donnée réellement ingérée
(`2024-04-18` au 20/08/2026), ce qui place S38 en **ALERTE** dans
`ft-fraicheur` (seuils 730/820 j) au lieu de masquer le décalage. Le
`notes` de la ligne S38 porte l'écart mesuré au passage du pipeline.

### 8. Les identifiants d'administration sont de surface

`cada_administrations.id` est un entier réattribué à chaque ingestion, par
ordre alphabétique de clé normalisée. Reproductible à corpus identique, mais
**instable dans le temps** : ne le stockez nulle part ailleurs, ne le mettez
dans aucune URL. Les quatre tables sont reconstruites ensemble à chaque
passage, rien d'autre en base ne les référence.

## La table `sirene_unites_legales` (S18) — ce qu'il faut savoir avant de s'en servir

### 1. C'est un référentiel d'attributs, pas un dictionnaire de noms

L'intuition première est qu'un référentiel Sirene sert à donner un nom aux
SIREN. La mesure dit le contraire : sur les quelque 164 000 SIREN cités par
l'ensemble des tables, à peine **0,25 %** n'avaient aucun nom nulle part — les
autres sources le fournissent déjà. Ce qui manquait, c'étaient les attributs :
environ **deux tiers** des SIREN cités n'avaient ni catégorie juridique, ni
code d'activité, ni état administratif, ni appartenance à l'économie sociale
et solidaire. `denomination` et `sigle` sont donc un bonus — la valeur de la
table est dans les colonnes qui les suivent.

Deux usages en découlent, du côté des tables qui citent des SIREN :
une **dénomination de référence** là où quelque 2 500 SIREN titulaires de
marchés portent de l'ordre de 6 400 libellés distincts dans les DECP (la même
entreprise écrite de deux ou trois façons, ce qui éclate tout classement par
nom) ; et un **test de validité de l'identifiant** pour les ~7 400 lignes DECP
qui portent un SIRET malformé (numéros de TVA intracommunautaire, `00001`,
`999999999`…) — un SIREN absent de Sirene n'est pas un SIREN.

### 2. Le périmètre est celui de la base, pas celui de Sirene

La table ne contient **que** les SIREN que les autres tables citent
réellement — de l'ordre de 163 000 lignes, quand le stock amont en compte
environ 30 millions. Un SIREN absent de `sirene_unites_legales` n'est donc pas
un SIREN inconnu de l'INSEE : c'est, dans la quasi-totalité des cas, un SIREN
que rien d'autre en base ne mentionne. Le coût mesuré est de **≈ 155 octets
par ligne** : de l'ordre de 24 Mio pour ce périmètre, contre ≈ 5,8 Gio pour le
stock entier — 238 fois plus de données pour un usage identique.

Conséquence pratique : la table est **dérivée**, elle se reconstruit
entièrement à chaque passage (`DELETE` puis `INSERT` dans une transaction
unique) et son pipeline doit s'exécuter **après** ceux dont il lit les SIREN.
Son volume suit celui de la base, pas celui de l'INSEE.

### 3. `denomination` est NULL pour les personnes physiques — délibérément

`StockUniteLegale` décrit aussi les entrepreneurs individuels : nom de
naissance, nom d'usage, quatre prénoms, prénom usuel, pseudonyme, sexe. Ce
sont des données à caractère personnel, et le périmètre en compte de l'ordre
de 6 000. **Aucune de ces colonnes n'est lue du fichier amont** : elles ne
figurent pas dans la requête d'extraction. Une personne physique entre au
référentiel avec sa catégorie juridique, son activité et son état — jamais
avec son identité.

Donc : `denomination IS NULL AND est_personne_physique = 1` signifie « unité
légale exploitée par une personne physique, dont l'identité n'est pas en
base ». Ce n'est **pas** une donnée manquante à aller chercher ailleurs, et
ce n'est pas un trou à combler : c'est le résultat voulu. Toute restitution
qui trie ou groupe par `denomination` doit traiter ce NULL comme une classe à
part entière, jamais comme une anomalie de qualité.

`est_personne_physique` vaut 1 quand la catégorie juridique amont est `1000`,
et 0 sinon ; la colonne est `NOT NULL DEFAULT 0`, il n'y a pas de troisième
état. Les unités **non diffusibles** (droit d'opposition de l'article A123-96
du code de commerce, de l'ordre d'un millier dans le périmètre) sont écartées
à l'extraction : elles ne sont ni dans la table, ni comptées dans ses lignes.

### 4. `categorie_juridique` est du texte de 4 caractères, jamais un entier

Le parquet livre `categorieJuridiqueUniteLegale` en entier alors que c'est un
**code** à quatre chiffres. Il est reformaté sur 4 positions à l'ingestion et
stocké en `TEXT` : un code à zéro initial resterait autrement amputé, et deux
codes distincts se confondraient. À l'usage : comparer avec des chaînes
(`categorie_juridique = '1000'`), jamais avec des nombres, et ne jamais
recalculer un préfixe par arithmétique — `substr()` sur le texte.

Même prudence pour `activite_principale` (code NAF, `'84.11Z'` — le point fait
partie du code) et pour `tranche_effectifs`, qui est le **code** de tranche
INSEE et non un effectif : `'02'` ne vaut pas 2 salariés, et l'ordre
alphabétique de ces codes n'est pas l'ordre des tailles.

### 5. Les booléens valent 1, 0 ou NULL — et NULL n'est pas 0

`economie_sociale_solidaire` et `societe_mission` traduisent un champ amont à
trois états (`'O'`, `'N'`, vide) en **1 / 0 / NULL**. NULL dit « non
renseigné par l'INSEE », pas « non ». Compter les entreprises de l'ESS avec
`WHERE economie_sociale_solidaire = 1` est correct ; en déduire que tout le
reste n'en est pas ne l'est pas — il faut opposer `= 1` à `= 0` et publier à
part le volume des NULL. La même règle vaut pour `annee_effectifs`,
`categorie_entreprise` et `date_creation`, tous facultatifs à la source.

`etat_administratif` porte `'A'` (active) ou `'C'` (cessée) : une unité cessée
reste dans la table si la base la cite, et c'est voulu — un marché notifié à
une entreprise aujourd'hui radiée est un fait, pas une erreur.

## La table `decp_qualite_montants` (S1) — ce qu'il faut savoir avant de s'en servir

### 1. Une ligne, et c'est structurel

`CHECK (id = 1)` : la table ne peut en contenir qu'une. Ce n'est pas une série,
c'est une **fiche d'auto-critique du total affiché** sur `/marches`. Elle
répond à une seule question — que vaut le chiffre que le lecteur voit ? — en
décomposant ce total en parts dont chacune a une cause identifiée. Elle se
lit donc toujours en entier, jamais colonne par colonne.

### 2. Son périmètre est celui de `decp_repartition`, pas celui de la carte

Même fenêtre de 12 mois et même vue `recents` que `decp_repartition` : au
21/08/2026, `nb_marches` valait 297 323, exactement la somme de
`decp_repartition.nb_marches` pour chacune de ses deux dimensions, et pour un
`montant_total` identique au centime. C'est le contrôle croisé à faire quand
un doute survient.

`decp_agg_departement`, lui, ne couvre **que** les acheteurs à département
connu : à la même date il totalisait 295 457 marchés pour 268,6 Md€, contre
297 323 et 270,6 Md€ ici. `SUM(decp_agg_departement.nb_marches_ecretes)`
valait 399 quand `nb_ecretes` valait 401 — deux marchés écrêtés dont
l'acheteur n'a pas de département. Les deux compteurs portent des noms
voisins et ne comptent pas la même chose ; les additionner ou les substituer
l'un à l'autre est l'erreur type.

### 3. `montant_ecretes` n'est pas ce que valent les marchés écrêtés

C'est leur contribution **après** écrêtage, donc exactement
`nb_ecretes × plafond` : au 21/08/2026, 401 × 100 M€ = 40,1 Md€, vérifiable à
l'euro près. La grandeur retranchée par l'écrêtage ne se lit nulle part
directement ; elle se déduit de `montant_brut − montant_total`. À la même
date, `montant_brut` (468,7 Md€) valait **1,73 fois** `montant_total`
(270,6 Md€) : l'écrêtage n'est pas un détail de présentation, il retire la
majorité du volume brut, et c'est précisément ce que cette table sert à
avouer.

Cette disproportion est le fait saillant : 0,135 % des marchés portaient
14,82 % du total affiché. Un plafond fixe de 100 M€ appliqué à une poignée de
lignes gouverne donc une part à deux chiffres du chiffre publié.

### 4. `montant_hors_suspects` est une BORNE BASSE, jamais un total « propre »

Le drapeau `montant_suspect` combine la classification de la source et le
dépassement du plafond ; il n'a **pas** été audité ligne à ligne. Un marché
marqué suspect peut être parfaitement exact — les maximums d'accords-cadres
d'énergie le sont. `montant_hors_suspects` (189,7 Md€ au 21/08/2026, soit
70,09 % du total) dit donc « au moins cela », jamais « seulement cela », et ne
doit jamais être présenté comme le vrai montant de la commande publique.

`montant_total` se décompose exactement en `montant_suspects +
montant_hors_suspects` : au 21/08/2026 l'écart mesuré était de 1,8 millième
d'euro, résidu d'arithmétique flottante sur des REAL, sans signification.
Ne pas le prendre pour une fuite de lignes.

### 5. `nb_sans_montant` compte des marchés, pas des zéros

297 marchés au 21/08/2026 avaient un `montant_retenu` NULL. Ils sont comptés
dans `nb_marches` et exclus de toutes les sommes — aucune donnée n'est
inventée. Conséquence : `montant_total / nb_marches` n'est pas un montant
moyen par marché, puisque le dénominateur inclut des lignes que le numérateur
ignore. Le diviseur honnête est `nb_marches − nb_sans_montant`.

### 6. Toutes ces valeurs dérivent, sauf le plafond

`plafond` est une constante du pipeline (`PLAFOND_ECRETAGE_EUR`, 100 000 000 €)
et ne bouge qu'avec le code. Les dix autres colonnes sont recalculées à chaque
ingestion sur une fenêtre glissante de 12 mois : les citer sans date n'a pas
de sens. La latence légale de publication des DECP allant jusqu'à deux mois,
le bord récent de cette fenêtre est de plus structurellement incomplet.

## Les tables `hatvp_decl_*` (S15) — ce qu'il faut savoir avant de s'en servir

### 1. Quatre tables, un seul grain d'entrée : la déclaration

`hatvp_decl_interets` porte la déclaration (1 ligne = 1 DI ou DIA rattachée à
un élu), `hatvp_decl_rubriques` le couple déclaration × rubrique,
`hatvp_decl_lignes` l'intérêt déclaré, `hatvp_decl_montants` le montant annuel
et daté attaché à une ligne. La chaîne se remonte par `uuid` →
`declaration_uuid` → `id` → `ligne_id`, et elle est cohérente : au 21/08/2026,
`SUM(hatvp_decl_interets.nb_lignes)`, `SUM(hatvp_decl_rubriques.nb_lignes)` et
`COUNT(*) FROM hatvp_decl_lignes` valaient tous trois 27 711, sans un montant
orphelin ni un `elu_id` inconnu de `elus`. Les colonnes `nb_lignes` sont donc
des dénormalisations fiables, utilisables sans jointure.

À ne pas confondre avec `hatvp_declarations` (S14), qui dit qu'une déclaration
**existe** et à quelle date : ces quatre tables-ci disent ce qu'elle
**contient**, et sur un périmètre bien plus étroit.

### 2. Le périmètre est celui des fiches d'élus publiées, pas celui de la HATVP

Le rattachement est restreint aux élus qui ont une fiche sur le site
(députés, sénateurs, présidents de conseil départemental et régional) : au
21/08/2026, 2 261 déclarations pour **948 élus distincts**, quand
`hatvp_declarations` en recensait plus de douze mille. C'est une minimisation
délibérée au titre de l'article 5(1)(c) du RGPD, pas un défaut d'ingestion.
Un élu absent de `hatvp_decl_interets` n'a donc pas « rien déclaré » : dans la
quasi-totalité des cas, il n'a simplement pas de fiche. Rien dans ces tables
ne permet de conclure à l'absence de déclaration — seul `hatvp_declarations`
le permet.

### 3. Un élu porte plusieurs déclarations, et il faut choisir laquelle

2,4 déclarations par élu en moyenne au 21/08/2026, jusqu'à **9** pour un seul.
`modificative` valait 1 pour 1 060 d'entre elles, soit près de la moitié :
une déclaration modificative ne remplace pas la précédente dans ces tables,
elle s'y ajoute. Compter les intérêts d'un élu en sommant toutes ses lignes
revient donc à compter plusieurs fois le même intérêt redéclaré. Toute
restitution par personne doit trancher explicitement — dernière `date_depot`,
ou déclaration désignée — et le dire.

`type_declaration` ne vaut que `'DI'` ou `'DIA'` (287 et 1 974 au 21/08/2026) :
c'est une garantie structurelle du pipeline, qui refuse les types
patrimoniaux DSP/DSPM/DSPFM par deux barrières indépendantes, l'une sur le
type, l'autre sur le nom de balise.

### 4. `neant` distingue « rien à déclarer » de « pas de donnée » — et il faut s'en servir

C'est la raison d'être de `hatvp_decl_rubriques`. `neant = 1` est un **fait
déclaré par la personne**, affichable comme tel ; `neant = 0` est une rubrique
renseignée ; `NULL` serait une rubrique présente sans mention. Et une rubrique
**absente de la table** signifie que nous n'avons pas la donnée.

Au 21/08/2026 la grille était complète : 15 827 lignes, soit exactement
7 × 2 261, avec un minimum et un maximum de 7 rubriques par déclaration et
**aucune** valeur NULL — les sept rubriques (`mandat_electif`, `dirigeant`,
`participation_financiere`, `activite_5ans`, `consultant`, `benevole`,
`observation`, dans cet ordre de `rubrique_ordre`) sont présentes pour chaque
déclaration. 8 562 rubriques portaient `neant = 1`, 7 265 `neant = 0`. Le code
de restitution ne doit pas pour autant présumer cette complétude : elle est
constatée, pas garantie par une contrainte.

Un garde-fou tient, un autre non : aucune rubrique n'avait `neant = 1` avec
`nb_lignes > 0` (la cohérence forte est vérifiée), mais **11** avaient
`neant = 0` avec `nb_lignes = 0` — rubrique déclarée renseignée dont aucune
ligne n'a survécu au nettoyage du marqueur de caviardage. Afficher « 0 »
sans plus pour ces onze-là dirait « rien à déclarer », ce qui est faux.

### 5. Aucune colonne numérique de montant, et c'est voulu

`hatvp_decl_montants.montant` est du `TEXT` verbatim. C'est une contrainte
éditoriale inscrite dans le schéma : un total, un classement ou une moyenne
bâtis sur ces libellés sont structurellement impossibles, donc jamais commis
par inadvertance.

Le piège est ailleurs, et il est massif : au 21/08/2026, **60 952** des
94 487 montants — 64,5 % — valaient le **zéro littéral** `'0'`. Seules 8 845
des 22 564 lignes portant au moins un montant en portaient un autre que zéro.
Une restitution qui affiche « 94 487 montants déclarés » ou qui trace une
courbe sans écarter ces zéros donne une image fausse. `montant = '0'` est une
déclaration de rémunération nulle, pas une rémunération inconnue.

Le commentaire porté par le DDL annonce une « espace fine insécable native » ;
la mesure dit autrement. Les seuls caractères non numériques observés au
21/08/2026 sont l'**espace ASCII ordinaire** `U+0020` (parfois doublée), le
trait d'union-moins et une virgule. Onze montants sont **négatifs**
(`'-13477'`, `'-9316'`…) et un porte une décimale à la virgule
(`'13633,8'`). Quiconque tenterait malgré tout une conversion numérique doit
donc traiter le signe, l'espace simple **et** double, et la virgule — et
n'obtiendrait de toute façon qu'un nombre que la source ne garantit pas.

`annee` est du `TEXT` mais valait partout quatre chiffres, de 2011 à 2026.
`brut_net` ne prend que `'Net'` (92 526) et `'Brut'` (1 961), sans NULL : les
deux ne sont pas comparables entre eux, et le rapport de 1 à 47 fait qu'un
agrégat qui les mélangerait serait dominé par le net sans le dire.

### 6. Le texte est brut de saisie, et les absences sont nombreuses

Aucune normalisation : « Education Nationale », « Education nationale » et
« ASSEMBLEE NATIONALE » cohabitent, les doublons de saisie sont fréquents.
Le marqueur `[Données non publiées]` est retiré systématiquement et un champ
qui n'en garde rien devient **NULL** — une absence, jamais une chaîne vide et
jamais un zéro. Au 21/08/2026, `description` était NULL sur 10 010 des 27 711
lignes, `libelle` sur 430.

Trois colonnes sont à trois états et leur NULL domine : `conservee` (NULL sur
17 121 lignes, `1` sur 8 120, `0` sur 2 470) et `activite_conseil` (NULL sur
24 540, `'Non'` sur 3 090, `'Oui'` sur 81). Traiter ces NULL comme des « non »
transformerait une absence de question en réponse négative. `date_debut` et
`date_fin` sont verbatim et non recomposées (`'01/2018'`, `'11/2019'`) : elles
ne se trient pas comme des dates.

Enfin la distribution des lignes est très inégale — au 21/08/2026,
`dirigeant` en portait 13 145 et `consultant` 239 — et celle des montants
plus encore, `dirigeant` en concentrant 57 270 sur 94 487. Une lecture
transversale par rubrique est trompeuse si elle ne le mentionne pas.

## Les tables `elections_participation_*` (S26) — ce qu'il faut savoir avant de s'en servir

### 1. `code_departement` est dérivé du code commune, et 6 codes ne joignent pas

La codification des départements **change selon le scrutin** dans la source :
la Guadeloupe est `ZA` jusqu'en 2024 et `971` en 2026, et onze territoires
sont dans ce cas. Le pipeline s'en affranchit en dérivant toujours le
département des deux ou trois premiers caractères de `code_commune`, stable
d'un scrutin à l'autre. Résultat vérifié au 21/08/2026 : les seuls codes non
numériques restants sont `2A` et `2B`, et aucun `Z*` ne subsiste.

Le piège s'est déplacé, il n'a pas disparu. Six codes de ces tables n'ont
**aucune correspondance** dans `ref_departements`, qui n'en compte que 101 :
`975` Saint-Pierre-et-Miquelon, `977` Saint-Barthélemy, `978` Saint-Martin,
`986` Wallis-et-Futuna, `987` Polynésie française, `988` Nouvelle-Calédonie.
Une jointure interne sur `ref_departements` perd donc 34 des 740 lignes — sans
erreur, sans avertissement — dont 463 336 inscrits pour la seule
présidentielle 2022 T1. Toute jointure sur ce référentiel doit être externe,
et l'écart affiché.

### 2. Aucun taux n'est stocké, et c'est délibéré

Les tables ne portent que des effectifs : `inscrits`, `votants`, `blancs`,
`nuls`, `exprimes`. Les ratios se calculent à l'affichage, pour qu'une donnée
absente reste absente — un taux stocké se lirait comme un zéro. Attention au
dénominateur : le taux de participation se calcule sur `inscrits`, mais les
parts de blancs et de nuls se calculent sur `votants`, dont `exprimes` est le
complément. `votants = blancs + nuls + exprimes` est vrai partout, aux deux
grains, sans une exception au 21/08/2026.

### 3. La somme des départements n'est pas le résultat national

`ZZ` — les Français établis hors de France, rangés par le parquet amont sous
210 à 213 « communes » consulaires (`docs/ELECTIONS.md`) — est exclu : ce
n'est pas un département, l'inclure dans une table départementale serait une
erreur de catégorie. Conséquence à dire au lecteur chaque fois que le total
est affiché : la somme des départements **exclut** ces électeurs et diffère
donc du taux publié par le ministère. Mesuré au 21/08/2026 sur ces tables, la
présidentielle 2022 T1 ressort à **74,86 %** de participation, là où le
ministère publie 73,69 % (chiffre amont relevé dans `docs/ELECTIONS.md`, non
recalculable depuis la base) — l'écart, ce sont ces électeurs-là.

### 4. Le grain communal est un échantillon choisi, jamais la France entière

`elections_participation_ville` est restreinte aux communes que le site
connaît déjà — `ref_villes` ∪ `collectivites_communes_top200`, 234 au
21/08/2026. Elle en contenait 233 distinctes : Uvea (98613) est absente de
**tous** les scrutins, Wallis-et-Futuna n'ayant pas de communes et le
ministère publiant sous une entité unique. Ces 233 communes ne forment ni un
échantillon représentatif ni un classement : agréger cette table pour en
tirer un chiffre « national », ou même départemental, est un contresens —
`elections_participation_departement` est là pour ça.

Le nombre de communes varie fortement d'un scrutin à l'autre : 233 aux
présidentielle, législatives T1 et européennes, 231 aux municipales 2026 T1,
mais 205 aux législatives 2024 T2 et 156 aux municipales 2026 T2. Ces écarts
sont des faits électoraux — pas de second tour là où le premier a suffi — et
non des trous de données. Comparer deux scrutins sans réaligner le périmètre
de communes produit un écart entièrement artificiel. Même prudence au grain
départemental, où le nombre de lignes va de 102 à 107 selon le scrutin.

### 5. Ce qui n'est pas dans ces tables

Ni nuance politique, ni nom de candidat, ni bureau de vote — aucune de ces
données n'est ingérée, et la ressource nominative amont n'est ni téléchargée
ni lue. Ces tables ne répondent qu'à une question, la participation ; toute
lecture partisane des chiffres qu'elles portent est hors de leur portée.

Les deux anomalies arithmétiques publiées par le ministère aux municipales
2026 T1 et relevées au grain du bureau de vote par `docs/ELECTIONS.md` — un
`nuls` négatif à Saint-Cyr-du-Gault (41205), 212 votants pour 209 inscrits au
Mesnil-sur-Bulles (60400) — sont des données réelles, ni corrigées ni
supprimées en amont. Elles n'apparaissent pas ici, ce qui se vérifie sur la
base : au 21/08/2026, aucune ligne des deux tables ne violait
`inscrits >= votants`.
Ces communes sont hors du périmètre communal du site, et l'agrégation
départementale absorbe l'écart. Le contrôle reste à refaire après tout
élargissement du périmètre : rien dans le schéma ne l'interdit.
